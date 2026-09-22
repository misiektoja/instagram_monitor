"""Browser-level dashboard tests using a real headless Chromium instance."""

import re
import threading
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from werkzeug.serving import make_server


playwright_sync = pytest.importorskip("playwright.sync_api")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Launches headless Chromium, skipping only when the Playwright package is present without its browser download
def launch_chromium(playwright):
    try:
        return playwright.chromium.launch(headless=True)
    except playwright_sync.Error as error:
        # Any other launch failure is a real problem and must fail rather than silently skip
        if "executable doesn't exist" not in str(error).casefold():
            raise
        pytest.skip("Chromium is not installed, run 'python -m playwright install chromium'")


# Runs the real dashboard application on an ephemeral loopback port
@pytest.fixture
def dashboard_server(im_module, monkeypatch) -> Iterator[str]:
    # Targets added through the running app sync into the module-global list, so isolate it from later tests
    monkeypatch.setattr(im_module, "TARGET_USERNAMES", [])
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_TEMPLATE_DIR", str(PROJECT_ROOT / "templates"))
    monkeypatch.setattr(im_module, "SESSION_USERNAME", "")
    monkeypatch.setattr(im_module, "SKIP_SESSION", True)
    monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 5400)
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_DATA", {"session": {"username": None, "active": False}, "targets": {"target.user": {"status": "Waiting", "posts": 7, "followers": 11, "followings": 5}}, "activities": [], "check_count": 2, "last_check": "Never", "next_check": "Pending", "is_monitoring": False})
    monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
    app = im_module.create_web_dashboard_app()
    assert app is not None
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    thread.join(timeout=5)


# Verifies rendered dashboard data, navigation and target creation in Chromium
@pytest.mark.e2e
def test_dashboard_user_flow_in_chromium(dashboard_server):
    server_url = dashboard_server
    page_errors = []
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        response = page.goto(server_url, wait_until="domcontentloaded")
        assert response is not None
        assert response.ok
        playwright_sync.expect(page).to_have_title("Instagram Monitor - Control Panel")
        playwright_sync.expect(page.locator("#active-targets")).to_have_text("1")
        playwright_sync.expect(page.locator("#dashboard-targets-simple-body")).to_contain_text("target.user")
        page.locator('[data-page="targets"]').click()
        playwright_sync.expect(page.locator("#page-targets")).to_have_class(re.compile(r"\bactive\b"))
        page.locator("#page-targets").get_by_role("button", name="Add Target").click()
        page.locator("#modal-add-target .toggle-slider").click()
        assert not page.locator("#start-immediately").is_checked()
        page.locator("#new-target-username").fill("Added.User")
        page.locator("#modal-add-target").get_by_role("button", name="Add Target").click()
        playwright_sync.expect(page.locator("#toast-message")).to_contain_text("Added target: added.user")
        playwright_sync.expect(page.locator("#targets-list")).to_contain_text("added.user")
        assert page_errors == []
        browser.close()


# Opens synthetic story data with every nonlocal browser request intercepted
@pytest.fixture
def story_dashboard_page(dashboard_server, im_module, monkeypatch):
    monkeypatch.setattr(im_module, "DASHBOARD_MODE", "user")
    external_requests = []

    # Serves external destinations locally so even a failed warning cannot contact Instagram
    def route_request(route):
        if urlsplit(route.request.url).netloc == urlsplit(dashboard_server).netloc:
            route.continue_()
        else:
            external_requests.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body="Offline destination")

    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        context = browser.new_context(service_workers="block")
        context.route("**/*", route_request)
        page = context.new_page()
        page.set_default_timeout(3000)
        yield page, context, external_requests, dashboard_server
        browser.close()


