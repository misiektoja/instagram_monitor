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

    # Every agent has to classify back to the family that produced it, or the impersonation target drifts
    @pytest.mark.parametrize("family", ["chrome", "firefox", "edge", "safari"])
    def test_each_family_classifies_back_to_itself(self, im_module, family):
        for _ in range(40):
            assert im_module._impersonate_target_from_ua(im_module.get_random_user_agent(family)) == family

    # The engine tokens are fixed in the real browsers, so randomising them would produce a string no browser sends
    @pytest.mark.parametrize("family, required", [("chrome", "AppleWebKit/537.36 (KHTML, like Gecko)"), ("edge", "AppleWebKit/537.36 (KHTML, like Gecko)"), ("safari", "AppleWebKit/605.1.15 (KHTML, like Gecko)"), ("firefox", "Gecko/20100101")])
    def test_the_engine_token_is_the_one_the_browser_really_sends(self, im_module, family, required):
        for _ in range(20):
            assert required in im_module.get_random_user_agent(family)

    # Chrome, Edge and Safari freeze the macOS version they report rather than naming the real release
    @pytest.mark.parametrize("family", ["chrome", "edge", "safari"])
    def test_the_reported_macos_version_is_the_frozen_one(self, im_module, family):
        for _ in range(40):
            agent = im_module.get_random_user_agent(family)
            if "Macintosh" in agent:
                assert f"Intel Mac OS X {im_module.USER_AGENT_MAC_OS})" in agent or f"Intel Mac OS X {im_module.USER_AGENT_MAC_OS};" in agent

    # Chrome has reported a zeroed build and patch since it reduced user agent granularity
    def test_chrome_reports_a_zeroed_build(self, im_module):
        for _ in range(20):
            assert re.search(r"Chrome/\d+\.0\.0\.0(?: |$)", im_module.get_random_user_agent("chrome"))

    # The Edge targets curl_cffi ships predate that convention, so their real build numbers are sent instead
    def test_a_pre_zeroing_edge_reports_its_real_builds(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {"edge99", "edge101", "edge"})

        agent = im_module.get_random_user_agent("edge")
        chrome_build, edge_build = im_module.EDGE_AGENT_BUILDS[101]
        assert agent == f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_build} Safari/537.36 Edg/{edge_build}"

    # An Edge new enough to zero its builds has no recorded pair, so the zeroed form is used
    def test_a_post_zeroing_edge_reports_a_zeroed_build(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {"edge140", "edge"})

        assert "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0" in im_module.get_random_user_agent("edge")

    # curl_cffi pins sec-ch-ua-platform per family and a User-Agent override does not change it, so the
    # agent has to name the platform that header already claims
    @pytest.mark.parametrize("family, platform", [("chrome", "Macintosh"), ("edge", "Windows NT 10.0")])
    def test_the_platform_follows_the_pinned_client_hint(self, im_module, monkeypatch, family, platform):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)

        for _ in range(40):
            assert platform in im_module.get_random_user_agent(family)

    # The stock transport sends no client hints, so there is nothing for the platform to contradict
    def test_the_platform_still_varies_without_curl_cffi(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")

        platforms = {"Macintosh" in im_module.get_random_user_agent("chrome") for _ in range(200)}
        assert platforms == {True, False}

    # An advertised version the transport does not impersonate is the mismatch this pairing exists to avoid
    @pytest.mark.parametrize("family, pattern", [("chrome", r"Chrome/(\d+)\."), ("edge", r"Edg/(\d+)\.")])
    def test_the_chromium_version_matches_what_curl_cffi_impersonates(self, im_module, monkeypatch, family, pattern):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {f"{family}131_android", f"{family}142", f"{family}146", family})

        for _ in range(20):
            found = re.search(pattern, im_module.get_random_user_agent(family))
            assert found and int(found.group(1)) == 146

    # Without curl_cffi there is no impersonated version to match, so the fallback range applies
    @pytest.mark.parametrize("family, pattern", [("chrome", r"Chrome/(\d+)\."), ("edge", r"Edg/(\d+)\.")])
    def test_the_fallback_range_applies_without_curl_cffi(self, im_module, monkeypatch, family, pattern):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: set())
        low, high = im_module.USER_AGENT_CHROME_VERSIONS

        for _ in range(40):
            found = re.search(pattern, im_module.get_random_user_agent(family))
            assert found and low <= int(found.group(1)) <= high

    # Only the plain numbered target names a desktop version, so the android and lettered ones are ignored
    def test_only_plain_numbered_targets_set_the_version(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {"chrome131_android", "chrome133a", "chrome124", "chrome_android", "chrome"})

        assert im_module.curl_cffi_alias_version("chrome") == 124

    # Firefox and Safari versions are not derived, so their pools have to stay current on their own
    @pytest.mark.parametrize("family, pattern, floor", [("firefox", r"Firefox/(\d+)\.", "USER_AGENT_FIREFOX_VERSIONS"), ("safari", r"Version/(\d+)\.", "USER_AGENT_SAFARI_VERSIONS")])
    def test_no_agent_falls_below_the_configured_floor(self, im_module, family, pattern, floor):
        low, high = getattr(im_module, floor)
        assert low <= high
        for _ in range(40):
            found = re.search(pattern, im_module.get_random_user_agent(family))
            assert found and low <= int(found.group(1)) <= high

    # curl_cffi cannot present a current Edge, so an unpinned run must not pick that identity by chance
    def test_edge_is_never_chosen_at_random(self, im_module):
        assert "edge" not in {im_module._impersonate_target_from_ua(im_module.get_random_user_agent()) for _ in range(300)}
        assert im_module._impersonate_target_from_ua(im_module.get_random_user_agent("edge")) == "edge"


