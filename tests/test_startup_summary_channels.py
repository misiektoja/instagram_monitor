"""Tests for the startup summary rows that report the delivery channels and the runtime this tool is on."""

import os
import platform

import pytest

import instagram_monitor as monitor


@pytest.fixture(autouse=True)
# Puts both channels into a known state, since these rows read the delivery settings directly
def configured_channels(monkeypatch):
    monkeypatch.setattr(monitor, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(monitor, "SMTP_PORT", 587)
    monkeypatch.setattr(monitor, "SMTP_SSL", True)
    monkeypatch.setattr(monitor, "RECEIVER_EMAIL", "michal.k@example.com")
    monkeypatch.setattr(monitor, "WEBHOOK_ENABLED", True)
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "discord")
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/private-token")
    monkeypatch.setattr(monitor, "NTFY_ACCESS_TOKEN", "tk_secret")
    monkeypatch.setattr(monitor, "DELIVERY_CONFIRMATIONS", True)


# Returns the channel and environment rows keyed by label, since this tool assembles its summary inside main()
def summary_values(**overrides):
    return {row.label: row.value for row in monitor._startup_notification_summary_rows() + monitor._startup_environment_rows(None)}


# Returns those same rows rendered as the lines the summary prints, keyed by label
def summary_lines(**overrides):
    return {row.label: monitor._format_startup_summary_row(row) for row in monitor._startup_notification_summary_rows() + monitor._startup_environment_rows(None)}


# Returns the labels of the channel and environment rows, in order
def summary_labels(**overrides):
    return [row.label for row in monitor._startup_notification_summary_rows() + monitor._startup_environment_rows(None)]


# Verifies the webhook row names the service alerts reach, since the categories alone do not say Discord or ntfy
@pytest.mark.parametrize("provider,url,expected", [
    ("discord", "https://discord.com/api/webhooks/1/abc", "Discord (enabled)"),
    ("ntfy", "https://ntfy.sh/private-topic", "ntfy (enabled)"),
])
def test_the_webhook_provider_row_names_the_service(monkeypatch, provider, url, expected):
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", provider)
    monkeypatch.setattr(monitor, "WEBHOOK_URL", url)

    assert summary_values()["Webhook provider"] == expected


# Verifies the row never leaks the topic or token that lives in the webhook path
def test_the_webhook_provider_row_prints_no_part_of_the_url_path(monkeypatch):
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", "ntfy")
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "https://ntfy.sh/private-topic")

    value = summary_values()["Webhook provider"]

    assert "private-topic" not in value
    assert "tk_secret" not in value


# Verifies a switched-off channel still names the service it holds a destination for, which the rollup cannot say
def test_the_webhook_provider_row_names_the_service_of_a_switched_off_channel(monkeypatch):
    monkeypatch.setattr(monitor, "WEBHOOK_ENABLED", False)

    assert summary_values()["Webhook provider"] == "Discord (disabled)"


# Verifies a run with no webhook destination says so rather than naming a provider it would never post to
def test_the_webhook_provider_row_reports_an_unconfigured_channel(monkeypatch):
    monkeypatch.setattr(monitor, "WEBHOOK_URL", "")

    assert summary_values()["Webhook provider"] == "Not configured"


# Verifies the mail server is reported with the transport security in effect, which is what a silent send failure needs
@pytest.mark.parametrize("use_ssl,expected", [(True, "smtp.example.com:587 (STARTTLS)"), (False, "smtp.example.com:587 (TLS off)")])
def test_the_email_transport_row_names_the_server_and_its_security(monkeypatch, use_ssl, expected):
    monkeypatch.setattr(monitor, "SMTP_SSL", use_ssl)

    assert summary_values()["Email transport"] == expected


# Verifies an unset mail server says so instead of printing a half-built address
def test_the_email_transport_row_reports_an_unconfigured_server(monkeypatch):
    monkeypatch.setattr(monitor, "SMTP_HOST", "")
    monkeypatch.setattr(monitor, "SMTP_PORT", 0)

    assert summary_values()["Email transport"] == "Not configured"