# Requires confirmation on every story surface for both current and older records
@pytest.mark.e2e
@pytest.mark.parametrize("surface", ["fetched", "legacy", "dashboard", "config", "activity"])
@pytest.mark.parametrize("story_flag", [True, None, False])
def test_story_warning_guards_navigation_in_chromium(story_dashboard_page, im_module, surface, story_flag):
    page, context, external_requests, server_url = story_dashboard_page
    story_url = "https://www.instagram.com/stories/target.user/123/"
    update = {"type": "Image", "user": "target.user", "post_url": story_url}
    details = {"url": story_url}
    if story_flag is not None:
        update["is_story"] = story_flag
        details["is_story"] = story_flag
    if surface == "legacy":
        im_module.WEB_DASHBOARD_DATA["targets"]["target.user"]["last_story"] = update
    else:
        im_module.WEB_DASHBOARD_DATA["targets"]["target.user"]["fetched_updates"] = [update]
    im_module.WEB_DASHBOARD_DATA["activities"] = [{"time": "12:00", "message": "New story item", "level": "update", "details": details}]
    page.goto(server_url, wait_until="domcontentloaded")
    if surface in ("fetched", "legacy"):
        control = page.locator("#last-fetched-container").get_by_text(re.compile(r"^View (Story|Post)$"))
        playwright_sync.expect(control).to_have_text("View Story")
    else:
        if surface == "config":
            page.locator("#mode-config-btn").click()
        elif surface == "activity":
            page.locator('[data-page="activity"]').click()
        feed_id = {"dashboard": "dashboard-activity", "config": "dashboard-activity-config", "activity": "activity-feed"}[surface]
        control = page.locator(f"#{feed_id}").get_by_text("View", exact=True)
    modal = page.locator("#modal-anonymity")
    for activation in ("click", "middle", "modified", "keyboard"):
        if activation == "middle":
            control.click(button="middle")
        elif activation == "modified":
            control.click(modifiers=["ControlOrMeta"])
        elif activation == "keyboard":
            control.press("Enter")
        else:
            control.click()
        playwright_sync.expect(modal).to_be_visible()
        playwright_sync.expect(modal).to_contain_text("Warning")
        playwright_sync.expect(page.locator("#anonymity-confirm-link")).to_have_attribute("href", story_url)
        assert external_requests == []
        assert len(context.pages) == 1
        modal.get_by_role("button", name="Cancel", exact=True).click()
        playwright_sync.expect(modal).to_be_hidden()

    control.click()
    page.keyboard.press("Escape")
    playwright_sync.expect(modal).to_be_hidden()
    control.click()
    modal.click(position={"x": 5, "y": 5})
    playwright_sync.expect(modal).to_be_hidden()
    assert control.get_attribute("href") is None
    control.click()
    with page.expect_popup() as popup_info:
        modal.get_by_role("link", name="I Understand, Proceed").click()
    popup_info.value.wait_for_load_state()
    assert external_requests == [story_url]
    playwright_sync.expect(modal).to_be_hidden()


# Leaves post links and downloaded images accessible without a story warning
@pytest.mark.e2e
def test_posts_and_local_media_do_not_require_story_confirmation(story_dashboard_page, im_module):
    page, context, external_requests, server_url = story_dashboard_page
    post_url = "https://www.instagram.com/p/offline/"
    im_module.WEB_DASHBOARD_DATA["targets"]["target.user"]["fetched_updates"] = [
        {"type": "Post", "post_url": post_url, "url": "/media/post.jpg", "video_url": None, "is_story": False},
        {"type": "Story Video", "post_url": "https://www.instagram.com/stories/target.user/", "video_url": "/media/story.mp4", "is_story": True},
    ]
    page.add_init_script("HTMLMediaElement.prototype.play = () => Promise.resolve()")
    page.goto(server_url, wait_until="domcontentloaded")
    modal = page.locator("#modal-anonymity")
    with page.expect_popup() as post_popup:
        page.get_by_role("link", name="View Post", exact=True).click()
    post_popup.value.wait_for_load_state()
    assert external_requests == [post_url]
    playwright_sync.expect(modal).to_be_hidden()
    with page.expect_popup() as media_popup:
        page.get_by_role("link", name="View Media", exact=True).click()
    media_popup.value.wait_for_load_state()
    assert media_popup.value.url == server_url + "media/post.jpg"
    page.get_by_role("link", name="Play Video", exact=True).click()
    playwright_sync.expect(page.locator("#modal-video-player")).to_be_visible()
    playwright_sync.expect(page.locator("#local-video-element")).to_have_attribute("src", server_url + "media/story.mp4")
    playwright_sync.expect(modal).to_be_hidden()
    assert external_requests == [post_url]


