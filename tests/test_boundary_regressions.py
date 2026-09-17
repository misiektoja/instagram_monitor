"""Exercise notification and configuration boundaries with real dependencies."""

import argparse
import copy
import errno
import os
import sys

import pytest
import requests
from requests.adapters import HTTPAdapter

import instagram_monitor as monitor


@pytest.fixture(autouse=True)
# Restores configuration and environment values changed by real startup calls
def restore_boundary_state(monkeypatch):
    for name, value in tuple(vars(monitor).items()):
        if name.isupper():
            monkeypatch.setattr(monitor, name, copy.deepcopy(value) if isinstance(value, (dict, list, set)) else value)
    for name in monitor.SECRET_KEYS:
        if name in os.environ:
            monkeypatch.setenv(name, os.environ[name])
        else:
            monkeypatch.setenv(name, "")
            monkeypatch.delenv(name)


# Returns real HTTP responses without contacting a notification provider
def reject_delivery(monkeypatch, token):
    seen = []

    # Captures a prepared requests request at the transport boundary
    def requests_reply(self, request, **kwargs):
        seen.append(request)
        monkeypatch.setattr(monitor, "WEBHOOK_HEADERS", {})
        response = requests.Response()
        response.status_code = 401
        response._content = ("Denied " + token).encode()
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr(HTTPAdapter, "send", requests_reply)
    return seen


@pytest.mark.parametrize("scheme", ["Bearer", "Basic"])
# Redacts both an outgoing Authorization header and the credential echoed without its scheme
def test_provider_cannot_echo_custom_authorization(monkeypatch, capsys, scheme):
    token = "synthetic-private-credential-value"
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://ntfy.example.test/topic")
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "ntfy")
    monkeypatch.setattr(monitor, "NTFY_ACCESS_TOKEN", "")
    monkeypatch.setattr(monitor, "DEBUG_MODE", True)
    monkeypatch.setattr(monitor, "WEBHOOK_HEADERS", {"Authorization": scheme + " " + token})
    seen = reject_delivery(monkeypatch, token)
    monkeypatch.setattr(monitor, "WEBHOOK_ENABLED", True)
    monitor.send_webhook("Boundary check", "Notification body", force=True)
    assert seen
    assert seen[-1].headers["Authorization"] == scheme + " " + token
    assert token not in capsys.readouterr().out


@pytest.mark.parametrize("url", ["https://ntfy.example.test:bad/topic", "https://ntfy.example.test:99999/topic"])
# Rejects invalid ports before notification transport is created
def test_invalid_webhook_ports_are_rejected(url):
    assert not monitor.validate_webhook_url(url)


# Keeps unsupported template lookups inside the delivery failure contract
def test_invalid_template_is_reported(monkeypatch, capsys):
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/synthetic")
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "WEBHOOK_TEMPLATE", {"content": "{title[999]}"})
    monkeypatch.setattr(monitor, "WEBHOOK_ENABLED", True)
    monitor.send_webhook("Boundary check", "Notification body", force=True)
    assert "template" in capsys.readouterr().out.casefold()


# Keeps privately entered values literal when startup or a reload reads the saved file
def test_private_password_survives_resolution(tmp_path, monkeypatch):
    value = "before${BOUNDARY_PASSWORD_PART}after"
    path = tmp_path / ".env"
    monkeypatch.setenv("BOUNDARY_PASSWORD_PART", "CHANGED")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    if hasattr(monitor, "DOTENV_RELOAD_STATE"):
        monkeypatch.setattr(monitor, "DOTENV_RELOAD_STATE", {})
    monitor.update_dotenv_file(path, {"SMTP_PASSWORD": value})
    monitor.load_managed_dotenv(path, override=True, interpolate=False)
    actual = os.environ["SMTP_PASSWORD"]
    assert actual == value


# Runs main with a configuration file that sets one path setting to a value that is not a path
def run_with_invalid_path(tmp_path, monkeypatch, setting, command):
    config = tmp_path / "monitor.conf"
    config.write_text(setting + " = 17\n", encoding="utf-8")
    args = [monitor.__file__, command, "--config-file", str(config)]
    if setting != "DOTENV_FILE":
        args.extend(["--env-file", "none"])
    monkeypatch.setattr(sys, "argv", args)

    # Fails unexpected connectivity checks at the requests transport boundary
    def offline_requests(self, request, **kwargs):
        raise requests.ConnectionError("Offline boundary check")

    monkeypatch.setattr(HTTPAdapter, "send", offline_requests)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    try:
        monitor.main()
    except SystemExit as stopped:
        return stopped.code
    return 0


