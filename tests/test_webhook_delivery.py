"""Offline workflow tests for send_webhook delivery formatting."""

from pathlib import Path
import tempfile
from unittest.mock import Mock

import pytest
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts"


# Creates a disposable test directory under the project local directory
def make_test_directory():
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT)


class _FakeResponse:
    # Stores the HTTP status and text returned by a fake webhook call
    def __init__(self, status_code=204, text=""):
        self.status_code = status_code
        self.text = text


class TestSendWebhook:
    # A successful JSON webhook call formats payload, headers, fields and privacy substitutions
    def test_json_payload_is_sanitized_and_posted(self, im_module, monkeypatch):
        calls = []
        long_value = "x" * (im_module.WEBHOOK_FIELD_VALUE_LIMIT + 10)

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"X-Title": "{title}"})
        monkeypatch.setattr(im_module, "WEBHOOK_TRANSFORMS", [("title", "replace", "secret", "masked")])
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("realuser", "User1")])
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        rc = im_module.send_webhook("realuser secret", "desc realuser", fields=[{"name": "realuser field", "value": long_value, "inline": True}], image_url="https://example.com/image.jpg")

        assert rc == 0
        assert len(calls) == 1
        args, kwargs = calls[0]
        payload = kwargs["json"]
        assert args == ("https://example.com/hook",)
        assert kwargs["headers"]["X-Title"] == "User1 masked"
        assert kwargs["headers"]["User-Agent"] == f"InstagramMonitor/{im_module.VERSION}"
        assert payload["embeds"][0]["title"] == "User1 masked"
        assert payload["embeds"][0]["description"] == "desc User1"
        assert payload["embeds"][0]["image"]["url"] == "https://example.com/image.jpg"
        assert payload["embeds"][0]["fields"][0]["name"] == "User1 field"
        assert payload["embeds"][0]["fields"][0]["value"] == "x" * im_module.WEBHOOK_FIELD_VALUE_LIMIT
        assert payload["embeds"][0]["fields"][0]["inline"] is True

    # A string webhook template is sent as raw data instead of JSON
    def test_string_template_uses_data_post(self, im_module, monkeypatch):
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_TEMPLATE", "{title}:{fields_str}")
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        rc = im_module.send_webhook("Title", "desc", fields=[{"name": "Name", "value": "Value"}])

        assert rc == 0
        assert len(calls) == 1
        _, kwargs = calls[0]
        assert kwargs["data"] == "Title:Name: Value"
        assert "json" not in kwargs

    # Disabled notification types return without posting to the webhook URL
    def test_notification_type_gate_blocks_post(self, im_module, monkeypatch):
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", False)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "desc", notification_type="status") == 1
        assert calls == []

    # HTTP 429 responses are retried and a later success is reported as delivered
    def test_rate_limit_response_retries(self, im_module, monkeypatch):
        responses = [_FakeResponse(429, "slow down"), _FakeResponse(204, "")]
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or responses.pop(0))

        assert im_module.send_webhook("Title", "desc") == 0
        assert len(calls) == 2

    # A native ntfy call sends UTF-8 text, field details and the title query parameter
    def test_ntfy_payload_uses_native_topic_api(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic?auth=private-value")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

        rc = im_module.send_webhook("Instagram title za\u017c\u00f3\u0142\u0107", "Body: Bj\u00f6rk", fields=[{"name": "Count", "value": "3"}], image_url="https://example.com/image.jpg")

        assert rc == 0
        args, kwargs = calls[0]
        assert args == ("https://ntfy.sh/private-topic?auth=private-value",)
        assert kwargs["data"] == "Body: Bj\u00f6rk\n\nCount: 3\n\nImage: https://example.com/image.jpg".encode("utf-8")
        assert kwargs["params"] == {"title": "Instagram title za\u017c\u00f3\u0142\u0107"}
        assert kwargs["headers"]["Content-Type"] == "text/plain; charset=utf-8"
        assert "json" not in kwargs

    # Static custom headers are copied to native ntfy requests
    def test_ntfy_custom_headers_are_preserved(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.example.test/private-topic")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"Authorization": "Basic shared-private-value", "X-Monitor": "instagram"})
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

        assert im_module.send_webhook("Title", "Body") == 0
        headers = calls[0][1]["headers"]
        assert headers["Authorization"] == "Basic shared-private-value"
        assert headers["X-Monitor"] == "instagram"
        assert headers["User-Agent"] == f"InstagramMonitor/{im_module.VERSION}"
        assert headers["Content-Type"] == "text/plain; charset=utf-8"

    # The private ntfy token overrides custom authorization while retaining other headers
    def test_ntfy_access_token_takes_precedence(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.example.test/private-topic")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"authorization": "Basic older-value", "Content-Type": "application/json", "X-Priority": "high"})
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", "tk_private_access_token")
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

        assert im_module.send_webhook("Title", "Body") == 0
        headers = calls[0][1]["headers"]
        assert headers["Authorization"] == "Bearer tk_private_access_token"
        assert "authorization" not in headers
        assert headers["Content-Type"] == "text/plain; charset=utf-8"
        assert headers["X-Priority"] == "high"

    # Malformed ntfy access tokens fail before a webhook request is attempted
    @pytest.mark.parametrize("token", ["Bearer tk_private_access_token", "Basic private-value", "first\nsecond", 3])
    def test_invalid_ntfy_access_tokens_are_rejected(self, im_module, monkeypatch, token):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.example.test/private-topic")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", token)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

        assert im_module.send_webhook("Title", "Body") == 1
        assert calls == []

    # Malformed custom headers fail before a webhook request is attempted
    @pytest.mark.parametrize("headers", [[("Authorization", "Bearer value")], {"Bad Header": "value"}, {"X-Test": 3}, {"X-Test": "first\nsecond"}, {"Authorization": "Bearer first", "authorization": "Bearer second"}])
    def test_invalid_webhook_headers_are_rejected(self, im_module, monkeypatch, headers):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", headers)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "Body") == 1
        assert calls == []

    # Header placeholders cannot inject line breaks after payload formatting
    def test_formatted_webhook_headers_reject_line_break_injection(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"X-Title": "{title}"})
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("first\nsecond", "Body") == 1
        assert calls == []

    # Ntfy message truncation respects its UTF-8 byte limit without splitting a character
    def test_ntfy_message_is_bounded_by_utf8_bytes(self, im_module):
        title, message = im_module.build_ntfy_webhook_message("Title", ("a" * (im_module.NTFY_MESSAGE_LIMIT_BYTES - 1)) + "\U0001f3a5")
        assert title == "Title"
        assert len(message.encode("utf-8")) == im_module.NTFY_MESSAGE_LIMIT_BYTES - 1
        assert not message.endswith("\U0001f3a5")

    # An unsupported provider fails before any webhook request is attempted
    def test_invalid_webhook_provider_is_rejected(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "unsupported")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.req, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "Body") == 1
        assert calls == []


