"""Offline workflow tests for send_webhook delivery formatting."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
    def __init__(self, status_code=204, text="", headers=None, json_payload=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.json_payload = json_payload

    # Returns the configured JSON body or raises when none was supplied
    def json(self):
        if self.json_payload is None:
            raise ValueError("No JSON body")
        return self.json_payload


@pytest.mark.parametrize("url,expected", [("https://discord.com/api/webhooks/123/token", "discord"), ("https://canary.discord.com/api/v10/webhooks/123/token", "discord"), ("https://ntfy.sh/private-topic", "ntfy"), ("https://ntfy.example.test/private-topic", ""), ("https://example.test/custom-hook", "")])
# Verifies distinctive Discord and public ntfy URLs select the proper payload provider
def test_webhook_provider_detection(im_module, url, expected):
    assert im_module.detect_webhook_provider(url) == expected


# Verifies SIGHUP redetects ntfy and schedules active Instaloader sessions for proxy refresh
def test_sighup_reload_updates_webhook_provider_and_proxy_session(im_module, monkeypatch):
    replacements = {"WEBHOOK_URL": "https://ntfy.sh/new-private-topic", "PROXY_URL": "https://new-user:new-password@proxy.example.test"}
    monkeypatch.setattr(im_module, "DOTENV_FILE", "test.env")
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/old-token")
    monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(im_module, "PROXY_ENABLED", True)
    monkeypatch.setattr(im_module, "PROXY_URL", "https://old-user:old-password@proxy.example.test")
    monkeypatch.setattr(im_module, "PROXY_REFRESH_VERSION", 4)
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)
    monkeypatch.setattr(im_module._thread_local, "last_proxy_version", 4, raising=False)
    session = SimpleNamespace(proxies={"https": "https://old-user:old-password@proxy.example.test"}, verify=True)
    bot = SimpleNamespace(context=SimpleNamespace(_session=session))
    with patch("dotenv.load_dotenv"), patch.object(im_module.os, "getenv", side_effect=replacements.get), patch.object(im_module, "log_activity"):
        im_module.reload_secrets_signal_handler(getattr(im_module.signal, "SIGHUP", im_module.signal.SIGTERM), None)
        im_module.refresh_proxy_if_needed(bot, "target")
    assert im_module.WEBHOOK_PROVIDER == "ntfy"
    assert im_module.PROXY_REFRESH_VERSION == 5
    assert session.proxies == {"http": replacements["PROXY_URL"], "https": replacements["PROXY_URL"]}


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
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

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
        assert payload["allowed_mentions"] == {"parse": []}

    # A string webhook template is sent as raw data instead of JSON
    def test_string_template_uses_data_post(self, im_module, monkeypatch):
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_TEMPLATE", "{title}:{fields_str}")
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

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
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "desc", notification_type="status") == 1
        assert calls == []

    # HTTP 429 responses are retried and a later success is reported as delivered
    def test_rate_limit_response_retries(self, im_module, monkeypatch):
        responses = [_FakeResponse(429, "slow down", headers={"Retry-After": "999"}), _FakeResponse(204, "")]
        calls = []
        sleeps = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.time, "sleep", sleeps.append)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or responses.pop(0))

        assert im_module.send_webhook("Title", "desc") == 0
        assert len(calls) == 2
        assert sleeps == [im_module.WEBHOOK_MAX_RETRY_AFTER_SECONDS]

    # HTTP 5xx responses are retried once while every 2xx response is accepted
    def test_server_error_retries_then_accepts_any_2xx(self, im_module, monkeypatch):
        responses = [_FakeResponse(503, "temporarily unavailable"), _FakeResponse(202, "accepted")]
        sleeps = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.time, "sleep", sleeps.append)
        post = Mock(side_effect=responses)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", post)

        assert im_module.send_webhook("Title", "desc") == 0
        assert post.call_count == 2
        assert sleeps == [im_module.WEBHOOK_FALLBACK_RETRY_SECONDS]

    # Non-retryable client errors fail after one request
    def test_client_error_is_not_retried(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        post = Mock(return_value=_FakeResponse(400, "bad request"))
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", post)

        assert im_module.send_webhook("Title", "desc") == 1
        post.assert_called_once()

    # A native ntfy call sends UTF-8 text, field details and the title query parameter
    def test_ntfy_payload_uses_native_topic_api(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic?auth=private-value")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

        rc = im_module.send_webhook("Instagram title za\u017c\u00f3\u0142\u0107", "Body: Bj\u00f6rk", fields=[{"name": "Count", "value": "3"}], image_url="https://example.com/image.jpg")

        assert rc == 0
        args, kwargs = calls[0]
        assert args == ("https://ntfy.sh/private-topic?auth=private-value",)
        assert kwargs["data"] == "Body: Bj\u00f6rk\n\nCount: 3\n\nImage: https://example.com/image.jpg".encode("utf-8")
        assert kwargs["params"] == {"title": "Instagram title za\u017c\u00f3\u0142\u0107"}
        assert kwargs["headers"]["Content-Type"] == "text/plain; charset=utf-8"
        assert "json" not in kwargs

    # A known ntfy URL corrects a stale configured provider and sends native text
    def test_runtime_provider_detection_corrects_config_mismatch(self, im_module, monkeypatch, capsys):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

        assert im_module.apply_webhook_provider_autodetection() == "ntfy"
        assert "Using ntfy" in capsys.readouterr().out
        assert im_module.send_webhook("Instagram title", "Native body") == 0
        assert calls[0][1]["data"] == b"Native body"
        assert "json" not in calls[0][1]

    # Static custom headers are copied to native ntfy requests
    def test_ntfy_custom_headers_are_preserved(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.example.test/private-topic")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"Authorization": "Basic shared-private-value", "X-Monitor": "instagram"})
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

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
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

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
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse(200))

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
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "Body") == 1
        assert calls == []

    # Header placeholders cannot inject line breaks after payload formatting
    def test_formatted_webhook_headers_reject_line_break_injection(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"X-Title": "{title}"})
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("first\nsecond", "Body") == 1
        assert calls == []

    # Custom templates cannot re-enable Discord mentions
    def test_custom_template_cannot_enable_mentions(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_TEMPLATE", {"content": "{title}: {description}", "allowed_mentions": {"parse": ["everyone"]}})
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("@everyone", "@here") == 0
        assert calls[0][1]["json"]["allowed_mentions"] == {"parse": []}

    # Unsafe transforms and avatar URLs fail before a webhook request is attempted
    @pytest.mark.parametrize("attribute,value", [("WEBHOOK_TRANSFORMS", [("title", "__class__")]), ("WEBHOOK_TRANSFORMS", [("title",)]), ("WEBHOOK_AVATAR_URL", "http://example.com/avatar.png"), ("WEBHOOK_TEMPLATE", 3)])
    def test_invalid_webhook_customization_is_rejected(self, im_module, monkeypatch, attribute, value):
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, attribute, value)
        post = Mock(side_effect=AssertionError("webhook request attempted"))
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", post)

        assert im_module.send_webhook("Title", "Body") == 1
        post.assert_not_called()

    # An ntfy image upload failure falls back to one text-only request
    def test_ntfy_image_failure_falls_back_to_text(self, im_module, monkeypatch):
        with make_test_directory() as directory_name:
            image_path = Path(directory_name) / "profile.jpg"
            image_path.write_bytes(b"fake-image")
            responses = [_FakeResponse(413, "attachment too large"), _FakeResponse(200)]
            calls = []
            monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
            monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
            monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.example.test/private-topic")
            monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
            monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or responses.pop(0))

            assert im_module.send_webhook("Title", "Body", local_image_file=str(image_path)) == 0
            assert calls[0][1]["data"] == b"fake-image"
            assert calls[0][1]["params"] == {"title": "Title", "message": "Body"}
            assert calls[0][1]["headers"]["X-Filename"] == "profile.jpg"
            assert calls[1][1]["data"] == b"Body"
            assert calls[1][1]["params"] == {"title": "Title"}

    # Long ntfy messages stay below the server attachment boundary with a visible truncation marker
    def test_ntfy_message_stays_below_attachment_boundary(self, im_module):
        title, message = im_module.build_ntfy_webhook_message("Title", ("a" * im_module.NTFY_MESSAGE_LIMIT_BYTES) + "\U0001f3a5")
        assert title == "Title"
        assert message.endswith(im_module.NTFY_TRUNCATION_SUFFIX)
        assert len(message.encode("utf-8")) <= im_module.NTFY_MESSAGE_LIMIT_BYTES
        assert len(message.encode("utf-8")) < 4096
        assert "\ufffd" not in message

    # An unsupported provider fails before any webhook request is attempted
    def test_invalid_webhook_provider_is_rejected(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "unsupported")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        assert im_module.send_webhook("Title", "Body") == 1
        assert calls == []


# Private webhook entry requires a terminal and a complete HTTPS URL
def test_set_webhook_url_requires_safe_input(im_module):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        with pytest.raises(im_module.WebhookConfigurationError, match="interactive terminal"):
            im_module.run_set_webhook_url(env_file=env_path, interactive=False)
        with pytest.raises(im_module.WebhookConfigurationError, match="complete HTTPS"):
            im_module.run_set_webhook_url(env_file=env_path, interactive=True, getpass_func=lambda prompt: "http://example.com/hook")
        assert not env_path.exists()


# Private webhook entry writes only the dotenv file and never displays the URL
def test_set_webhook_url_persists_privately(im_module, monkeypatch, capsys):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        webhook_url = "https://example.test/private-hook"
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")

        result = im_module.run_set_webhook_url(env_file=env_path, interactive=True, getpass_func=lambda prompt: webhook_url)

        assert result == str(env_path.resolve())
        dotenv = dotenv_values(env_path, interpolate=False)
        assert dotenv["WEBHOOK_URL"] == webhook_url
        assert "WEBHOOK_PROVIDER" not in dotenv
        assert webhook_url not in capsys.readouterr().out


# Declining replacement leaves an existing private webhook URL unchanged
def test_set_webhook_url_declined_replacement_is_non_destructive(im_module):
    with make_test_directory() as directory_name:
        env_path = Path(directory_name) / ".env"
        env_path.write_text('WEBHOOK_URL="https://example.test/original"\n', encoding="utf-8")
        with pytest.raises(im_module.WebhookConfigurationError, match="cancelled"):
            im_module.run_set_webhook_url(env_file=env_path, interactive=True, input_func=lambda prompt: "no", getpass_func=lambda prompt: "https://example.test/replacement")
        assert dotenv_values(env_path, interpolate=False)["WEBHOOK_URL"] == "https://example.test/original"


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
        assert "WEBHOOK_PROVIDER" not in dotenv
        output = capsys.readouterr().out
        assert topic_name not in output
        assert topic_url not in output
        assert token not in output
