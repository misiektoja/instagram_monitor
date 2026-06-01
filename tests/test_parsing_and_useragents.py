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
    def test_is_nonempty_browser_string(self, im_module):
        random.seed(1)
        for _ in range(50):
            ua = im_module.get_random_user_agent()
            assert ua.startswith("Mozilla/5.0")
            assert len(ua) > 30

    def test_covers_known_browser_families(self, im_module):
        random.seed(0)
        seen = set()
        for _ in range(400):
            ua = im_module.get_random_user_agent()
            if "Edg/" in ua:
                seen.add("edge")
            elif "Firefox/" in ua:
                seen.add("firefox")
            elif "Chrome/" in ua:
                seen.add("chrome")
            elif "Version/" in ua and "Safari/" in ua:
                seen.add("safari")
        # Over many samples all four families should appear
        assert {"chrome", "firefox", "edge", "safari"} <= seen


class TestGetRandomMobileUserAgent:
    def test_instagram_app_format(self, im_module):
        random.seed(2)
        pattern = re.compile(r"^Instagram \d+\.\d+\.\d+\.\d+ \((iPhone|iPad)[^)]*; iOS \d+_\d+; en_US; en-US; scale=\d\.\d\d; \d+x\d+; \d+\) AppleWebKit/420\+$")
        for _ in range(50):
            ua = im_module.get_random_mobile_user_agent()
            assert pattern.match(ua), ua