# Verifies the connection card is filled from the settings endpoint and saves what the user picks
@pytest.mark.e2e
def test_connection_settings_save_from_chromium(dashboard_server, im_module, monkeypatch):
    monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")
    monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
    monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "auto")
    monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
    monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {"chrome", "firefox"})
    monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)
    page_errors = []
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(dashboard_server, wait_until="domcontentloaded")
        page.locator('[data-page="settings"]').click()

        playwright_sync.expect(page.locator("#http-backend")).to_have_value("requests")
        # Only curl_cffi acts on an impersonation target, so the stock transport hides that question
        playwright_sync.expect(page.locator("#impersonate-group")).to_be_hidden()
        page.locator("#http-backend").select_option("curl_cffi")
        playwright_sync.expect(page.locator("#impersonate-group")).to_be_visible()
        assert page.locator("#impersonate option").all_text_contents() == ["Auto (match the user agent)", "chrome", "firefox"]
        page.locator("#impersonate").select_option("firefox")
        page.locator("#page-settings").get_by_role("button", name="Save Settings").click()
        playwright_sync.expect(page.locator("#toast-message")).to_contain_text("Settings saved")

        # The browser source drives a Chromium build, so it only saves alongside a Chromium target
        page.locator("#impersonate").select_option("chrome")
        page.locator("#follow-list-source").select_option("browser")
        playwright_sync.expect(page.locator("#connection-note")).to_contain_text("experimental")
        page.locator("#page-settings").get_by_role("button", name="Save Settings").click()
        playwright_sync.expect(page.locator("#toast-message")).to_contain_text("Settings saved")

        assert im_module.HTTP_BACKEND == "curl_cffi"
        assert im_module.CURL_CFFI_IMPERSONATE == "chrome"
        assert im_module.FOLLOW_LIST_SOURCE == "browser"
        assert page_errors == []
        browser.close()


# Verifies the dashboard cannot put a running session into the split identity monitoring refuses to start in
@pytest.mark.e2e
def test_a_split_identity_cannot_be_saved_in_chromium(dashboard_server, im_module, monkeypatch):
    monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
    monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "auto")
    monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "auto")
    monkeypatch.setattr(im_module, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium")
    monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", True)
    monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {"chrome", "firefox"})
    monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.goto(dashboard_server, wait_until="domcontentloaded")
        page.locator('[data-page="settings"]').click()

        page.locator("#impersonate").select_option("firefox")
        page.locator("#follow-list-source").select_option("browser")
        page.locator("#page-settings").get_by_role("button", name="Save Settings").click()

        playwright_sync.expect(page.locator("#toast-message")).to_contain_text("two different clients")
        assert im_module.FOLLOW_LIST_SOURCE == "auto"
        assert im_module.CURL_CFFI_IMPERSONATE == "auto"
        browser.close()


# Verifies a machine without curl_cffi cannot pick it, rather than saving a transport every request would fail on
@pytest.mark.e2e
def test_an_uninstalled_transport_cannot_be_selected_in_chromium(dashboard_server, im_module, monkeypatch):
    monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")
    monkeypatch.setattr(im_module, "_CURL_CFFI_AVAILABLE", False)
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.goto(dashboard_server, wait_until="domcontentloaded")
        page.locator('[data-page="settings"]').click()

        option = page.locator('#http-backend option[value="curl_cffi"]')
        playwright_sync.expect(option).to_be_disabled()
        playwright_sync.expect(option).to_contain_text("not installed")
        playwright_sync.expect(page.locator("#http-backend")).to_have_value("requests")
        browser.close()


