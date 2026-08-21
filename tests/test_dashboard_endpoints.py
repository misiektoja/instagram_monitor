"""Offline tests for Web Dashboard endpoints."""

from datetime import datetime, timedelta
import os

import pytest


# Creates a Flask test client with the repository template directory configured
def _dashboard_client(im_module, monkeypatch):
    template_dir = os.path.join(os.path.dirname(os.path.abspath(im_module.__file__)), "templates")
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_TEMPLATE_DIR", template_dir)
    app = im_module.create_web_dashboard_app()
    assert app is not None
    return app.test_client()


class TestDashboardStatus:
    # Status data substitutes private values while preserving real target keys
    def test_status_substitutes_display_values(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "realuser")
        monkeypatch.setattr(im_module, "SKIP_SESSION", False)
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("realuser", "User1")])
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_DATA", {"session": {"username": "realuser", "active": True}, "targets": {"realuser": {"status": "Watching realuser"}}, "start_time": datetime.now() - timedelta(seconds=65)})

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["session"]["username"] == "User1"
        assert "realuser" in data["targets"]
        assert data["targets"]["realuser"]["display_name"] == "User1"
        assert data["targets"]["realuser"]["status"] == "Watching User1"
        assert "uptime" in data


class TestDashboardSettings:
    # Settings form numeric bounds match the server-side validation contract
    def test_settings_form_exposes_server_numeric_bounds(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)

        html = client.get("/").get_data(as_text=True)

        assert 'id="check-interval" min="300" max="86400"' in html
        assert 'id="liveness-check-interval" min="0" max="2678400"' in html
        assert 'id="random-low" min="0" max="3600"' in html
        assert 'id="smtp-port" min="1" max="65535"' in html

    # Settings GET reports whether an SMTP password is configured without exposing the secret
    def test_settings_get_hides_smtp_password(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "secret")

        response = client.get("/api/settings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["smtp_password_set"] is True
        assert "smtp_password" not in data

    # Settings GET reports configured URL state without returning either URL
    def test_settings_get_hides_webhook_and_proxy_urls(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/private-hook")
        monkeypatch.setattr(im_module, "PROXY_URL", "http://user:secret@proxy.example:8080")

        data = client.get("/api/settings").get_json()

        assert data["webhook_url"] == ""
        assert data["webhook_url_set"] is True
        assert data["proxy_url"] == ""
        assert data["proxy_url_set"] is True
        config = im_module.get_dashboard_config_data()
        assert config["webhook_url"] == "Configured"
        assert config["proxy_url"] == "Configured"
        assert "private-hook" not in str(config)
        assert "secret" not in str(config)

    # Settings GET and POST expose and update the non-secret webhook provider
    def test_settings_round_trip_webhook_provider(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        assert client.get("/api/settings").get_json()["webhook_provider"] == "discord"
        response = client.post("/api/settings", json={"webhook_provider": "ntfy"})
        assert response.status_code == 200
        assert im_module.WEBHOOK_PROVIDER == "ntfy"

    # Settings POST corrects a stale provider when a known webhook URL identifies its service
    def test_settings_autodetects_webhook_provider(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "discord")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/123/private-token")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"webhook_url": "https://ntfy.sh/private-topic"})

        assert response.status_code == 200
        assert im_module.WEBHOOK_PROVIDER == "ntfy"

    # Settings POST rejects a too-small interval without changing the live value
    def test_settings_post_rejects_too_small_check_interval(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 5400)

        response = client.post("/api/settings", json={"check_interval": 10})

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "between 300 and 86400" in data["error"]
        assert im_module.INSTA_CHECK_INTERVAL == 5400

    # Malformed setting types and out-of-range numbers return explicit client errors
    @pytest.mark.parametrize("payload,error_text", [({"email_notifications": "false"}, "must be a boolean"), ({"check_interval": True}, "must be an integer"), ({"check_interval": 300.5}, "must be an integer"), ({"smtp_port": 0}, "between 1 and 65535"), ({"liveness_check_interval": -1}, "between 0 and 2678400"), ({"min_h1": 24}, "between 0 and 23"), ({"webhook_provider": "teams"}, "must be 'discord' or 'ntfy'")])
    def test_settings_post_rejects_malformed_values(self, im_module, monkeypatch, payload, error_text):
        client = _dashboard_client(im_module, monkeypatch)

        response = client.post("/api/settings", json=payload)

        assert response.status_code == 400
        assert response.get_json()["success"] is False
        assert error_text in response.get_json()["error"]

    # Validation completes before any setting mutates so a mixed payload is atomic
    def test_settings_post_rejects_payload_without_partial_mutation(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 5400)

        response = client.post("/api/settings", json={"email_notifications": False, "check_interval": "fast"})

        assert response.status_code == 400
        assert im_module.STATUS_NOTIFICATION is True
        assert im_module.INSTA_CHECK_INTERVAL == 5400

    # Settings POST rejects non-object JSON including an empty list
    def test_settings_post_rejects_non_object_json(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)

        response = client.post("/api/settings", json=[])

        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid data format"

    # Hour ranges reject reversed endpoints even when only one endpoint changes
    def test_settings_post_rejects_reversed_hour_range(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "MIN_H1", 8)
        monkeypatch.setattr(im_module, "MAX_H1", 17)

        response = client.post("/api/settings", json={"min_h1": 20})

        assert response.status_code == 400
        assert "cannot be greater" in response.get_json()["error"]
        assert im_module.MIN_H1 == 8

    # Valid interval changes recompute the cycle-based liveness threshold
    def test_settings_post_recomputes_liveness_counter(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 3600)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_INTERVAL", 43200)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_COUNTER", 12)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"check_interval": 7200, "liveness_check_interval": 21600})

        assert response.status_code == 200
        assert im_module.LIVENESS_CHECK_COUNTER == 3


