"""Tests for the --doctor preflight checks (no real network)."""

import ast
import inspect
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
    @pytest.mark.parametrize("status", ["PASS", "WARN", "FAIL", "SKIP"])
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

    # An explicitly selected missing dotenv file is reported as missing rather than loaded
    def test_a_missing_dotenv_file_is_a_warning(self, im_module, tmp_path):
        missing = tmp_path / "missing.env"

        checks = im_module.doctor_check_configuration([], env_path=str(missing))
        missing_check = next(check for check in checks if check.label == "The requested dotenv file was not found")

        assert missing_check.status == "WARN"
        assert missing_check.detail == f"Path: {missing}"
        assert "--env-file" in missing_check.fix
        assert missing_check.guide == im_module.SECRETS_GUIDE_URL
        assert not any(check.label == "Dotenv file loaded" for check in checks)

    # A dotenv file that exists is named as loaded
    def test_an_existing_dotenv_file_is_named(self, im_module, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("", encoding="utf-8")

        checks = im_module.doctor_check_configuration([], env_path=str(env_path))

        assert any(check.label == "Dotenv file loaded" and check.detail == f"Path: {env_path}" and check.status == "PASS" for check in checks)

    # A configuration rejected at startup becomes a failing check carrying its fix and guide
    def test_configuration_rejection_becomes_a_failing_check(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        errors = [{"summary": "* Error loading config file 'x.conf':", "detail": "line 2: bad", "fix": "use documented settings."}]

        checks = im_module.doctor_check_configuration([], errors, ())
        failures = [check for check in checks if check.status == "FAIL"]

        assert len(failures) == 1
        assert failures[0].label == "Error loading config file 'x.conf'"
        assert failures[0].fix == "use documented settings."
        assert failures[0].guide == im_module.CONFIG_FILE_GUIDE_URL

    # A retired setting is a warning that still names the file and links the guide
    def test_retired_settings_become_a_warning_check(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: "im.conf")
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)

        checks = im_module.doctor_check_configuration([], (), ["DISCORD_MAX_FIELDS"])
        warnings = [check for check in checks if check.status == "WARN"]

        assert len(warnings) == 1
        assert "DISCORD_MAX_FIELDS" in warnings[0].detail
        assert warnings[0].guide == im_module.CONFIG_FILE_GUIDE_URL

    # Doctor resolves an automatic timezone instead of reporting the literal Auto value
    def test_automatic_timezone_is_resolved(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "Auto", raising=False)
        monkeypatch.setattr(im_module, "get_localzone", Mock(return_value="Europe/Warsaw"), raising=False)
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE_STATE", "config", raising=False)

        checks = im_module.doctor_check_configuration([], timezone_advice=im_module.resolve_local_timezone())

        assert ("PASS", "Local timezone can be detected", "Time zone: Europe/Warsaw") in {(check.status, check.label, check.detail) for check in checks}

    # Every unusable timing or count setting is named in one row, so a fix does not need one run per setting
    def test_invalid_numeric_settings_are_reported_in_one_row(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 0, raising=False)
        monkeypatch.setattr(im_module, "MAX_H1", 24, raising=False)
        monkeypatch.setattr(im_module, "SMTP_PORT", 70000, raising=False)

        rows = [item for item in im_module.doctor_check_configuration([]) if item.label == "One or more numeric settings are invalid"]

        assert [item.status for item in rows] == ["FAIL"]
        assert all(name in rows[0].detail for name in ("INSTA_CHECK_INTERVAL", "MAX_H1", "SMTP_PORT"))

    # An interval below the documented minimum makes a challenge far more likely, which looks like the tool being broken
    def test_a_rate_limiting_interval_is_warned_about(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 60, raising=False)

        rows = [item for item in im_module.doctor_check_configuration([]) if item.label == "Check intervals are short"]

        assert [item.status for item in rows] == ["WARN"]
        assert str(im_module.DOCTOR_MIN_SAFE_CHECK_INTERVAL) in rows[0].fix

    # The default interval is safe, so the row must stay away rather than warning about every run
    def test_a_safe_interval_is_not_warned_about(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", im_module.DOCTOR_MIN_SAFE_CHECK_INTERVAL, raising=False)

        assert not [item for item in im_module.doctor_check_configuration([]) if item.label == "Check intervals are short"]

    # Without tzlocal an automatic timezone cannot be resolved, so Doctor names the missing package
    def test_automatic_timezone_without_tzlocal_fails(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "Auto", raising=False)
        monkeypatch.setattr(im_module, "get_localzone", None, raising=False)
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE_STATE", "config", raising=False)

        checks = im_module.doctor_check_configuration([], timezone_advice=im_module.resolve_local_timezone())
        check = next(item for item in checks if item.label == "Automatic timezone detection is unavailable")

        assert check.status == "FAIL"
        assert "tzlocal" in check.fix
        assert check.guide == im_module.CONFIG_FILE_GUIDE_URL

    # An unusable timezone name is reported before monitoring rather than at the first timestamp
    def test_invalid_timezone_fails(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "Europe/Nowhere", raising=False)
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE_STATE", "config", raising=False)

        checks = im_module.doctor_check_configuration([], timezone_advice=im_module.resolve_local_timezone())
        check = next(item for item in checks if item.label == "Local timezone is invalid")

        assert check.status == "FAIL"
        assert check.detail == "Time zone: Europe/Nowhere"
        assert check.fix == "Set LOCAL_TIMEZONE to a valid pytz timezone"

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

        assert checks[0].status == "FAIL"
        assert "No saved session" in checks[0].fix
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
        assert any(check.status == "PASS" and "Webhook URL" in check.label for check in checks)

    # Configured SMTP credentials with placeholder addresses cannot deliver, so Doctor must not report a working setup
    def test_placeholder_email_addresses_fail_before_login(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.com", raising=False)
        monkeypatch.setattr(im_module, "SMTP_USER", "user", raising=False)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "secret", raising=False)
        # Set here rather than inherited, since the check only reaches the address test while an email alert can fire
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "SENDER_EMAIL", "your_sender_email", raising=False)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "your_receiver_email", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "", raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.smtp_ready is False
        warning = next(check for check in checks if check.status == "WARN")
        assert warning.label == im_module.EMAIL_UNUSABLE_CHECK_LABEL
        assert warning.detail == "SENDER_EMAIL or RECEIVER_EMAIL is not an email address"
        assert warning.fix == "Correct SENDER_EMAIL and RECEIVER_EMAIL or turn the email alerts off"
        assert warning.guide == im_module.SMTP_GUIDE_URL

    # A switched-off webhook is reported as disabled, not validated, so the report matches the sibling monitors
    def test_disabled_webhook_is_not_validated(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/private-topic", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.webhook_ready is False
        assert any(check.status == "PASS" and check.label == "Webhook alerts are disabled" for check in checks)
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
        assert any(check.status == "PASS" and check.label == "Email notifications are disabled" for check in checks)

    # Email alerts that can fire without a usable SMTP host are a warning, not a silent pass
    def test_enabled_email_without_smtp_warns(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "", raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.smtp_ready is False
        warning = next(check for check in checks if check.status == "WARN")
        assert warning.label == im_module.EMAIL_UNUSABLE_CHECK_LABEL
        assert warning.detail == "SMTP_HOST, SMTP_USER or SMTP_PASSWORD is empty or still set to its placeholder"
        assert warning.fix == "Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD or turn the email alerts off"
        assert warning.guide == im_module.SMTP_GUIDE_URL

    # The row names only the settings that are actually unset, not every setting it checked
    def test_the_unusable_email_row_names_only_the_unset_settings(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.test", raising=False)
        monkeypatch.setattr(im_module, "SMTP_USER", "monitor@example.invalid", raising=False)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "your_smtp_password", raising=False)
        monkeypatch.setattr(im_module, "SENDER_EMAIL", "monitor@example.invalid", raising=False)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "owner@example.invalid", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "", raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)

        checks = im_module.doctor_check_notifications(im_module.DoctorReport())

        warning = next(check for check in checks if check.status == "WARN")
        assert warning.label == im_module.EMAIL_UNUSABLE_CHECK_LABEL
        assert warning.detail == "SMTP_PASSWORD is empty or still set to its placeholder"
        assert warning.fix == "Set SMTP_PASSWORD or turn the email alerts off"

    # The shipped WEBHOOK_URL placeholder means the webhook was never configured, not that it is broken
    def test_webhook_placeholder_is_not_a_failure(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "your_webhook_url", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert report.webhook_ready is False
        assert not any(check.status == "FAIL" for check in checks)
        assert any(check.status == "PASS" and "Webhook alerts are disabled" in check.label for check in checks)

    # An enabled webhook still holding the placeholder can never deliver, so it fails rather than warns
    def test_enabled_webhook_placeholder_fails_about_setup(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "your_webhook_url", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert any(check.status == "FAIL" and "WEBHOOK_URL is not set" in check.label for check in checks)

    # Every failure a user sees must offer an action, which is what the renderer guarantees
    def test_renderer_prints_an_action_for_every_failure(self, im_module, capsys, monkeypatch):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        report = im_module.DoctorReport()
        report.checks = [
            im_module.make_doctor_check("Session", "FAIL", "broken", "detail text", "do the thing.", "https://example.invalid/guide"),
            im_module.make_doctor_check("Targets", "PASS", "fine"),
        ]

        im_module.render_doctor_sections(report)
        out = capsys.readouterr().out

        assert "[FAIL] broken\n  detail text\n  To fix: do the thing.\n  Guide: https://example.invalid/guide" in out
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


    # The renderer owns the 'To fix:' prefix, so a missing config file must record the bare action
    def test_missing_config_file_action_does_not_repeat_the_prefix(self, im_module, monkeypatch, tmp_path):
        recorded = {}

        def _capture(targets, config_errors=(), retired_settings=(), env_path=None, timezone_advice=None):
            recorded["errors"] = list(config_errors)
            return 0

        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--config-file", str(tmp_path / "missing.conf"), "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", _capture)

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert recorded["errors"] and not recorded["errors"][0]["fix"].startswith("To fix:")

    # Every action reads as one capitalised instruction with no trailing period, matching the sibling monitors
    def test_doctor_actions_use_the_shared_sentence_style(self, im_module):
        actions = [node.args[4] for node in ast.walk(ast.parse(inspect.getsource(im_module))) if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "make_doctor_check" and len(node.args) >= 5]
        checked = 0
        for action in actions:
            parts = action.values if isinstance(action, ast.JoinedStr) else [action]
            head, tail = parts[0], parts[-1]
            if isinstance(head, ast.Constant) and isinstance(head.value, str) and head.value:
                checked += 1
                assert head.value[0].isupper(), f"line {action.lineno}: {head.value}"
            if isinstance(tail, ast.Constant) and isinstance(tail.value, str) and tail.value:
                assert not tail.value.endswith("."), f"line {action.lineno}: {tail.value}"
        assert checked > 10


class TestDoctorProgress:
    # Verifies doctor progress stops at the visible message and clears only that width
    def test_uses_visible_message_width(self, im_module, monkeypatch):
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        im_module._doctor_progress.width = 0
        im_module._doctor_progress("authentication")
        line = "* Checking authentication ..."
        assert stream.getvalue() == "\r" + line
        im_module._doctor_progress_clear()
        assert stream.getvalue() == "\r" + line + "\r" + (" " * len(line)) + "\r"

    # Verifies a shorter progress message fully erases the longer one it replaces
    def test_erases_previous_longer_message(self, im_module, monkeypatch):
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        im_module._doctor_progress.width = 0
        im_module._doctor_progress("the monitored profile 'testuser'")
        first = "* Checking the monitored profile 'testuser' ..."
        im_module._doctor_progress("connectivity")
        second = "* Checking connectivity ..."
        expected = "\r" + first + "\r" + (" " * len(first)) + "\r" + "\r" + second
        assert stream.getvalue() == expected


class TestRunDoctor:
    # The install method is context rather than a check, so it is stated once instead of taking a result row
    def test_the_install_method_is_stated_without_a_marker(self, im_module, capsys):
        checks = im_module.doctor_check_environment((3, 12, 1), lambda _name: object())
        im_module.render_doctor_sections(im_module.DoctorReport(checks=checks))

        output = capsys.readouterr().out
        assert not any(check.label.startswith("Install method") for check in checks)
        assert f"Doctor\nDetected install method: {im_module._wizard_install_method()}\n" in output

    # Every file monitoring would write is named, so a disabled destination is stated rather than left out
    def test_disabled_output_destinations_are_stated(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "CSV_FILE", "")
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True)

        checks = im_module.doctor_check_configuration([])

        rows = {(check.status, check.label, check.detail) for check in checks}
        # The labels say everything, so neither row carries a detail that only repeats them
        assert ("PASS", "CSV logging is disabled", "") in rows
        assert ("PASS", "Output logging is disabled", "") in rows

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

    # Exported values win over duplicate dotenv keys and retain their effective source
    def test_environment_secret_wins_over_duplicate_dotenv_key(self, im_module, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("NTFY_ACCESS_TOKEN=tk_from_file\n", encoding="utf-8")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--env-file", str(env_file), "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda *args, **kwargs: 0)
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", "", raising=False)
        monkeypatch.setattr(im_module, "SECRET_SOURCES", {}, raising=False)
        monkeypatch.setenv("NTFY_ACCESS_TOKEN", "tk_from_environment")

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert im_module.NTFY_ACCESS_TOKEN == "tk_from_environment"
        assert im_module.SECRET_SOURCES["NTFY_ACCESS_TOKEN"] == "environment"

    # Each secret is attributed to the source it actually came from, so the report can name the dotenv path
    def test_secret_sources_split_by_origin(self, im_module, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("SMTP_PASSWORD=from-file\n", encoding="utf-8")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "from-file", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.sh/topic", raising=False)
        monkeypatch.setattr(im_module, "PROXY_URL", "your_proxy_url", raising=False)
        monkeypatch.setattr(im_module, "SECRET_SOURCES", {"SMTP_PASSWORD": "dotenv file", "WEBHOOK_URL": "environment"}, raising=False)

        from_file, from_environment, from_settings, from_command_line = im_module.doctor_secret_sources(str(env_file))

        assert from_file == ["SMTP_PASSWORD"]
        assert from_environment == ["WEBHOOK_URL"]
        assert "PROXY_URL" not in from_file + from_environment + from_settings + from_command_line

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

    # Verifies a warning about a library that cannot affect this machine is not shown at all
    @pytest.mark.parametrize("system, reported", [("Windows", True), ("Linux", False), ("Darwin", False)])
    def test_a_platform_specific_dependency_is_only_reported_where_it_applies(self, im_module, monkeypatch, system, reported):
        monkeypatch.setattr(im_module.platform, "system", lambda: system)

        checks = im_module.doctor_check_environment((3, 12, 1), lambda _name: None)

        assert any("colorama" in check.label for check in checks) is reported

    # Verifies the Windows colour library is reported there, so broken colours on that platform have a diagnostic
    def test_missing_colorama_is_reported_on_windows(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.platform, "system", lambda: "Windows")

        checks = im_module.doctor_check_environment((3, 12, 1), lambda name: None if name == "colorama" else object())

        missing = next(check for check in checks if "colorama" in check.label)
        assert missing.status == "WARN"
        assert "Coloured output may not render in the classic Windows Command Prompt" in missing.detail
        assert "Windows Terminal needs nothing extra" in missing.detail
        assert 'pip3 install "colorama"' in missing.fix

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

    def test_bad_target_fails(self, im_module, monkeypatch, capsys):
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
        assert rc == 1
        assert "[FAIL] Target 'ghost' could not be fetched" in out

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

        assert any(check.status == "WARN" and check.label == "Webhook alerts are on but no alert types are selected" for check in checks)
        assert report.webhook_ready is False

    # Webhook alert types selected while the channel is off warn, since nothing would ever be delivered
    def test_webhook_alerts_selected_but_switched_off_warn(self, im_module, monkeypatch):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_STATUS_NOTIFICATION", True, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        webhook = checks[-1]
        assert (webhook.status, webhook.label) == ("WARN", "Webhook alert types are selected but webhooks are switched off")
        assert "WEBHOOK_ENABLED" in webhook.fix
        assert report.webhook_ready is False

    # Configured mail settings with no alert types selected warn, since nothing would ever be emailed
    def test_email_configured_but_nothing_selected_warns(self, im_module, monkeypatch):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        for setting in ("STATUS_NOTIFICATION", "FOLLOWERS_NOTIFICATION", "ERROR_NOTIFICATION"):
            monkeypatch.setattr(im_module, setting, False, raising=False)
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.test")
        monkeypatch.setattr(im_module, "SMTP_USER", "monitor")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "private-password")
        monkeypatch.setattr(im_module, "SENDER_EMAIL", "monitor@example.test")
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "alerts@example.test")
        monkeypatch.setattr(im_module.smtplib, "SMTP", Mock(side_effect=AssertionError("SMTP was contacted")))
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        email = checks[0]
        assert (email.status, email.label) == ("WARN", "Email is configured but no alert types are selected")
        assert email.fix == "Turn on at least one email alert in the configuration file"
        assert report.smtp_ready is False

    # Doctor reports one fully validated webhook under the label shared with the sibling monitors
    def test_valid_webhook_reports_the_shared_ready_label(self, im_module, monkeypatch, capsys):
        _setup_no_network(monkeypatch, im_module)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/token", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True, raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        assert any(check.status == "PASS" and check.label == f"{im_module.WEBHOOK_READY_CHECK_LABEL} for Discord" for check in checks)
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

    # The report ends with the next action in every sibling, so it ends with one here too
    def test_cli_doctor_ends_with_the_monitoring_command(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, *doctor_findings: 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        output = capsys.readouterr().out
        assert "Next steps" in output
        assert "Start monitoring:" in output

    # The monitoring command needs a target, so it carries one the config will not supply and drops one it does
    def test_the_monitoring_command_leaves_out_targets_the_config_supplies(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)

        im_module.print_doctor_next_steps(["target.user"], None, None, ["target.user"])
        saved_output = capsys.readouterr().out
        im_module.print_doctor_next_steps([], None, None, [])
        unsaved_output = capsys.readouterr().out
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True)
        im_module.print_doctor_next_steps([], None, None, [])
        dashboard_output = capsys.readouterr().out

        assert "target.user" not in saved_output
        assert "<target_insta_user>" not in saved_output
        assert "<target_insta_user>" in unsaved_output
        # The dashboard can add a target after startup, so the command stays complete without one
        assert "<target_insta_user>" not in dashboard_output

    # Both sentinels belong in the printed command, so the retest monitors with the setup doctor just checked
    def test_cli_doctor_carries_both_disabled_searches_into_the_monitoring_command(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--config-file", "none", "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, *doctor_findings: 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        assert "--config-file none --env-file none" in capsys.readouterr().out

    # Doctor exists to explain a broken setup, so a rejected config must reach it instead of exiting first
    def test_cli_doctor_reports_a_rejected_config_instead_of_exiting(self, im_module, monkeypatch, tmp_path):
        config_path = tmp_path / "instagram_monitor.conf"
        config_path.write_text("INSTA_CHECK_INTERVAL = 5400\nNOT_A_REAL_SETTING = 1\n", encoding="utf-8")
        received = {}
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--config-file", str(config_path), "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, errors=(), retired=(), env_path=None, timezone_advice=None: received.update(errors=list(errors), retired=list(retired)) or len(errors))

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
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, errors=(), retired=(), env_path=None, timezone_advice=None: received.update(errors=list(errors), retired=list(retired)) or 0)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 0
        assert received["errors"] == []
        assert received["retired"] == ["DISCORD_MAX_FIELDS"]

    # A failing report still names the command, labelled so the failures are fixed first
    def test_cli_doctor_failure_asks_for_the_failures_first(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--doctor", "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda targets, *doctor_findings: 1)

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 1
        assert "After Doctor passes, start monitoring:" in capsys.readouterr().out


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
        report = im_module.DoctorReport(smtp_ready=True, webhook_ready=True)
        im_module._doctor_offer_notification_tests(report)
        assert report.count("FAIL") == 0
        assert consent.call_count == 2
        email.assert_not_called()
        webhook.assert_not_called()
        output = stream.getvalue()
        assert "Test email was not sent" in output
        assert f"Test webhook through {im_module.webhook_provider_display_name()} was not sent" in output

    # The delivery rows print the same label and detail the sibling tools print
    def test_the_delivery_rows_print_the_shared_label_and_detail(self, im_module, monkeypatch):
        consent = Mock(side_effect=[True, False])
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "_doctor_ask_yes_no", consent)
        monkeypatch.setattr(im_module, "send_email", Mock(return_value=0))
        monkeypatch.setattr(im_module, "_doctor_send_test_webhook", Mock(side_effect=AssertionError("webhook sent without approval")))
        report = im_module.DoctorReport(smtp_ready=True, webhook_ready=True)

        im_module._doctor_offer_notification_tests(report)
        output = stream.getvalue()
        provider = im_module.webhook_provider_display_name()

        assert "Optional delivery tests" in output
        assert "Doctor test email delivered" in output
        assert "One real test email was sent after confirmation" in output
        assert f"Test webhook through {provider} was not sent" in output
        assert "You declined the real delivery test. Run doctor again and approve the webhook test when ready" in output


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
        report = im_module.DoctorReport(smtp_ready=True, webhook_ready=True)
        im_module._doctor_offer_notification_tests(report)
        assert report.count("FAIL") == 0
        email.assert_called_once_with("instagram_monitor: doctor test email", "This test email was sent after approval in --doctor. Your SMTP delivery settings work.", "This test email was sent after approval in <b>--doctor</b>. Your SMTP delivery settings work.", im_module.SMTP_SSL, smtp_timeout=5)
        webhook.assert_called_once_with()

    # Noninteractive doctor runs never offer or send delivery tests
    def test_noninteractive_doctor_never_offers_delivery_tests(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module.sys, "stdout", Mock(isatty=lambda: False))
        monkeypatch.setattr(im_module, "_doctor_ask_yes_no", Mock(side_effect=AssertionError("consent prompt attempted")))
        monkeypatch.setattr(im_module, "send_email", Mock(side_effect=AssertionError("email attempted")))
        monkeypatch.setattr(im_module, "_doctor_send_test_webhook", Mock(side_effect=AssertionError("webhook attempted")))
        report = im_module.DoctorReport(smtp_ready=True, webhook_ready=True)
        im_module._doctor_offer_notification_tests(report)
        assert report.checks == []

    # An approved delivery failure contributes one doctor failure
    def test_approved_delivery_failure_is_counted(self, im_module, monkeypatch):
        stream = _TTYBuffer()
        monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
        monkeypatch.setattr(im_module.sys, "stdout", stream)
        monkeypatch.setattr(im_module, "_doctor_ask_yes_no", Mock(return_value=True))
        monkeypatch.setattr(im_module, "send_email", Mock(return_value=1))
        report = im_module.DoctorReport(smtp_ready=True)
        im_module._doctor_offer_notification_tests(report)
        assert report.count("FAIL") == 1

    # Doctor webhook delivery temporarily enables sending and restores the setting
    def test_doctor_webhook_test_restores_enabled_state(self, im_module, monkeypatch):
        delivery = Mock(return_value=0)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)
        monkeypatch.setattr(im_module, "send_webhook", delivery)
        assert im_module._doctor_send_test_webhook() == 0
        assert im_module.WEBHOOK_ENABLED is False
        delivery.assert_called_once_with("instagram_monitor: doctor test webhook", "This test notification was sent after approval in --doctor. Your webhook delivery settings work.", color=0x7289DA, notification_type=im_module.WEBHOOK_TEST_NOTIFICATION_TYPE)


