"""Tests for the --doctor preflight checks (no real network)."""

import ast
import inspect
import io
from unittest.mock import Mock, call

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
    monkeypatch.setattr(im, "check_internet", lambda **kwargs: True)


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
        assert "--env-file" in missing_check.advice.fix
        assert missing_check.advice.fix.endswith(f"\nGuide: {im_module.SECRETS_GUIDE_URL}")
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
        assert failures[0].advice.fix == im_module.recovery_fix_with_guide("use documented settings.", im_module.CONFIG_GUIDE_URL)

    # A retired setting is a warning that still names the file and links the guide
    def test_retired_settings_become_a_warning_check(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: "im.conf")
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)

        checks = im_module.doctor_check_configuration([], (), ["DISCORD_MAX_FIELDS"])
        warnings = [check for check in checks if check.status == "WARN"]

        assert len(warnings) == 1
        assert "DISCORD_MAX_FIELDS" in warnings[0].detail
        assert warnings[0].advice.fix.endswith(f"\nGuide: {im_module.CONFIG_GUIDE_URL}")

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

    # A string such as "false" counts as on, so an on/off setting holding anything but True or False is named in one row
    def test_invalid_boolean_settings_are_reported_in_one_row(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", "false", raising=False)
        monkeypatch.setattr(im_module, "SMTP_SSL", 1, raising=False)

        rows = [item for item in im_module.doctor_check_configuration([]) if item.label == "One or more on/off settings are invalid"]

        assert [item.status for item in rows] == ["FAIL"]
        assert "ERROR_NOTIFICATION must be True or False, not 'false'" in rows[0].detail
        assert "SMTP_SSL must be True or False, not 1" in rows[0].detail
        assert rows[0].advice.fix.startswith("Set the reported settings to True or False")

    # An on/off setting written as 0 or 1 was accepted before the values were checked, so it still reads as off and on
    def test_a_numeric_on_off_setting_is_read_as_a_boolean(self, im_module):
        parsed = im_module.parse_config_content("VERIFY_SSL = 0\nDISABLE_LOGGING = 1\n")

        assert parsed == {"VERIFY_SSL": False, "DISABLE_LOGGING": True}
        assert all(isinstance(value, bool) for value in parsed.values())

    # The shipped defaults are all real booleans, so a run with nothing overridden never sees the on/off row
    def test_the_shipped_defaults_pass_the_boolean_check(self, im_module):
        assert im_module.runtime_boolean_errors() == []
        assert "ERROR_NOTIFICATION" in [name for name, value in im_module.config_template_defaults().items() if isinstance(value, bool)]

    # An interval below the documented minimum makes a challenge far more likely, which looks like the tool being broken
    def test_a_rate_limiting_interval_is_warned_about(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 60, raising=False)

        rows = [item for item in im_module.doctor_check_configuration([]) if item.label == "Check intervals are short"]

        assert [item.status for item in rows] == ["WARN"]
        assert str(im_module.DOCTOR_MIN_SAFE_CHECK_INTERVAL) in rows[0].advice.fix

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
        assert "tzlocal" in check.advice.fix
        assert check.advice.fix.endswith(f"\nGuide: {im_module.INSTALLATION_GUIDE_URL}")

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
        assert check.advice.fix == im_module.recovery_fix_with_guide("Set LOCAL_TIMEZONE to a valid pytz timezone", im_module.CONFIG_GUIDE_URL)

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
        assert "No saved session" in checks[0].advice.fix
        assert checks[0].advice.fix.endswith(f"\nGuide: {im_module.SESSION_IMPORT_GUIDE_URL}")

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
        assert warning.advice.fix == im_module.recovery_fix_with_guide("Correct SENDER_EMAIL and RECEIVER_EMAIL or turn the email alerts off", im_module.SMTP_GUIDE_URL)

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
        assert warning.advice.fix == im_module.recovery_fix_with_guide("Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD or turn the email alerts off", im_module.SMTP_GUIDE_URL)

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
        assert warning.advice.fix == im_module.recovery_fix_with_guide("Set SMTP_PASSWORD or turn the email alerts off", im_module.SMTP_GUIDE_URL)

    # A malformed destination is a FAIL under the label every tool in the family uses, so a fix reads the same everywhere
    def test_a_malformed_webhook_url_fails_under_the_family_label(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_HOST", "your_smtp_server_ssl", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "discord.com/api/webhooks/1/abc", raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord", raising=False)
        report = im_module.DoctorReport()

        checks = im_module.doctor_check_notifications(report)

        failure = next(check for check in checks if check.status == "FAIL")
        assert failure.label == "WEBHOOK_URL must contain a complete HTTPS link"
        assert failure.advice.fix.startswith("Use a complete HTTPS destination")

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
            im_module.make_doctor_check("Session", "FAIL", "broken", "detail text", im_module.make_recovery_advice("session.expired", "broken", im_module.recovery_fix_with_guide("do the thing.", "https://example.invalid/guide"), False)),
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
        assert not any(check.advice is not None and check.advice.fix.startswith("To fix:") for check in checks)

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
        builders = [node for node in ast.walk(ast.parse(inspect.getsource(im_module))) if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "make_recovery_advice" and len(node.args) >= 3]
        # The fix sits in the third slot, or inside recovery_fix_with_guide when the advice names a page
        actions = [node.args[2].args[0] if isinstance(node.args[2], ast.Call) and getattr(node.args[2].func, "id", "") == "recovery_fix_with_guide" else node.args[2] for node in builders]
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

    # An empty export is a shell-profile leftover rather than a value, so it neither blocks nor blanks the dotenv value
    def test_an_empty_export_does_not_shadow_the_dotenv_value(self, im_module, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("NTFY_ACCESS_TOKEN=tk_from_file\n", encoding="utf-8")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--env-file", str(env_file), "--no-color"])
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda *args, **kwargs: 0)
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", "", raising=False)
        monkeypatch.setattr(im_module, "SECRET_SOURCES", {}, raising=False)
        monkeypatch.setenv("NTFY_ACCESS_TOKEN", "")

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert im_module.NTFY_ACCESS_TOKEN == "tk_from_file"
        assert im_module.SECRET_SOURCES["NTFY_ACCESS_TOKEN"] == "dotenv file"

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

    # Verifies the library the width cap uses is reported, since without it a wide glyph is measured short
    def test_the_truncation_library_is_reported(self, im_module):
        installed = [check for check in im_module.doctor_check_environment((3, 12, 1), lambda _name: object()) if "wcwidth" in check.label]
        missing = [check for check in im_module.doctor_check_environment((3, 12, 1), lambda name: None if name == "wcwidth" else object()) if "wcwidth" in check.label]

        assert [(check.status, check.detail) for check in installed] == [("PASS", "Used only to measure display width for screen truncation")]
        assert [(check.status, check.detail) for check in missing] == [("WARN", "Wide characters count as one column, so a line holding them can run past the limit. Normal monitoring is unaffected")]
        assert "pip3 install \"wcwidth\"" in missing[0].advice.fix

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
        assert 'pip3 install "colorama"' in missing.advice.fix

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
        assert call("instagram_monitor_friend.log") in writable.call_args_list, "the log row checks the final target-specific filename"

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
        assert "WEBHOOK_ENABLED" in webhook.advice.fix
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
        assert email.advice.fix == im_module.recovery_fix_with_guide("Turn on at least one email alert in the configuration file", im_module.SMTP_GUIDE_URL)
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
        email.assert_called_once_with("Instagram Monitor doctor test email", "This test email was sent after approval in --doctor. Your SMTP delivery settings work.", "This test email was sent after approval in <b>--doctor</b>. Your SMTP delivery settings work.", im_module.SMTP_SSL, smtp_timeout=5, report_delivery=False)
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
        delivery.assert_called_once_with("Instagram Monitor doctor test webhook", "This test notification was sent after approval in --doctor. Your webhook delivery settings work.", color=0x7289DA, notification_type=im_module.WEBHOOK_TEST_NOTIFICATION_TYPE, report_delivery=False)


# Verifies a secret passed as an argument is reported under the command line rather than the configuration file
def test_a_command_line_secret_is_reported_as_such(im_module, monkeypatch):
    for name in im_module.SECRET_KEYS:
        monkeypatch.setattr(im_module, name, "your_placeholder", raising=False)
    monkeypatch.setattr(im_module, "SECRET_SOURCES", {"SMTP_PASSWORD": "command line"}, raising=False)
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "a-real-secret-value", raising=False)

    labels = [check.label for check in im_module.doctor_secret_checks(None)]

    assert "Secrets loaded from the command line" in labels
    assert "Secrets loaded from the configuration file or command line" not in labels


