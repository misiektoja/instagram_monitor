"""Offline tests for the experimental browser follower list source, with no browser started."""

from types import SimpleNamespace
from unittest.mock import Mock

import instaloader
import pytest


# Stands in for a Playwright page, answering the two scripts the harvester evaluates
class FakePage:
    # Takes the username lists the dialog renders in order, one per harvest step
    def __init__(self, frames, url="https://www.instagram.com/target.user/", scrollable=True, dialog_closes_after=None):
        self.frames = list(frames)
        self.url = url
        self.scrollable = scrollable
        self.dialog_closes_after = dialog_closes_after
        self.reads = 0
        self.scrolls = 0
        self.waits = []

    # Answers the scroll script with whether a scrollable box was found, and the names script with the next frame
    def evaluate(self, script):
        if "scrollTop" in script:
            self.scrolls += 1
            return self.scrollable
        self.reads += 1
        if self.dialog_closes_after is not None and self.reads > self.dialog_closes_after:
            return None
        return self.frames.pop(0) if self.frames else []

    # Records the pause the harvester asked for instead of sleeping
    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)


# Builds a target profile stub carrying the counts the shortfall guard compares against
def fake_profile(username="target.user", followers=0, followees=0):
    return SimpleNamespace(username=username, userid=4242, followers=followers, followees=followees)


# Builds a logged-in bot stub
def fake_bot(logged_in=True):
    return SimpleNamespace(context=SimpleNamespace(is_logged_in=logged_in, _session=SimpleNamespace()))


CHROME_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
FIREFOX_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0"
SAFARI_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
EDGE_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"


class TestDialogHarvest:
    # Names already yielded are never yielded again as the list grows under the scroll
    def test_only_new_names_are_yielded(self, im_module):
        page = FakePage([["a", "b"], ["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"]])

        batches = list(im_module.harvest_follow_list_dialog(page, 0))

        assert batches == [["a", "b"], ["c"]]

    # A list that stops growing ends the scan rather than scrolling for ever
    def test_a_stalled_dialog_ends_the_scan(self, im_module):
        page = FakePage([["a"]] * 10)

        list(im_module.harvest_follow_list_dialog(page, 0, stall_limit=3))

        assert page.scrolls == 3

    # A dialog with nothing to scroll is a short list that is already fully rendered
    def test_an_unscrollable_dialog_ends_the_scan(self, im_module):
        page = FakePage([["a", "b"]], scrollable=False)

        assert list(im_module.harvest_follow_list_dialog(page, 0)) == [["a", "b"]]
        assert page.scrolls == 1

    # A dialog that disappears mid-scan is reported rather than treated as a finished list
    def test_a_closed_dialog_is_reported(self, im_module):
        page = FakePage([["a"], ["a", "b"]], dialog_closes_after=1)

        with pytest.raises(im_module.BrowserFollowListError):
            list(im_module.harvest_follow_list_dialog(page, 0))

    # A stop request ends the scan between scrolls
    def test_a_stop_request_ends_the_scan(self, im_module):
        page = FakePage([["a"], ["a", "b"], ["a", "b", "c"]])
        stop_event = SimpleNamespace(is_set=lambda: page.scrolls >= 1)

        assert list(im_module.harvest_follow_list_dialog(page, 0, stop_event=stop_event)) == [["a"]]

    # Each scroll is followed by the configured pause
    def test_each_scroll_waits_the_configured_delay(self, im_module):
        page = FakePage([["a"], ["a", "b"]])

        list(im_module.harvest_follow_list_dialog(page, 1.5, stall_limit=2))

        assert page.waits and set(page.waits) == {1500}