@pytest.mark.parametrize("setting", ["CSV_FILE", "DOTENV_FILE"])
# Names a malformed path as a doctor row and still reports the rest of the configuration
def test_doctor_reports_invalid_path_types(tmp_path, monkeypatch, capsys, setting):
    run_with_invalid_path(tmp_path, monkeypatch, setting, "--doctor")
    output = capsys.readouterr().out
    assert f"{setting} must be a path string" in output
    # The report keeps going, so one unusable value cannot hide the checks the user came for
    assert output.count("[PASS]") > 1


# Keeps the commands that correct a malformed path usable, since stopping there leaves no way to fix it
def test_recovery_commands_run_with_an_invalid_path(tmp_path, monkeypatch, capsys):
    run_with_invalid_path(tmp_path, monkeypatch, "DOTENV_FILE", "--setup")
    output = capsys.readouterr().out
    # Not fatal, and the wizard reached its own stop instead of the gate that would have blocked the repair
    assert "Error: Invalid settings" not in output
    assert "--generate-config" in output


# Keeps a run that is not one of those commands stopping on a path it cannot use
def test_a_normal_run_still_stops_on_an_invalid_path(monkeypatch, capsys):
    monkeypatch.setattr(monitor, "DOTENV_FILE", 17)
    monkeypatch.setattr(sys, "argv", [monitor.__file__])
    with pytest.raises(SystemExit) as stopped:
        monitor.prepare_configured_paths(argparse.Namespace())
    assert stopped.value.code == 1
    assert "Error: Invalid settings: DOTENV_FILE must be a path string" in capsys.readouterr().out


# Treats a provider that repeats the words of the local limit as the remote failure it is
def test_a_server_reply_cannot_claim_local_resource_exhaustion():
    response = requests.Response()
    response.status_code = 503
    response.reason = "too many open files"
    rejected = requests.HTTPError("503 Server Error: too many open files for url: https://example.test", response=response)
    assert not monitor.is_too_many_open_files(rejected)
    exhausted = requests.ConnectionError("Could not open socket")
    exhausted.__cause__ = OSError(errno.EMFILE, "Too many open files")
    assert monitor.is_too_many_open_files(exhausted)


# Names the placeholder a dictionary template cannot fill instead of asking for a dictionary
def test_an_unfillable_placeholder_is_named(monkeypatch):
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "WEBHOOK_TEMPLATE", {"content": "{title[9]}"})
    monkeypatch.setattr(monitor, "WEBHOOK_AVATAR_URL", "")
    error = monitor.validate_webhook_customization("discord")
    assert error is not None
    assert "{title[9]}" in error
    assert "must be a dictionary" not in error
    monkeypatch.setattr(monitor, "WEBHOOK_TEMPLATE", "not a json object")
    assert monitor.validate_webhook_customization("discord") == "WEBHOOK_TEMPLATE must be a dictionary or a JSON object string"


# Doctor is also reachable by an argparse abbreviation, so the gate reads the parsed namespace rather than
# the words that were typed. Matching the literal flag sent an abbreviated run to the stop it exists to avoid
def test_an_abbreviated_doctor_flag_still_reports_an_invalid_path(tmp_path, monkeypatch, capsys):
    run_with_invalid_path(tmp_path, monkeypatch, "CSV_FILE", "--doct")
    output = capsys.readouterr().out
    assert "CSV_FILE must be a path string" in output
    assert "Error: Invalid settings" not in output
    assert output.count("[PASS]") > 1


# Pins the namespace contract the gate depends on, including a namespace carrying none of those flags
def test_configuration_commands_are_read_from_the_parsed_namespace():
    assert monitor.command_reports_configuration(argparse.Namespace(doctor=True))
    assert monitor.command_reports_configuration(argparse.Namespace(setup=True))
    assert not monitor.command_reports_configuration(argparse.Namespace(doctor=False, setup=False))
    assert not monitor.command_reports_configuration(argparse.Namespace())