# A setting holding the wrong type raises at the comparison or the format string that reads it, which is nowhere
# near where the value was set. Doctor is the command asked to explain that setup, so it has to survive one
class TestASettingOfTheWrongType:
    # Runs one command line and returns its exit code and output, letting anything but SystemExit escape
    @staticmethod
    def _run(im_module, monkeypatch, capsys, argv_tail):
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", *argv_tail, "--config-file", "none", "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        with pytest.raises(SystemExit) as exit_call:
            im_module.run_main()
        return exit_call.value.code, capsys.readouterr().out

    # The comparison guarding against a zero interval used to raise on a value it could not compare at all
    def test_the_doctor_reports_it_instead_of_raising(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", "3600", raising=False)

        code, output = self._run(im_module, monkeypatch, capsys, ["--doctor"])

        assert code == 1
        assert "INSTA_CHECK_INTERVAL must be a number greater than zero, not '3600'" in output
        # The rest of the report has to follow, or the row is just a crash with better wording
        assert "Next steps" in output

    # An interval out of range stopped the doctor at the startup gate, so the report it was asked for never arrived
    def test_a_zero_interval_is_a_row_rather_than_an_early_exit(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 0, raising=False)

        code, output = self._run(im_module, monkeypatch, capsys, ["--doctor"])

        assert code == 1
        assert "INSTA_CHECK_INTERVAL must be a number greater than zero, not 0" in output
        assert "Next steps" in output

    # A monitoring run has no report to put it in, so it says which setting and what it needs, then stops
    def test_a_monitoring_run_names_the_setting_and_stops(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "SMTP_PORT", "587", raising=False)
        monkeypatch.setattr(im_module, "check_internet", lambda: (_ for _ in ()).throw(AssertionError("stopped before the connectivity check")))

        code, output = self._run(im_module, monkeypatch, capsys, ["target.user"])

        assert code == 1
        assert "SMTP_PORT must be an integer from 1 through 65535, not '587'" in output
        assert "Correct the reported settings in the configuration file" in output

    # A row that reads the broken setting would raise, so it is left out while the checks around it still run
    def test_the_rows_that_read_the_setting_are_skipped(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", "3600", raising=False)

        checks = im_module.doctor_check_configuration([])
        labels = [item.label for item in checks]

        assert "One or more numeric settings are invalid" in labels
        assert "Check intervals are short" not in labels
        assert "TLS certificate verification is on" in labels

    # Every setting is named in one row whatever its type, so one fix pass clears them all
    def test_every_broken_setting_is_named_at_once(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "DISABLE_LOGGING", True, raising=False)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", "3600", raising=False)
        monkeypatch.setattr(im_module, "MIN_H1", 99, raising=False)
        monkeypatch.setattr(im_module, "FOLLOWERS_PER_BATCH", -1, raising=False)

        row = next(item for item in im_module.doctor_check_configuration([]) if item.label == "One or more numeric settings are invalid")

        assert row.status == "FAIL"
        assert "INSTA_CHECK_INTERVAL must be a number greater than zero, not '3600'" in row.detail
        assert "MIN_H1 must be an integer from 0 through 23, not 99" in row.detail
        assert "FOLLOWERS_PER_BATCH must be an integer zero or greater, not -1" in row.detail

    # Validation that rejects the shipped configuration would stop every run, so the defaults are pinned
    def test_the_shipped_defaults_have_no_numeric_problems(self, im_module):
        assert im_module.runtime_configuration_problems() == {}
        assert im_module.runtime_configuration_errors() == []


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
            return "".join(part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{}" for part in node.values)
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
    advice = im_module.make_recovery_advice("config.invalid", "a label", "do the thing", False)
    assert [im_module.make_doctor_check("Configuration", status, "a label", "", advice).status for status in im_module.DOCTOR_STATUSES] == list(im_module.DOCTOR_STATUSES)
    assert set(im_module.DOCTOR_MARK_STYLES) == set(im_module.DOCTOR_STATUSES)

    with pytest.raises(ValueError):
        im_module.make_doctor_check("Configuration", "info", "a label")


# Verifies one row reads as one block: the action lines sit under the marker at the detail indent while a pass row has none
def test_the_action_lines_sit_indented_under_their_marker(im_module, capsys, monkeypatch):
    monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
    report = im_module.DoctorReport()
    report.checks = [
        im_module.make_doctor_check("Configuration", "WARN", "a warning row", "a detail worth keeping", im_module.make_recovery_advice("config.invalid", "a warning row", im_module.recovery_fix_with_guide("do the thing", im_module.DOCTOR_GUIDE_URL), False)),
        im_module.make_doctor_check("Configuration", "PASS", "a passing row"),
    ]

    im_module.render_doctor_sections(report)
    lines = capsys.readouterr().out.splitlines()
    rows = lines[lines.index("[WARN] a warning row"):]

    assert rows[:5] == ["[WARN] a warning row", "  a detail worth keeping", "  To fix: do the thing", f"  Guide: {im_module.DOCTOR_GUIDE_URL}", "[PASS] a passing row"]


# Verifies the report renders in the declared section order rather than the order the checks were collected
def test_the_sections_render_in_the_declared_order(im_module, capsys, monkeypatch):
    monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
    checks = [im_module.make_doctor_check(section, "PASS", f"row for {section}") for section in reversed(im_module.DOCTOR_SECTIONS)]

    im_module.render_doctor_sections(im_module.DoctorReport(checks=checks))

    printed = [line for line in capsys.readouterr().out.splitlines() if line in im_module.DOCTOR_SECTIONS]
    assert tuple(printed) == im_module.DOCTOR_SECTIONS


# Verifies the two headers this tool names differently from its siblings stay in the shared slots. Session is
# the Instagram term for the saved login the check reads, and Targets is plural because this tool monitors a list
def test_the_two_headers_this_tool_names_its_own_way_keep_the_shared_slots(im_module):
    assert im_module.DOCTOR_SECTIONS == ("Environment", "Configuration", "Session", "Connectivity", "Targets", "Notifications")


# Verifies a link in a detail line takes the link colour while a styled action line keeps its own colour
def test_a_link_in_a_detail_line_is_coloured_as_a_link(im_module, capsys, monkeypatch):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {name: im_module._build_ansi_sequence(value) for name, value in im_module.DEFAULT_COLOR_THEME.items() if im_module._build_ansi_sequence(value)})
    report = im_module.DoctorReport()
    report.checks = [
        im_module.make_doctor_check("Connectivity", "PASS", "The connectivity endpoint is reachable", "Endpoint: https://www.instagram.com/"),
        im_module.make_doctor_check("Session", "FAIL", "The session did not validate", "", im_module.make_recovery_advice("session.expired", "The session did not validate", im_module.recovery_fix_with_guide("Sign in again at https://www.instagram.com/", im_module.DOCTOR_GUIDE_URL), False)),
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


# Verifies a failed delivery test fails the whole run, so the exit code and the last sentence agree
def test_a_failed_delivery_test_changes_the_exit_code(im_module, monkeypatch):
    _setup_no_network(monkeypatch, im_module)
    monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
    monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
    monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.invalid", raising=False)
    monkeypatch.setattr(im_module, "SMTP_PORT", 587, raising=False)
    monkeypatch.setattr(im_module, "SMTP_SSL", True, raising=False)
    monkeypatch.setattr(im_module, "SMTP_USER", "monitor@example.invalid", raising=False)
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "app-password-value", raising=False)
    monkeypatch.setattr(im_module, "SENDER_EMAIL", "monitor@example.invalid", raising=False)
    monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "owner@example.invalid", raising=False)
    monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True, raising=False)
    monkeypatch.setattr(im_module.smtplib, "SMTP", Mock(return_value=Mock()))
    stream = _TTYBuffer()
    monkeypatch.setattr(im_module.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr(im_module.sys, "stdout", stream)
    monkeypatch.setattr(im_module, "_doctor_ask_yes_no", Mock(return_value=True))
    monkeypatch.setattr(im_module, "send_email", Mock(return_value=1))

    rc = im_module.run_doctor([])

    output = stream.getvalue()
    assert rc == 1
    assert "[FAIL] Doctor test email delivery failed" in output
    assert "1 check(s) failed" in output
    assert "All checks passed" not in output


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
    assert checks[0].advice.fix == im_module.recovery_fix_with_guide(im_module.NO_TARGET_FIX, im_module.QUICK_START_GUIDE_URL)


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
    assert failing.advice.fix == "Check network, DNS, proxy and CHECK_INTERNET_URL settings"


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
    assert checks[0].advice.fix == im_module.recovery_fix_with_guide("Reinstall the instaloader package then run --doctor again", im_module.INSTALLATION_GUIDE_URL)


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


# One row shape and one advice shape across the family: the advice rides on the row and its fix carries the
# guide, so a row or an advice copied from a sibling means the same thing here
def test_the_doctor_row_and_its_advice_share_one_contract(im_module):
    row_parameters = list(inspect.signature(im_module.make_doctor_check).parameters.values())
    advice_parameters = list(inspect.signature(im_module.make_recovery_advice).parameters.values())

    assert [parameter.name for parameter in row_parameters] == ["section", "status", "label", "detail", "advice"]
    assert [parameter.default for parameter in row_parameters[3:]] == ["", None]
    assert [parameter.name for parameter in advice_parameters] == ["code", "summary", "fix", "retryable", "detail"]
    assert im_module.recovery_fix_with_guide("do the thing", "https://example.invalid/page") == "do the thing\nGuide: https://example.invalid/page"


# A non-pass row is refused without advice and keeps the advice it was given, which is where its fix and guide live
def test_a_row_carries_its_advice_and_refuses_to_go_without(im_module):
    advice = im_module.make_recovery_advice("config.invalid", "a warning row", im_module.recovery_fix_with_guide("do the thing", im_module.DOCTOR_GUIDE_URL), False)

    row = im_module.make_doctor_check("Configuration", "WARN", "a warning row", "a detail worth keeping", advice)

    assert row.advice is advice
    assert not hasattr(advice, "guide_url")
    with pytest.raises(ValueError):
        im_module.make_doctor_check("Configuration", "WARN", "a warning row", "a detail worth keeping")


# Verifies doctor reports the output destinations the run was given, since it exits before monitoring applies them
def test_doctor_reports_the_output_overrides_the_run_was_given(im_module, monkeypatch, tmp_path):
    csv_path = tmp_path / "chosen.csv"
    seen = {}

    def capture(*args, **keywords):
        seen["csv"] = im_module.CSV_FILE
        seen["logging_disabled"] = im_module.DISABLE_LOGGING
        return 0

    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "someuser", "--config-file", "none", "--env-file", "none", "--no-color", "-b", str(csv_path), "-d"])
    monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "CSV_FILE", "")
    monkeypatch.setattr(im_module, "DISABLE_LOGGING", False)
    monkeypatch.setattr(im_module, "run_doctor", capture)

    with pytest.raises(SystemExit):
        im_module.run_main()

    assert seen["csv"] == str(csv_path)
    assert seen["logging_disabled"] is True