class TestPageStateGuard:
    # An ordinary profile page is not an interruption
    def test_a_profile_page_passes(self, im_module):
        im_module.guard_browser_page_state(FakePage([], url="https://www.instagram.com/target.user/"))

    # Instagram answering with a challenge, a notice or the login page stops the scan
    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/challenge/?next=/target.user/",
        "https://www.instagram.com/accounts/suspended/",
        "https://www.instagram.com/accounts/disabled/",
        "https://www.instagram.com/accounts/login/?next=/target.user/",
    ])
    def test_an_interrupted_page_stops_the_scan(self, im_module, url):
        with pytest.raises(im_module.BrowserFollowListError):
            im_module.guard_browser_page_state(FakePage([], url=url))

    # A challenge is an action against the account, so it trips the durable breaker
    def test_a_challenge_is_an_account_level_failure(self, im_module):
        with pytest.raises(im_module.BrowserFollowListError) as raised:
            im_module.guard_browser_page_state(FakePage([], url="https://www.instagram.com/challenge/"))

        failure_class = im_module.classify_failure_class(im_module.format_error_message(raised.value))
        assert im_module.is_account_level_failure(failure_class) is True

    # A login page means the session is gone, which is also an account-level failure
    def test_a_login_page_is_an_account_level_failure(self, im_module):
        with pytest.raises(im_module.BrowserFollowListError) as raised:
            im_module.guard_browser_page_state(FakePage([], url="https://www.instagram.com/accounts/login/"))

        assert im_module.is_account_level_failure(im_module.classify_failure_class(im_module.format_error_message(raised.value))) is True

    # A dialog that never opens is an Instagram layout change, so it must not trip the breaker
    def test_a_missing_dialog_is_an_api_change(self, im_module):
        message = im_module.format_error_message(im_module.BrowserFollowListError("Instagram's follower list dialog did not open for target.user, so the page layout may have changed"))
        failure_class = im_module.classify_failure_class(message)

        assert failure_class == "schema_change"
        assert im_module.failure_class_group(failure_class) == "B"


class TestDialogOpening:
    # Browser layout errors give browser advice without claiming the API returned empty data
    def test_a_dialog_error_has_browser_recovery_advice(self, im_module):
        error = im_module.BrowserFollowListError("Instagram's follower list dialog could not be read for target.user: the profile's followers control could not be clicked")

        advice = im_module.classify_recovery_error(im_module.format_error_message(error))

        assert advice.code == "instagram.browser_dialog"
        assert "FOLLOW_LIST_BROWSER_HEADLESS" in advice.fix
        assert "FOLLOW_LIST_BROWSER_TIMEOUT" in advice.fix
        assert im_module.BROWSER_FOLLOW_LIST_GUIDE_URL in advice.fix
        assert "empty data" not in advice.fix

    # A click failure and a dialog that never renders names identify different failed steps
    @pytest.mark.parametrize("click_fails", [False, True])
    def test_the_failed_step_is_reported(self, im_module, click_fails):
        page = Mock(url="https://www.instagram.com/target.user/")
        cause = RuntimeError("selector did not become ready")
        if click_fails:
            page.locator.return_value.or_.return_value.first.click.side_effect = cause
        else:
            page.wait_for_selector.side_effect = cause

        with pytest.raises(im_module.BrowserFollowListError) as raised:
            im_module.open_browser_follow_list_dialog(page, "target.user", "following")

        assert ("control could not be clicked" if click_fails else "no profile links appeared") in str(raised.value)
        assert "following" in str(raised.value)
        assert raised.value.__cause__ is cause
        assert im_module.classify_failure_class(str(raised.value)) == "schema_change"

    # A redirect during either opening step retains the account-level failure instead of layout advice
    @pytest.mark.parametrize("click_fails", [False, True])
    @pytest.mark.parametrize("path, failure_class", [("challenge/", "challenge"), ("accounts/login/", "auth_expired")])
    def test_account_interruptions_take_priority(self, im_module, click_fails, path, failure_class):
        page = Mock(url=f"https://www.instagram.com/{path}")
        if click_fails:
            page.locator.return_value.or_.return_value.first.click.side_effect = RuntimeError("selector failed")
        else:
            page.wait_for_selector.side_effect = RuntimeError("selector failed")

        with pytest.raises(im_module.BrowserFollowListError) as raised:
            im_module.open_browser_follow_list_dialog(page, "target.user", "followers")

        assert im_module.classify_failure_class(str(raised.value)) == failure_class


