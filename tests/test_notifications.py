"""Tests for webhook / Discord notification helpers (no network)."""

import pytest


class TestStartupNotificationSummary:
    # Verifies every startup view shares independent email and webhook category rows
    @pytest.mark.parametrize("email_flags,webhook_flags,webhook_enabled,expected_email,expected_webhook", [((), (), False, "Off", "Off"), (("STATUS_NOTIFICATION", "FOLLOWERS_NOTIFICATION", "ERROR_NOTIFICATION"), (), False, "On (status/profile changes, followers, errors)", "Off"), ((), ("WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_FOLLOWERS_NOTIFICATION", "WEBHOOK_ERROR_NOTIFICATION"), True, "Off", "On (status/profile changes, followers, errors)"), (("STATUS_NOTIFICATION", "ERROR_NOTIFICATION"), ("WEBHOOK_FOLLOWERS_NOTIFICATION",), True, "On (status/profile changes, errors)", "On (followers)"), ((), ("WEBHOOK_ERROR_NOTIFICATION",), False, "Off", "Off")])
    def test_channel_rows(self, im_module, monkeypatch, email_flags, webhook_flags, webhook_enabled, expected_email, expected_webhook):
        all_flags = ("STATUS_NOTIFICATION", "FOLLOWERS_NOTIFICATION", "ERROR_NOTIFICATION", "WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_FOLLOWERS_NOTIFICATION", "WEBHOOK_ERROR_NOTIFICATION")
        for name in all_flags:
            monkeypatch.setattr(im_module, name, False)
        for name in email_flags + webhook_flags:
            monkeypatch.setattr(im_module, name, True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", webhook_enabled)
        assert im_module._startup_notification_summary_rows() == [(f"* Notifications (email):\t\t{expected_email}", True, True), (f"* Notifications (webhook):\t\t{expected_webhook}", True, True)]

    # Verifies compact notification rows color only their On or Off state
    def test_channel_rows_color_on_off_state(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
        monkeypatch.setattr(im_module, "_COLOR_STYLES", {"boolean_true": "\033[32m", "boolean_false": "\033[31m"})
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "RICH_AVAILABLE", False)
        text = "* Notifications (email):\t\tOn (status/profile changes, followers, errors)\n* Notifications (webhook):\t\tOff\n"
        expected = "* Notifications (email):\t\t\033[32mOn\033[0m (status/profile changes, followers, errors)\n* Notifications (webhook):\t\t\033[31mOff\033[0m\n"
        colored = im_module.apply_color_to_text(text)
        assert colored == expected
        assert im_module.ANSI_ESCAPE_RE.sub("", colored) == text


class TestValidateWebhookUrl:
    @pytest.mark.parametrize("url", ["https://discord.com/api/webhooks/123/abc", "https://example.com/hook", "https://example.com/", "https://example.com", "https://example.com/?token=value", "https://ntfy.example.test/private-topic?auth=value"])
    def test_valid_urls(self, im_module, url):
        assert im_module.validate_webhook_url(url) is True

    @pytest.mark.parametrize("url", ["", None, "http://example.com/hook", "https://user:password@example.com/hook", "ftp://example.com/hook", "discord.com/webhook", "https://"])
    def test_invalid_urls(self, im_module, url):
        assert im_module.validate_webhook_url(url) is False


class TestValidateProxyUrl:
    @pytest.mark.parametrize("url", ["http://example.com", "https://example.com:8443", "http://user:password@example.com:3128"])
    def test_valid_urls(self, im_module, url):
        assert im_module.validate_proxy_url(url) is True

    @pytest.mark.parametrize("url", ["", None, "ftp://example.com", "https://"])
    def test_invalid_urls(self, im_module, url):
        assert im_module.validate_proxy_url(url) is False


class TestNormalizeNtfyTopicUrl:
    @pytest.mark.parametrize("value,expected", [("https://ntfy.example.test/private-topic?auth=value", "https://ntfy.example.test/private-topic?auth=value"), ("http://ntfy.internal/private-topic", ""), (" private_Topic-123 ", "https://ntfy.sh/private_Topic-123"), ("a" * 64, f"https://ntfy.sh/{'a' * 64}"), ("a" * 65, ""), ("ntfy.sh/private-topic", ""), ("private.topic", ""), ("private/topic", ""), (None, "")])
    def test_normalization(self, im_module, value, expected):
        assert im_module.normalize_ntfy_topic_url(value) == expected


class TestEscapeDiscordMarkdown:
    def test_empty_string(self, im_module):
        assert im_module.escape_discord_markdown("") == ""

    def test_none_returns_empty(self, im_module):
        assert im_module.escape_discord_markdown(None) == ""

    def test_all_special_chars_escaped(self, im_module):
        assert im_module.escape_discord_markdown("a*b_c~`|d") == r"a\*b\_c\~\`\|d"

    def test_backslash_escaped(self, im_module):
        assert im_module.escape_discord_markdown("a\\b") == "a\\\\b"

    def test_plain_text_untouched(self, im_module):
        assert im_module.escape_discord_markdown("plain text 123") == "plain text 123"


class TestMaskUrlCredentials:
    def test_none_passthrough(self, im_module):
        assert im_module.mask_url_credentials(None) is None

    def test_no_credentials_unchanged(self, im_module):
        assert im_module.mask_url_credentials("http://host:3128") == "http://host:3128"

    def test_user_and_password_masked(self, im_module):
        assert im_module.mask_url_credentials("http://user:pass@host:3128") == "http://***:***@host:3128"

    def test_user_only_masked(self, im_module):
        assert im_module.mask_url_credentials("http://user@host") == "http://***@host"

    def test_host_and_port_preserved(self, im_module):
        masked = im_module.mask_url_credentials("https://u:p@proxy.example.com:8080/path")
        assert "proxy.example.com:8080" in masked
        assert "u:p" not in masked


class TestFormatPayload:
    def test_string_substitution(self, im_module):
        assert im_module.format_payload("{title}", {"title": "Hello"}) == "Hello"

    def test_missing_key_returns_template(self, im_module):
        assert im_module.format_payload("{missing}", {"title": "Hello"}) == "{missing}"

    def test_fields_placeholder_returns_list(self, im_module):
        fields = [{"name": "n", "value": "v"}]
        assert im_module.format_payload("{fields}", {"fields": fields}) == fields

    def test_color_placeholder_returns_int(self, im_module):
        assert im_module.format_payload("{color}", {"color": 123}) == 123

    def test_color_placeholder_default(self, im_module):
        assert im_module.format_payload("{color}", {}) == 0x7289DA

    def test_nested_template_is_recursed(self, im_module):
        template = {"content": "{title}", "embeds": [{"title": "{title}", "color": "{color}", "fields": "{fields}"}]}
        payload = {"title": "T", "color": 99, "fields": [{"name": "a", "value": "b"}]}
        result = im_module.format_payload(template, payload)
        assert result == {"content": "T", "embeds": [{"title": "T", "color": 99, "fields": [{"name": "a", "value": "b"}]}]}

    def test_non_string_scalar_passthrough(self, im_module):
        assert im_module.format_payload(42, {}) == 42
        assert im_module.format_payload(True, {}) is True


class TestSendFollowerChangeWebhook:
    def test_returns_one_when_webhook_disabled(self, im_module, monkeypatch):
        # With WEBHOOK_ENABLED False (baseline), send_webhook short-circuits to 1 without any network call
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)
        rc = im_module.send_follower_change_webhook("user", "followers", 10, 12, "- a (<url>)\n", "")
        assert rc == 1

    def test_passes_through_when_url_missing(self, im_module, monkeypatch):
        # Enabled but no URL -> still guarded, no network
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "")
        rc = im_module.send_follower_change_webhook("user", "followings", 5, 4, "", "- b (<url>)\n")
        assert rc == 1

    # Follower changes pass a follower notification payload through to send_webhook
    def test_followers_payload_passed_to_send_webhook(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: calls.append((args, kwargs)) or 0)

        rc = im_module.send_follower_change_webhook("user", "followers", 10, 12, "- a (<url>)\n", "")

        assert rc == 0
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert "user Followers Changed" in args[0]
        assert args[1] == "User **user** followers changed from **10** to **12**"
        assert kwargs["color"] == 0x2ecc71
        assert kwargs["notification_type"] == "followers"
        assert kwargs["fields"][:3] == [
            {"name": "Old Count", "value": "10", "inline": True},
            {"name": "New Count", "value": "12", "inline": True},
            {"name": "Change", "value": "+2", "inline": True},
        ]
        assert kwargs["fields"][3] == {"name": "**Added followers:**", "value": "- a (<url>)\n"}

    # Following changes pass a status notification payload through to send_webhook
    def test_followings_payload_passed_to_send_webhook(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: calls.append((args, kwargs)) or 0)

        rc = im_module.send_follower_change_webhook("user", "followings", 5, 4, "", "- b (<url>)\n")

        assert rc == 0
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert "user Followings Changed" in args[0]
        assert args[1] == "User **user** followings changed from **5** to **4**"
        assert kwargs["color"] == 0x3498db
        assert kwargs["notification_type"] == "status"
        assert kwargs["fields"][:3] == [
            {"name": "Old Count", "value": "5", "inline": True},
            {"name": "New Count", "value": "4", "inline": True},
            {"name": "Change", "value": "-1", "inline": True},
        ]
        assert kwargs["fields"][3] == {"name": "**Removed followings:**", "value": "- b (<url>)\n"}