# Collects the rows one doctor section produced, so a test asserts on results rather than rendered output
def rows_for(checks, section):
    return [check for check in checks if check.section == section]


class TestDoctorProxyRows:
    # Verifies the report says whether Instagram traffic leaves through a proxy, which nothing else in it stated
    def test_an_enabled_proxy_is_reported_without_its_credentials(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PROXY_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "PROXY_URL", "http://user:secret@proxy.example:8080", raising=False)
        monkeypatch.setattr(im_module, "PROXY_CERT_PATH", "", raising=False)
        monkeypatch.setattr(im_module, "PROXY_WEBHOOKS", False, raising=False)

        rows = im_module.doctor_proxy_checks()

        assert [row.status for row in rows] == ["PASS"]
        assert "proxy.example:8080" in rows[0].detail
        assert "secret" not in rows[0].detail and "user" not in rows[0].detail

    # Verifies a run without a proxy still says so, since silence reads the same as not being checked
    def test_a_disabled_proxy_is_stated(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PROXY_ENABLED", False, raising=False)

        rows = im_module.doctor_proxy_checks()

        assert rows[0].status == "PASS" and "Proxy is disabled" in rows[0].label

    # Verifies a proxy setting that would stop every request is a failure that names the setting, not the value
    @pytest.mark.parametrize("url,expected", [("", "PROXY_URL has no value"), ("ftp://proxy.example", "not http or https"), ("proxy.example:8080", "no http:// or https:// prefix")])
    def test_a_broken_proxy_url_is_named_without_being_quoted(self, im_module, monkeypatch, url, expected):
        monkeypatch.setattr(im_module, "PROXY_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "PROXY_URL", url, raising=False)
        monkeypatch.setattr(im_module, "PROXY_CERT_PATH", "", raising=False)
        monkeypatch.setattr(im_module, "PROXY_STARTUP_ERRORS", [], raising=False)

        rows = im_module.doctor_proxy_checks()

        assert rows[0].status == "FAIL"
        assert expected in rows[0].label
        assert url not in rows[0].label or not url

    # Verifies a certificate path that does not exist is reported rather than raising on the first request
    def test_a_missing_proxy_certificate_is_reported(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "PROXY_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "PROXY_URL", "http://proxy.example:8080", raising=False)
        monkeypatch.setattr(im_module, "PROXY_CERT_PATH", str(tmp_path / "absent.pem"), raising=False)
        monkeypatch.setattr(im_module, "PROXY_STARTUP_ERRORS", [], raising=False)

        rows = im_module.doctor_proxy_checks()

        assert rows[0].status == "FAIL" and "does not exist" in rows[0].label

    # Verifies the commands that exist to explain or repair a configuration are not stopped by the proxy in it
    def test_a_broken_proxy_does_not_stop_the_reporting_commands(self, im_module, monkeypatch):
        seen = {}
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "--doctor", "--config-file", "none", "--env-file", "none", "--no-color", "--enable-proxy", "--proxy-url", "notaurl"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "run_doctor", lambda *args, **kwargs: seen.setdefault("reached", True) and 0)

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert seen.get("reached") is True, "doctor is the command that explains a broken proxy, so it has to run"
        assert im_module.PROXY_STARTUP_ERRORS, "the problem is recorded so the report can name it"
        assert im_module.PROXY_ENABLED is False, "the report continues with the proxy switched off"

    # Verifies the proxy, interface and state-path rows reach the rendered report, not just their own helpers
    def test_the_new_rows_reach_the_configuration_section(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "find_config_file", lambda p=None: None)
        monkeypatch.setattr(im_module, "PROXY_ENABLED", False, raising=False)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "FLASK_AVAILABLE", False, raising=False)
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False, raising=False)
        monkeypatch.setattr(im_module, "exposure_state_path", lambda: str(tmp_path / "ledger.json"))

        labels = [row.label for row in im_module.doctor_check_configuration([])]

        assert any("Proxy is disabled" in label for label in labels)
        assert any("Web Dashboard is enabled but cannot start" in label for label in labels)
        assert any("Account safety ledger" in label for label in labels)