# Verifies a secret passed as an argument is reported under the command line rather than the configuration file
def test_a_command_line_secret_is_reported_as_such(im_module, monkeypatch):
    for name in im_module.SECRET_KEYS:
        monkeypatch.setattr(im_module, name, "your_placeholder", raising=False)
    monkeypatch.setattr(im_module, "SECRET_SOURCES", {"SMTP_PASSWORD": "command line"}, raising=False)
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "a-real-secret-value", raising=False)

    labels = [check.label for check in im_module.doctor_secret_checks(None)]

    assert "Secrets loaded from the command line" in labels
    assert "Secrets loaded from the configuration file or command line" not in labels



class TestPythonRow:
    # The row states the minimum it was judged against, whichever way the judgement went
    def test_the_python_row_names_the_minimum_supported_version(self, im_module):
        below = (im_module.MINIMUM_PYTHON_VERSION[0], im_module.MINIMUM_PYTHON_VERSION[1] - 1, 0)
        minimum = ".".join(str(part) for part in im_module.MINIMUM_PYTHON_VERSION)

        supported = im_module.doctor_check_environment((3, 12, 1), lambda _name: object())[0]
        unsupported = im_module.doctor_check_environment(below, lambda _name: object())[0]

        assert supported.status == "PASS"
        assert supported.detail == f"Minimum supported version: {minimum}"
        assert unsupported.status == "FAIL"
        assert unsupported.detail == supported.detail