# Full setup expands a bare ntfy topic and persists both ntfy secrets only in the dotenv file
def test_setup_wizard_persists_ntfy_secrets_privately(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        directory = Path(directory_name)
        config_path = directory / "instagram_monitor.conf"
        env_path = directory / ".env"
        topic_name = "private-topic"
        topic_url = f"https://ntfy.sh/{topic_name}"
        token = "tk_private_access_token"
        answers = iter([True, False, True, True, False, False])
        choices = iter([0, 2, 1, 0])
        secrets = iter([topic_name, token])
        monkeypatch.delenv("WEBHOOK_URL", raising=False)
        monkeypatch.delenv("NTFY_ACCESS_TOKEN", raising=False)
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
        monkeypatch.setattr(im_module, "_wizard_ask_secret", lambda *args, **kwargs: next(secrets))
        monkeypatch.setattr(im_module, "run_doctor", Mock(side_effect=AssertionError("doctor called")))
        for name in ("CLI_CONFIG_PATH", "DOTENV_FILE", "SESSION_USERNAME", "SKIP_SESSION", "TARGET_USERNAMES", "WEB_DASHBOARD_ENABLED", "DASHBOARD_ENABLED", "STATUS_NOTIFICATION", "WEBHOOK_ENABLED", "WEBHOOK_PROVIDER", "WEBHOOK_STATUS_NOTIFICATION", "NTFY_ACCESS_TOKEN"):
            monkeypatch.setattr(im_module, name, getattr(im_module, name), raising=False)

        with pytest.raises(SystemExit) as error:
            im_module.run_setup_wizard(config_file=config_path, env_file=env_path)

        assert error.value.code == 0
        config = config_path.read_text(encoding="utf-8")
        dotenv = dotenv_values(env_path, interpolate=False)
        assert 'WEBHOOK_PROVIDER = "ntfy"' in config
        assert topic_url not in config
        assert token not in config
        assert dotenv["WEBHOOK_URL"] == topic_url
        assert dotenv["NTFY_ACCESS_TOKEN"] == token
        output = capsys.readouterr().out
        assert topic_name not in output
        assert topic_url not in output
        assert token not in output