class TestDoctorCircuitBreakerRow:
    # Verifies a stopped account is reported, since every other check can pass while monitoring makes no request
    @pytest.mark.parametrize("session_valid,expected", [(True, "WARN"), (False, "FAIL")])
    def test_a_stopped_account_is_reported(self, im_module, monkeypatch, session_valid, expected):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "alice", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)
        monkeypatch.setattr(im_module, "circuit_breaker_state", lambda: {"tripped_ts": 1758000000, "failure_class": "action_block", "target": "bob", "error": ""})

        rows = im_module.doctor_breaker_checks(session_valid)

        assert [row.status for row in rows] == [expected]
        assert "alice" in rows[0].label
        assert "action_block" in rows[0].detail
        assert rows[0].advice is not None and "several hours" in rows[0].advice.fix

    # Verifies an account that is not stopped adds no row at all
    def test_a_running_account_adds_no_row(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "circuit_breaker_state", lambda: None)

        assert im_module.doctor_breaker_checks(True) == []

    # Verifies the row reaches the Session section of a full check, not just the helper
    def test_the_row_reaches_the_session_section(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "me", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)
        monkeypatch.setattr(im_module, "circuit_breaker_state", lambda: {"tripped_ts": 1758000000, "failure_class": "challenge"})
        report = im_module.DoctorReport()
        report.bot = _FakeBot()

        rows = im_module.doctor_check_session(report)

        assert [row.status for row in rows] == ["PASS", "WARN"]
        assert all(row.section == "Session" for row in rows)


