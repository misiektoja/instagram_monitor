"""Tests for JSON username extraction, follow-string formatting and user-agent generation."""

import random
import re

import pytest


def _followers_payload(usernames):
    return {"data": {"user": {"edge_followed_by": {"edges": [{"node": {"username": u}} for u in usernames]}}}}


def _followings_payload(usernames):
    return {"data": {"user": {"edge_follow": {"edges": [{"node": {"username": u}} for u in usernames]}}}}


class TestExtractUsernamesSafely:
    def test_followers_edges(self, im_module):
        assert im_module.extract_usernames_safely(_followers_payload(["a", "b", "c"])) == ["a", "b", "c"]

    def test_followings_edges(self, im_module):
        assert im_module.extract_usernames_safely(_followings_payload(["x", "y"])) == ["x", "y"]

    def test_followers_preferred_over_followings(self, im_module):
        data = {"data": {"user": {"edge_followed_by": {"edges": [{"node": {"username": "fromfollowers"}}]}, "edge_follow": {"edges": [{"node": {"username": "fromfollowing"}}]}}}}
        assert im_module.extract_usernames_safely(data) == ["fromfollowers"]

    def test_missing_top_level_user_returns_empty(self, im_module):
        assert im_module.extract_usernames_safely({"something": "else"}) == []

    def test_missing_edges_returns_empty(self, im_module):
        assert im_module.extract_usernames_safely({"data": {"user": {"edge_followed_by": {}}}}) == []

    def test_edges_not_a_list_returns_empty(self, im_module):
        assert im_module.extract_usernames_safely({"data": {"user": {"edge_followed_by": {"edges": "nope"}}}}) == []

    def test_malformed_single_edge_is_skipped(self, im_module):
        data = {"data": {"user": {"edge_followed_by": {"edges": [{"node": {"username": "good"}}, {"node": {}}, {"missing": 1}]}}}}
        assert im_module.extract_usernames_safely(data) == ["good"]

    def test_empty_edges_list(self, im_module):
        assert im_module.extract_usernames_safely(_followers_payload([])) == []

    # Malformed containers return an empty username list instead of raising
    def test_malformed_containers_return_empty(self, im_module):
        cases = [
            None,
            {"data": None},
            {"data": {"user": None}},
            {"data": {"user": {"edge_followed_by": None}}},
            {"data": {"user": {"edge_followed_by": {"edges": [None, {"node": None}, {"node": {"username": None}}]}}}},
        ]
        for data in cases:
            assert im_module.extract_usernames_safely(data) == []


class TestBuildFollowString:
    def test_disabled(self, im_module):
        assert im_module.build_follow_string(False, 0, 0, 0) == "False"

    def test_limit_only(self, im_module):
        assert im_module.build_follow_string(True, 100, None, None) == "Maximum of 100 accounts"

    def test_limit_with_batches(self, im_module):
        assert im_module.build_follow_string(True, 100, 10, 5) == "Maximum of 100 accounts in batches of 10 accounts with a 5 second delay"

    def test_batches_without_limit(self, im_module):
        assert im_module.build_follow_string(True, None, 10, 5) == "Batches of 10 accounts with a 5 second delay"

    def test_alt_format_drops_maximum_prefix(self, im_module):
        assert im_module.build_follow_string(True, 100, None, None, alt_format=True) == "100 accounts"

    def test_alt_format_batches(self, im_module):
        assert im_module.build_follow_string(True, None, 10, 5, alt_format=True) == "batches of 10 accounts with a 5 second delay"


class TestGetRandomUserAgent:
    # Generated desktop user agents use browser-style Mozilla prefixes
    def test_is_nonempty_browser_string(self, im_module, monkeypatch):
        monkeypatch.setattr(random, "choice", lambda seq: seq[0])
        monkeypatch.setattr(random, "randrange", lambda *args: args[0])
        ua = im_module.get_random_user_agent()
        assert ua.startswith("Mozilla/5.0")
        assert len(ua) > 30

    # Each desktop browser branch can be selected without relying on random sampling
    def test_known_browser_family_branches(self, im_module, monkeypatch):
        cases = [
            ("chrome", "Chrome/80.0.3000.60"),
            ("firefox", "Firefox/90.0"),
            ("edge", "Edg/80.0.3000.60"),
            ("safari", "Version/13.0 Safari"),
        ]
        for browser, marker in cases:
            picks = [browser]
            monkeypatch.setattr(random, "choice", lambda seq, picks=picks: picks.pop(0) if picks else seq[0])
            monkeypatch.setattr(random, "randint", lambda start, stop: start)
            monkeypatch.setattr(random, "randrange", lambda *args: args[0])
            assert marker in im_module.get_random_user_agent()


class TestGetRandomMobileUserAgent:
    # Mobile user-agent generation covers both iPhone and iPad shapes deterministically
    def test_instagram_app_format(self, im_module, monkeypatch):
        pattern = re.compile(r"^Instagram \d+\.\d+\.\d+\.\d+ \((iPhone|iPad)[^)]*; iOS \d+_\d+; en_US; en-US; scale=\d\.\d\d; \d+x\d+; \d+\) AppleWebKit/420\+$")
        for is_iphone in (True, False):
            picks = [is_iphone]
            monkeypatch.setattr(random, "choice", lambda seq, picks=picks: picks.pop(0) if picks else seq[0])
            monkeypatch.setattr(random, "randint", lambda start, stop: start)
            ua = im_module.get_random_mobile_user_agent()
            assert pattern.match(ua), ua