class TestBrowserProvider:
    # Each rendered batch is counted against the account as it arrives
    def test_batches_are_counted_as_they_arrive(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([["a", "b"], ["c"]]))

        names = [entry.username for entry in im_module.iter_browser_follow_list(fake_bot(), fake_profile(followers=3), "followers", record_exposure=True)]

        assert names == ["a", "b", "c"]
        assert im_module.exposure_snapshot()["identities"] == 3

    # The daily budget caps a browser scan exactly as it caps the HTTP sources
    def test_the_daily_budget_caps_a_browser_scan(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "IDENTITY_BUDGET_PER_DAY", 3)
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([["a", "b"], ["c", "d"], ["e"]]))

        names = [entry.username for entry in im_module.iter_browser_follow_list(fake_bot(), fake_profile(followers=5), "followers", record_exposure=True)]

        assert names == ["a", "b", "c"]
        assert im_module.exposure_snapshot()["identities"] == 3

    # A dialog that stops rendering well short of the reported count is reported, never saved as complete
    def test_a_truncated_scan_is_reported(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([["a", "b"]]))

        with pytest.raises(im_module.BrowserFollowListError):
            list(im_module.iter_browser_follow_list(fake_bot(), fake_profile(followers=500), "followers"))

    # A small difference is ordinary churn during a slow scan, so the names are returned. Returning them is
    # not the same as saving them: reject_shrinking_username_baseline decides whether they may replace a
    # larger saved list, since a dialog that stalls this little looks identical to a drifting count
    def test_a_small_shortfall_is_accepted(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([[f"user{index}" for index in range(95)]]))

        assert len(list(im_module.iter_browser_follow_list(fake_bot(), fake_profile(followers=100), "followers"))) == 95

    # The tolerated shortfall is only safe because a later guard refuses to shrink a saved list with it. Checking
    # the generator alone says nothing about that, so this runs both halves of the decision
    def test_a_tolerated_shortfall_still_cannot_replace_a_larger_saved_list(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([[f"user{index}" for index in range(95)]]))
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        saved = [f"user{index}" for index in range(100)]

        returned = im_module.PaginatedUsernameResult(entry.username for entry in im_module.iter_browser_follow_list(fake_bot(), fake_profile(followers=100), "followers"))
        returned.complete = True
        im_module.reject_shrinking_username_baseline(returned, 100, saved, "followers", "target")

        assert len(returned) == 95, "the names are still returned, so the run can report the change"
        assert returned.complete is False, "but they must not replace the larger saved list"
        assert im_module.is_complete_username_baseline(returned, 100) is False
        assert "so the saved list is kept" in capsys.readouterr().out

    # A real unfollow moves the reported count with it, so the smaller list is still allowed to save
    def test_a_shortfall_the_reported_count_agrees_with_still_saves(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([[f"user{index}" for index in range(95)]]))
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        saved = [f"user{index}" for index in range(100)]

        returned = im_module.PaginatedUsernameResult(entry.username for entry in im_module.iter_browser_follow_list(fake_bot(), fake_profile(followers=95), "followers"))
        returned.complete = True
        im_module.reject_shrinking_username_baseline(returned, 95, saved, "followers", "target")

        assert returned.complete is True
        assert capsys.readouterr().out == ""

    # An anonymous session is reported as a login problem instead of starting a browser
    def test_an_anonymous_session_is_rejected(self, im_module):
        with pytest.raises(instaloader.exceptions.LoginRequiredException):
            list(im_module.iter_browser_follow_list(fake_bot(logged_in=False), fake_profile(), "followers"))

    # A missing Playwright package names the two commands that install it
    def test_a_missing_playwright_names_the_install_commands(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "playwright_available", lambda: False)

        with pytest.raises(im_module.BrowserFollowListError) as raised:
            list(im_module.browser_follow_list_batches(fake_bot(), fake_profile(), "followers"))

        assert "pip install playwright" in str(raised.value) and "playwright install chromium" in str(raised.value)

    # An unsupported kind is a programming error, not something to open a browser for
    def test_an_unknown_kind_is_rejected(self, im_module):
        with pytest.raises(ValueError):
            list(im_module.browser_follow_list_batches(fake_bot(), fake_profile(), "friends"))