class TestDoctorSessionIdentity:
    # Verifies a session signing in as another account fails, the way monitoring itself refuses to resume it
    def test_a_session_for_another_account_fails(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "alice", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)
        monkeypatch.setattr(im_module, "circuit_breaker_state", lambda: None)
        report = im_module.DoctorReport()
        report.bot = _FakeBot()

        rows = im_module.doctor_check_session(report)

        assert rows[0].status == "FAIL"
        assert "signs in as me, not alice" in rows[0].label

    # Verifies the matching case still passes, so the check cannot be satisfied by failing everything
    def test_a_matching_session_passes(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "ME", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)
        monkeypatch.setattr(im_module, "circuit_breaker_state", lambda: None)
        report = im_module.DoctorReport()
        report.bot = _FakeBot()

        assert im_module.doctor_check_session(report)[0].status == "PASS"


class TestDoctorInterfaceRows:
    # Verifies an interface the configuration switches on but this machine cannot start is a failure
    @pytest.mark.parametrize("flag,available,package", [("WEB_DASHBOARD_ENABLED", "FLASK_AVAILABLE", "flask"), ("DASHBOARD_ENABLED", "RICH_AVAILABLE", "rich")])
    def test_an_enabled_interface_without_its_package_fails(self, im_module, monkeypatch, flag, available, package):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False, raising=False)
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False, raising=False)
        monkeypatch.setattr(im_module, flag, True, raising=False)
        monkeypatch.setattr(im_module, available, False, raising=False)

        rows = im_module.doctor_interface_checks()

        assert [row.status for row in rows] == ["FAIL"]
        assert "cannot start" in rows[0].label
        assert package in rows[0].detail

    # Verifies the Web Dashboard is not offered as the place to add targets when it cannot start
    def test_a_dashboard_that_cannot_start_is_not_offered_for_targets(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "FLASK_AVAILABLE", False, raising=False)

        rows = im_module.doctor_check_targets(im_module.DoctorReport(), [])

        assert rows[0].status == "FAIL"
        assert "cannot start" in rows[0].label
        assert "targets can be added there" not in rows[0].detail

    # Verifies a working dashboard still stands in for a configured target
    def test_a_working_dashboard_still_passes(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True, raising=False)
        monkeypatch.setattr(im_module, "FLASK_AVAILABLE", True, raising=False)

        assert im_module.doctor_check_targets(im_module.DoctorReport(), [])[0].status == "PASS"