# Verifies a configuration still holding the shipped sample values reports no channel, rather than naming a server and a recipient no alert can reach
@pytest.mark.parametrize("label,setting,placeholder,expected", [
    ("Email transport", "SMTP_HOST", "your_smtp_server_ssl", "Not configured"),
    ("Email recipient", "RECEIVER_EMAIL", "your_receiver_email", "Not configured"),
    ("Webhook provider", "WEBHOOK_URL", "your_webhook_url", "Not configured"),
])
def test_a_placeholder_destination_is_reported_as_unconfigured(monkeypatch, label, setting, placeholder, expected):
    monkeypatch.setattr(monitor, setting, placeholder)

    assert summary_values()[label] == expected


# Verifies the recipient keeps enough shape to spot a typo while the address itself does not survive a pasted log
@pytest.mark.parametrize("address,expected", [
    ("michal.k@example.com", "m******k@example.com"),
    ("ab@example.com", "a*@example.com"),
    ("a@example.com", "a@example.com"),
    ("not-an-address", "not-an-address"),
    ("", ""),
])
def test_the_recipient_address_is_masked(address, expected):
    assert monitor.mask_email_address(address) == expected


# Verifies the recipient row uses the mask rather than the configured address
def test_the_email_recipient_row_is_masked():
    value = summary_values()["Email recipient"]

    assert value == "m******k@example.com"
    assert "michal.k" not in value


# Verifies the row that explains a quiet run, since turning the confirmations off looks like a channel that stopped working
def test_the_delivery_confirmation_row_reports_the_setting(monkeypatch):
    monkeypatch.setattr(monitor, "DELIVERY_CONFIRMATIONS", False)

    assert summary_values()["Delivery confirmations"] == "False"


# Verifies the run reports the pid the documented signals have to be sent to, and the runtime a bug report needs
def test_the_runtime_rows_report_the_process_and_the_interpreter():
    values = summary_values()

    assert values["Process id"] == str(os.getpid())
    assert values["Python version"] == platform.python_version()
    assert values["Operating system"] == f"{platform.platform(terse=True)} ({platform.machine()})"


# Verifies each channel's detail rows are indented under it while their values stay in the shared column
def test_the_channel_detail_rows_are_indented_under_their_channel():
    lines = summary_lines()

    assert lines["Notifications (webhook)"].startswith("* Notifications (webhook):")
    for label in ("Email transport", "Email recipient", "Webhook provider"):
        assert lines[label].startswith(f"*   {label}:")
        assert lines[label][32] != " "


# Verifies every row added for the verbose views stays out of the short one, which is the screen a default run gets
def test_the_new_detail_rows_stay_out_of_the_concise_view():
    detail_labels = {"Email transport", "Email recipient", "Email images", "Webhook provider", "ntfy images", "Delivery confirmations", "Process id", "Python version", "Operating system"}
    concise = {row.label for row in monitor._startup_notification_summary_rows() + monitor._startup_environment_rows(None) if row.concise}

    assert not concise & detail_labels


# Verifies the send line names the service in every mode, since a run with the delivery confirmations off has no other clue
@pytest.mark.parametrize("provider,expected", [("discord", "Discord"), ("ntfy", "ntfy")])
def test_the_webhook_send_line_names_the_provider(monkeypatch, capsys, provider, expected):
    monkeypatch.setattr(monitor, "WEBHOOK_PROVIDER", provider)
    monkeypatch.setattr(monitor, "DELIVERY_CONFIRMATIONS", False)
    monkeypatch.setattr(monitor, "send_webhook", lambda *args, **kwargs: 0)

    monitor.send_notification_channels("error", "subject", "body", webhook_enabled=True)

    assert f"Sending webhook notification via {expected}" in capsys.readouterr().out