class TestBrowserSetup:
    # Session cookies are handed to the browser for the Instagram domain
    def test_session_cookies_are_scoped_to_instagram(self, im_module):
        import requests

        session = requests.Session()
        session.cookies.update({"sessionid": "abc", "csrftoken": "def", "empty": ""})
        cookies = im_module.browser_session_cookies(SimpleNamespace(context=SimpleNamespace(_session=session)))

        assert {cookie["name"] for cookie in cookies} == {"sessionid", "csrftoken"}
        assert all(cookie["domain"] == ".instagram.com" and cookie["secure"] is True for cookie in cookies)

    # Proxy credentials are passed as fields, since Chromium ignores them inside the server URL
    def test_proxy_credentials_are_kept_out_of_the_server_url(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PROXY_ENABLED", True)
        monkeypatch.setattr(im_module, "PROXY_URL", "http://bob:secret@proxy.example:3128")

        settings = im_module.browser_proxy_settings()

        assert settings == {"server": "http://proxy.example:3128", "username": "bob", "password": "secret"}
        assert "secret" not in settings["server"]

    # No proxy configured means the browser is launched without one
    def test_no_proxy_means_no_proxy_settings(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "PROXY_ENABLED", False)

        assert im_module.browser_proxy_settings() is None
        assert "proxy" not in im_module.browser_launch_options()

    # The launch options follow the configured browser, window mode and user agent
    def test_launch_options_follow_the_settings(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_HEADLESS", False)
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chrome")
        monkeypatch.setattr(im_module, "USER_AGENT", "Mozilla/5.0 Test")

        options = im_module.browser_launch_options()

        assert options["headless"] is False
        assert options["channel"] == "chrome"
        assert options["user_agent"] == "Mozilla/5.0 Test"
        assert "--disable-blink-features=AutomationControlled" in options["args"]

    # Each session account keeps its own profile directory, with the name made safe for a path
    def test_each_account_keeps_its_own_profile(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_PROFILE_DIR", str(tmp_path))
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "some/acct")
        first = im_module.browser_profile_dir()
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "other.acct")

        assert first != im_module.browser_profile_dir()
        assert "/" not in im_module.os.path.basename(first)


class TestSourceSelection:
    # The browser source is used only when it was asked for by name
    def test_the_browser_source_is_selected_by_name(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "browser")
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([["a"]]))

        names = [entry.username for entry in im_module.follow_list_generator(fake_bot(), fake_profile(followers=1), "followers")]

        assert names == ["a"]

    # Auto never reaches for the browser, since it is slower, heavier and experimental
    def test_auto_never_selects_the_browser(self, im_module, monkeypatch):
        started = False

        # Fails the test if the automatic source ever opens a browser
        def never(*args, **kwargs):
            nonlocal started
            started = True
            return iter([])

        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "auto")
        monkeypatch.setattr(im_module, "browser_follow_list_batches", never)
        monkeypatch.setattr(im_module, "iter_rest_follow_list", lambda *args, **kwargs: iter([]))

        list(im_module.follow_list_generator(fake_bot(), fake_profile(), "followers"))

        assert started is False

    # The startup summary names the browser source as experimental so it is never mistaken for a default
    def test_the_summary_names_the_browser_source(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "browser")
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_HEADLESS", True)
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")

        assert im_module.follow_list_source_display() == "browser (experimental, headless chromium)"

    # The shipped template offers every browser setting with a working default
    def test_the_template_ships_the_browser_settings(self, im_module):
        parsed = im_module.parse_config_content(im_module.CONFIG_BLOCK, "<built-in>")

        assert parsed["FOLLOW_LIST_BROWSER_CHANNEL"] == "chromium"
        assert parsed["FOLLOW_LIST_BROWSER_HEADLESS"] is True
        assert parsed["FOLLOW_LIST_BROWSER_PROFILE_DIR"] == ""
        assert parsed["FOLLOW_LIST_BROWSER_SCROLL_DELAY"] == 1.5
        assert parsed["FOLLOW_LIST_BROWSER_TIMEOUT"] == 30


class TestDoctorReadiness:
    # Doctor names the install commands when the browser source is selected without Playwright
    def test_a_missing_playwright_is_reported(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "playwright_available", lambda: False)

        ready, detail, fix = im_module.browser_follow_list_readiness()

        assert ready is False
        assert "not installed" in detail
        assert "pip install playwright" in fix

    # A browser installed outside Playwright is reported as checked only when a scan runs
    def test_an_external_channel_is_reported_as_unchecked(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "playwright_available", lambda: True)
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chrome")

        ready, detail, fix = im_module.browser_follow_list_readiness()

        assert ready is True and fix == ""
        assert "chrome" in detail


