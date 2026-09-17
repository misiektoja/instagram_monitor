"""Exercise notification and configuration boundaries with real dependencies."""

import copy
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


@pytest.mark.parametrize("setting", ["CSV_FILE", "DOTENV_FILE"])
# Reports malformed paths before startup expands or opens them
def test_doctor_reports_invalid_path_types(tmp_path, monkeypatch, capsys, setting):
    config = tmp_path / "monitor.conf"
    config.write_text(setting + " = 17\n", encoding="utf-8")
    args = [monitor.__file__, "--doctor", "--config-file", str(config)]
    if setting != "DOTENV_FILE":
        args.extend(["--env-file", "none"])
    monkeypatch.setattr(sys, "argv", args)

    # Fails unexpected connectivity checks at the requests transport boundary
    def offline_requests(self, request, **kwargs):
        raise requests.ConnectionError("Offline boundary check")

    monkeypatch.setattr(HTTPAdapter, "send", offline_requests)
    with pytest.raises(SystemExit) as stopped:
        monitor.main()
    assert stopped.value.code == 1
    assert setting in capsys.readouterr().out
