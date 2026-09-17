"""Exercise delivery and output boundaries with real HTTP clients and log streams."""

import contextlib
import io
import json

from smtplib import SMTP as RealSMTP

import pytest
import requests
from requests.adapters import HTTPAdapter

import instagram_monitor as monitor


# Supplies realistic responses at the HTTP transport boundary and records prepared requests
@pytest.fixture
def delivery(monkeypatch):
    seen = []
    old_url = "https://ntfy.sh/initial-private-topic"
    new_url = "https://discord.com/api/webhooks/123456789012345678/replacement"
    for key, value in {"WEBHOOK_ENABLED": True, "WEBHOOK_PROVIDER": "ntfy", "WEBHOOK_URL": old_url, "NTFY_ACCESS_TOKEN": "initial-private-access-token", "WEBHOOK_HEADERS": {}, "DEBUG_MODE": False, "PROXY_ENABLED": False, "WEBHOOK_MAX_ATTEMPTS": 2}.items():
        monkeypatch.setattr(monitor, key, value, raising=False)
    if hasattr(monitor, "WEBHOOK_SESSION"):
        monkeypatch.setattr(monitor, "WEBHOOK_SESSION", requests.Session())
    state = {"rotate": False, "reject": False}

    # Records transport inputs before applying a settings reload between attempts
    def record(url, headers, body):
        seen.append({"url": str(url), "headers": dict(headers), "body": body})
        if state["rotate"] and len(seen) == 1:
            monkeypatch.setattr(monitor, "WEBHOOK_URL", new_url)
            monkeypatch.setattr(monitor, "NTFY_ACCESS_TOKEN", "replacement-access-token")
            monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
            return 429
        return 400 if state["reject"] else 204

    # Returns a response through requests after its real request preparation
    def respond(adapter, request, **kwargs):
        status = record(request.url, request.headers, request.body)
        response = requests.Response()
        response.status_code = status
        response._content = b'{"error": "initial-private-access-token was rejected", "retry_after": 0}'
        response.headers["Retry-After"] = "0"
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr(HTTPAdapter, "send", respond)
    if monitor.__name__ == "xbox_monitor":
        import httpx

        # Returns a response through the real HTTPX client and transport
        def httpx_respond(transport, request):
            status = record(request.url, request.headers, request.read())
            return httpx.Response(status, request=request, json={"error": "initial-private-access-token was rejected", "retry_after": 0}, headers={"Retry-After": "0"})

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", httpx_respond)
    return seen, state, old_url


# Keeps the destination and authorization paired when settings change during delivery
def test_retry_keeps_credentials_at_the_original_destination(delivery):
    seen, state, old_url = delivery
    state["rotate"] = True
    assert monitor.send_webhook("Activity", "A game started", force=True) == 0
    assert len(seen) == 2
    assert all(item["url"].split("?")[0] == old_url for item in seen)
    assert all(next(value for name, value in item["headers"].items() if name.lower() == "authorization") == "Bearer initial-private-access-token" for item in seen)


# Applies the no-mentions guarantee to JSON string templates before sending
def test_json_string_template_cannot_enable_discord_mentions(delivery, monkeypatch):
    seen, _, _ = delivery
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/private")
    monkeypatch.setattr(monitor, "WEBHOOK_TEMPLATE", json.dumps({"content": "{description}", "allowed_mentions": {"parse": ["everyone"]}}))
    assert monitor.send_webhook("Activity", "@everyone", force=True) == 0
    payload = json.loads(seen[0]["body"])
    assert payload["content"] == "@everyone"
    assert payload["allowed_mentions"] == {"parse": []}


# Preserves complete log records while bounding lines assembled by separate writes
def test_split_writes_obey_terminal_width_and_preserve_the_log(tmp_path, monkeypatch):
    terminal = io.StringIO()
    monkeypatch.setattr(monitor, "TRUNCATE_CHARS", 10)
    monkeypatch.setattr(monitor, "COLOR_ENABLED", False, raising=False)
    monkeypatch.setattr(monitor, "DASHBOARD_ENABLED", False)
    monkeypatch.setattr(monitor, "pbar", None)
    monkeypatch.setattr(monitor._thread_local, "pbar", None, raising=False)
    path = tmp_path / "activity.log"
    with contextlib.redirect_stdout(terminal):
        logger = monitor.Logger(str(path))
        logger.write("abcdefghij")
        logger.write("KLM\n")
        logger.terminal_only("12345")
        logger.terminal_only("67890extra\n")
        logger.flush()
    assert terminal.getvalue() == "abcdefghij\n1234567890\n"
    assert path.read_text() == "abcdefghijKLM\n"


