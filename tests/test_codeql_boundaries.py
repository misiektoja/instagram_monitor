"""Regressions for untrusted text, local paths and CodeQL data-flow boundaries."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("value,expected", [
    ("HTTPS://WWW.INSTAGRAM.COM/Alice/?next=/elsewhere", "alice"),
    ("instagram.com/alice#bio", "alice"),
    ("https://sub-domain.instagram.com/alice/", "alice"),
    ("@Alice", "alice"),
])
# Preserves accepted profile URLs and public usernames
def test_profile_url_normalization(im_module, value, expected):
    assert im_module.normalize_instagram_username(value) == expected


@pytest.mark.parametrize("value", [".", "..", "https://instagram.com/../", "instagram.com/alice/extra", "https://instagram.com.evil/alice", "https://evil@instagram.com/alice", "https://.instagram.com/alice"])
# Rejects traversal components and URLs that are not single Instagram profiles
def test_profile_rejects_invalid_paths(im_module, value):
    with pytest.raises(ValueError):
        im_module.normalize_instagram_username(value)


@pytest.mark.parametrize("account", [".", ".."])
# Refuses browser profile names that resolve to the base directory or its parent
def test_browser_profile_rejects_dot_directories(im_module, monkeypatch, tmp_path, account):
    monkeypatch.setattr(im_module, "SESSION_USERNAME", account)
    monkeypatch.setattr(im_module, "SKIP_SESSION", False)
    monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_PROFILE_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="subdirectory"):
        im_module.browser_profile_dir()


@pytest.mark.parametrize("line,expected", [
    ("Caption: 'Don't miss this one'", "Caption: '<username>Don't miss this one<reset>'"),
    ('"a" and \'b\'', '"<username>a<reset>" and \'<username>b<reset>\''),
    ('\'unfinished "inner" text', '\'unfinished "<username>inner<reset>" text'),
    ("'... 'word' tail", "'<username>... 'word<reset>' tail"),
    ("'...'", "'...'"),
    ("'first\nsecond'", "'first\nsecond'"),
    ("'a'b' ", "'<username>a'b<reset>' "),
])
# Keeps leftmost quoted content and embedded apostrophes intact
def test_quoted_content_keeps_existing_boundaries(im_module, monkeypatch, line, expected):
    monkeypatch.setattr(im_module, "COLOR_ENABLED", True)
    monkeypatch.setattr(im_module, "_COLOR_STYLES", {"username": "<username>"})
    monkeypatch.setattr(im_module, "ANSI_RESET", "<reset>")
    assert im_module._colorize_quoted_content(line) == expected


# Completes formerly expensive text scans within a bounded subprocess without truncating the input
def test_long_input_does_not_stall_formatting(im_module):
    program = r"""
import instagram_monitor as monitor
monitor.COLOR_ENABLED = True
monitor._COLOR_STYLES = {}
size = 100_000
assert monitor.strip_instagram_profile_url("-" * size) == "-" * size
for value in ('"a' + "0" * size, " " * size + "* Warning: x", "\t" * size, "* Signal " + "a" * size):
    assert monitor._colorize_line(value) == value
nested = "<http://" * size
assert monitor.strip_discord_markdown(nested) == nested
"""
    completed = subprocess.run([sys.executable, "-c", program], cwd=Path(im_module.__file__).parent, capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr


# Keeps exceptions and private values out of a failed follow-analysis response
def test_follow_analysis_failure_keeps_local_details_private(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_TEMPLATE_DIR", str(Path(im_module.__file__).parent / "templates"))
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_DATA", {"targets": {"alice": {}}})
    monkeypatch.setattr(im_module, "SMTP_PASSWORD", "synthetic-private-password")
    monkeypatch.setattr(im_module, "DEBUG_MODE", True)

    # Simulates a local file failure containing a private value
    def fail_analysis(*args, **kwargs):
        raise OSError("Cannot read /private/saved-followers: synthetic-private-password")

    monkeypatch.setattr(im_module, "analyze_follows_for_user", fail_analysis)
    app = im_module.create_web_dashboard_app()
    assert app is not None
    response = app.test_client().get("/api/follow-analysis/alice")
    assert response.status_code == 500
    assert "local debug output" in response.get_json()["error"]
    assert "/private/" not in response.get_data(as_text=True)
    assert "synthetic-private-password" not in response.get_data(as_text=True)
    diagnostic = capsys.readouterr().out
    assert "/private/saved-followers" in diagnostic
    assert "synthetic-private-password" not in diagnostic


# Reports only the source and presence of a secret through the shared debug logger
def test_secret_resolution_does_not_log_values(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "DEBUG_MODE", True)
    im_module.record_secret_source("SMTP_PASSWORD", "environment", "synthetic-private-password")
    diagnostic = capsys.readouterr().out
    assert "SMTP_PASSWORD" in diagnostic
    assert "value=set" in diagnostic
    assert "synthetic-private-password" not in diagnostic
