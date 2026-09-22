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


@pytest.mark.parametrize("provider,expected", [("discord", "Discord"), ("DISCORD", "Discord"), (" Discord ", "Discord"), ("ntfy", "ntfy"), ("NTFY", "ntfy"), ("slack", ""), ("", "")])
# Verifies user-facing text spells each provider the way its service brands it
def test_webhook_provider_display_name(im_module, provider, expected):
    assert im_module.webhook_provider_display_name(provider) == expected


# Verifies SIGHUP redetects ntfy and schedules active Instaloader sessions for proxy refresh
def test_sighup_reload_updates_webhook_provider_and_proxy_session(im_module, monkeypatch, capsys, tmp_path):
    if not hasattr(im_module.signal, "SIGHUP"):
        pytest.skip("SIGHUP is unavailable on Windows")
    replacements = {"WEBHOOK_URL": "https://ntfy.sh/new-private-topic", "PROXY_URL": "https://new-user:new-password@proxy.example.test"}
    dotenv_path = tmp_path / "test.env"
    dotenv_path.write_text("".join(key + "=" + repr(value) + "\n" for key, value in replacements.items()), encoding="utf-8")
    monkeypatch.setattr(im_module, "DOTENV_FILE", str(dotenv_path))
    monkeypatch.setattr(im_module, "DOTENV_RELOAD_STATE", {})
    for key in replacements:
        monkeypatch.setenv(key, "")
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/old-token")
    monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(im_module, "PROXY_ENABLED", True)
    monkeypatch.setattr(im_module, "PROXY_URL", "https://old-user:old-password@proxy.example.test")
    monkeypatch.setattr(im_module, "PROXY_REFRESH_VERSION", 4)
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)
    monkeypatch.setattr(im_module._thread_local, "last_proxy_version", 4, raising=False)
    session = SimpleNamespace(proxies={"https": "https://old-user:old-password@proxy.example.test"}, verify=True)
    bot = SimpleNamespace(context=SimpleNamespace(_session=session))
    with patch.object(im_module, "log_activity"):
        im_module.reload_secrets_signal_handler(im_module.signal.SIGHUP, None)
        im_module.refresh_proxy_if_needed(bot, "target")
    assert im_module.WEBHOOK_PROVIDER == "ntfy"
    assert im_module.PROXY_REFRESH_VERSION == 5
    assert session.proxies == {"http": replacements["PROXY_URL"], "https": replacements["PROXY_URL"]}
    output = capsys.readouterr().out
    assert f"Reloaded WEBHOOK_URL from {dotenv_path}" in output
    assert f"Reloaded PROXY_URL from {dotenv_path}" in output
    assert "new-private-topic" not in output
    assert "new-password" not in output


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

    # Delivery must stay bounded even if a future call site forgets to pass the configured deadline
    def test_delivery_falls_back_to_the_configured_deadline(self, im_module, monkeypatch):
        post = Mock(return_value=_FakeResponse())
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", post)

        im_module.post_webhook_request("https://example.com/hook", True, None, json={"content": "body"})

        assert post.call_args.kwargs["timeout"] == im_module.WEBHOOK_TIMEOUT_SECONDS
        assert post.call_args.kwargs["allow_redirects"] is False

    # An unconfigured WEBHOOK_URL still holding the shipped placeholder must not be treated as a destination
    def test_placeholder_url_sends_nothing(self, im_module, monkeypatch, capsys):
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "your_webhook_url")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        rc = im_module.send_webhook("Title", "desc")

        assert rc == 1
        assert calls == []
        assert "Webhook error" not in capsys.readouterr().out

    # Rejects a non-JSON Discord template before contacting the service
    def test_non_json_template_is_refused(self, im_module, monkeypatch):
        calls = []

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_TEMPLATE", "{title}:{fields_str}")
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or _FakeResponse())

        rc = im_module.send_webhook("Title", "desc", fields=[{"name": "Name", "value": "Value"}])

        assert rc == 1
        assert calls == []

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
        assert kwargs["headers"]["X-Title"] == "Instagram title za\u017c\u00f3\u0142\u0107"
        # Alert content must never travel in the query string, where servers and proxies log it
        assert "params" not in kwargs
        assert kwargs["allow_redirects"] is False
        assert kwargs["headers"]["Content-Type"] == "text/plain; charset=utf-8"
        assert "json" not in kwargs

    # A known ntfy URL corrects a stale configured provider and sends native text
    def test_runtime_provider_detection_corrects_config_mismatch(self, im_module, monkeypatch, capsys):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        # Only a provider the configuration actually sets is worth warning about, so the warning needs it named here
        monkeypatch.setattr(im_module, "CONFIGURED_SETTING_NAMES", {"WEBHOOK_PROVIDER"})
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
            assert calls[0][1]["headers"]["X-Title"] == "Title"
            assert calls[0][1]["headers"]["X-Message"] == "Body"
            assert "params" not in calls[0][1]
            assert calls[0][1]["headers"]["X-Filename"] == "profile.jpg"
            assert calls[1][1]["data"] == b"Body"
            assert calls[1][1]["headers"]["X-Title"] == "Title"
            assert "params" not in calls[1][1]

    # Long ntfy messages stay below the server attachment boundary with a visible truncation marker
    def test_ntfy_message_stays_below_attachment_boundary(self, im_module):
        title, message = im_module.build_ntfy_webhook_message("Title", ("a" * im_module.NTFY_MESSAGE_LIMIT_BYTES) + "\U0001f3a5")
        assert title == "Title"
        assert message.endswith(im_module.NTFY_TRUNCATION_SUFFIX)
        assert len(message.encode("utf-8")) <= im_module.NTFY_MESSAGE_LIMIT_BYTES
        assert len(message.encode("utf-8")) < 4096
        assert "\ufffd" not in message

    # ntfy renders no markdown, so the emphasis, code spans and bracketed links the Discord embed carries are removed
    def test_ntfy_receives_the_alert_text_without_markdown(self, im_module):
        added = f"- {im_module.escape_discord_markdown('some_user*name')} (<https://www.instagram.com/some_user/>)\n"
        embed = im_module.follower_change_embed("misiektoja", "followers", 10, 11, added, "")

        title, message = im_module.build_ntfy_webhook_message(embed["webhook_title"], embed["webhook_description"], embed["webhook_fields"])

        assert title == "\U0001f4c8 misiektoja Followers Changed"
        assert "User misiektoja followers changed from 10 to 11" in message
        # The escapes that keep a name literal on Discord would reach ntfy as visible backslashes
        assert "Added followers: - some_user*name (https://www.instagram.com/some_user/)" in message
        assert "**" not in message and "\\" not in message and "<https" not in message

    # A code span marks the failing call on Discord and reads as stray backticks anywhere else
    def test_ntfy_drops_the_code_span_around_an_error(self, im_module):
        _, message = im_module.build_ntfy_webhook_message("Title", "Session flagged\n\nTriggering error: `401 Unauthorized`")

        assert message == "Session flagged\n\nTriggering error: 401 Unauthorized"

    # The Discord embed keeps its markdown, so removing it for ntfy must not reach the other provider
    def test_the_discord_embed_keeps_its_markdown(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls.append(kwargs) or _FakeResponse(200))

        assert im_module.send_webhook("Title", "User **misiektoja** posts count changed from **10** to **11**") == 0
        assert calls[0]["json"]["embeds"][0]["description"] == "User **misiektoja** posts count changed from **10** to **11**"

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
        webhook_url = "https://example.test"
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
        with pytest.raises(im_module.WebhookConfigurationError, match="left as it is"):
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
        choices = iter([0, 2, 1, 0, 0])
        secrets = iter([topic_name, token])
        monkeypatch.delenv("WEBHOOK_URL", raising=False)
        monkeypatch.delenv("NTFY_ACCESS_TOKEN", raising=False)
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
        monkeypatch.setattr(im_module, "_wizard_ask_text", lambda *args, **kwargs: "target.user")
        monkeypatch.setattr(im_module, "_wizard_ask_duration", lambda question, default: default)
        monkeypatch.setattr(im_module, "_wizard_ask_yes_no", lambda *args, **kwargs: next(answers))
        monkeypatch.setattr(im_module, "_wizard_ask_choice", lambda *args, **kwargs: next(choices))
        monkeypatch.setattr(im_module, "_wizard_collect_connection_section", lambda state: None)
        monkeypatch.setattr(im_module, "_wizard_collect_output_section", lambda state: None)
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


