"""Notification acceptance and receipt behavior with isolated transports."""

from email import policy
from email.message import Message
from email.parser import Parser
from unittest.mock import Mock

import pytest

import instagram_monitor as monitor


@pytest.fixture
# Configures a fake SMTP connection with valid delivery settings
def smtp_connection(monkeypatch):
    connection = Mock()
    for name, value in {"SMTP_HOST": "smtp.example.test", "SMTP_PORT": 587, "SMTP_USER": "sender@example.test", "SMTP_PASSWORD": "test-password", "SENDER_EMAIL": "sender@example.test", "RECEIVER_EMAIL": "receiver@example.test", "DEBUG_MODE": False}.items():
        monkeypatch.setattr(monitor, name, value)
    monkeypatch.setattr(monitor.smtplib, "SMTP", Mock(return_value=connection))
    return connection


@pytest.mark.parametrize("failure_stage", ["quit", "sendmail", "login"])
# Preserves the SMTP acceptance result when closing the session also fails
def test_smtp_cleanup_preserves_delivery_result(smtp_connection, capsys, failure_stage):
    smtp_connection.quit.side_effect = OSError("Session already closed")
    if failure_stage != "quit":
        getattr(smtp_connection, failure_stage).side_effect = OSError("SMTP operation failed")
    result = monitor.send_email("A complete subject", "A complete body", "", False, report_delivery=False)
    assert result == (0 if failure_stage == "quit" else 1)
    assert smtp_connection.sendmail.call_count == (0 if failure_stage == "login" else 1)
    smtp_connection.quit.assert_called_once()
    smtp_connection.close.assert_called_once()
    output = capsys.readouterr().out
    assert "Email sent to" not in output
    if failure_stage == "quit":
        assert "Error:" not in output


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("confirmations", [False, True])
@pytest.mark.parametrize("report_delivery", [False, True])
# Keeps the email content intact and reports acceptance only when all receipt controls allow it
def test_email_receipt_does_not_repeat_content(monkeypatch, smtp_connection, capsys, verbose, confirmations, report_delivery):
    monkeypatch.setattr(monitor, "VERBOSE_MODE", verbose)
    monkeypatch.setattr(monitor, "DELIVERY_CONFIRMATIONS", confirmations)
    subject = "instagram_monitor: user-provided subject"
    body = "Complete event details.\nProfile: https://example.test/profile"
    assert monitor.send_email(subject, body, "<p>Complete event details.</p>", False, report_delivery=report_delivery) == 0
    message = Parser(policy=policy.default).parsestr(smtp_connection.sendmail.call_args.args[2])
    assert message["Subject"] == subject
    plain_part = message.get_payload(0)
    assert isinstance(plain_part, Message)
    payload = plain_part.get_payload(decode=True)
    assert isinstance(payload, bytes)
    assert payload.decode("utf-8") == body
    output = capsys.readouterr().out
    assert output.count("* Email sent to receiver@example.test") == int(verbose and confirmations and report_delivery)
    assert subject not in output
    assert body not in output


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("confirmations", [False, True])
@pytest.mark.parametrize("report_delivery", [False, True])
# Keeps webhook content intact while leaving explicit tests to print their own result
def test_webhook_receipt_does_not_repeat_content(monkeypatch, capsys, verbose, confirmations, report_delivery):
    settings = {"WEBHOOK_ENABLED": True, "WEBHOOK_URL": "https://discord.com/api/webhooks/123/test-token", "WEBHOOK_PROVIDER": "discord", "WEBHOOK_HEADERS": {}, "WEBHOOK_TRANSFORMS": [], "VERBOSE_MODE": verbose, "DEBUG_MODE": False, "DELIVERY_CONFIRMATIONS": confirmations}
    for name, value in settings.items():
        monkeypatch.setattr(monitor, name, value)
    response = Mock(status_code=204)
    post = Mock(return_value=response)
    monkeypatch.setattr(monitor, "post_webhook_request", post)
    subject = "instagram_monitor: user-provided title"
    body = "Complete event details.\nProfile: https://example.test/profile"
    assert monitor.send_webhook(subject, body, force=True, report_delivery=report_delivery) == 0
    payload = post.call_args.kwargs["json"]
    assert payload["embeds"][0]["title"] == subject
    assert body in payload["embeds"][0]["description"]
    output = capsys.readouterr().out
    assert output.count("* Webhook sent through Discord") == int(verbose and confirmations and report_delivery)
    assert subject not in output
    assert body not in output