class TestBrowserIdentityAlignment:
    # A Chromium build cannot honestly present a Firefox or Safari agent, so the families have to line up
    @pytest.mark.parametrize("channel, expected", [("chromium", "chrome"), ("chrome", "chrome"), ("msedge", "edge"), ("", "chrome"), ("Chromium", "chrome")])
    def test_each_channel_reports_the_family_it_presents(self, im_module, monkeypatch, channel, expected):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", channel)

        assert im_module.browser_channel_family() == expected

    # A pinned target carries its version, which does not change the browser it impersonates
    @pytest.mark.parametrize("target, expected", [("chrome", "chrome"), ("chrome131", "chrome"), ("safari_ios", "safari"), ("edge99", "edge"), ("", "")])
    def test_a_versioned_target_keeps_its_family(self, im_module, target, expected):
        assert im_module.impersonate_family(target) == expected

    # An aligned session presents one browser everywhere, so nothing is reported
    def test_an_aligned_session_reports_no_mismatch(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)

        assert im_module.browser_identity_mismatch() is None

    # The stock transport cannot present a browser handshake, so one session would arrive as two clients
    def test_the_stock_transport_is_reported_as_a_mismatch(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)

        detail, fix = im_module.browser_identity_mismatch()
        assert "requests" in detail and "two different clients" in detail
        assert "HTTP_BACKEND" in fix

    # curl_cffi selected but absent leaves the stock transport in place, which is the same mismatch
    def test_a_missing_curl_cffi_is_reported_as_a_mismatch(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", False)
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)

        assert im_module.browser_identity_mismatch() is not None

    # This is the default-configuration defect: a random agent from another family against a Chromium build
    @pytest.mark.parametrize("agent, named", [(FIREFOX_AGENT, "firefox"), (SAFARI_AGENT, "safari")])
    def test_an_agent_from_another_family_is_reported(self, im_module, monkeypatch, agent, named):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "USER_AGENT", agent)

        detail, fix = im_module.browser_identity_mismatch()
        assert named in detail and "announce itself as a browser it is not" in detail
        assert "USER_AGENT" in fix

    # A pinned target overrides the agent, so it is checked even when the agent itself agrees
    def test_a_pinned_target_from_another_family_is_reported(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "firefox")
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)

        detail, fix = im_module.browser_identity_mismatch()
        assert "CURL_CFFI_IMPERSONATE" in fix and "firefox" in detail

    # An Edge channel is aligned by an Edge agent, not by the Chrome default
    def test_the_edge_channel_is_aligned_by_an_edge_agent(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "msedge")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "USER_AGENT", EDGE_AGENT)

        assert im_module.browser_identity_mismatch() is None

    # A pinned family always produces an agent of that family, so the random pool cannot break the alignment
    @pytest.mark.parametrize("family", ["chrome", "edge", "firefox", "safari"])
    def test_a_pinned_family_produces_an_agent_of_that_family(self, im_module, family):
        for _ in range(30):
            assert im_module._impersonate_target_from_ua(im_module.get_random_user_agent(family)) == family

    # No family keeps the original random pool, so ordinary runs still vary
    def test_no_family_still_varies(self, im_module):
        families = {im_module._impersonate_target_from_ua(im_module.get_random_user_agent()) for _ in range(200)}

        assert len(families) > 1


class TestBrowserIdentityGates:
    # Doctor has to explain the mismatch, so it reports a failure row instead of the experimental warning
    def test_doctor_fails_on_a_mismatched_identity(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "browser")
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "USER_AGENT", FIREFOX_AGENT)
        monkeypatch.setattr(im_module, "browser_follow_list_readiness", lambda: (True, "Channel: chromium", ""))

        rows = [check for check in im_module.doctor_check_configuration(["target.user"]) if "browser follower list" in check.label]

        assert len(rows) == 1
        assert rows[0].status == "FAIL"
        assert "firefox" in rows[0].detail
        assert rows[0].advice is not None and rows[0].advice.fix

    # An aligned identity leaves the experimental warning as the only browser row
    def test_doctor_keeps_the_experimental_warning_when_aligned(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "browser")
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)
        monkeypatch.setattr(im_module, "browser_follow_list_readiness", lambda: (True, "Channel: chromium", ""))

        statuses = {check.status for check in im_module.doctor_check_configuration(["target.user"]) if "browser" in check.label.casefold()}

        assert statuses == {"WARN"}

    # Monitoring must not start on an identity the browser source cannot present honestly
    def test_monitoring_refuses_to_start_on_a_mismatch(self, im_module, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--no-color", "--disable-logging", "--follow-list-source", "browser", "--user-agent", FIREFOX_AGENT])
        monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "find_config_file", lambda path=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: True)

        with pytest.raises(SystemExit) as error:
            im_module.run_main()

        output = capsys.readouterr().out
        assert error.value.code == 1
        assert "firefox" in output and "* To fix: " in output
        assert im_module.FOLLOW_LIST_SOURCE_GUIDE_URL in output

    # A random agent must not silently make a Chromium build claim another browser
    def test_the_random_agent_follows_the_browser_channel(self, im_module, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--no-color", "--disable-logging", "--follow-list-source", "browser"])
        monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
        monkeypatch.setattr(im_module, "USER_AGENT", "")
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "msedge")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "find_config_file", lambda path=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: True)
        monkeypatch.setattr(im_module, "start_dashboard_input_handler", Mock(side_effect=SystemExit(0)))

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert im_module._impersonate_target_from_ua(im_module.USER_AGENT) == "edge"
        assert im_module.browser_identity_mismatch() is None


