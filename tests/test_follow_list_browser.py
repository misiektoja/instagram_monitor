"""Offline tests for the experimental browser follower list source, with no browser started."""

from types import SimpleNamespace

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

    # A small difference is ordinary churn during a slow scan and is accepted
    def test_a_small_shortfall_is_accepted(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "browser_follow_list_batches", lambda *args, **kwargs: iter([[f"user{index}" for index in range(95)]]))

        assert len(list(im_module.iter_browser_follow_list(fake_bot(), fake_profile(followers=100), "followers"))) == 95

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
