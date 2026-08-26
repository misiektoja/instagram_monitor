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


def _unreachable_smtp(*args, **kwargs):
    raise AssertionError("Doctor must not open an SMTP connection when the configuration cannot deliver")


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
        assert out.splitlines()[-1] == "  the-detail"


class TestDoctorChecks:
    # Checks are data, so a caller can assert on them without parsing rendered console output
    def test_make_doctor_check_rejects_an_unknown_status(self, im_module):
        with pytest.raises(ValueError, match="Unsupported doctor status"):
            im_module.make_doctor_check("Environment", "broken", "label")

    # A configuration rejected at startup becomes a failing check carrying its fix and guide
    def test_configuration_rejection_becomes_a_failing_check(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        errors = [{"summary": "* Error loading config file 'x.conf':", "detail": "line 2: bad", "fix": "use documented settings."}]

        checks = im_module.doctor_check_configuration([], errors, ())
        failures = [check for check in checks if check.status == "fail"]

        assert len(failures) == 1
        assert failures[0].label == "Error loading config file 'x.conf'"
        assert failures[0].fix == "use documented settings."
        assert failures[0].guide == im_module.CONFIG_FILE_GUIDE_URL

    # A retired setting is a warning that still names the file and links the guide
    def test_retired_settings_become_a_warning_check(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: "im.conf")
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)

        checks = im_module.doctor_check_configuration([], (), ["DISCORD_MAX_FIELDS"])
        warnings = [check for check in checks if check.status == "warn"]

        assert len(warnings) == 1
        assert "DISCORD_MAX_FIELDS" in warnings[0].detail
        assert warnings[0].guide == im_module.CONFIG_FILE_GUIDE_URL

    # Session advice is derived from the shared fix hints so Doctor and monitoring stay consistent
    def test_session_failure_carries_the_shared_fix_hint(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "someacct", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)
        report = im_module.DoctorReport()

        class _NoSession:
            def load_session_from_file(self, username):
                raise FileNotFoundError()

        report.bot = _NoSession()
        checks = im_module.doctor_check_session(report)

        assert checks[0].status == "fail"
        assert "no saved session" in checks[0].fix
        assert checks[0].guide == im_module.SESSION_IMPORT_GUIDE_URL

    # A valid webhook configuration records readiness on the report for the later delivery offer
    def test_valid_webhook_marks_the_report_ready(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_HEADERS", {}, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.webhook_ready is True
        assert any(check.status == "ok" and "Webhook URL" in check.label for check in checks)

    # Configured SMTP credentials with placeholder addresses cannot deliver, so Doctor must not report a working setup
    def test_placeholder_email_addresses_fail_before_login(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.com", raising=False)
        monkeypatch.setattr(im_module, "SMTP_USER", "user", raising=False)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "secret", raising=False)
        monkeypatch.setattr(im_module, "SENDER_EMAIL", "your_sender_email", raising=False)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "your_receiver_email", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "", raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.smtp_ready is False
        failure = next(check for check in checks if check.status == "fail")
        assert failure.label == "Email address is not set in SENDER_EMAIL and RECEIVER_EMAIL"
        assert failure.guide == im_module.SMTP_GUIDE_URL

    # A switched-off webhook is reported as disabled, not validated, so the report matches the sibling monitors
    def test_disabled_webhook_is_not_validated(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.webhook_ready is False
        assert any(check.status == "ok" and check.label == "Webhook alerts are disabled" for check in checks)
        assert not any("look valid" in check.label for check in checks)

    # The error alert ships on, so it must not report email as enabled until an SMTP host exists
    def test_default_error_alert_alone_does_not_enable_email(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", False, raising=False)
        monkeypatch.setattr(im_module, "FOLLOWERS_NOTIFICATION", False, raising=False)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "", raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert im_module.email_notifications_enabled() is False
        assert any(check.status == "ok" and check.label == "Email notifications are disabled" for check in checks)

    # Email alerts that can fire without a usable SMTP host are a warning, not a silent pass
    def test_enabled_email_without_smtp_warns(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "", raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.smtp_ready is False
        assert any(check.status == "warn" and check.label == "Email alerts are on but SMTP is not configured" for check in checks)

    # The shipped WEBHOOK_URL placeholder means the webhook was never configured, not that it is broken
    def test_webhook_placeholder_is_not_a_failure(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "your_webhook_url", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.webhook_ready is False
        assert not any(check.status == "fail" for check in checks)
        assert any(check.status == "ok" and "Webhook alerts are disabled" in check.label for check in checks)

    # An enabled webhook still holding the placeholder is a warning about missing setup, not an invalid URL
    def test_enabled_webhook_placeholder_warns_about_setup(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "your_webhook_url", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert not any(check.status == "fail" for check in checks)
        assert any(check.status == "warn" and "WEBHOOK_URL is not set" in check.label for check in checks)

    # Every failure a user sees must offer an action, which is what the renderer guarantees
    def test_renderer_prints_an_action_for_every_failure(self, im_module, capsys, monkeypatch):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        report = im_module.DoctorReport()
        report.checks = [
            im_module.make_doctor_check("Session", "fail", "broken", "detail text", "do the thing.", "https://example.invalid/guide"),
            im_module.make_doctor_check("Targets", "ok", "fine"),
        ]

        im_module.render_doctor_report(report)
        out = capsys.readouterr().out

        assert "[FAIL] broken\n  detail text\nTo fix: do the thing.\nGuide: https://example.invalid/guide" in out
        assert "To fix:" not in out.split("[PASS] fine", 1)[1]

    # The renderer owns the 'To fix:' prefix, so a recorded action must not carry its own
    def test_recorded_config_actions_do_not_repeat_the_prefix(self, im_module, tmp_path, monkeypatch):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        config_path = tmp_path / "im.conf"
        config_path.write_text("NOT_A_REAL_SETTING = 1\n", encoding="utf-8")
        errors = []

        assert im_module.load_config_file(str(config_path), {}, error_out=errors, report_errors=False) is False
        assert errors and not errors[0]["fix"].startswith("To fix:")

        checks = im_module.doctor_check_configuration([], errors, ())
        assert not any(check.fix.startswith("To fix:") for check in checks)


class TestDoctorProgress:
    # Verifies doctor progress stops at the visible message and clears only that width
    def test_uses_visible_message_width(self, im_module, monkeypatch):
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        im_module._doctor_progress.width = 0
        im_module._doctor_progress("Checking authentication")
        line = "Checking authentication ..."
        assert stream.getvalue() == "\r" + line
        im_module._doctor_progress_clear()
        assert stream.getvalue() == "\r" + line + "\r" + (" " * len(line)) + "\r"

    # Verifies a shorter progress message fully erases the longer one it replaces
    def test_erases_previous_longer_message(self, im_module, monkeypatch):
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        im_module._doctor_progress.width = 0
        im_module._doctor_progress("Contacting Instagram")
        first = "Contacting Instagram ..."
        im_module._doctor_progress("Looking up 'testuser'")
        second = "Looking up 'testuser' ..."
        expected = "\r" + first + "\r" + (" " * len(first)) + "\r" + "\r" + second
        assert stream.getvalue() == expected


class TestRunDoctor:
    # Exported secrets are a documented alternative to a dotenv file, so they must apply when no file is loaded
    def test_environment_secrets_apply_without_a_dotenv_file(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda *args, **kwargs: 0)
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", "", raising=False)
        monkeypatch.setenv("NTFY_ACCESS_TOKEN", "tk_from_environment")

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert im_module.NTFY_ACCESS_TOKEN == "tk_from_environment"

    # Each secret is attributed to the source it actually came from, so the report can name the dotenv path
    def test_secret_sources_split_by_origin(self, im_module, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("SMTP_PASSWORD=from-file\n", encoding="utf-8")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "from-file", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/topic", raising=False)
        monkeypatch.setattr(im_module, "PROXY_URL", "your_proxy_url", raising=False)
        monkeypatch.setenv("WEBHOOK_URL", "https://ntfy.sh/topic")

        from_file, from_environment, from_settings = im_module.doctor_secret_sources(str(env_file))

        assert from_file == ["SMTP_PASSWORD"]
        assert from_environment == ["WEBHOOK_URL"]
        assert "PROXY_URL" not in from_file + from_environment + from_settings

    # Verifies the preflight notice reaches the user before any check runs
    def test_preflight_notice_precedes_the_report(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)

        im_module.run_doctor([])

        out = capsys.readouterr().out
        assert "Running preflight checks. No files will be written. Interactive email and webhook tests run only after separate approval." in out
        assert out.index("Running preflight checks.") < out.index("Doctor")

    # Verifies Chromium dependency guidance explicitly preserves Firefox import support
    def test_browser_dependency_scope_is_explicit(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr("importlib.util.find_spec", lambda name: object())

        im_module.run_doctor([])

        out = capsys.readouterr().out
        assert "Optional dependency pycookiecheat is installed\n  Used only for importing sessions from Chromium-based browsers. Firefox session import does not need it" in out

    # Verifies Doctor checks and displays the final target-specific log filename
    def test_log_destination_uses_final_target_path(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        writable = Mock(return_value=True)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", False, raising=False)
        monkeypatch.setattr(im_module, "INSTA_LOGFILE", "instagram_monitor", raising=False)
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "", raising=False)
        monkeypatch.setitem(im_module.DASHBOARD_DATA, "targets_list", ["friend"])
        monkeypatch.setattr(im_module, "output_destination_is_writable", writable)

        im_module.run_doctor(["friend"])

        out = capsys.readouterr().out
        assert "Log destination for 'friend' appears writable\n  Path: instagram_monitor_friend.log" in out
        writable.assert_called_once_with("instagram_monitor_friend.log")

    def test_all_pass_no_login_returns_zero(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        rc = im_module.run_doctor([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Instagram reachable" in out
        assert "No-login mode" in out
        assert "ASCII_LOG_SEPARATORS resolves" not in out

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

    # Doctor warns when webhook alerts are on but no alert type can ever fire, and offers no delivery test
    def test_webhook_without_alert_types_warns(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/token", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord", raising=False)
        for setting in ("WEBHOOK_STATUS_NOTIFICATION", "WEBHOOK_FOLLOWERS_NOTIFICATION", "WEBHOOK_ERROR_NOTIFICATION"):
            monkeypatch.setattr(im_module, setting, False, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert any(check.status == "warn" and check.label == "Webhook alerts are on but no alert types are selected" for check in checks)
        assert report.webhook_ready is False

    # Doctor reports one fully validated webhook under the label shared with the sibling monitors
    def test_valid_webhook_reports_the_shared_ready_label(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/token", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert any(check.status == "ok" and check.label == f"{im_module.WEBHOOK_READY_CHECK_LABEL} for Discord" for check in checks)
        assert report.webhook_ready is True

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
        clear_mock = Mock()
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: (_ for _ in ()).throw(AssertionError("global connectivity gate should be skipped")))
        monkeypatch.setattr(im_module, "clear_screen", clear_mock)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, *doctor_findings: calls.append(list(targets)) or 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        assert calls == [[]]
        clear_mock.assert_called_once_with(False)

    # Doctor receives the autodetected provider after runtime options are applied
    def test_cli_doctor_autodetects_ntfy_provider(self, im_module, monkeypatch):
        providers = []
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--webhook-url", "https://ntfy.sh/private-topic", "--no-color"])
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, *doctor_findings: providers.append(im_module.WEBHOOK_PROVIDER) or 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        assert providers == ["ntfy"]

    def test_cli_doctor_success_prints_monitoring_command(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, *doctor_findings: 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        output = capsys.readouterr().out
        assert "After Doctor passes, start monitoring:" in output
        assert "target.user --env-file none" in output
        assert "--doctor" not in output.split("After Doctor passes, start monitoring:", 1)[1]

    # Doctor exists to explain a broken setup, so a rejected config must reach it instead of exiting first
    def test_cli_doctor_reports_a_rejected_config_instead_of_exiting(self, im_module, monkeypatch, tmp_path):
        config_path = tmp_path / "instagram_monitor.conf"
        config_path.write_text("INSTA_CHECK_INTERVAL = 5400\nNOT_A_REAL_SETTING = 1\n", encoding="utf-8")
        received = {}
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--config-file", str(config_path), "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, errors=(), retired=(), env_path=None: received.update(errors=list(errors), retired=list(retired)) or len(errors))

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 1
        assert len(received["errors"]) == 1
        assert "NOT_A_REAL_SETTING" in received["errors"][0]["summary"]

    # A setting a later release removed is a warning Doctor reports, not a reason to reject the file
    def test_cli_doctor_reports_retired_settings_as_a_warning(self, im_module, monkeypatch, tmp_path):
        config_path = tmp_path / "instagram_monitor.conf"
        config_path.write_text("INSTA_CHECK_INTERVAL = 5400\nDISCORD_MAX_FIELDS = 25\n", encoding="utf-8")
        received = {}
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--config-file", str(config_path), "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, errors=(), retired=(), env_path=None: received.update(errors=list(errors), retired=list(retired)) or 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        assert received["errors"] == []
        assert received["retired"] == ["DISCORD_MAX_FIELDS"]

    def test_cli_doctor_failure_does_not_print_monitoring_command(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, *doctor_findings: 1)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 1
        assert "After Doctor passes, start monitoring:" not in capsys.readouterr().out


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
        delivery.assert_called_once_with("Instagram Monitor doctor test", "This test notification was sent after approval in --doctor. Your webhook delivery settings work.", color=0x7289DA, notification_type=im_module.WEBHOOK_TEST_NOTIFICATION_TYPE)