class TestEffectiveIdentityReport:
    # The report has to name the target and the agents, not only flag a mismatch
    def test_doctor_states_the_impersonated_identity(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)
        monkeypatch.setattr(im_module, "USER_AGENT_MOBILE", "Instagram 445.0.0.1.100 (iPhone17,1; iOS 26_0)")

        rows = [check for check in im_module.doctor_check_configuration(["target.user"]) if "Requests reach Instagram" in check.label]

        assert len(rows) == 1
        assert rows[0].status == "PASS"
        assert rows[0].label.endswith("chrome")
        assert "auto -> chrome" in rows[0].detail
        assert CHROME_AGENT in rows[0].detail
        assert "iPhone17,1" in rows[0].detail

    # A pinned target must be reported as itself rather than as a resolved Auto
    def test_doctor_reports_a_pinned_target_without_the_auto_arrow(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "safari")
        monkeypatch.setattr(im_module, "USER_AGENT", SAFARI_AGENT)

        row = next(check for check in im_module.doctor_check_configuration(["target.user"]) if "Requests reach Instagram" in check.label)

        assert "auto ->" not in row.detail
        assert "impersonating safari" in row.detail

    # The stock transport cannot present a browser handshake, so the report has to say so and name the fix
    def test_doctor_warns_that_the_requests_backend_is_not_a_browser(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)

        row = next(check for check in im_module.doctor_check_configuration(["target.user"]) if "Requests reach Instagram" in check.label)

        assert row.status == "WARN"
        assert "curl_cffi" in row.advice.fix
        assert row.advice.fix.endswith(f"\nGuide: {im_module.HTTP_BACKEND_GUIDE_URL}")

    # An empty agent must not leave a dangling label in the detail line
    def test_doctor_omits_an_agent_that_is_not_set_yet(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
        monkeypatch.setattr(im_module, "USER_AGENT", CHROME_AGENT)
        monkeypatch.setattr(im_module, "USER_AGENT_MOBILE", "")

        row = next(check for check in im_module.doctor_check_configuration(["target.user"]) if "Requests reach Instagram" in check.label)

        assert "Mobile agent" not in row.detail
        assert row.detail.endswith(CHROME_AGENT)


class TestChromiumProbeIsolation:
    # Stopping the Playwright driver logs asyncio noise, so the probe must not run in this process
    def test_the_probe_runs_in_a_child_process(self, im_module, monkeypatch):
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0, stdout="/tmp/chromium\n", stderr="noise\n")

        monkeypatch.setattr(im_module.subprocess, "run", fake_run)

        assert im_module.browser_chromium_executable() == ("/tmp/chromium", "")
        assert calls[0][0][0] == im_module.sys.executable
        assert "sync_playwright" in calls[0][0][2]
        assert calls[0][1]["capture_output"] is True

    # A failing probe has to surface the child's own last message, not a bare exit code
    def test_a_failed_probe_reports_the_last_stderr_line(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.subprocess, "run", lambda command, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="Traceback\nModuleNotFoundError: playwright\n"))

        assert im_module.browser_chromium_executable() == ("", "ModuleNotFoundError: playwright")

    # A silent non-zero exit still needs a readable reason
    def test_a_silent_failure_reports_the_exit_code(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.subprocess, "run", lambda command, **kwargs: SimpleNamespace(returncode=3, stdout="", stderr=""))

        assert im_module.browser_chromium_executable() == ("", "the probe exited with code 3")

    # A probe that never returns must not hang the doctor run
    def test_a_probe_that_raises_is_reported_as_an_error(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module.subprocess, "run", Mock(side_effect=OSError("no such executable")))

        executable, error = im_module.browser_chromium_executable()

        assert executable == ""
        assert "no such executable" in error

    # Readiness reports the probe's failure rather than claiming the browser source can run
    def test_readiness_fails_when_the_probe_fails(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "playwright_available", lambda: True)
        monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
        monkeypatch.setattr(im_module, "browser_chromium_executable", lambda: ("", "driver crashed"))

        ready, detail, fix = im_module.browser_follow_list_readiness()

        assert ready is False
        assert "driver crashed" in detail
        assert fix
