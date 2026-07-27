"""Browser-level dashboard tests using a real headless Chromium instance."""

import re
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from werkzeug.serving import make_server


playwright_sync = pytest.importorskip("playwright.sync_api")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Runs the real dashboard application on an ephemeral loopback port
@pytest.fixture
def dashboard_server(im_module, monkeypatch) -> Iterator[str]:
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
        browser = playwright.chromium.launch(headless=True)
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