# Verifies every doctor detail keeps to the agreed shapes: it never repeats its label, gives an instruction or joins values with a pipe
def test_doctor_details_keep_to_the_agreed_shapes(im_module):
    import ast
    import inspect

    # Renders one detail argument as text, standing in {} for the parts an f-string fills at runtime
    def detail_text(node):
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.JoinedStr):
            return "".join(part.value if isinstance(part, ast.Constant) else "{}" for part in node.values)
        return None

    offenders = []
    for node in ast.walk(ast.parse(inspect.getsource(im_module))):
        if not isinstance(node, ast.Call) or ast.unparse(node.func) not in {"make_doctor_check", "report.add"} or len(node.args) < 4:
            continue
        label, text = node.args[2], detail_text(node.args[3])
        if text is None:
            continue
        if isinstance(label, ast.Constant) and text == label.value:
            offenders.append(f"{node.lineno}: the detail repeats its label")
        if text.startswith(("Use ", "Set ", "Run ")):
            offenders.append(f"{node.lineno}: the detail gives an instruction, which belongs in the fix line")
        if " | " in text:
            offenders.append(f"{node.lineno}: the detail joins two values with a pipe")
        if text.endswith("."):
            offenders.append(f"{node.lineno}: the detail ends with a full stop")

    assert not offenders, "doctor details outside the agreed shapes:\n" + "\n".join(offenders)


