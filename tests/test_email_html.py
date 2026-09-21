"""Tests for the HTML notification body, its ntfy plain form and its match with the plain text email."""

import difflib
import html as html_module
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import instagram_monitor as im

USER = "target"


# Reduces one HTML body back to the text it represents, independently of the module's own helpers
def html_to_text(body_html):
    text = re.sub(r"(?is)</?(?:html|head|body)\s*>", "", str(body_html or ""))
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    return html_module.unescape(text)


# Returns the unified diff between the plain body and the text the HTML body reduces to, empty when they match
def structural_diff(body, body_html):
    reduced = html_to_text(body_html)
    if reduced == body:
        return ""
    return "\n".join(difflib.unified_diff(body.split("\n"), reduced.split("\n"), fromfile="plain", tofile="html-reduced", lineterm=""))


# Returns one profile shaped the way the loop reads it, standing in for an instaloader profile
def profile(posts=0, followers=0, followings=0, bio="", private=False, followed=False, story=False):
    return SimpleNamespace(username=USER, userid=123, followers=followers, followees=followings, biography=bio, is_private=private, followed_by_viewer=followed, mediacount=posts, has_public_story=story, profile_pic_url_no_iphone="")


# The profile timeline the alerts are captured from, one entry per check
TIMELINE = [
    profile(),
    profile(posts=3),
    profile(posts=3, followers=10),
    profile(posts=3, followers=10, followings=4),
    profile(posts=3, followers=10, followings=4, bio="A new bio"),
    profile(posts=3, followers=10, followings=4, bio="A new bio", followed=True),
    profile(posts=3, followers=10, followings=4, bio="A new bio", followed=True, story=True),
]


@pytest.fixture
# Collects every alert the monitoring loop tries to send, without delivering any of them
def captured_alerts(monkeypatch):
    captured = []

    def fake_send(notification_type, subject, body, body_html="", email_enabled=False, webhook_enabled=None, **kwargs):
        discord = kwargs.get("webhook_description") or body
        captured.append({"type": notification_type, "subject": subject, "body": body, "body_html": body_html, "discord": discord, "ntfy": im.strip_discord_markdown(discord)})
        return bool(email_enabled), bool(webhook_enabled)

    monkeypatch.setattr(im, "send_notification_channels", fake_send)
    return captured