class TestWebhookDeliveryTests:
    # An operator-requested delivery test sends even though every event switch is off by default
    def test_delivery_test_bypasses_event_switches(self, im_module, monkeypatch):
        posts = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_FOLLOWERS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", False)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: posts.append(kwargs) or SimpleNamespace(status_code=204, text="", headers={}))

        result = im_module.send_webhook("test", "body", notification_type=im_module.WEBHOOK_TEST_NOTIFICATION_TYPE)

        assert result == 0
        assert len(posts) == 1

    # Real event categories still honour their configured switch so notifications stay opt-in
    @pytest.mark.parametrize("notification_type", ["status", "followers", "error"])
    def test_event_categories_still_honour_their_switch(self, im_module, monkeypatch, notification_type):
        posts = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_FOLLOWERS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", False)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: posts.append(kwargs) or SimpleNamespace(status_code=204, text="", headers={}))

        assert im_module.send_webhook("t", "b", notification_type=notification_type) == 1
        assert posts == []


# Verifies a webhook receipt names its provider
def test_a_delivered_webhook_is_reported_in_verbose(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
    monkeypatch.setattr(im_module, "VERBOSE_MODE", True)
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", Mock(return_value=_FakeResponse()))

    assert im_module.send_webhook("Profile picture changed", "desc", notification_type="status") == 0

    assert "* Webhook sent through Discord" in capsys.readouterr().out


# Verifies the delivery line follows the flag rather than printing on every alert, so an ordinary run stays
# quiet and --send-test-webhook reports the result once through its own confirmation
def test_a_delivered_webhook_stays_quiet_without_the_flag(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
    monkeypatch.setattr(im_module, "VERBOSE_MODE", False)
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", Mock(return_value=_FakeResponse()))

    assert im_module.send_webhook("Profile picture changed", "desc", notification_type="status") == 0

    assert capsys.readouterr().out == ""


# Verifies an email receipt names its recipient
def test_a_delivered_email_is_reported_in_verbose(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(im_module, "SMTP_PORT", 587)
    monkeypatch.setattr(im_module, "SMTP_USER", "sender")
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "not-a-real-password")
    monkeypatch.setattr(im_module, "SENDER_EMAIL", "sender@example.com")
    monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "receiver@example.com")
    monkeypatch.setattr(im_module, "VERBOSE_MODE", True)
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    monkeypatch.setattr(im_module.smtplib, "SMTP", Mock(return_value=Mock()))

    assert im_module.send_email("Profile picture changed", "Body", "", False) == 0

    assert "* Email sent to receiver@example.com" in capsys.readouterr().out


# Verifies DELIVERY_CONFIRMATIONS drops both delivery lines without turning the rest of verbose mode off
def test_delivery_confirmations_can_be_turned_off(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
    monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(im_module, "SMTP_PORT", 587)
    monkeypatch.setattr(im_module, "SMTP_USER", "sender")
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "not-a-real-password")
    monkeypatch.setattr(im_module, "SENDER_EMAIL", "sender@example.com")
    monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "receiver@example.com")
    monkeypatch.setattr(im_module, "VERBOSE_MODE", True)
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    monkeypatch.setattr(im_module, "DELIVERY_CONFIRMATIONS", False)
    monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", Mock(return_value=_FakeResponse()))
    monkeypatch.setattr(im_module.smtplib, "SMTP", Mock(return_value=Mock()))

    assert im_module.send_webhook("Profile picture changed", "desc", notification_type="status") == 0
    assert im_module.send_email("Profile picture changed", "Body", "", False) == 0

    output = capsys.readouterr().out
    assert "Webhook sent through" not in output
    assert "Email sent to" not in output


