"""Tests for webhook / Discord notification helpers (no network)."""

from unittest.mock import Mock

import time

import pytest


# Gives both channels a destination, since the rollup rows report a channel with none as off whatever its alert types are
def _configure_channel_destinations(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(im_module, "SMTP_PORT", 587)
    monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "michal.k@example.com")
    monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/abc")


class TestStartupNotificationSummary:
    # Verifies every startup view shares independent email and webhook category rows
    @pytest.mark.parametrize("email_flags,webhook_flags,webhook_enabled,expected_email,expected_webhook", [((), (), False, "Off", "Off"), (("STATUS_NOTIFICATION", "FOLLOWERS_NOTIFICATION", "ERROR_NOTIFICATION"), (), False, "On (status/profile changes, followers, errors)", "Off"), ((), ("WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_FOLLOWERS_NOTIFICATION", "WEBHOOK_ERROR_NOTIFICATION"), True, "Off", "On (status/profile changes, followers, errors)"), (("STATUS_NOTIFICATION", "ERROR_NOTIFICATION"), ("WEBHOOK_FOLLOWERS_NOTIFICATION",), True, "On (status/profile changes, errors)", "On (followers)"), ((), ("WEBHOOK_ERROR_NOTIFICATION",), False, "Off", "Off")])
    def test_channel_rows(self, im_module, monkeypatch, email_flags, webhook_flags, webhook_enabled, expected_email, expected_webhook):
        all_flags = ("STATUS_NOTIFICATION", "FOLLOWERS_NOTIFICATION", "ERROR_NOTIFICATION", "WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_FOLLOWERS_NOTIFICATION", "WEBHOOK_ERROR_NOTIFICATION")
        for name in all_flags:
            monkeypatch.setattr(im_module, name, False)
        _configure_channel_destinations(im_module, monkeypatch)
        for name in email_flags + webhook_flags:
            monkeypatch.setattr(im_module, name, True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", webhook_enabled)
        rows = {row.label: (row.value, row.concise, row.full) for row in im_module._startup_notification_summary_rows()}
        assert rows["Notifications (email)"] == (expected_email, True, True)
        assert rows["Notifications (webhook)"] == (expected_webhook, True, True)
        # The detail rows sit next to the channel they describe and stay out of the short view
        assert [label for label in rows] == ["Notifications (email)", "Email transport", "Email recipient", "Notifications (webhook)", "Webhook provider", "Delivery confirmations"]
        assert not any(concise for label, (_, concise, _full) in rows.items() if label.startswith(("Email ", "Webhook ", "Delivery ")))

    # Verifies a channel with its alert types on but no destination is not reported as live, since the rollup is the only line the short view prints
    @pytest.mark.parametrize("label,unset", [("Notifications (email)", {"SMTP_HOST": "your_smtp_server_ssl"}), ("Notifications (email)", {"RECEIVER_EMAIL": "your_receiver_email"}), ("Notifications (webhook)", {"WEBHOOK_URL": "your_webhook_url"})])
    def test_a_channel_without_a_destination_is_reported_as_off(self, im_module, monkeypatch, label, unset):
        _configure_channel_destinations(im_module, monkeypatch)
        for name in ("STATUS_NOTIFICATION", "FOLLOWERS_NOTIFICATION", "ERROR_NOTIFICATION", "WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_FOLLOWERS_NOTIFICATION", "WEBHOOK_ERROR_NOTIFICATION"):
            monkeypatch.setattr(im_module, name, True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        for name, value in unset.items():
            monkeypatch.setattr(im_module, name, value)

        rows = {row.label: row.value for row in im_module._startup_notification_summary_rows()}

        assert rows[label] == "Off (not configured)"

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


class TestValidateFqdn:
    # Accepts ordinary SMTP hostnames including a final DNS root dot
    @pytest.mark.parametrize("hostname", ["smtp.example.com", "mail-2.eu.example.org", "smtp.example.com."])
    def test_valid_hostnames(self, im_module, hostname):
        assert im_module.is_valid_fqdn(hostname) is True

    # Rejects malformed and unbounded hostnames without running a backtracking expression
    @pytest.mark.parametrize("hostname", ["", "localhost", "-smtp.example.com", "smtp-.example.com", "smtp.example.123", f"{'a' * 64}.example.com", f"{'a.' * 130}com"])
    def test_invalid_hostnames(self, im_module, hostname):
        assert im_module.is_valid_fqdn(hostname) is False


class TestValidateEmailAddress:
    # Accepts the same mailbox forms as the prior expression through direct linear parsing
    @pytest.mark.parametrize("address", ["alerts@example.com", "monitor+daily@mail-2.example.org", "alerts@example.c", " display name <alerts@example.com> "])
    def test_valid_addresses(self, im_module, address):
        assert im_module.is_valid_email_address(address) is True

    # Rejects values that lack a mailbox, domain label or suffix without applying a backtracking expression
    @pytest.mark.parametrize("address", ["", "alerts", "alerts@example", "@example.com", "alerts@.com", "alerts@example.", "two words@example.com", "alerts@exa mple.com", "alerts@example.com\nBcc: other@example.com", "<>"])
    def test_invalid_addresses(self, im_module, address):
        assert im_module.is_valid_email_address(address) is False


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

    # Verifies masking preserves the complete destination and path without retaining credentials
    def test_host_and_port_preserved(self, im_module):
        masked = im_module.mask_url_credentials("https://u:p@proxy.example.com:8080/path")
        assert masked == "https://***:***@proxy.example.com:8080/path"


class TestFormatPayload:
    def test_string_substitution(self, im_module):
        assert im_module.format_payload("{title}", {"title": "Hello"}) == "Hello"

    # Reports an unknown field instead of sending an unexpanded template
    def test_missing_key_names_the_template_error(self, im_module):
        with pytest.raises(ValueError, match="missing"):
            im_module.format_payload("{missing}", {"title": "Hello"})

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


class TestFollowerChangeEmbed:
    # A follower change shapes a follower embed, green when the count went up
    def test_a_follower_gain_shapes_a_green_follower_embed(self, im_module):
        embed = im_module.follower_change_embed("user", "followers", 10, 12, "- a (<url>)\n", "")

        assert embed["webhook_title"].endswith("user Followers Changed")
        assert embed["webhook_description"] == "User **user** followers changed from **10** to **12**"
        assert embed["webhook_color"] == 0x2ecc71
        assert embed["webhook_fields"][:3] == [
            {"name": "Old Count", "value": "10", "inline": True},
            {"name": "New Count", "value": "12", "inline": True},
            {"name": "Change", "value": "+2", "inline": True},
        ]
        assert embed["webhook_fields"][3] == {"name": "**Added followers:**", "value": "- a (<url>)\n"}

    # A following change shapes a blue embed listing what was removed
    def test_a_following_loss_shapes_a_blue_following_embed(self, im_module):
        embed = im_module.follower_change_embed("user", "followings", 5, 4, "", "- b (<url>)\n")

        assert embed["webhook_title"].endswith("user Followings Changed")
        assert embed["webhook_description"] == "User **user** followings changed from **5** to **4**"
        assert embed["webhook_color"] == 0x3498db
        assert embed["webhook_fields"][:3] == [
            {"name": "Old Count", "value": "5", "inline": True},
            {"name": "New Count", "value": "4", "inline": True},
            {"name": "Change", "value": "-1", "inline": True},
        ]
        assert embed["webhook_fields"][3] == {"name": "**Removed followings:**", "value": "- b (<url>)\n"}

    # The embed is what the channels helper hands to the webhook, under the follower switch
    def test_the_embed_reaches_the_webhook_as_a_follower_alert(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_FOLLOWERS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
        embed = im_module.follower_change_embed("user", "followers", 10, 12, "- a (<url>)\n", "")

        assert im_module.send_notification_channels("followers", "subject", "body", **embed) == (False, True)
        assert calls[0][0] == (embed["webhook_title"], embed["webhook_description"])
        assert calls[0][1]["fields"] == embed["webhook_fields"]
        assert calls[0][1]["notification_type"] == "followers"


# A followings change is delivered on the status channel, so the follower switches never gate it. Setup used to
# offer them as one answer, which promised control the switch does not have
class TestWhichSwitchGatesAFollowChange:
    # Runs the real dispatcher for one change and reports which channels it reached
    @staticmethod
    def _delivered(im_module, monkeypatch, channel, email_enabled):
        sent = []
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: sent.append("email") or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: sent.append("webhook") or 0)
        im_module.send_notification_channels(channel, "subject", "body", "", email_enabled=email_enabled)
        return sorted(sent)

    # The switch each caller passes is the contract: followers is ANDed with status, followings is status alone
    @pytest.mark.parametrize("status,followers,expected_followers,expected_followings", [(True, True, ["email"], ["email"]), (True, False, [], ["email"]), (False, True, [], []), (False, False, [], [])])
    def test_only_the_follower_email_needs_both_switches(self, im_module, monkeypatch, status, followers, expected_followers, expected_followings):
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", status)
        monkeypatch.setattr(im_module, "FOLLOWERS_NOTIFICATION", followers)

        assert self._delivered(im_module, monkeypatch, "followers", status and followers) == expected_followers
        assert self._delivered(im_module, monkeypatch, "status", status) == expected_followings

    # The webhook follower switch stands on its own, so a followings alert follows the status one instead
    @pytest.mark.parametrize("webhook_status,webhook_followers,expected_followers,expected_followings", [(True, True, ["webhook"], ["webhook"]), (False, True, ["webhook"], []), (True, False, [], ["webhook"]), (False, False, [], [])])
    def test_the_webhook_follower_switch_is_independent(self, im_module, monkeypatch, webhook_status, webhook_followers, expected_followers, expected_followings):
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/example")
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", webhook_status)
        monkeypatch.setattr(im_module, "WEBHOOK_FOLLOWERS_NOTIFICATION", webhook_followers)

        assert self._delivered(im_module, monkeypatch, "followers", False) == expected_followers
        assert self._delivered(im_module, monkeypatch, "status", False) == expected_followings


# Verifies both test commands carry the subject, title and body shared with the sibling monitors
def test_the_test_messages_use_the_shared_wording(im_module, monkeypatch):
    email = Mock(return_value=0)
    delivery = Mock(return_value=0)
    monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
    monkeypatch.setattr(im_module, "DOTENV_FILE", "")
    monkeypatch.setattr(im_module, "check_internet", lambda *args, **kwargs: True)
    monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "send_email", email)
    monkeypatch.setattr(im_module, "send_webhook", delivery)
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic")

    for flag in ("--send-test-email", "--send-test-webhook"):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", flag, "--config-file", "none", "--env-file", "none"])
        with pytest.raises(SystemExit) as exc:
            im_module.run_main()
        assert exc.value.code == 0

    assert email.call_args.args[:2] == ("Instagram Monitor test email", "This test email was sent by --send-test-email. Your SMTP settings work.")
    assert delivery.call_args.args[:2] == ("Instagram Monitor test webhook", "This test notification was sent by --send-test-webhook. Your webhook settings work.")


# Verifies a test webhook with no destination reports the shared three-line block instead of a bare error
def test_a_missing_webhook_destination_reports_the_shared_block(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
    monkeypatch.setattr(im_module, "DOTENV_FILE", "")
    monkeypatch.setattr(im_module, "check_internet", lambda *args, **kwargs: True)
    monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: pytest.fail("a webhook was attempted"))
    monkeypatch.setattr(im_module, "WEBHOOK_URL", "")
    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--send-test-webhook", "--config-file", "none", "--env-file", "none", "--no-color"])

    with pytest.raises(SystemExit) as exc:
        im_module.run_main()

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "* Error: No webhook destination is configured" in output
    assert "To fix: Save one with --set-webhook-url, pass --webhook-url or set WEBHOOK_URL in the config file" in output
    assert f"Guide: {im_module.WEBHOOK_GUIDE_URL}" in output
    # The run says nothing about sending, because it never got that far
    assert "Sending test webhook notification" not in output


class TestAccountFlagIdentity:
    # Captures the flagged alert without sending anything
    @pytest.fixture
    def flagged_alert(self, im_module, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "CIRCUIT_BREAKER", False)
        monkeypatch.setattr(im_module, "record_failure_event", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "FLAGGED_NOTIFY_STATE", {"ts": 0})
        monkeypatch.setattr(im_module, "send_email", lambda subject, body, html, ssl, *args, **kwargs: captured.update(body=body, html=html))
        monkeypatch.setattr(im_module, "send_webhook", lambda title, description, *args, **kwargs: captured.update(webhook=description))

        def run():
            im_module.notify_session_flagged("target.user", "Instagram flagged this session account", "checkpoint_required")
            return captured

        return run

    # A flag is only actionable if the reader knows which client produced it
    def test_the_flag_alert_carries_the_transport_and_agent(self, im_module, monkeypatch, flagged_alert):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "USER_AGENT", "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0")

        captured = flagged_alert()

        for surface in (captured["body"], captured["html"], captured["webhook"]):
            assert "curl_cffi impersonating firefox" in surface
            assert "Firefox/147.0" in surface

    # An impersonation that never ran is the likeliest cause of a flag, so the alert has to say so
    def test_the_flag_alert_names_the_transport_fallback(self, im_module, monkeypatch, flagged_alert):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", False)

        assert "requests (curl_cffi is not installed)" in flagged_alert()["body"]

    # An agent that is not set yet must not leave a dangling label in an outgoing message
    def test_the_flag_alert_omits_an_unset_agent(self, im_module, monkeypatch, flagged_alert):
        monkeypatch.setattr(im_module, "USER_AGENT", "")

        captured = flagged_alert()

        assert "Transport:" in captured["body"]
        assert "Browser agent" not in captured["body"] and "Browser agent" not in captured["html"]

    # The agent reaches an HTML mail body, so it goes through the same escaping as the error text
    def test_the_agent_is_escaped_in_the_html_body(self, im_module, monkeypatch, flagged_alert):
        monkeypatch.setattr(im_module, "USER_AGENT", "Mozilla/5.0 <script>alert(1)</script>")

        html = flagged_alert()["html"]

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    # These messages leave the machine, so routine failures must not publish the identity on every threshold hit
    def test_a_routine_error_alert_carries_no_identity(self, im_module, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "ERROR_ALERT_AFTER_SECONDS", 0)
        monkeypatch.setattr(im_module, "USER_AGENT", "Mozilla/5.0 SecretBuild/1")
        monkeypatch.setattr(im_module, "send_email", lambda subject, body, html, ssl, *args, **kwargs: captured.update(body=body))
        monkeypatch.setattr(im_module, "send_webhook", lambda title, description, *args, **kwargs: captured.update(webhook=description))

        advice = im_module.classify_recovery_error("connection reset", is_logged_in=True)
        im_module.notify_monitoring_error("target.user", advice, int(time.time()), 1, 3600, im_module.ErrorAlertState())

        assert "SecretBuild" not in captured["body"] and "SecretBuild" not in captured["webhook"]
        assert "Transport:" not in captured["body"]

    # The guide link sits under the fix in the HTML body too, since HTML renders the newline the fix carries as a space
    def test_the_guide_link_keeps_its_own_line_in_the_html_body(self, im_module, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "ERROR_ALERT_AFTER_SECONDS", 0)
        monkeypatch.setattr(im_module, "send_email", lambda subject, body, html, ssl, *args, **kwargs: captured.update(html=html))

        advice = im_module.classify_recovery_error("connection reset", is_logged_in=True)
        assert "\nGuide: " in advice.fix
        im_module.notify_monitoring_error("target.user", advice, int(time.time()), 1, 3600, im_module.ErrorAlertState())

        parts = captured["html"].split("<br>")
        fix_index = next(index for index, part in enumerate(parts) if part.startswith("To fix: "))
        assert parts[fix_index + 1].startswith('Guide: <a href="https://')
        assert "\n" not in parts[fix_index]
