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

            response = client.post("/api/session/clear")

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

            response = client.post("/api/session/clear")

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


class TestDashboardTestNotifications:
    # Test email route delegates to send_email and returns success
    def test_test_email_uses_stubbed_sender(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        calls = []
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/test-email")

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

        response = client.post("/api/test-webhook")

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