class TestSendNotificationChannels:
    # Puts a real webhook destination behind a recording post and a recording email sender, each answering as told
    def _channels(self, im_module, monkeypatch, email_result=0, post_status=204):
        calls = {"email": [], "posts": []}
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_FOLLOWERS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "alerts@example.test")
        monkeypatch.setattr(im_module, "SMTP_SSL", True, raising=False)
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: calls["email"].append((args, kwargs)) or email_result)
        monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: calls["posts"].append(kwargs) or _FakeResponse(post_status))
        return calls

    # The helper starts with the family's parameters in the family's order, so a call written for a sibling works here
    def test_the_helper_starts_with_the_shared_parameters(self, im_module):
        import inspect
        parameters = list(inspect.signature(im_module.send_notification_channels).parameters.values())

        assert [parameter.name for parameter in parameters[:6]] == ["notification_type", "subject", "body", "body_html", "email_enabled", "webhook_enabled"]
        assert [parameter.default for parameter in parameters[3:6]] == ["", False, None]

    # Each enabled channel receives the alert and the return value reports delivery
    def test_each_enabled_channel_receives_the_alert(self, im_module, monkeypatch, capsys):
        calls = self._channels(im_module, monkeypatch)

        delivered = im_module.send_notification_channels("status", "subject", "body", "<b>body</b>", email_enabled=True)

        assert delivered == (True, True)
        assert calls["email"] == [(("subject", "body", "<b>body</b>", True), {"image_file": "", "image_name": "image1"})]
        assert len(calls["posts"]) == 1
        output = capsys.readouterr().out
        assert "Sending email notification to alerts@example.test" in output
        assert "Sending webhook notification" in output

    # A channel that failed reports no delivery, so the caller can retry it while leaving the other alone
    def test_a_failed_channel_reports_no_delivery(self, im_module, monkeypatch):
        self._channels(im_module, monkeypatch, email_result=1, post_status=400)

        assert im_module.send_notification_channels("status", "subject", "body", email_enabled=True, webhook_enabled=True) == (False, False)

    # A channel the caller switched off is not contacted at all
    def test_a_channel_the_caller_switched_off_is_not_contacted(self, im_module, monkeypatch):
        calls = self._channels(im_module, monkeypatch)

        assert im_module.send_notification_channels("status", "subject", "body", email_enabled=False, webhook_enabled=False) == (False, False)
        assert calls["email"] == []
        assert calls["posts"] == []

    # The configured switch decides the webhook channel when the caller does not say
    def test_the_configured_switch_decides_the_webhook_when_the_caller_does_not_say(self, im_module, monkeypatch):
        calls = self._channels(im_module, monkeypatch)

        assert im_module.send_notification_channels("followers", "subject", "body")[1] is False
        assert calls["posts"] == []
        assert im_module.send_notification_channels("status", "subject", "body")[1] is True
        assert len(calls["posts"]) == 1

    # The embed the caller shaped reaches the webhook unchanged and the switch is not applied a second time
    def test_the_embed_reaches_the_webhook_as_shaped(self, im_module, monkeypatch):
        sent = {}
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: sent.update(args=args, kwargs=kwargs) or 0)
        fields = [{"name": "Followers", "value": "10 -> 12", "inline": True}]

        im_module.send_notification_channels("error", "subject", "body", webhook_title="Error for user", webhook_description="what happened", webhook_color=0xFF0000, webhook_fields=fields, image_url="https://example.test/pic.jpg", local_image_file="pic.jpg")

        assert sent["args"] == ("Error for user", "what happened")
        assert sent["kwargs"] == {"color": 0xFF0000, "fields": fields, "image_url": "https://example.test/pic.jpg", "local_image_file": "pic.jpg", "notification_type": "error", "force": True}

    # Without an embed of its own the webhook carries the subject and body, the way the family's plain alerts do
    def test_the_subject_and_body_stand_in_for_a_missing_embed(self, im_module, monkeypatch):
        sent = {}
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: sent.update(args=args, kwargs=kwargs) or 0)

        im_module.send_notification_channels("status", "subject", "body")

        assert sent["args"] == ("subject", "body")
        assert sent["kwargs"]["color"] == 0x7289DA

    # An email with a picture hands the file and its name to the sender
    def test_an_email_picture_reaches_the_sender(self, im_module, monkeypatch):
        calls = self._channels(im_module, monkeypatch)

        im_module.send_notification_channels("status", "subject", "body", "<b>body</b>", email_enabled=True, webhook_enabled=False, email_image_file="story.jpg", email_image_name="story_pic")

        assert calls["email"] == [(("subject", "body", "<b>body</b>", True), {"image_file": "story.jpg", "image_name": "story_pic"})]


