"""Tests for webhook / Discord notification helpers (no network)."""

import pytest


class TestValidateWebhookUrl:
    @pytest.mark.parametrize("url", ["https://discord.com/api/webhooks/123/abc", "http://example.com/hook", "https://example.com"])
    def test_valid_urls(self, im_module, url):
        assert im_module.validate_webhook_url(url) is True

    @pytest.mark.parametrize("url", ["", None, "ftp://example.com", "discord.com/webhook", "https://"])
    def test_invalid_urls(self, im_module, url):
        assert im_module.validate_webhook_url(url) is False


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
