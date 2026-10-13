"""Generated commands retain executable arguments while diagnostics keep secrets hidden."""

import io
import sys

import pytest

import instagram_monitor as monitor


COMMAND = 'instagram_monitor --doctor account-name --config-file "C:\\Profiles\\account-name.conf" --env-file "C:\\Profiles\\account-name.env"'


@pytest.fixture
# Configures a credential that also occurs in otherwise valid command arguments
def command_collision(monkeypatch):
    monkeypatch.setattr(monitor, "SMTP_PASSWORD", "account-name")
    monkeypatch.setattr(monitor, "DEBUG_MODE", True)
    monkeypatch.setattr(monitor, "COLOR_ENABLED", False, raising=False)
    monkeypatch.setattr(monitor, "TRUNCATE_CHARS", 0, raising=False)
    monkeypatch.setattr(monitor, "PRIVACY_SUBSTITUTIONS", [("account-name", "MASKED")])
    monkeypatch.setattr(monitor, "DASHBOARD_ENABLED", False)
    monkeypatch.setattr(monitor, "pbar", None)
    return monitor.make_recovery_advice("unknown", "Server rejected account-name", "Run: " + COMMAND, False, "SMTP_PASSWORD=account-name")


@pytest.mark.parametrize("surface", ["recovery", "doctor"])
# Keeps paths and targets intact without exposing the matching credential in diagnostic fields
def test_generated_command_survives_redaction(command_collision, surface, capsys):
    advice = command_collision
    if surface == "recovery":
        print(monitor.render_recovery_advice(advice, debug=True))
    else:
        report = monitor.DoctorReport()
        report.checks.append(monitor.make_doctor_check(monitor.DOCTOR_SECTIONS[0], "FAIL", advice.summary, advice.detail, advice))
        rendered = monitor.render_doctor_sections(report)
        if rendered is not None:
            print(rendered)
    output = capsys.readouterr().out
    assert COMMAND in output
    assert "Server rejected account-name" not in output
    assert "SMTP_PASSWORD=account-name" not in output


# Keeps serialized secret assignments hidden independently of any generated command
def test_raw_diagnostics_still_redact_credentials(monkeypatch):
    monkeypatch.setattr(monitor, "SMTP_PASSWORD", "account-name")
    output = monitor.sanitize_error_text("SMTP_PASSWORD=account-name")
    assert "account-name" not in output


@pytest.mark.parametrize("surface", ["recovery", "doctor", "wizard", "smtp_retry"])
@pytest.mark.parametrize("logging", [False, True])
# Preserves commands through the final stream while ordinary output retains its privacy filtering
def test_command_output_through_streams(monkeypatch, command_collision, surface, logging):
    terminal = io.StringIO()
    log = io.StringIO()
    monkeypatch.setattr(sys, "stdout", terminal)
    if logging:
        stream = monitor.Logger.__new__(monitor.Logger)
        stream.terminal = terminal
        monkeypatch.setattr(stream, "main_log", log, raising=False)
        stream.target_logs = {}
        stream.target_paths = {}
    else:
        stream = monitor.ColorStream(terminal)
    monkeypatch.setattr(sys, "stdout", stream)
    if surface == "recovery":
        print(monitor.render_recovery_advice(command_collision, debug=True))
    elif surface == "doctor":
        report = monitor.DoctorReport()
        report.checks.append(monitor.make_doctor_check(monitor.DOCTOR_SECTIONS[0], "FAIL", command_collision.summary, command_collision.detail, command_collision))
        rendered = monitor.render_doctor_sections(report)
        if rendered is not None:
            print(rendered)
    elif surface == "smtp_retry":
        monkeypatch.setattr(monitor, "_wizard_verify_smtp", lambda *args: (command_collision.summary, command_collision.detail, command_collision.fix, True))
        monkeypatch.setattr(monitor, "_wizard_offer_retry", lambda *args, **kwargs: True)
        assert monitor._wizard_smtp_sign_in_accepted({}, "account-name") is False
    else:
        monitor._wizard_print_command("Run command:", COMMAND)
    print("Ordinary output: account-name")
    output = terminal.getvalue()
    assert COMMAND in output
    assert "Server rejected account-name" not in output
    assert "SMTP_PASSWORD=account-name" not in output
    assert "Ordinary output: account-name" not in output
    if logging:
        assert COMMAND in log.getvalue()
        assert "Ordinary output: account-name" not in log.getvalue()


@pytest.mark.parametrize("surface", ["recovery", "doctor", "wizard"])
# Keeps a configured name substitution out of session import commands
def test_session_command_preserves_paths_with_privacy_substitutions(monkeypatch, tmp_path, capsys, surface):
    monkeypatch.setattr(monitor, "DOTENV_FILE", str(tmp_path / "account-name.env"))
    monkeypatch.setattr(monitor, "CLI_CONFIG_PATH", str(tmp_path / "account-name.conf"))
    monkeypatch.setattr(monitor, "_wizard_install_method", lambda: "pip")
    monkeypatch.setattr(monitor, "PRIVACY_SUBSTITUTIONS", [("account-name", "MASKED")])
    command = monitor.session_recovery_command()
    advice = monitor.make_recovery_advice("session.missing", "No session for account-name", "Run: " + command, False)
    if surface == "recovery":
        monitor.print_recovery_advice(advice)
    elif surface == "doctor":
        report = monitor.DoctorReport()
        report.checks.append(monitor.make_doctor_check("Session", "FAIL", advice.summary, advice=advice))
        monitor.render_doctor_sections(report)
    else:
        monitor._wizard_print_command("Import session:", command)
    output = capsys.readouterr().out
    assert command in output
    assert "MASKED.env" not in output
    if surface != "wizard":
        assert "No session for MASKED" in output