# Verifies the constructor drops a detail that only repeats its label, so no row says the same thing twice
def test_a_detail_that_repeats_its_label_is_dropped(im_module):
    check = im_module.make_doctor_check("Configuration", "PASS", "Output logging is disabled", "Output logging is disabled")

    assert check.detail == ""


# Verifies only the four shared markers can reach a report, so the neutral fifth cannot come back
def test_an_actionable_row_is_rejected_without_a_fix(im_module):
    for status in ("WARN", "FAIL"):
        with pytest.raises(ValueError):
            im_module.make_doctor_check("Configuration", status, "a label", "some detail")

    assert im_module.make_doctor_check("Configuration", "SKIP", "a label").status == "SKIP"


# Verifies only the four shared markers can reach a report
def test_only_the_four_shared_markers_are_accepted(im_module):
    assert im_module.DOCTOR_STATUSES == ("PASS", "WARN", "FAIL", "SKIP")
    assert [im_module.make_doctor_check("Configuration", status, "a label", "", "do the thing").status for status in im_module.DOCTOR_STATUSES] == list(im_module.DOCTOR_STATUSES)
    assert set(im_module.DOCTOR_MARK_STYLES) == set(im_module.DOCTOR_STATUSES)

    with pytest.raises(ValueError):
        im_module.make_doctor_check("Configuration", "info", "a label")