# Validates and reloads the exact password through a real SMTP AUTH exchange
def test_private_smtp_entry_preserves_significant_spaces(tmp_path, monkeypatch):
    import base64
    import socketserver
    import threading
    from dotenv import dotenv_values

    password = " synthetic-password-with-spaces "
    attempts = []

    # Serves only the ESMTP commands needed by the real smtplib client
    class Peer(socketserver.StreamRequestHandler):
        # Checks the decoded AUTH password without accepting a message
        def handle(self):
            self.wfile.write(b"220 fixture.local ESMTP\r\n")
            while True:
                line = self.rfile.readline()
                if not line:
                    return
                command = line.decode().rstrip("\r\n")
                if command.upper().startswith(("EHLO", "HELO")):
                    self.wfile.write(b"250-fixture.local\r\n250 AUTH PLAIN\r\n")
                elif command.upper().startswith("AUTH PLAIN "):
                    supplied = base64.b64decode(command.split(" ", 2)[2]).split(b"\0")[-1].decode()
                    attempts.append(supplied)
                    self.wfile.write(b"235 2.7.0 Accepted\r\n" if supplied == password else b"535 5.7.8 Rejected\r\n")
                elif command.upper() == "QUIT":
                    self.wfile.write(b"221 Bye\r\n")
                    return
                else:
                    self.wfile.write(b"500 Unsupported command\r\n")

    monkeypatch.setattr(monitor.smtplib, "SMTP", RealSMTP)
    with socketserver.TCPServer(("127.0.0.1", 0), Peer) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        for key, value in {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": server.server_address[1], "SMTP_USER": "fixture-user", "SMTP_SSL": False, "SENDER_EMAIL": "from@example.test", "RECEIVER_EMAIL": "to@example.test"}.items():
            monkeypatch.setattr(monitor, key, value)
        destination = tmp_path / ".env"
        try:
            monitor.run_set_smtp_password(env_file=str(destination), interactive=True, getpass_func=lambda _: password)
            saved = dotenv_values(destination)["SMTP_PASSWORD"]
            assert saved == password
            monitor.smtp_sign_in(saved)
        finally:
            server.shutdown()
            worker.join()
    assert attempts == [password, password]


# Diagnoses malformed paths and color entries before formatting configuration output
def test_doctor_names_invalid_path_and_color_values(monkeypatch):
    path_setting = next(name for name in ("PSN_LOGFILE", "GITHUB_LOGFILE", "INSTA_LOGFILE", "LF_LOGFILE", "LOL_LOGFILE", "SP_LOGFILE", "ST_LOGFILE", "XBOX_LOGFILE") if hasattr(monitor, name))
    monkeypatch.setattr(monitor, path_setting, [])
    monkeypatch.setattr(monitor, "COLOR_THEME", {"game": 7}, raising=False)
    checks = monitor.doctor_check_configuration([])
    failures = [check for check in checks if check.status == "FAIL"]
    assert all(check.advice is not None for check in failures)
    assert any(path_setting in check.label for check in failures)
    assert any("COLOR_THEME['game']" in check.label for check in failures)
    # The rest of the section still reports, so one unusable value cannot hide the whole configuration
    assert any(check.status == "PASS" for check in checks)
    assert isinstance(getattr(monitor, path_setting), str)


# Redacts an old token even when the provider repeats it after a settings reload
def test_rotated_delivery_errors_keep_the_old_token_private(delivery, monkeypatch, capsys):
    seen, state, _ = delivery
    state.update(rotate=True, reject=True)
    monkeypatch.setattr(monitor, "DEBUG_MODE", True)
    assert monitor.send_webhook("Activity", "A game started", force=True) == 1
    assert len(seen) == 2
    assert "initial-private-access-token" not in capsys.readouterr().out


# Hidden dashboard log writes do not consume the width of later visible output
def test_suppressed_log_writes_leave_terminal_columns_unchanged(tmp_path, monkeypatch):
    terminal = io.StringIO()
    monkeypatch.setattr(monitor, "TRUNCATE_CHARS", 10)
    monkeypatch.setattr(monitor, "COLOR_ENABLED", False)
    monkeypatch.setattr(monitor, "DASHBOARD_ENABLED", True)
    monkeypatch.setattr(monitor, "RICH_AVAILABLE", True)
    with contextlib.redirect_stdout(terminal):
        logger = monitor.Logger(str(tmp_path / "activity.log"))
        logger.write("hidden status without a newline")
        logger.terminal_only("visible\n")
    assert terminal.getvalue() == "visible\n"


# Reports an unrenderable Discord template rather than raising out of validation and delivery
@pytest.mark.parametrize("template", ["{0}", "{}{}", "{title!z}", "plain body"])
def test_an_unrenderable_discord_template_is_reported_not_raised(delivery, monkeypatch, capsys, template):
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/private")
    monkeypatch.setattr(monitor, "WEBHOOK_TEMPLATE", template)
    error = monitor.validate_webhook_customization("discord")
    # The advice has to name the placeholder that failed, since a dictionary template is already a dictionary
    assert error is None or "WEBHOOK_TEMPLATE cannot render" in error or error == "WEBHOOK_TEMPLATE must be a dictionary or a JSON object string"
    assert monitor.send_webhook("Activity", "A post appeared", force=True) in (0, 1)
    assert "Traceback" not in capsys.readouterr().out


# Applies the same width rule with and without wcwidth, so a missing library never changes whether lines are cut
def test_screen_truncation_still_applies_without_wcwidth(monkeypatch):
    import builtins

    real_import = builtins.__import__

    # Hides only wcwidth, so the helper and the stateful terminal writer both take their fallback path
    def without_wcwidth(name, *arguments, **keywords):
        if name == "wcwidth":
            raise ImportError("wcwidth is not installed")
        return real_import(name, *arguments, **keywords)

    monkeypatch.setattr(builtins, "__import__", without_wcwidth)
    monkeypatch.setattr(monitor, "TRUNCATE_CHARS", 10)
    logger = monitor.Logger.__new__(monitor.Logger)
    line = "x" * 40 + "\n"
    assert monitor.truncate_string_per_line(line, 10) == "x" * 10 + "\n"
    assert logger._truncate_terminal(line) == "x" * 10 + "\n"


# Holds a retained delivery secret to the same minimum length as every other redaction path
def test_a_short_retained_secret_never_replaces_ordinary_words(monkeypatch):
    monkeypatch.setattr(monitor, "SESSION_PASSWORD", "cat", raising=False)
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/private")
    monkeypatch.setattr(monitor, "NTFY_ACCESS_TOKEN", "")
    monkeypatch.setattr(monitor, "WEBHOOK_HEADERS", {})
    text = "the category catalog was concatenated"

    @monitor._retain_webhook_secrets
    # Reads the redaction from inside the delivery scope the decorator opens
    def during_delivery():
        return monitor.sanitize_webhook_error_text(text)

    assert during_delivery() == text


# Verifies a provider the configuration file actually set is reported when the URL disagrees with it
def test_a_configured_provider_that_disagrees_is_reported(monkeypatch, capsys):
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://ntfy.sh/private-topic")
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "CONFIGURED_SETTING_NAMES", {"WEBHOOK_PROVIDER"})

    monitor.apply_webhook_provider_autodetection()

    assert monitor.WEBHOOK_PROVIDER == "ntfy"
    assert "did not match the URL" in capsys.readouterr().out