class TestDashboardConfigAndSession:
    # Config generation rejects non-object JSON instead of raising an endpoint error
    def test_generate_config_rejects_non_object_json(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)

        response = client.post("/api/generate-config", json=[])

        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid data format"

    # Config generation rejects paths before writing any file
    def test_generate_config_rejects_path_filename(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)

        response = client.post("/api/generate-config", json={"filename": "../bad.conf"})

        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid filename (paths are not allowed)"

    # Targets added in the browser are saved into the generated config so a restart keeps monitoring them
    def test_generate_config_saves_dashboard_targets(self, im_module, monkeypatch, tmp_path):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_DATA", {"targets": {}})
        monkeypatch.setattr(im_module, "TARGET_USERNAMES", [])
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)
        monkeypatch.chdir(tmp_path)

        for username in ("bob.target", "alice.target"):
            assert client.post("/api/targets", json={"username": username}).status_code == 200

        assert im_module.TARGET_USERNAMES == ["alice.target", "bob.target"]

        response = client.post("/api/generate-config", json={"filename": "instagram_monitor.conf", "settings": {}})

        assert response.status_code == 200
        generated = (tmp_path / "instagram_monitor.conf").read_text(encoding="utf-8")
        assert im_module.parse_config_content(generated)["TARGET_USERNAMES"] == ["alice.target", "bob.target"]

    # Removing a target in the browser drops it from the list a generated config would save
    def test_target_delete_drops_saved_target(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_DATA", {"targets": {}})
        monkeypatch.setattr(im_module, "TARGET_USERNAMES", [])
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "stop_monitoring_for_target", lambda username: True)

        for username in ("bob.target", "alice.target"):
            assert client.post("/api/targets", json={"username": username}).status_code == 200

        response = client.delete("/api/targets/bob.target", headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        assert im_module.TARGET_USERNAMES == ["alice.target"]

    # Session POST updates the configured username and switches out of anonymous mode
    def test_session_post_sets_username(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "")
        monkeypatch.setattr(im_module, "SKIP_SESSION", True)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/session", json={"username": "session_user", "method": "firefox"})

        assert response.status_code == 200
        assert response.get_json() == {"success": True, "message": "Session set for session_user"}
        assert im_module.SESSION_USERNAME == "session_user"
        assert im_module.SKIP_SESSION is False

    # Session POST rejects values that could escape paths or executable HTML contexts
    def test_session_post_rejects_unsafe_username(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)

        response = client.post("/api/session", json={"username": "../../<script>"})

        assert response.status_code == 400
        assert "Instagram username" in response.get_json()["error"]

    # Session clear removes the resolved Instaloader file then broadcasts the mode change
    def test_session_clear_removes_resolved_file(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        local_dir = os.path.join(os.path.dirname(os.path.abspath(im_module.__file__)), "local")
        os.makedirs(local_dir, exist_ok=True)
        session_file = os.path.join(local_dir, "test_session_target")
        try:
            with open(session_file, "w", encoding="utf-8") as handle:
                handle.write("session")
            monkeypatch.setattr(im_module, "SESSION_USERNAME", "session_user")
            monkeypatch.setattr(im_module, "SKIP_SESSION", False)
            monkeypatch.setattr(im_module, "get_session_file_candidates", lambda username: [session_file])
            monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
            monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

            response = client.post("/api/session/clear", json={})

            assert response.status_code == 200
            assert response.get_json()["files_removed"] == 1
            assert not os.path.exists(session_file)
            assert im_module.SKIP_SESSION is True
        finally:
            if os.path.isfile(session_file):
                os.remove(session_file)

    # Session clear removes every canonical and legacy candidate that exists
    def test_session_clear_removes_all_session_candidates(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        local_dir = os.path.join(os.path.dirname(os.path.abspath(im_module.__file__)), "local")
        os.makedirs(local_dir, exist_ok=True)
        session_files = [os.path.join(local_dir, "test_session_canonical"), os.path.join(local_dir, "test_session_legacy")]
        try:
            for session_file in session_files:
                with open(session_file, "w", encoding="utf-8") as handle:
                    handle.write("session")
            monkeypatch.setattr(im_module, "SESSION_USERNAME", "session_user")
            monkeypatch.setattr(im_module, "SKIP_SESSION", False)
            monkeypatch.setattr(im_module, "get_session_file_candidates", lambda username: session_files)
            monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
            monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

            response = client.post("/api/session/clear", json={})

            assert response.status_code == 200
            assert response.get_json()["files_removed"] == 2
            assert not any(os.path.exists(session_file) for session_file in session_files)
        finally:
            for session_file in session_files:
                if os.path.isfile(session_file):
                    os.remove(session_file)

    # Chromium profile detection returns the explicit unsupported-platform error on Windows
    def test_chromium_profiles_reports_windows_unsupported(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "system", lambda: "Windows")

        response = client.get("/api/session/chromium/profiles?browser=chrome")

        assert response.status_code == 400
        assert "not supported on Windows" in response.get_json()["error"]

    # Dashboard profile failures retain the filesystem detail the local operator needs to troubleshoot them
    def test_profile_listing_failure_returns_exception_details(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "smtp-secret")
        monkeypatch.setattr(im_module, "list_firefox_profiles", lambda: (_ for _ in ()).throw(RuntimeError("permission denied for /profiles with smtp-secret")))

        response = client.get("/api/session/firefox/profiles")

        assert response.status_code == 500
        assert response.get_json() == {"success": False, "error": "permission denied for /profiles with [private value]"}


class TestDashboardTestNotifications:
    # Test email route delegates to send_email and returns success
    def test_test_email_uses_stubbed_sender(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        calls = []
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/test-email", json={})

        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        assert calls[0][0][0] == "instagram_monitor: test email"

    # Test webhook route temporarily enables webhooks and restores the previous value
    def test_test_webhook_uses_stubbed_sender(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        calls = []
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/test-webhook", json={})

        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        assert calls[0][0][0] == "instagram_monitor: test webhook"
        assert im_module.WEBHOOK_ENABLED is False


class TestDashboardSecurityAndLifecycle:
    # Target creation rejects a username before it can enter storage or rendering
    def test_target_post_rejects_unsafe_username(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)

        response = client.post("/api/targets", json={"username": "bad' onclick='alert(1)"})

        assert response.status_code == 400
        assert "bad' onclick='alert(1)" not in im_module.WEB_DASHBOARD_DATA.get("targets", {})

    # Media serving allows registered files but cannot read arbitrary working-directory files
    def test_media_route_only_serves_registered_files(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_MEDIA_FILES", {})
        local_dir = os.path.join(os.path.dirname(os.path.abspath(im_module.__file__)), "local")
        os.makedirs(local_dir, exist_ok=True)
        media_file = os.path.join(local_dir, "test_dashboard_media.jpg")
        try:
            with open(media_file, "wb") as handle:
                handle.write(b"image-data")
            assert client.get("/media/instagram_monitor.py").status_code == 404
            media_url = im_module.register_dashboard_media_file(media_file)
            response = client.get(media_url)
            assert response.status_code == 200
            assert response.data == b"image-data"
        finally:
            if os.path.isfile(media_file):
                os.remove(media_file)

    # Consecutive dashboard items cannot reuse media paths from the prior item
    def test_dashboard_media_metadata_does_not_reuse_prior_item_files(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_MEDIA_FILES", {})
        local_dir = os.path.join(os.path.dirname(os.path.abspath(im_module.__file__)), "local")
        os.makedirs(local_dir, exist_ok=True)
        image_file = os.path.join(local_dir, "test_dashboard_item_image.jpg")
        video_file = os.path.join(local_dir, "test_dashboard_item_video.mp4")
        try:
            with open(image_file, "wb") as handle:
                handle.write(b"image")
            with open(video_file, "wb") as handle:
                handle.write(b"video")

            first = im_module.get_dashboard_media_metadata("https://example.com/first.jpg", image_file, video_file)
            second = im_module.get_dashboard_media_metadata("https://example.com/second.jpg", None, None)

            assert first["file_path"] == video_file
            assert first["url"].startswith("/media/")
            assert first["video_url"].startswith("/media/")
            assert second == {"file_path": None, "url": "https://example.com/second.jpg", "video_url": None}
        finally:
            for media_file in (image_file, video_file):
                if os.path.isfile(media_file):
                    os.remove(media_file)

    # A timed-out stop retains thread ownership and blocks a duplicate start
    def test_timed_out_stop_retains_thread_registry(self, im_module, monkeypatch):
        class AliveThread:
            # Reports a monitor that remains alive after join
            def is_alive(self):
                return True

            # Simulates a join timeout without ending the monitor
            def join(self, timeout=None):
                return None

        target = "target"
        thread = AliveThread()
        stop_event = im_module.threading.Event()
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_MONITOR_THREADS", {target: thread})
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_STOP_EVENTS", {target: stop_event})
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "update_ui_data", lambda *args, **kwargs: None)

        assert im_module.stop_monitoring_for_target(target) is False
        assert im_module.WEB_DASHBOARD_MONITOR_THREADS[target] is thread
        assert im_module.start_monitoring_for_target(target) is False

    # Generation broadcasts remain visible to every waiter until each observes them
    def test_session_refresh_generation_is_not_consumed(self, im_module):
        first = im_module.get_session_refresh_generation()
        second = im_module.get_session_refresh_generation()

        updated = im_module.notify_session_refresh()

        assert im_module.wait_for_session_refresh(first, timeout=0) == updated
        assert im_module.wait_for_session_refresh(second, timeout=0) == updated


class TestDashboardRequestBoundary:
    # Requests addressed to an unrecognized Host are refused so DNS rebinding cannot reach the dashboard
    @pytest.mark.parametrize("method,path", [("get", "/api/status"), ("get", "/"), ("post", "/api/settings")])
    def test_foreign_host_header_is_rejected(self, im_module, monkeypatch, method, path):
        client = _dashboard_client(im_module, monkeypatch)

        response = getattr(client, method)(path, headers={"Host": "attacker-controlled.example"})

        assert response.status_code == 403
        assert "Host header" in response.get_json()["error"]

    # Loopback names stay reachable so the documented local workflow is unaffected
    @pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost", "localhost:8000", "[::1]:8000"])
    def test_loopback_host_headers_are_accepted(self, im_module, monkeypatch, host):
        client = _dashboard_client(im_module, monkeypatch)

        assert client.get("/api/status", headers={"Host": host}).status_code == 200

    # A deliberately configured host name is accepted without loosening the default
    def test_configured_allowed_host_is_accepted(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ALLOWED_HOSTS", ["monitor.lan"])
        client = _dashboard_client(im_module, monkeypatch)

        assert client.get("/api/status", headers={"Host": "monitor.lan:8000"}).status_code == 200
        assert client.get("/api/status", headers={"Host": "other.lan:8000"}).status_code == 403

    # The explicit wildcard opt-out accepts any Host for operators who front the dashboard themselves
    def test_wildcard_allowed_host_accepts_any_name(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ALLOWED_HOSTS", ["*"])
        client = _dashboard_client(im_module, monkeypatch)

        assert client.get("/api/status", headers={"Host": "anything.example"}).status_code == 200

    # A wildcard bind address is never treated as a name a browser may address the dashboard by
    def test_wildcard_bind_address_does_not_widen_accepted_hosts(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_HOST", "0.0.0.0")
        client = _dashboard_client(im_module, monkeypatch)

        assert client.get("/api/status", headers={"Host": "127.0.0.1:8000"}).status_code == 200
        assert client.get("/api/status", headers={"Host": "0.0.0.0:8000"}).status_code == 403

    # A cross-site HTML form post cannot change dashboard state even with a valid Host
    @pytest.mark.parametrize("path", ["/api/monitoring/stop", "/api/monitoring/start", "/api/trigger-check", "/api/activity/clear", "/api/test-email", "/api/test-webhook", "/api/settings"])
    def test_cross_site_form_post_is_rejected(self, im_module, monkeypatch, path):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "stop_monitoring_for_target", lambda user: pytest.fail("monitoring was stopped by a cross-site request"))
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: pytest.fail("email was sent by a cross-site request"))
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: pytest.fail("webhook was sent by a cross-site request"))

        response = client.post(path, data="", content_type="application/x-www-form-urlencoded", headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"})

        assert response.status_code == 403

    # A cross-origin JSON request is refused, which is the shape a rebound page would send
    def test_cross_origin_json_post_is_rejected(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.org")

        response = client.post("/api/settings", json={"smtp_host": "attacker.example"}, headers={"Origin": "https://attacker.example"})

        assert response.status_code == 403
        assert im_module.SMTP_HOST == "smtp.example.org"

    # State-changing requests without a JSON body are refused even when no browser headers are present
    @pytest.mark.parametrize("path", ["/api/monitoring/stop", "/api/activity/clear", "/api/test-email", "/api/test-webhook"])
    def test_state_change_requires_json_content_type(self, im_module, monkeypatch, path):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "stop_monitoring_for_target", lambda user: pytest.fail("monitoring was stopped without a JSON request"))
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: pytest.fail("email was sent without a JSON request"))
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: pytest.fail("webhook was sent without a JSON request"))

        assert client.post(path, data="", content_type="application/x-www-form-urlencoded").status_code == 415

    # Same-origin dashboard requests keep working with the headers a browser actually sends
    def test_same_origin_request_is_accepted(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 5400)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"check_interval": 3600}, headers={"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000", "Sec-Fetch-Site": "same-origin"})

        assert response.status_code == 200
        assert im_module.INSTA_CHECK_INTERVAL == 3600


class TestDashboardCredentialBoundary:
    # Repointing SMTP without re-entering the password drops it instead of offering it to the new server
    def test_smtp_password_is_cleared_when_the_server_changes(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.org")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "stored-secret")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"smtp_host": "attacker.example"})

        assert response.status_code == 200
        assert im_module.SMTP_HOST == "attacker.example"
        assert im_module.SMTP_PASSWORD == ""
        assert any("smtp_password" in change and "cleared" in change for change in response.get_json()["changes"])

    # Changing only the port also invalidates the stored password because the destination moved
    def test_smtp_password_is_cleared_when_the_port_changes(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_PORT", 587)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "stored-secret")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"smtp_port": 2525})

        assert response.status_code == 200
        assert im_module.SMTP_PASSWORD == ""

    # Supplying the password alongside the new server keeps email working in the legitimate flow
    def test_smtp_password_survives_a_server_change_when_supplied(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.org")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "stored-secret")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"smtp_host": "smtp.other.org", "smtp_password": "new-secret"})

        assert response.status_code == 200
        assert im_module.SMTP_PASSWORD == "new-secret"

    # The masked placeholder is not a re-entered password, so it cannot carry the secret to a new server
    def test_masked_smtp_password_does_not_survive_a_server_change(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.org")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "stored-secret")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"smtp_host": "attacker.example", "smtp_password": "********"})

        assert response.status_code == 200
        assert im_module.SMTP_PASSWORD == ""

    # An unrelated settings change never disturbs the stored password
    def test_smtp_password_is_untouched_without_a_server_change(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_HOST", "smtp.example.org")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "stored-secret")
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 5400)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"check_interval": 3600})

        assert response.status_code == 200
        assert im_module.SMTP_PASSWORD == "stored-secret"

    # The dashboard may name a CSV file but never choose where the monitor writes it
    @pytest.mark.parametrize("candidate", ["/etc/cron.d/payload", "../escape.csv", "sub/dir.csv", "back\\slash.csv", ".."])
    def test_csv_filename_rejects_paths(self, im_module, monkeypatch, candidate):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "CSV_FILE", "activity.csv")

        response = client.post("/api/settings", json={"csv_filename": candidate})

        assert response.status_code == 400
        assert "without a path" in response.get_json()["error"]
        assert im_module.CSV_FILE == "activity.csv"

    # An over-long CSV name is refused before it reaches the filesystem
    def test_csv_filename_rejects_over_long_names(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "CSV_FILE", "activity.csv")

        response = client.post("/api/settings", json={"csv_filename": "a" * 256 + ".csv"})

        assert response.status_code == 400
        assert im_module.CSV_FILE == "activity.csv"

    # A plain file name is still accepted so the documented dashboard workflow keeps working
    def test_csv_filename_accepts_plain_name(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "CSV_FILE", "activity.csv")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"csv_filename": "renamed.csv"})

        assert response.status_code == 200
        assert im_module.CSV_FILE == "renamed.csv"

    # A CSV path configured outside the dashboard round-trips through the form without being rejected
    def test_csv_filename_round_trips_an_externally_configured_path(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "CSV_FILE", "/var/log/instagram/activity.csv")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"csv_filename": "/var/log/instagram/activity.csv"})

        assert response.status_code == 200
        assert im_module.CSV_FILE == "/var/log/instagram/activity.csv"

    # Clearing the CSV name disables CSV logging instead of failing validation
    def test_csv_filename_accepts_empty_value(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "CSV_FILE", "activity.csv")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"csv_filename": ""})

        assert response.status_code == 200
        assert im_module.CSV_FILE == ""

    # An ntfy bearer token is not carried to a webhook server the operator did not set it for
    def test_ntfy_token_is_cleared_when_the_webhook_server_changes(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.example.org/private-topic")
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", "tk_secret")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"webhook_url": "https://attacker.example/topic"})

        assert response.status_code == 200
        assert im_module.NTFY_ACCESS_TOKEN == ""

    # Changing only the topic on the same server keeps the token so self-hosted ntfy stays usable
    def test_ntfy_token_survives_a_topic_change_on_the_same_server(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://ntfy.example.org/private-topic")
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", "tk_secret")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"webhook_url": "https://ntfy.example.org/other-topic"})

        assert response.status_code == 200
        assert im_module.NTFY_ACCESS_TOKEN == "tk_secret"

    # Setting a first webhook destination also clears a pre-existing token, because the token was never
    # bound to a server the tool had seen. Recovery is the documented dotenv reload
    def test_ntfy_token_is_cleared_when_a_first_destination_is_set(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "")
        monkeypatch.setattr(im_module, "WEBHOOK_PROVIDER", "ntfy")
        monkeypatch.setattr(im_module, "NTFY_ACCESS_TOKEN", "tk_secret")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"webhook_url": "https://ntfy.example.org/topic"})

        assert response.status_code == 200
        assert im_module.NTFY_ACCESS_TOKEN == ""
        assert any("ntfy_access_token" in change for change in response.get_json()["changes"])

    # The dashboard view mode is restricted to the two names every consumer understands
    @pytest.mark.parametrize("payload", [{"mode": "hacked"}, {"mode": ""}, {"mode": None}, {}, {"mode": 1}])
    def test_mode_rejects_unknown_values(self, im_module, monkeypatch, payload):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "DASHBOARD_MODE", "user")

        response = client.post("/api/mode", json=payload)

        assert response.status_code == 400
        assert im_module.DASHBOARD_MODE == "user"

    # Both supported modes still switch the view
    @pytest.mark.parametrize("mode", ["user", "config"])
    def test_mode_accepts_supported_values(self, im_module, monkeypatch, mode):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/mode", json={"mode": mode})

        assert response.status_code == 200
        assert im_module.DASHBOARD_MODE == mode

    # A generated config must look like a config, so this endpoint cannot overwrite a script or dotfile
    @pytest.mark.parametrize("filename", ["instagram_monitor.py", ".bashrc", "notes.txt", "config.conf.bak"])
    def test_generate_config_requires_a_conf_suffix(self, im_module, monkeypatch, filename):
        client = _dashboard_client(im_module, monkeypatch)

        response = client.post("/api/generate-config", json={"filename": filename})

        assert response.status_code == 400
        assert "must end with .conf" in response.get_json()["error"]
