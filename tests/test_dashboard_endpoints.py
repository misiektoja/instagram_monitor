"""Offline tests for Web Dashboard endpoints."""

from datetime import datetime, timedelta
import os


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
    # Settings GET reports whether an SMTP password is configured without exposing the secret
    def test_settings_get_hides_smtp_password(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "secret")

        response = client.get("/api/settings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["smtp_password_set"] is True
        assert "smtp_password" not in data

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

    # Settings POST clamps too-small intervals and reports the adjusted change
    def test_settings_post_clamps_check_interval(self, im_module, monkeypatch):
        client = _dashboard_client(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 5400)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        response = client.post("/api/settings", json={"check_interval": 10})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert im_module.INSTA_CHECK_INTERVAL == 300
        assert data["changes"] == ["'check_interval' changed from 5400 to 300 (min 300s limit)"]


class TestDashboardConfigAndSession:
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
