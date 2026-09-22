"""SMTP rejection privacy through real credential and notification entry points."""

import dataclasses
import smtplib

import pytest

import instagram_monitor as monitor

_REAL_WIZARD_VERIFY = monitor._wizard_verify_smtp


# Flattens diagnostic fields without adding another layer of string escaping
def diagnostic_text(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return " ".join(diagnostic_text(getattr(value, field.name)) for field in dataclasses.fields(value))
    if isinstance(value, (tuple, list)):
        return " ".join(diagnostic_text(item) for item in value)
    advice = getattr(value, "advice", None)
    return str(value) + (" " + diagnostic_text(advice) if advice is not None else "")


@pytest.mark.parametrize("password", ["1234", r"test\mail-value", "test-'\"\\-value", "caf\u00e9-test-value"])
@pytest.mark.parametrize("surface", ["command", "wizard", "doctor", "delivery"])
# Keeps rejected credentials private at every SMTP entry point without changing the server status
def test_smtp_rejection_keeps_password_private(monkeypatch, tmp_path, capsys, password, surface):
    attempts = []
    replies = []

    class RejectingSMTP:
        # Accepts connection arguments without opening a socket
        def __init__(self, *args, **kwargs):
            pass

        # Accepts TLS setup without opening a socket
        def starttls(self, **kwargs):
            pass

        # Echoes the password as raw server bytes to exercise the escaping boundary
        def login(self, username, candidate):
            attempts.append(candidate)
            error = smtplib.SMTPAuthenticationError(535, ("Rejected credential " + candidate).encode("utf-8"))
            replies.append(error)
            raise error

        # Closes the fake connection
        def quit(self):
            pass

    settings = dict(SMTP_HOST="smtp.example.test", SMTP_PORT=587, SMTP_USER="sender@example.test", SENDER_EMAIL="sender@example.test", RECEIVER_EMAIL="owner@example.test", SMTP_SSL=True)
    for key, value in settings.items():
        monkeypatch.setattr(monitor, key, value)
    for key in ("ERROR_NOTIFICATION", "STATUS_NOTIFICATION", "PLAY_NOTIFICATION"):
        if hasattr(monitor, key):
            monkeypatch.setattr(monitor, key, True)
    monkeypatch.setattr(monitor, "SMTP_PASSWORD", password if surface in ("doctor", "delivery") else "")
    monkeypatch.setattr(smtplib, "SMTP", RejectingSMTP)
    result = None
    try:
        if surface == "command":
            result = monitor.run_set_smtp_password(env_file=str(tmp_path / "private.env"), interactive=True, input_func=lambda _: "n", getpass_func=lambda _: password)
        elif surface == "wizard":
            result = _REAL_WIZARD_VERIFY(settings, password)
        elif surface == "doctor":
            result = monitor.doctor_check_notifications(monitor.DoctorReport())
        else:
            result = monitor.send_email("Test subject", "Test body", "", True)
    except Exception as error:
        result = error
    text = capsys.readouterr().out + diagnostic_text(result)
    assert attempts == [password], text
    assert replies[0].smtp_code == 535
    assert password.encode("utf-8") not in replies[0].smtp_error
    assert password not in text
    assert repr(password.encode("utf-8"))[2:-1] not in text
    assert not (tmp_path / "private.env").exists()


# Leaves successful authentication results and unrelated transport failures unchanged
def test_smtp_login_preserves_transport_contract():
    class Connection:
        # Returns the successful authentication status
        def login(self, username, password):
            return 235, b"Accepted"

    assert monitor.smtp_login(Connection(), "sender", "1234") == (235, b"Accepted")
    failure = OSError("Connection closed")

    class Disconnected:
        # Raises the original transport error
        def login(self, username, password):
            raise failure

    with pytest.raises(OSError) as raised:
        monitor.smtp_login(Disconnected(), "sender", "1234")
    assert raised.value is failure
