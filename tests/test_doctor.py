"""Tests for the --doctor preflight checks (no real network)."""

import io
from unittest.mock import Mock

import pytest


class _TTYBuffer(io.StringIO):
    # Reports interactive terminal capability for delivery prompt tests
    def isatty(self):
        return True


class _FakeBot:
    def load_session_from_file(self, username):
        pass

    def test_login(self):
        return "me"


def _setup_no_network(monkeypatch, im):
    monkeypatch.setattr(im.instaloader, "Instaloader", lambda *a, **k: _FakeBot())
    monkeypatch.setattr(im, "profile_from_username_resilient", lambda bot, user: object())
    monkeypatch.setattr(im, "find_config_file", lambda p=None: None)
    monkeypatch.setattr(im, "PROXY_ENABLED", False, raising=False)
    monkeypatch.setattr(im, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
    monkeypatch.setattr(im, "WEBHOOK_URL", "", raising=False)
    monkeypatch.setattr(im, "WEBHOOK_ENABLED", False, raising=False)


class TestDoctorLine:
    @pytest.mark.parametrize("status", ["ok", "warn", "fail", "info"])
    def test_prints_label_and_detail(self, im_module, capsys, status):
        im_module._doctor_line(status, "the-label", "the-detail")
        out = capsys.readouterr().out
        assert "the-label" in out
        assert "the-detail" in out


class TestRunDoctor:
    def test_all_pass_no_login_returns_zero(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        rc = im_module.run_doctor([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Instagram reachable" in out
        assert "No-login mode" in out

    def test_missing_session_fails(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "someacct", raising=False)

        class _NoSession(_FakeBot):
            def load_session_from_file(self, username):
                raise FileNotFoundError()

        monkeypatch.setattr(im_module.instaloader, "Instaloader", lambda *a, **k: _NoSession())
        rc = im_module.run_doctor([])
        out = capsys.readouterr().out
        assert rc >= 1
        assert "No saved session" in out

    def test_bad_target_warns_but_does_not_fail(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)

        def resolver(bot, user):
            if user == "ghost":
                raise RuntimeError("ProfileNotExistsException: not found")
            return object()

        monkeypatch.setattr(im_module, "profile_from_username_resilient", resolver)
        rc = im_module.run_doctor(["ghost"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "could not be fetched" in out

    def test_connectivity_failure_fails(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)

        def boom(bot, user):
            raise RuntimeError("429 Too Many Requests")

        monkeypatch.setattr(im_module, "profile_from_username_resilient", boom)
        rc = im_module.run_doctor([])
        out = capsys.readouterr().out
        assert rc >= 1
        assert "not reachable or blocked" in out

    # Doctor rejects an unsupported webhook provider without sending a message
    def test_invalid_webhook_provider_fails(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "unsupported", raising=False)

        rc = im_module.run_doctor([])
        out = capsys.readouterr().out
        assert rc >= 1
        assert "Webhook provider is invalid" in out

    # Doctor rejects malformed custom headers without sending a webhook
    def test_invalid_webhook_headers_fail(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {"Bad Header": "private-value"}, raising=False)

        rc = im_module.run_doctor([])
        out = capsys.readouterr().out
        assert rc >= 1
        assert "Webhook headers are invalid" in out
        assert "invalid HTTP header name" in out

    def test_cli_doctor_runs_without_targets_or_global_connectivity_gate(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: (_ for _ in ()).throw(AssertionError("global connectivity gate should be skipped")))
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets: calls.append(list(targets)) or 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        assert calls == [[]]


class TestDoctorDeliveryTests:
    # Separate default-no decisions can skip both delivery channels without sending
    def test_delivery_tests_can_be_declined_independently(self, im_module, monkeypatch):
        consent = Mock(side_effect=[False, False])
        email = Mock(side_effect=AssertionError("email sent without approval"))
        webhook = Mock(side_effect=AssertionError("webhook sent without approval"))
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "_doctor_ask_yes_no", consent)
        monkeypatch.setattr(im_module, "send_email", email)
        monkeypatch.setattr(im_module, "_doctor_send_test_webhook", webhook)
        assert im_module._doctor_offer_notification_tests(True, True) == 0
        assert consent.call_count == 2
        email.assert_not_called()
        webhook.assert_not_called()
        output = stream.getvalue()
        assert "Test email skipped" in output
        assert "Test webhook skipped" in output

    # An empty delivery answer defaults safely to no
    def test_delivery_consent_defaults_to_no(self, im_module, monkeypatch):
        prompts = []
        monkeypatch.setattr("builtins.input", lambda prompt: (prompts.append(prompt) or ""))
        assert im_module._doctor_ask_yes_no("Send one test") is False
        assert len(prompts) == 1
        assert prompts[0].endswith("Send one test [y/N]: ")

    # Separate approvals deliver one email and one webhook
    def test_delivery_tests_send_approved_messages(self, im_module, monkeypatch):
        consent = Mock(side_effect=[True, True])
        email = Mock(return_value=0)
        webhook = Mock(return_value=0)
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "_doctor_ask_yes_no", consent)
        monkeypatch.setattr(im_module, "send_email", email)
        monkeypatch.setattr(im_module, "_doctor_send_test_webhook", webhook)
        assert im_module._doctor_offer_notification_tests(True, True) == 0
        email.assert_called_once_with("instagram_monitor: doctor test email", "This test email was sent after approval in --doctor. Your SMTP delivery settings work.", "This test email was sent after approval in <b>--doctor</b>. Your SMTP delivery settings work.", im_module.SMTP_SSL, smtp_timeout=5)
        webhook.assert_called_once_with()

    # Noninteractive doctor runs never offer or send delivery tests
    def test_noninteractive_doctor_never_offers_delivery_tests(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module.sys, "stdout", Mock(isatty=lambda: False))
        monkeypatch.setattr(im_module, "_doctor_ask_yes_no", Mock(side_effect=AssertionError("consent prompt attempted")))
        monkeypatch.setattr(im_module, "send_email", Mock(side_effect=AssertionError("email attempted")))
        monkeypatch.setattr(im_module, "_doctor_send_test_webhook", Mock(side_effect=AssertionError("webhook attempted")))
        assert im_module._doctor_offer_notification_tests(True, True) == 0

    # An approved delivery failure contributes one doctor failure
    def test_approved_delivery_failure_is_counted(self, im_module, monkeypatch):
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "_doctor_ask_yes_no", Mock(return_value=True))
        monkeypatch.setattr(im_module, "send_email", Mock(return_value=1))
        assert im_module._doctor_offer_notification_tests(True, False) == 1

    # Doctor webhook delivery temporarily enables sending and restores the setting
    def test_doctor_webhook_test_restores_enabled_state(self, im_module, monkeypatch):
        delivery = Mock(return_value=0)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)
        monkeypatch.setattr(im_module, "send_webhook", delivery)
        assert im_module._doctor_send_test_webhook() == 0
        assert im_module.WEBHOOK_ENABLED is False
        delivery.assert_called_once_with("Instagram Monitor doctor test", "This test notification was sent after approval in --doctor. Your webhook delivery settings work.", color=0x7289DA, notification_type="doctor")