class TestDoctorTargetAdvice:
    # Verifies a no-login run is never told its session may be flagged, matching the connectivity row above it
    def test_no_login_target_failure_does_not_blame_a_session(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, user: (_ for _ in ()).throw(Exception("Profile nosuchuser does not exist")))
        report = im_module.DoctorReport()
        report.bot = _FakeBot()

        rows = im_module.doctor_check_targets(report, ["nosuchuser"])

        assert rows[0].status == "FAIL"
        assert rows[0].advice is not None and "session or IP may be temporarily flagged" not in rows[0].advice.fix

    # Verifies a logged-in run keeps the extra cause, so the fix was made conditional and not deleted
    def test_a_logged_in_target_failure_keeps_the_session_cause(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "alice", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, user: (_ for _ in ()).throw(Exception("Profile nosuchuser does not exist")))
        report = im_module.DoctorReport()
        report.bot = _FakeBot()

        rows = im_module.doctor_check_targets(report, ["nosuchuser"])

        assert rows[0].advice is not None and "session or IP may be temporarily flagged" in rows[0].advice.fix


class TestDoctorEmailSettingShapes:
    # Verifies a port the sender would refuse is named as a setting instead of raising inside the connection
    def test_an_unusable_port_is_named_and_no_connection_is_attempted(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_PORT", "not-a-port", raising=False)
        monkeypatch.setattr(im_module, "SMTP_HOST", "mail.example.test", raising=False)
        monkeypatch.setattr(im_module, "SMTP_USER", "user", raising=False)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "pass", raising=False)
        monkeypatch.setattr(im_module, "SENDER_EMAIL", "a@example.test", raising=False)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "b@example.test", raising=False)
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)

        rows = rows_for(im_module.doctor_check_notifications(im_module.DoctorReport()), "Notifications")

        assert rows[0].status == "WARN"
        assert "SMTP_PORT" in rows[0].detail
        assert "ValueError" not in rows[0].detail and "int()" not in rows[0].detail

    # Verifies a host the sender would refuse is named here too, rather than surfacing as a lookup failure
    def test_an_unusable_host_is_named_and_no_connection_is_attempted(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SMTP_PORT", 587, raising=False)
        monkeypatch.setattr(im_module, "SMTP_HOST", "not a host name", raising=False)
        monkeypatch.setattr(im_module, "SMTP_USER", "user", raising=False)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "pass", raising=False)
        monkeypatch.setattr(im_module, "SENDER_EMAIL", "a@example.test", raising=False)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "b@example.test", raising=False)
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module.smtplib, "SMTP", _unreachable_smtp)

        rows = rows_for(im_module.doctor_check_notifications(im_module.DoctorReport()), "Notifications")

        assert rows[0].status == "WARN" and "SMTP_HOST" in rows[0].detail

    # Verifies Doctor and the sender judge the host through the same helper, so they cannot drift apart
    @pytest.mark.parametrize("host,usable", [("mail.example.test", True), ("192.0.2.10", True), ("not a host name", False), ("", False)])
    def test_the_host_rule_is_shared_with_the_sender(self, im_module, host, usable):
        assert im_module.smtp_host_is_usable(host) is usable