@pytest.fixture
# Runs the real loop against a scripted profile timeline, with no waiting and nothing written outside tmp_path
def timeline_alerts(monkeypatch, tmp_path, captured_alerts, capsys):
    settings = {
        "OUTPUT_DIR": str(tmp_path), "LOCAL_TIMEZONE": "UTC", "SESSION_USERNAME": "loop.account",
        "SESSION_PASSWORD": "", "SKIP_SESSION": False, "CIRCUIT_BREAKER": False, "IDENTITY_BUDGET_PER_DAY": 0,
        "SKIP_FOLLOWERS": True, "SKIP_FOLLOWINGS": True, "SKIP_GETTING_STORY_DETAILS": True,
        "SKIP_GETTING_POSTS_DETAILS": True, "GET_MORE_POST_DETAILS": False, "DETECT_CHANGED_PROFILE_PIC": False,
        "CHECK_POSTS_IN_HOURS_RANGE": False, "WEB_DASHBOARD_ENABLED": False, "DASHBOARD_ENABLED": False,
        "RICH_AVAILABLE": False, "PROXY_ENABLED": False, "DISABLE_LOGGING": True, "COLORED_OUTPUT": False,
        "ERROR_NOTIFICATION": False, "WEBHOOK_ENABLED": False, "BE_HUMAN": False, "NEXT_OPERATION_DELAY": 0,
        "FOLLOWERS_CHURN_DETECTION": False, "ADVANCED_FOLLOWER_FETCH": False, "STATUS_NOTIFICATION": True,
        "FOLLOWERS_NOTIFICATION": True, "INSTA_CHECK_INTERVAL": 1, "RANDOM_SLEEP_DIFF_LOW": 0, "RANDOM_SLEEP_DIFF_HIGH": 0,
    }
    for name, value in settings.items():
        monkeypatch.setattr(im, name, value, raising=False)
    for name in ("log_activity", "update_ui_data", "update_check_times", "print_cur_ts", "ensure_instagram_session_wrapped", "refresh_proxy_if_needed"):
        monkeypatch.setattr(im, name, lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(im.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(im.instaloader.Profile, "own_profile", lambda ctx: SimpleNamespace(username="loop.account"))
    monkeypatch.setattr(im, "get_total_reels_count", lambda user, bot, skip_session=False, posts_count=None: 0)
    monkeypatch.setattr(im, "get_dashboard_config_data", lambda *args, **kwargs: {"ready": True})

    bot = SimpleNamespace(context=SimpleNamespace(_session=SimpleNamespace(), is_logged_in=True, iphone_headers={}), load_session_from_file=lambda *args: None)
    lookups = {"count": 0}

    def lookup(_bot, username):
        entry = TIMELINE[min(lookups["count"], len(TIMELINE) - 1)]
        lookups["count"] += 1
        return entry

    waits = {"count": 0}

    def wait(*args, **kwargs):
        waits["count"] += 1
        return waits["count"] >= len(TIMELINE) + 1

    monkeypatch.setattr(im, "instaloader_client", lambda **kwargs: bot, raising=False)
    monkeypatch.setattr(im, "profile_from_username_resilient", lookup, raising=False)
    monkeypatch.setattr(im, "interruptible_sleep", wait, raising=False)
    im.instagram_monitor_user(USER, str(tmp_path / "events.csv"), False, True, True, True, True, False)
    capsys.readouterr()
    return captured_alerts


# Verifies a value taken from Instagram is escaped before it reaches the HTML body
def test_untrusted_text_is_escaped():
    assert im.html_text("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert im.html_text("line\nbreak") == "line<br>break"
    assert im.escape_html_attr('" onload="x') == "&quot; onload=&quot;x"


# Verifies a bare URL in an alert becomes a link while one already inside an attribute is left alone
def test_bare_urls_are_linked_once():
    assert im.html_autolink_urls("Guide: https://example.test/a") == 'Guide: <a href="https://example.test/a">https://example.test/a</a>'
    assert im.html_autolink_urls('<a href="https://example.test/a">x</a>') == '<a href="https://example.test/a">x</a>'


# Verifies the shared document wraps a rendered body and leaves an absent one absent
def test_the_shared_document_wraps_only_a_real_body():
    assert im.html_email_body("Body") == "<html><head></head><body>Body</body></html>"
    assert im.html_email_body("") == ""


# Verifies the failure alert bolds its summary and the two values that say how bad the outage is
def test_the_failure_alert_bolds_its_summary_and_outage_fields(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    advice = im_module.make_recovery_advice("network.unavailable", "Instagram is unreachable", "Retry later", True)

    rendered = im_module.recovery_alert_body_html(advice, 60, failed_checks=2, failing_since=1700000000)

    assert rendered.startswith("<b>Instagram is unreachable</b><br><br>")
    assert "Failed checks in a row: <b>2</b>" in rendered
    assert "Failing since: <b>" in rendered
    # The retry delay is configured rather than observed, so it carries no emphasis
    assert "Next retry in: 1 minute" in rendered


# Verifies the Discord copy of the failure alert carries the email's emphasis and its guide link
def test_the_failure_alert_reaches_discord_with_its_emphasis(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    advice = im_module.make_recovery_advice("network.unavailable", "Instagram is unreachable", im_module.recovery_fix_with_guide("Retry later", "https://example.test/guide"), True)
    rendered = im_module.recovery_alert_body_html(advice, 60, failed_checks=2, failing_since=1700000000)

    discord = im_module.html_body_to_discord_markdown(rendered)

    assert discord.startswith("**Instagram is unreachable**\n\n")
    assert "Guide: https://example.test/guide" in discord
    assert "Failed checks in a row: **2**" in discord
    assert "<" not in discord
    # ntfy shows a marker literally, so it gets the same wording without any
    assert im_module.strip_discord_markdown(discord) == im_module.recovery_alert_body(advice, 60, failed_checks=2, failing_since=1700000000)


# Verifies a link whose label repeats its destination is left bare, which Discord turns into a link itself
def test_a_self_labeled_link_stays_bare_in_discord(im_module):
    assert im_module.html_body_to_discord_markdown('<a href="https://example.test/a">https://example.test/a</a>') == "https://example.test/a"
    assert im_module.html_body_to_discord_markdown('<a href="https://example.test/a">docs</a>') == "[docs](https://example.test/a)"


# Verifies the timeline reaches several alert types, so the structural check is not silently narrow
def test_the_timeline_covers_several_alert_types(timeline_alerts):
    assert len({alert["subject"] for alert in timeline_alerts}) >= 6


# Verifies every alert carries an HTML body next to its plain one
def test_every_alert_has_an_html_body(timeline_alerts):
    assert [alert["subject"] for alert in timeline_alerts if not alert["body_html"]] == []


# Verifies each HTML body reduces back to its plain body, so no line break was added or lost
def test_html_bodies_match_the_plain_text(timeline_alerts):
    mismatches = [f"{alert['type']}: {alert['subject']}\n{structural_diff(alert['body'], alert['body_html'])}" for alert in timeline_alerts if structural_diff(alert["body"], alert["body_html"])]

    assert mismatches == []


# Verifies the ntfy body carries no markdown markers, since every ntfy client shows them literally
def test_the_ntfy_body_carries_no_markers(timeline_alerts):
    for alert in timeline_alerts:
        assert "**" not in alert["ntfy"]


# Verifies the monitored account is the bold subject of every alert that names it
def test_alerts_bold_the_account_they_name(timeline_alerts):
    named = [alert for alert in timeline_alerts if USER in alert["body"]]

    assert named
    for alert in named:
        assert f"<b>{USER}</b>" in alert["body_html"]


# Writes the captured alerts as JSON when PREVIEW_ALERTS_JSON names a destination, so a preview tool can render them
@pytest.mark.skipif(not os.environ.get("PREVIEW_ALERTS_JSON"), reason="set PREVIEW_ALERTS_JSON to dump the alerts")
def test_dump_the_alerts_for_a_preview(timeline_alerts):
    Path(os.environ["PREVIEW_ALERTS_JSON"]).write_text(json.dumps(timeline_alerts, indent=2), encoding="utf-8")
