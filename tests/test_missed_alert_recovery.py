#!/usr/bin/env python3
"""Covers the recovery alert sent to a channel that never received the failure alert."""

import instagram_monitor as monitor


# Records the alert a dispatcher hands the channels instead of delivering it
class RecordingChannels:
    def __init__(self):
        self.calls = []

    def __call__(self, notification_type, subject, body, body_html="", email_enabled=False, webhook_enabled=None, **keywords):
        self.calls.append({"subject": subject, "body": body, "body_html": body_html, "webhook_body": keywords.get("webhook_body", ""), "webhook_description": keywords.get("webhook_description", ""), "email": email_enabled, "webhook": webhook_enabled})
        return bool(email_enabled), bool(webhook_enabled)


# Verifies a channel whose failure alert never landed is told about the outage and its end together, since a
# channel blocked for the length of the outage would otherwise hear nothing at all
def test_a_channel_that_missed_the_failure_alert_is_told_about_the_whole_outage(monkeypatch):
    channels = RecordingChannels()
    for name, value in (("SMTP_HOST", "smtp.example.com"), ("SMTP_PORT", 587), ("SMTP_USER", "sender@example.com"), ("SMTP_PASSWORD", "test-password"), ("SENDER_EMAIL", "sender@example.com"), ("RECEIVER_EMAIL", "ops@example.com"), ("WEBHOOK_ENABLED", True), ("WEBHOOK_URL", "https://discord.com/api/webhooks/1/token"), ("WEBHOOK_PROVIDER", "discord")):
        monkeypatch.setattr(monitor, name, value)
    monkeypatch.setattr(monitor, "send_notification_channels", channels)
    monkeypatch.setattr(monitor, "ERROR_NOTIFICATION", True)
    monkeypatch.setattr(monitor, "webhook_event_enabled", lambda notification_type: True)
    monkeypatch.setattr(monitor, "LOCAL_TIMEZONE", "UTC")
    monkeypatch.setattr(monitor, "print_outage_recovery", lambda *arguments, **keywords: None)
    state = monitor.ErrorAlertState()
    state.email_sent = True
    state.webhook_failures = 1
    state.summary = "The service is temporarily unavailable"
    state.failing_since = int(monitor.time.time()) - 600

    monitor.notify_monitoring_recovery("watched-user", state)

    assert len(channels.calls) == 1
    call = channels.calls[0]
    assert (call["email"], call["webhook"]) == (True, True)
    assert call["body"].startswith("Monitoring recovered for watched-user after 10 minutes.")
    assert call["webhook_description"].startswith("Monitoring failed for **watched-user** at ")
    assert "The failure was: The service is temporarily unavailable" in call["webhook_description"]
    assert call["webhook_description"].endswith("The failure alert could not be delivered here while the failure lasted.")