# Verifies one row reads as one block: the action lines sit under the marker at the detail indent while a pass row has none
def test_the_action_lines_sit_indented_under_their_marker(im_module, capsys, monkeypatch):
    monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
    report = im_module.DoctorReport()
    report.checks = [
        im_module.make_doctor_check("Configuration", "WARN", "a warning row", "a detail worth keeping", "do the thing", im_module.DOCTOR_GUIDE_URL),
        im_module.make_doctor_check("Configuration", "PASS", "a passing row"),
    ]

    im_module.render_doctor_sections(report)
    lines = capsys.readouterr().out.splitlines()
    rows = lines[lines.index("[WARN] a warning row"):]

    assert rows[:5] == ["[WARN] a warning row", "  a detail worth keeping", "  To fix: do the thing", f"  Guide: {im_module.DOCTOR_GUIDE_URL}", "[PASS] a passing row"]


# Verifies a link in a detail line takes the link colour while a styled action line keeps its own colour
def test_a_link_in_a_detail_line_is_coloured_as_a_link(im_module, capsys, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {name: im_module._build_ansi_sequence(value) for name, value in im_module.DEFAULT_COLOR_THEME.items() if im_module._build_ansi_sequence(value)})
    report = im_module.DoctorReport()
    report.checks = [
        im_module.make_doctor_check("Connectivity", "PASS", "The connectivity endpoint is reachable", "Endpoint: https://www.instagram.com/"),
        im_module.make_doctor_check("Session", "FAIL", "The session did not validate", "", "Sign in again at https://www.instagram.com/", im_module.DOCTOR_GUIDE_URL),
    ]

    im_module.render_doctor_sections(report)
    rendered = capsys.readouterr().out
    fix_line = next(line for line in rendered.splitlines() if "To fix:" in line)

    assert f"  Endpoint: {im_module.colorize('link', 'https://www.instagram.com/')}" in rendered
    assert fix_line == f"  {im_module.colorize('info', 'To fix: Sign in again at https://www.instagram.com/')}"