# Runs the dashboard seeded with a hostile Instagram-supplied media item
@pytest.fixture
def hostile_media_server(im_module, monkeypatch) -> Iterator[str]:
    # Targets added through the running app sync into the module-global list, so isolate it from later tests
    monkeypatch.setattr(im_module, "TARGET_USERNAMES", [])
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_TEMPLATE_DIR", str(PROJECT_ROOT / "templates"))
    monkeypatch.setattr(im_module, "SESSION_USERNAME", "")
    monkeypatch.setattr(im_module, "SKIP_SESSION", True)
    monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 5400)
    hostile_update = {
        "type": "Post",
        "caption": "holiday",
        "timestamp": "01 Jan 26 10:00",
        "user": "target.user",
        "is_story": False,
        "url": 'https://cdn.example/a.jpg" onerror="window.__xss_img=1',
        "post_url": 'https://www.instagram.com/p/x/" onmouseover="window.__xss_href=1" data-x="',
        "video_url": "javascript:window.__xss_scheme=1",
    }
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_DATA", {"session": {"username": None, "active": False}, "targets": {"target.user": {"status": "Waiting", "fetched_updates": [hostile_update]}}, "activities": [], "check_count": 1, "last_check": "Never", "next_check": "Pending", "is_monitoring": False})
    monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
    app = im_module.create_web_dashboard_app()
    assert app is not None
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    thread.join(timeout=5)


# Verifies Instagram-supplied media URLs cannot break out of their attribute or smuggle a javascript scheme
@pytest.mark.e2e
def test_hostile_media_urls_do_not_execute_in_chromium(hostile_media_server):
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.goto(hostile_media_server, wait_until="domcontentloaded")
        page.wait_for_selector(".fetched-history-item")

        assert page.evaluate("() => [window.__xss_img, window.__xss_href, window.__xss_scheme]") == [None, None, None]
        assert page.locator("[onerror]").count() == 0
        assert page.locator("[onmouseover]").count() == 0
        assert page.evaluate("() => Array.from(document.querySelectorAll('.fetched-history-item a')).every(a => a.protocol === 'http:' || a.protocol === 'https:')")

        browser.close()


# Mimics the structure of Instagram's follower dialog: a scrollable box that appends more entries as it scrolls
FOLLOW_DIALOG_PAGE = """
<html><body>
<div role="dialog">
  <div id="scroller" style="height:300px;overflow-y:auto">
    <div id="items"></div>
  </div>
</div>
<script>
  const items = document.getElementById('items');
  let next = 0;
  function add(count) {
    for (let i = 0; i < count; i++) {
      const link = document.createElement('a');
      link.setAttribute('href', '/user' + next + '/');
      link.textContent = 'user' + next;
      link.style.display = 'block';
      link.style.height = '60px';
      items.appendChild(link);
      next++;
    }
  }
  add(10);
  document.getElementById('scroller').addEventListener('scroll', () => { if (next < 30) add(10); });
  const dialog = document.querySelector('div[role="dialog"]');
  for (const href of ['/p/ABC123/', '/explore/tags/travel/', '/user0/followers/', '/', '/reels/audio/1/']) {
    const decoy = document.createElement('a');
    decoy.setAttribute('href', href);
    dialog.appendChild(decoy);
  }
</script>
</body></html>
"""


# Verifies the follower dialog scripts read real rendered markup, since those selectors are the fragile part
@pytest.mark.e2e
def test_follow_list_dialog_is_harvested_in_chromium(im_module):
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.set_content(FOLLOW_DIALOG_PAGE)

        # Chromium dispatches the scroll event that appends the next page asynchronously, so the delay has to outlast a loaded CI runner or the harvest stalls out early
        batches = list(im_module.harvest_follow_list_dialog(page, 0.5))
        harvested = [name for batch in batches for name in batch]

        browser.close()

    # Every rendered profile link is read, scrolling loads the rest, and post, tag and sub-page links are ignored
    assert harvested == [f"user{index}" for index in range(30)]
    assert len(batches) > 1


