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


# Resets the handful of module-level globals the helpers read so each test starts from a known, deterministic baseline
@pytest.fixture(autouse=True)
def deterministic_globals(monkeypatch):
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
    monkeypatch.setattr(im, "DAILY_HUMAN_HITS", 5, raising=False)
    # Drop any cached flag-probe verdict between tests
    with im.FLAGGED_PROBE_LOCK:
        im.FLAGGED_PROBE_CACHE["ts"] = 0.0
        im.FLAGGED_PROBE_CACHE["flagged"] = False
    yield