class TestGetRandomMobileUserAgent:
    # Mobile user-agent generation covers both iPhone and iPad shapes deterministically
    def test_instagram_app_format(self, im_module, monkeypatch):
        pattern = re.compile(r"^Instagram \d+\.0\.0\.\d+\.\d+ \((iPhone|iPad)[^)]*; iOS \d+_\d+; en_US; en-US; scale=\d\.\d\d; \d+x\d+; \d+\) AppleWebKit/420\+$")
        for is_iphone in (True, False):
            picks = [is_iphone]
            monkeypatch.setattr(random, "choice", lambda seq, picks=picks: picks.pop(0) if picks else seq[0])
            monkeypatch.setattr(random, "randint", lambda start, stop: start)
            ua = im_module.get_random_mobile_user_agent()
            assert pattern.match(ua), ua

    # A device that cannot run the iOS release it claims is an impossible pair, so the two pools have to agree
    def test_the_device_and_the_ios_release_are_a_possible_pair(self, im_module):
        assert im_module.MOBILE_IPHONE_MODELS and im_module.MOBILE_IPAD_MODELS
        for model, (width, height) in im_module.MOBILE_IPHONE_MODELS + im_module.MOBILE_IPAD_MODELS:
            generation = int(model.split(",")[0])
            assert generation >= 13, model
            assert height > width, model

    # Apple went straight from iOS 18 to iOS 26, so a ranged pool would claim releases that never shipped
    def test_only_shipped_ios_majors_are_claimed(self, im_module):
        assert set(im_module.MOBILE_IOS_MAJORS).isdisjoint(range(19, 26))
        for _ in range(60):
            found = re.search(r"iOS (\d+)_", im_module.get_random_mobile_user_agent())
            assert found and int(found.group(1)) in im_module.MOBILE_IOS_MAJORS

    # A device reports one fixed display scale, so picking it independently would describe hardware that does not exist
    def test_the_scale_follows_the_device(self, im_module):
        for _ in range(60):
            agent = im_module.get_random_mobile_user_agent()
            assert ("scale=3.00" if "(iPhone" in agent else "scale=2.00") in agent

    # The Instagram app version has to stay near the released one, since a years-old build is itself a signal
    def test_the_app_version_pool_is_current(self, im_module):
        low, high = im_module.MOBILE_APP_VERSIONS
        assert low <= high
        for _ in range(40):
            found = re.match(r"Instagram (\d+)\.", im_module.get_random_mobile_user_agent())
            assert found and low <= int(found.group(1)) <= high
