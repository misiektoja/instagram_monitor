"""Offline tests that drive the real monitoring loop to check account safety reaches every failure path.

The unit tests around the classifier cannot see these: each helper was correct on its own while the loop
never called the one that records a failure, so the circuit breaker only ever armed inside the follow list
fetch. These drive instagram_monitor_user itself and assert on the ledger it leaves behind.
"""

import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

import instagram_monitor as im

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts"

# Captured before the autouse ledger-isolation fixture can patch it, so the loop writes a real file under tmp_path
_REAL_EXPOSURE_STATE_PATH = im.exposure_state_path


# Returns an isolated local artifact directory for one loop test
def _artifact_dir() -> Path:
    artifact_dir = ARTIFACT_ROOT / "account_safety_loop" / uuid.uuid4().hex
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


@pytest.fixture
# Runs the real loop against a fake Instagram, with a real ledger under tmp_path and no waiting
def monitored_account(monkeypatch, tmp_path):
    monkeypatch.setattr(im, "exposure_state_path", _REAL_EXPOSURE_STATE_PATH, raising=False)
    im.ACCOUNT_BREAKER_MEMORY.clear()
    settings = {
        "OUTPUT_DIR": str(tmp_path), "LOCAL_TIMEZONE": "UTC", "SESSION_USERNAME": "loop.account",
        "SESSION_PASSWORD": "", "SKIP_SESSION": False, "CIRCUIT_BREAKER": True, "IDENTITY_BUDGET_PER_DAY": 0,
        "SKIP_FOLLOWERS": True, "SKIP_FOLLOWINGS": True, "SKIP_GETTING_STORY_DETAILS": True,
        "SKIP_GETTING_POSTS_DETAILS": True, "GET_MORE_POST_DETAILS": False, "DETECT_CHANGED_PROFILE_PIC": False,
        "CHECK_POSTS_IN_HOURS_RANGE": False, "WEB_DASHBOARD_ENABLED": False, "DASHBOARD_ENABLED": False,
        "RICH_AVAILABLE": False, "PROXY_ENABLED": False, "DISABLE_LOGGING": True, "COLORED_OUTPUT": False,
        "ERROR_NOTIFICATION": False, "WEBHOOK_ENABLED": False, "BE_HUMAN": False, "NEXT_OPERATION_DELAY": 0,
        "INSTA_CHECK_INTERVAL": 1, "RANDOM_SLEEP_DIFF_LOW": 0, "RANDOM_SLEEP_DIFF_HIGH": 0,
    }
    for name, value in settings.items():
        monkeypatch.setattr(im, name, value, raising=False)
    for name in ("log_activity", "update_ui_data", "update_check_times", "print_cur_ts", "ensure_instagram_session_wrapped", "refresh_proxy_if_needed"):
        monkeypatch.setattr(im, name, lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(im.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(im.instaloader.Profile, "own_profile", lambda ctx: SimpleNamespace(username="loop.account"))
    monkeypatch.setattr(im, "get_total_reels_count", lambda user, bot, skip_session=False: 0)
    monkeypatch.setattr(im, "get_dashboard_config_data", lambda *args, **kwargs: {"ready": True})
    return monkeypatch


# Returns a profile shaped the way the loop reads it, standing in for an instaloader profile
def _profile():
    return SimpleNamespace(username="target", userid=123, followers=0, followees=0, biography="", is_private=False, followed_by_viewer=False, mediacount=0, has_public_story=False, profile_pic_url_no_iphone="")


# Drives the loop through one healthy check and then repeated failures, stopping after `cycles` waits
def _run_loop(monkeypatch, failure, cycles=4):
    lookups = []
    bot = SimpleNamespace(context=SimpleNamespace(_session=SimpleNamespace(), is_logged_in=True, iphone_headers={}), load_session_from_file=lambda *args: None)
    profile = _profile()

    def lookup(_bot, username):
        lookups.append(username)
        if username == im.FLAGGED_PROBE_USERNAME:
            raise failure
        if len(lookups) > 1:
            raise failure
        return profile

    waits = []

    def wait(*args, **kwargs):
        waits.append(1)
        return len(waits) >= cycles

    monkeypatch.setattr(im, "instaloader_client", lambda **kwargs: bot, raising=False)
    monkeypatch.setattr(im, "profile_from_username_resilient", lookup, raising=False)
    monkeypatch.setattr(im, "interruptible_sleep", wait, raising=False)
    im.instagram_monitor_user("target", str(_artifact_dir() / "events.csv"), False, True, True, True, True, False)
    return [name for name in lookups if name == "target"]


class TestTheLoopStopsAnAccountItKeepsFailingAgainst:
    # An expired session reported by an ordinary profile lookup never reached the classifier, so the loop
    # retried a dead session for as long as it was left running
    def test_an_expired_session_arms_the_breaker_and_halts_the_loop(self, monitored_account):
        target_lookups = _run_loop(monitored_account, im.instaloader.exceptions.LoginRequiredException("login_required"))

        breaker = im.circuit_breaker_state()
        assert breaker is not None
        assert breaker["failure_class"] == "auth_expired"
        assert im.exposure_snapshot()["failures"] == {"auth_expired": 1}
        # The healthy check plus the one that failed. The breaker stops the loop before a third
        assert len(target_lookups) == 2

    # A challenge on any endpoint is account level, so the breaker arms before the flagged session ends the run.
    # Without the Web Dashboard there is nothing that can re-import a session, so the tool exits rather than waiting
    def test_a_challenge_arms_the_breaker_before_the_flagged_session_ends_the_run(self, monitored_account):
        with pytest.raises(SystemExit):
            _run_loop(monitored_account, im.instaloader.exceptions.AbortDownloadException("400 checkpoint_required"))

        breaker = im.circuit_breaker_state()
        assert breaker is not None
        assert breaker["failure_class"] == "challenge"
        # One challenge on one request is one entry, whichever path recorded it
        assert im.exposure_snapshot()["failures"] == {"challenge": 1}

    # A transient fault must not stop the account, or a lost connection would end monitoring until cleared by hand
    def test_a_network_fault_keeps_the_loop_running(self, monitored_account):
        target_lookups = _run_loop(monitored_account, ConnectionError("timed out"))

        assert im.circuit_breaker_state() is None
        assert len(target_lookups) > 2
        assert threading.current_thread() is threading.main_thread()