# Keeps suggested accounts out of a follow list even when both sections contain profile links
@pytest.mark.e2e
def test_follow_list_suggestions_are_excluded_in_chromium(im_module):
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_content('<div role="dialog"><div><a href="/actual.user/">actual.user</a><a href="/actual.user/"><img alt="profile"></a></div><div><h4>Suggested for you</h4></div><div><a href="/suggested.user/">suggested.user</a></div><a href="/explore/people/">See All Suggestions</a></div>')

        names = [name for batch in im_module.harvest_follow_list_dialog(page, 0) for name in batch]

        assert names == ["actual.user"]
        browser.close()


# Opens count links from both profile layouts and waits for asynchronously rendered names
@pytest.mark.e2e
@pytest.mark.parametrize("kind", ["followers", "following"])
@pytest.mark.parametrize("legacy", [False, True])
def test_follow_list_count_links_open_in_chromium(im_module, kind, legacy):
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(1000)
        href = f"/target.user/{kind}/" if legacy else "#"
        # The direct URL also covers accounts whose display language differs from the browser locale
        label = "localized count" if legacy else f"6 {kind}"
        page.set_content(f'<button onclick="window.wrongControl = true">Following</button><a href="#">About followers</a><a href="#">6 {"following" if kind == "followers" else "followers"}</a><a id="count" href="{href}" role="link"><span>{label}</span></a>')
        page.locator("#count").evaluate("""link => link.addEventListener('click', event => {
          event.preventDefault();
          const dialog = document.createElement('div');
          dialog.setAttribute('role', 'dialog');
          document.body.appendChild(dialog);
          setTimeout(() => { dialog.innerHTML = '<a href="/first.user/">first.user</a><a href="/second.user/">second.user</a>'; }, 100);
        })""")

        im_module.open_browser_follow_list_dialog(page, "target.user", kind)
        names = [name for batch in im_module.harvest_follow_list_dialog(page, 0) for name in batch]

        assert names == ["first.user", "second.user"]
        assert page.evaluate("window.wrongControl") is None
        browser.close()


# Verifies the dialog scripts report a page with no follower dialog instead of harvesting the rest of it
@pytest.mark.e2e
def test_a_page_without_a_dialog_is_reported_in_chromium(im_module):
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.set_content('<html><body><a href="/someone/">someone</a></body></html>')

        with pytest.raises(im_module.BrowserFollowListError):
            list(im_module.harvest_follow_list_dialog(page, 0))

        browser.close()


# Verifies the dashboard profile picker marks the profiles holding an Instagram session and preselects the only one
@pytest.mark.e2e
def test_browser_import_marks_signed_in_profiles_in_chromium(dashboard_server, im_module, monkeypatch):
    signed_in = "/u/b/cookies.sqlite"
    monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: [{"dir": "a.work", "name": "work", "path": "/u/a/cookies.sqlite", "install": ""}, {"dir": "b.default", "name": "default-release", "path": signed_in, "install": ""}, {"dir": "c.default", "name": "default-release", "path": "/u/c/cookies.sqlite", "install": "Snap"}])
    monkeypatch.setattr(im_module, "cookie_file_has_instagram_session", lambda cookie_file, firefox=False: cookie_file == signed_in)
    page_errors = []
    with playwright_sync.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(dashboard_server, wait_until="domcontentloaded")
        page.locator('[data-page="session"]').click()
        page.locator("#browser-import-btn").click()

        playwright_sync.expect(page.locator("#browser-profiles-container")).to_be_visible()
        assert page.locator("#browser-profile-select option").all_text_contents() == ["work", "* default-release", "default-release (Snap)"]
        # The two installs share a friendly name, so the packaging has to reach the label the user reads
        playwright_sync.expect(page.locator("#browser-profile-select")).to_have_value(signed_in)
        playwright_sync.expect(page.locator("#toast-message")).to_contain_text("* marks the 1 signed in to Instagram")

        assert page_errors == []
        browser.close()
