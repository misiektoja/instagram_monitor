"""Shared pytest fixtures and import setup for the offline test suite.

These tests never touch the network. They import the single-file module
``instagram_monitor`` and exercise its pure / offline-safe helpers, stubbing
out the few functions that would otherwise reach Instagram.
"""

import os
import sys

# The project ships an installable copy (``instagram_monitor.egg-info``) that may
# also live in site-packages. Force the in-repo source onto the front of the
# import path so tests always run against the working tree, never a stale wheel.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
elif sys.path.index(_PROJECT_ROOT) != 0:
    sys.path.remove(_PROJECT_ROOT)
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

import instagram_monitor as im


# Fails fast if pytest accidentally imported an installed copy instead of the working tree
def _assert_in_repo_module() -> None:
    resolved = os.path.abspath(im.__file__)
    expected = os.path.join(_PROJECT_ROOT, "instagram_monitor.py")
    assert resolved == expected, (f"Tests imported the wrong instagram_monitor module.\n  imported: {resolved}\n  expected: {expected}\nAn installed copy is shadowing the working tree.")


_assert_in_repo_module()


# Exposes the imported module to every test
@pytest.fixture
def im_module():
    return im


_REAL_WIZARD_VERIFY_SMTP = im._wizard_verify_smtp
_REAL_LIST_FIREFOX_PROFILES = im.list_firefox_profiles
_REAL_LIST_CHROMIUM_PROFILES = im.list_chromium_profiles


# Restores the real profile enumeration for the tests that exercise it directly against a stubbed filesystem
@pytest.fixture
def real_browser_profiles(monkeypatch, deterministic_globals):
    monkeypatch.setattr(im, "list_firefox_profiles", _REAL_LIST_FIREFOX_PROFILES)
    monkeypatch.setattr(im, "list_chromium_profiles", _REAL_LIST_CHROMIUM_PROFILES)


@pytest.fixture(autouse=True)
# Keeps the wizard's mail server sign-in check offline, so a scripted setup run never opens a connection
def accepted_smtp_sign_in(monkeypatch):
    monkeypatch.setattr(im, "_wizard_verify_smtp", lambda values, password: None)


@pytest.fixture
# Restores the real sign-in check for the tests that exercise it directly against a stubbed SMTP class
def real_smtp_sign_in(monkeypatch, accepted_smtp_sign_in):
    monkeypatch.setattr(im, "_wizard_verify_smtp", _REAL_WIZARD_VERIFY_SMTP)


# Keeps the identity exposure ledger inside the test's temporary directory so no test can write account state into the repository
@pytest.fixture(autouse=True)
def isolated_exposure_ledger(monkeypatch, tmp_path):
    ledger_path = tmp_path / "exposure" / im.EXPOSURE_STATE_FILENAME
    monkeypatch.setattr(im, "exposure_state_path", lambda: str(ledger_path), raising=False)
    return ledger_path