# Verifies the follow analysis states its findings as plain value rows rather than borrowing a doctor marker
def test_the_follow_analysis_states_values_without_a_marker(im_module, capsys):
    im_module._report_value_line("Followers: 42")

    assert capsys.readouterr().out == "* Followers: 42\n"


# Verifies an approved delivery test that failed reaches the summary, so a failing run cannot report a clean one
def test_a_failed_delivery_test_reaches_the_summary(im_module, monkeypatch):
    monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr(im_module.sys, "stdout", _TTYBuffer())
    monkeypatch.setattr(im_module, "_doctor_ask_yes_no", Mock(return_value=True))
    monkeypatch.setattr(im_module, "send_email", Mock(return_value=1))
    report = im_module.DoctorReport(smtp_ready=True)

    im_module._doctor_offer_notification_tests(report)

    assert [(check.section, check.status, check.label) for check in report.checks] == [(im_module.DOCTOR_DELIVERY_SECTION, "FAIL", "Doctor test email delivery failed")]
    assert report.count("FAIL") == 1


# Verifies every doctor entry point renders its summary after the delivery tests, so the sentence and the exit code describe one run
def test_the_summary_is_rendered_after_the_delivery_tests(im_module):
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(im_module))
    checked = 0
    for function in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
        calls = [(call.lineno, ast.unparse(call.func)) for call in ast.walk(function) if isinstance(call, ast.Call)]
        offers = [lineno for lineno, name in calls if name.endswith("_doctor_offer_notification_tests")]
        summaries = [lineno for lineno, name in calls if name.endswith("render_doctor_summary")]
        if not offers or not summaries:
            continue
        checked += 1
        assert max(offers) < min(summaries), f"{function.name} renders the summary before the delivery tests"

    assert checked, "no doctor entry point runs the delivery tests and then the summary"


