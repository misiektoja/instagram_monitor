"""Configuration and notification boundary regressions."""

import argparse
import json

import pytest
import requests
from requests.adapters import HTTPAdapter

import instagram_monitor as monitor


@pytest.mark.parametrize("template", [
    {"content": "{title}: {descripton}"},
    '{"content": "{title}: {descripton}"}',
    '{{"content": "{title}: {descripton}"}}',
])
# Rejects an unknown field before a real webhook request can be sent
def test_unknown_webhook_field_stops_delivery(monkeypatch, template, capsys):
    requests_seen = []

    # Records any attempted delivery at the HTTP transport boundary
    def respond(adapter, request, **kwargs):
        requests_seen.append(request)
        response = requests.Response()
        response.status_code = 204
        response.request = request
        return response

    monkeypatch.setattr(HTTPAdapter, "send", respond)
    monkeypatch.setattr(monitor, "WEBHOOK_ENABLED", True)
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/test-boundary-token")
    monkeypatch.setattr(monitor, "WEBHOOK_TEMPLATE", template)
    error = monitor.validate_webhook_customization("discord")
    assert error and "descripton" in error
    assert monitor.send_webhook("Title", "Description", force=True) == 1
    assert requests_seen == []
    assert "descripton" in capsys.readouterr().out


@pytest.mark.parametrize("legacy", [False, True])
# Expands each field once while preserving JSON quotes and literal braces in supplied values
def test_json_webhook_templates_preserve_supplied_text(legacy):
    template = '{"content": "{title}: {description}", "embeds": [{"footer": {"text": "{{literal}}"}}]}'
    if legacy:
        template = '{{"content": "{title}: {description}", "embeds": [{{"footer": {{"text": "{{literal}}"}}}}]}}'
    values = {"title": 'A "quoted" {artist}', "description": 'Line one\nLine two \\ end'}
    rendered = monitor.render_discord_template(template, values)
    assert isinstance(rendered, dict)
    assert rendered == {"content": values["title"] + ": " + values["description"], "embeds": [{"footer": {"text": "{literal}"}}]}
    assert json.loads(json.dumps(rendered)) == rendered


@pytest.mark.parametrize("width", ["80", None, True, -1, 1.5, {}, []])
# Names unusable terminal widths before a logger or startup summary consumes them
def test_invalid_truncation_is_a_configuration_error(width):
    assert any("TRUNCATE_CHARS" in error for error in monitor.configuration_shape_errors({"TRUNCATE_CHARS": width}))


@pytest.mark.parametrize("width", [0, 1, 80, 999])
# Keeps documented fixed and automatic terminal widths valid
def test_valid_truncation_widths(width):
    assert monitor.configuration_shape_errors({"TRUNCATE_CHARS": width}) == []


@pytest.mark.parametrize("width", [0, 80])
# Applies the command-line width before deciding whether the configured value is usable
def test_cli_truncation_overrides_invalid_config(monkeypatch, width):
    monkeypatch.setattr(monitor, "TRUNCATE_CHARS", "broken")
    monkeypatch.setattr(monitor, "DISCARDED_SETTING_ERRORS", [])
    monitor.prepare_configured_paths(argparse.Namespace(truncate=width))
    assert monitor.DISCARDED_SETTING_ERRORS == []
    assert monitor.TRUNCATE_CHARS == width
    assert not any("TRUNCATE_CHARS" in error for error in monitor.configuration_shape_errors())


# Keeps Doctor usable while retaining the original malformed setting in its report
def test_doctor_discards_invalid_truncation(monkeypatch):
    monkeypatch.setattr(monitor, "TRUNCATE_CHARS", "broken")
    monkeypatch.setattr(monitor, "DISCARDED_SETTING_ERRORS", [])
    monitor.prepare_configured_paths(argparse.Namespace(doctor=True, truncate=None))
    assert monitor.TRUNCATE_CHARS == monitor.BUILT_IN_SHAPE_SETTINGS["TRUNCATE_CHARS"]
    assert any("TRUNCATE_CHARS" in error for error in monitor.configuration_shape_errors())


@pytest.mark.parametrize("name", [name for name in monitor.BUILT_IN_SHAPE_SETTINGS if name not in ("COLOR_THEME", "TRUNCATE_CHARS")])
@pytest.mark.parametrize("value", [17, None, False, []])
# Keeps Doctor available for every malformed output and authentication path
def test_doctor_discards_invalid_paths(monkeypatch, name, value):
    monkeypatch.setattr(monitor, name, value)
    monkeypatch.setattr(monitor, "DISCARDED_SETTING_ERRORS", [])
    monitor.prepare_configured_paths(argparse.Namespace(doctor=True))
    assert getattr(monitor, name) == monitor.BUILT_IN_SHAPE_SETTINGS[name]
    assert any(name in error for error in monitor.configuration_shape_errors())