# Resets the handful of module-level globals the helpers read so each test starts from a known, deterministic baseline
@pytest.fixture(autouse=True)
def deterministic_globals(monkeypatch, tmp_path):
    monkeypatch.setattr(im, "LOCAL_TIMEZONE", "UTC", raising=False)
    monkeypatch.setattr(im, "TIME_FORMAT_12H", False, raising=False)
    monkeypatch.setattr(im, "PRIVACY_SUBSTITUTIONS", [], raising=False)
    monkeypatch.setattr(im, "PRIVACY_SUBSTITUTIONS_INVALID_WARNED", False, raising=False)
    monkeypatch.setattr(im, "DEBUG_MODE", False, raising=False)
    monkeypatch.setattr(im, "VERBOSE_MODE", False, raising=False)
    monkeypatch.setattr(im, "CHECK_POSTS_IN_HOURS_RANGE", False, raising=False)
    monkeypatch.setattr(im, "MIN_H1", 0, raising=False)
    monkeypatch.setattr(im, "MAX_H1", 0, raising=False)
    monkeypatch.setattr(im, "MIN_H2", 0, raising=False)
    monkeypatch.setattr(im, "MAX_H2", 0, raising=False)
    monkeypatch.setattr(im, "WEBHOOK_ENABLED", False, raising=False)
    monkeypatch.setattr(im, "WEBHOOK_URL", "", raising=False)
    monkeypatch.setattr(im, "WEBHOOK_PROVIDER", "discord", raising=False)
    monkeypatch.setattr(im, "WEBHOOK_HEADERS", {}, raising=False)
    monkeypatch.setattr(im, "NTFY_ACCESS_TOKEN", "", raising=False)
    monkeypatch.setattr(im, "DAILY_HUMAN_HITS", 5, raising=False)
    # The real CLI path leaves these set, and every account-scoped helper keys off them
    monkeypatch.setattr(im, "SESSION_USERNAME", "", raising=False)
    monkeypatch.setattr(im, "SKIP_SESSION", False, raising=False)
    # A run derives these from the configured identity and leaves them set, and the settings endpoint writes
    # the rest straight onto the module, so a later test would inherit whichever identity ran before it
    monkeypatch.setattr(im, "USER_AGENT", "", raising=False)
    monkeypatch.setattr(im, "USER_AGENT_MOBILE", "", raising=False)
    monkeypatch.setattr(im, "HTTP_BACKEND", "curl_cffi", raising=False)
    monkeypatch.setattr(im, "CURL_CFFI_IMPERSONATE", "auto", raising=False)
    monkeypatch.setattr(im, "FOLLOW_LIST_SOURCE", "auto", raising=False)
    monkeypatch.setattr(im, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium", raising=False)
    # Setup and the dashboard both write these, and the wizard snapshots the module to build its baseline
    monkeypatch.setattr(im, "SKIP_FOLLOWERS", False, raising=False)
    monkeypatch.setattr(im, "SKIP_FOLLOWINGS", False, raising=False)
    # Setup and the profile pickers enumerate the real browsers of whoever runs the suite, and reading their
    # cookie databases makes a test depend on that machine's browsers and wait on the ones that are running
    monkeypatch.setattr(im, "list_firefox_profiles", lambda: [], raising=False)
    monkeypatch.setattr(im, "list_chromium_profiles", lambda browser: [], raising=False)
    im._WIZARD_BROWSER_SESSION_COUNTS.clear()
    # A run that reported a broken proxy leaves the record on the module, and Doctor reads it in place of the
    # live settings, so a later test would inherit the earlier run's proxy problem
    im.PROXY_STARTUP_ERRORS.clear()
    # Resolved user ids are reused for the whole run, so one test's target must not answer for another's
    im.USER_ID_CACHE.clear()
    # Resolved ids outlive a run in a file, so each test is given its own rather than the working directory's
    im.USER_ID_CACHE_LOADED = False
    monkeypatch.setattr(im, "user_id_cache_path", lambda: str(tmp_path / "instagram_monitor_user_ids.json"), raising=False)
    # A reels count established for one test's posts count must not answer for another's
    im.REELS_COUNT_CACHE.clear()
    # Set by the first startup notice a test prints, and read by the Doctor notice to decide its leading blank line
    im.CONSOLE_OUTPUT_PRINTED = False
    # Drop any cached flag-probe verdict between tests
    with im.FLAGGED_PROBE_LOCK:
        im.FLAGGED_PROBE_CACHE["ts"] = 0.0
        im.FLAGGED_PROBE_CACHE["flagged"] = False
    # Drop the flag-alert de-dup timestamp so each test starts able to alert
    with im.FLAGGED_NOTIFY_LOCK:
        im.FLAGGED_NOTIFY_STATE["ts"] = 0.0
    # Drop in-memory account stops so one safety test cannot block another test's request path
    with im.ACCOUNT_BREAKER_MEMORY_LOCK:
        im.ACCOUNT_BREAKER_MEMORY.clear()
        im.ACCOUNT_RECOVERY_ATTEMPTED.clear()
        im.ACCOUNT_PAUSED_TARGETS.clear()
    # load_dotenv writes into os.environ and nothing removes it again, so a test that loads a dotenv would
    # otherwise leak its secrets into every later test through the exported-environment lookup at startup
    for secret in im.SECRET_KEYS:
        monkeypatch.delenv(secret, raising=False)
    yield