# Verifies the documented setup is silent, because the built-in default is not a provider anyone chose
def test_the_default_provider_follows_the_url_without_a_warning(monkeypatch, capsys):
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://ntfy.sh/private-topic")
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "CONFIGURED_SETTING_NAMES", set())
    monkeypatch.setattr(monitor, "VERBOSE_MODE", False)

    monitor.apply_webhook_provider_autodetection()

    assert monitor.WEBHOOK_PROVIDER == "ntfy"
    assert "did not match the URL" not in capsys.readouterr().out


# Verifies the same detection is still reported to anyone who asked for the operational detail
def test_verbose_mode_reports_the_detected_provider(monkeypatch, capsys):
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://ntfy.sh/private-topic")
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "CONFIGURED_SETTING_NAMES", set())
    monkeypatch.setattr(monitor, "VERBOSE_MODE", True)

    monitor.apply_webhook_provider_autodetection()

    assert "Webhook provider detected from the URL: ntfy" in capsys.readouterr().out


# Verifies a configuration read for the wizard or a report is not mistaken for the settings this run uses
def test_only_a_load_into_the_module_records_a_configured_setting(tmp_path, monkeypatch):
    path = tmp_path / "scoped.conf"
    path.write_text('WEBHOOK_PROVIDER = "ntfy"\n')
    monkeypatch.setattr(monitor, "CONFIGURED_SETTING_NAMES", set())

    monitor.load_config_file(str(path), namespace={}, report_errors=False)

    assert "WEBHOOK_PROVIDER" not in monitor.CONFIGURED_SETTING_NAMES