class TestWebhookEventEnabled:
    # The master switch gates every alert type, so switching webhooks off silences all of them at once
    def test_the_master_switch_gates_every_alert_type(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_FOLLOWERS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)

        assert [im_module.webhook_event_enabled(event) for event in ("status", "followers", "error")] == [False, False, False]

        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)

        assert [im_module.webhook_event_enabled(event) for event in ("status", "followers", "error")] == [True, True, True]

    # Each alert type follows its own setting, so one can be on while the others are off
    def test_each_alert_type_is_gated_by_its_own_setting(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_FOLLOWERS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", False)

        assert [im_module.webhook_event_enabled(event) for event in ("status", "followers", "error")] == [False, True, False]

    # An alert type the tool does not have is off rather than treated as enabled
    def test_an_unknown_alert_type_is_off(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)

        assert im_module.webhook_event_enabled("mastery") is False


# A caller that already applied the switch says so, and the webhook then posts even though the switch is off
def test_a_forced_webhook_skips_the_switch_it_was_already_given(im_module, monkeypatch):
    posts = []
    monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", False)
    monkeypatch.setattr(im_module.WEBHOOK_SESSION, "post", lambda *args, **kwargs: posts.append(kwargs) or _FakeResponse())

    assert im_module.send_webhook("t", "b", notification_type="status", force=True) == 0
    assert len(posts) == 1