# Verifies the Doctor target row names the same fix as the startup gate, so the two surfaces cannot word it differently
def test_a_missing_target_reuses_the_startup_gate_fix(im_module):
    report = im_module.DoctorReport()

    checks = im_module.doctor_check_targets(report, [])

    assert checks[0].status == "WARN"
    assert checks[0].fix == im_module.NO_TARGET_FIX


# Verifies the connectivity row carries the label and the endpoint detail shared with the sibling monitors
def test_the_connectivity_row_names_the_shared_endpoint(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://probe.example/ping")
    monkeypatch.setattr(im_module, "check_internet", lambda **kwargs: True)
    passing = im_module.doctor_connectivity_endpoint_check()
    monkeypatch.setattr(im_module, "check_internet", lambda **kwargs: False)
    failing = im_module.doctor_connectivity_endpoint_check()

    assert (passing.status, passing.label, passing.detail) == ("PASS", "The connectivity endpoint is reachable", "Endpoint: https://probe.example/ping")
    assert (failing.status, failing.label, failing.detail) == ("FAIL", "The connectivity endpoint could not be reached", "Endpoint: https://probe.example/ping")
    # The row carries no guide, because no page covers this check and the report ends with the doctor link
    assert (failing.fix, failing.guide) == ("Check network, DNS, proxy and CHECK_INTERNET_URL settings", "")


# Verifies the row names the state the shared resolver settled on, so it says what a restart would say
def test_the_timezone_row_follows_the_shared_resolver(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "Mars/Olympus_Mons")
    monkeypatch.setattr(im_module, "LOCAL_TIMEZONE_STATE", "config", raising=False)

    advice = im_module.resolve_local_timezone()

    assert im_module.LOCAL_TIMEZONE_STATE == "invalid"
    row = next(item for item in im_module.doctor_check_configuration([], timezone_advice=advice) if item.label in im_module.TIMEZONE_CHECK_LABELS.values())
    assert (row.status, row.label, row.detail) == ("FAIL", "Local timezone is invalid", "Time zone: Mars/Olympus_Mons")


# Verifies Ctrl+C at a delivery prompt ends the run instead of declining one test and asking the next
def test_a_delivery_prompt_interrupt_ends_the_run(im_module, monkeypatch):
    def interrupt(prompt=""):
        raise KeyboardInterrupt

    # The handler restores the saved stream, so it is pointed at the one this test captures
    monkeypatch.setattr(im_module, "stdout_bck", im_module.sys.stdout)
    monkeypatch.setattr("builtins.input", interrupt)

    with pytest.raises(SystemExit) as raised:
        im_module._doctor_ask_yes_no("Send one test")

    assert raised.value.code == 0


# Verifies an Instaloader that cannot be built becomes one failure row with an action, not a crash of the whole report
def test_an_instaloader_that_cannot_be_built_is_one_failure_row(im_module, monkeypatch):
    def refuse(**kwargs):
        raise RuntimeError("no instaloader today")
    monkeypatch.setattr(im_module, "instaloader_client", refuse)
    report = im_module.DoctorReport()

    checks = im_module.doctor_prepare_bot(report)

    assert report.bot is None
    assert (checks[0].section, checks[0].status, checks[0].label) == ("Configuration", "FAIL", "Could not initialise Instaloader")
    assert "no instaloader today" in checks[0].detail
    assert checks[0].fix == "Reinstall the instaloader package then run --doctor again"
    assert checks[0].guide == im_module.INSTALLATION_GUIDE_URL


# Verifies the live checks that need Instaloader are skipped with a reason when it could not be built, the way the sibling monitors skip a check that cannot run
def test_the_live_checks_are_skipped_without_instaloader(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "SESSION_USERNAME", "monitor_account")
    monkeypatch.setattr(im_module, "SKIP_SESSION", False)
    monkeypatch.setattr(im_module, "check_internet", lambda **kwargs: True)
    report = im_module.DoctorReport()

    session = im_module.doctor_check_session(report)
    connectivity = im_module.doctor_check_connectivity(report)
    targets = im_module.doctor_check_targets(report, ["someone"])

    assert (session[0].status, session[0].label) == ("SKIP", "The saved session was not checked")
    assert (connectivity[-1].status, connectivity[-1].label) == ("SKIP", "Instagram connectivity check was skipped")
    assert (targets[0].status, targets[0].label) == ("SKIP", "The monitored profiles were not checked")
    assert all(row.detail.startswith("Instaloader could not be initialised") for row in (session[0], connectivity[-1], targets[0]))