class TestDoctorStatePaths:
    # Verifies the safety ledger is checked, since an unwritable one stops the account rather than one output file
    def test_an_unwritable_ledger_is_a_failure(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "exposure_state_path", lambda: str(tmp_path / "ledger.json"))
        monkeypatch.setattr(im_module, "SKIP_FOLLOWERS", True, raising=False)
        monkeypatch.setattr(im_module, "SKIP_FOLLOWINGS", True, raising=False)
        monkeypatch.setattr(im_module, "output_destination_is_writable", lambda destination: False)

        rows = im_module.doctor_state_path_checks([])

        assert [row.status for row in rows] == ["FAIL"]
        assert "Account safety ledger" in rows[0].label

    # Verifies the saved follower lists are checked when names are collected, whatever the log and CSV settings say
    def test_the_saved_list_directory_is_checked_when_names_are_collected(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "exposure_state_path", lambda: str(tmp_path / "ledger.json"))
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        monkeypatch.setattr(im_module, "SKIP_FOLLOWERS", False, raising=False)
        monkeypatch.setattr(im_module, "SKIP_FOLLOWINGS", False, raising=False)
        monkeypatch.setattr(im_module, "output_destination_is_writable", lambda destination: True)

        labels = [row.label for row in im_module.doctor_state_path_checks(["friend"])]

        assert any("Saved follower list directory" in label for label in labels)

    # Verifies a counts-only run is not asked about a directory it never writes into
    def test_a_counts_only_run_checks_no_list_directory(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "exposure_state_path", lambda: str(tmp_path / "ledger.json"))
        monkeypatch.setattr(im_module, "SKIP_FOLLOWERS", True, raising=False)
        monkeypatch.setattr(im_module, "SKIP_FOLLOWINGS", True, raising=False)
        monkeypatch.setattr(im_module, "output_destination_is_writable", lambda destination: True)

        assert len(im_module.doctor_state_path_checks(["friend"])) == 1


