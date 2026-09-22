"""Offline tests that drive the real monitoring loop to check account safety reaches every failure path.

The unit tests around the classifier cannot see these: each helper was correct on its own while the loop
never called the one that records a failure, so the circuit breaker only ever armed inside the follow list
fetch. These drive instagram_monitor_user itself and assert on the ledger it leaves behind.
"""

import json
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
        "FOLLOWERS_CHURN_DETECTION": False, "ADVANCED_FOLLOWER_FETCH": False,
        "INSTA_CHECK_INTERVAL": 1, "RANDOM_SLEEP_DIFF_LOW": 0, "RANDOM_SLEEP_DIFF_HIGH": 0,
    }
    for name, value in settings.items():
        monkeypatch.setattr(im, name, value, raising=False)
    for name in ("log_activity", "update_ui_data", "update_check_times", "print_cur_ts", "ensure_instagram_session_wrapped", "refresh_proxy_if_needed"):
        monkeypatch.setattr(im, name, lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(im.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(im.instaloader.Profile, "own_profile", lambda ctx: SimpleNamespace(username="loop.account"))
    monkeypatch.setattr(im, "get_total_reels_count", lambda user, bot, skip_session=False, posts_count=None: 0)
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


class TestATruncatedListDoesNotReplaceASavedBaseline:
    """A browser dialog that stops rendering returns a short list with nothing to say it stopped early.

    The shortfall tolerance lets a small gap through as a finished list, so a saved baseline of 100 was
    replaced by the 90 that rendered and the ten missing accounts were reported as removals.
    """

    # Drives the real startup pass against a saved baseline and a follow list that comes back short
    @staticmethod
    def _run(monkeypatch, tmp_path, saved, fetched, reported_count):
        baseline = tmp_path / "target" / "json" / "instagram_target_followers.json"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(json.dumps([len(saved), saved]), encoding="utf-8")
        monkeypatch.setattr(im, "SKIP_FOLLOWERS", False, raising=False)
        monkeypatch.setattr(im, "SKIP_FOLLOW_CHANGES", False, raising=False)
        removals = []
        monkeypatch.setattr(im, "compare_and_log_follower_changes", lambda user, kind, old, new, csv_file: (removals.append((kind, sorted(set(old) - set(new)))), ("", "", "", "", "", "", "", ""))[1], raising=False)

        def fetch(*args, **kwargs):
            result = im.PaginatedUsernameResult(fetched)
            result.complete = True
            return result

        monkeypatch.setattr(im, "fetch_usernames_paginated", fetch, raising=False)
        bot = SimpleNamespace(context=SimpleNamespace(_session=SimpleNamespace(), is_logged_in=True, iphone_headers={}), load_session_from_file=lambda *args: None)
        profile = _profile()
        profile.followers = reported_count
        monkeypatch.setattr(im, "instaloader_client", lambda **kwargs: bot, raising=False)
        monkeypatch.setattr(im, "profile_from_username_resilient", lambda _bot, username: profile, raising=False)
        monkeypatch.setattr(im, "interruptible_sleep", lambda *args, **kwargs: True, raising=False)
        im.instagram_monitor_user("target", str(tmp_path / "events.csv"), False, False, True, True, True, False, skip_follow_changes=False)
        return json.loads(baseline.read_text(encoding="utf-8")), removals

    # One new follower makes the tool refetch. The dialog stalls at 91 of the 101 Instagram reports, a
    # shortfall inside the tolerance, so the list reads as finished and would drop ten saved accounts
    def test_a_render_short_of_the_count_keeps_the_saved_list(self, monitored_account, tmp_path, capsys):
        saved = [f"user{index}" for index in range(100)]
        stored, removals = self._run(monitored_account, tmp_path, saved, saved[:91], 101)

        assert stored == [100, saved]
        assert removals == []
        assert "came back with 91 of about 101 while 100 were already saved" in capsys.readouterr().out

    # Accounts that really unfollowed move the count too, so the smaller list replaces the saved one
    def test_a_real_unfollow_replaces_the_saved_list(self, monitored_account, tmp_path):
        saved = [f"user{index}" for index in range(100)]
        stored, removals = self._run(monitored_account, tmp_path, saved, saved[:80], 80)

        assert stored == [80, saved[:80]]
        assert removals == [("followers", sorted(saved[80:]))]


@pytest.mark.parametrize("kind", ["followers", "followings"])
@pytest.mark.parametrize("challenge", [False, True])
# Records a periodic list failure once when it passes from the paginator to the real monitor
def test_periodic_list_failure_is_recorded_once(monitored_account, kind, challenge):
    monkeypatch = monitored_account
    monkeypatch.setattr(im, "SKIP_" + kind.upper(), False)
    bot = SimpleNamespace(context=SimpleNamespace(_session=SimpleNamespace(), is_logged_in=True, iphone_headers={}), load_session_from_file=lambda *args: None)
    profile = _profile()
    field = "followers" if kind == "followers" else "followees"
    lookups = []
    fetches = []
    waits = []
    failure = im.instaloader.exceptions.AbortDownloadException("400 checkpoint_required") if challenge else im.instaloader.exceptions.TooManyRequestsException("429 Too Many Requests")

    # Changes the reported count after startup so the periodic list path runs
    def lookup(*args):
        lookups.append(1)
        setattr(profile, field, 1 if len(lookups) == 1 else 2)
        return profile

    # Produces the startup baseline then fails the next list request
    def names(*args, **kwargs):
        fetches.append(1)
        if len(fetches) > 1:
            raise failure
        yield SimpleNamespace(username="saved")

    # Ends the probe after the first periodic check if it remains retryable
    def wait(*args, **kwargs):
        waits.append(1)
        return len(waits) >= 2

    monkeypatch.setattr(im, "instaloader_client", lambda **kwargs: bot)
    monkeypatch.setattr(im, "profile_from_username_resilient", lookup)
    monkeypatch.setattr(im, "follow_list_generator", names)
    monkeypatch.setattr(im, "interruptible_sleep", wait)
    args = ("target", "", False, kind != "followers", kind != "followings", True, True, False)
    if challenge:
        with pytest.raises(SystemExit):
            im.instagram_monitor_user(*args)
    else:
        im.instagram_monitor_user(*args)
    assert len(fetches) == 2
    assert im.exposure_snapshot()["failures"] == {"challenge" if challenge else "rate_limit": 1}