class TestDoctorRequestCost:
    # Verifies the notice states what running Doctor costs, since it is reached for when Instagram is already refusing
    def test_the_notice_counts_the_live_requests(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "alice", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", False, raising=False)

        im_module.render_doctor_notice(["one", "two"])

        assert "about 4 Instagram request(s)" in capsys.readouterr().out

    # Verifies a no-login run with no targets is counted as the single connectivity request it makes
    def test_a_no_login_run_counts_one_request(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True, raising=False)

        im_module.render_doctor_notice([])

        assert "about 1 Instagram request(s)" in capsys.readouterr().out

    # The banner already ends with a blank line, so a notice printed straight after it must not add a second one
    def test_the_notice_follows_the_banner_without_a_gap(self, im_module, capsys):
        im_module.render_doctor_notice([])

        assert not capsys.readouterr().out.startswith("\n")

    # A startup warning between the banner and the notice runs the two blocks together, so the notice stands apart
    def test_the_notice_stands_apart_from_a_startup_warning(self, im_module, capsys):
        im_module.print_recovery_error("dotenv file '/absent/.env' does not exist", context="dotenv_missing", label="Warning")
        capsys.readouterr()

        im_module.render_doctor_notice([])

        assert capsys.readouterr().out.startswith("\n")

    # A caller that knows what came before it decides for itself, so the flag is a default rather than the rule
    def test_the_caller_can_override_the_spacing(self, im_module, capsys):
        im_module.note_console_output()

        im_module.render_doctor_notice([], separate=False)

        assert not capsys.readouterr().out.startswith("\n")
