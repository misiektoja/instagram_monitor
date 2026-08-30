"""Verifies config-file settings actually reach the code that consumes them (no network)."""

from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
# Restores every module-level setting a real startup run mutates, so one test cannot leak into the next
def restored_globals(im_module):
    snapshot = {name: value for name, value in vars(im_module).items() if name.isupper()}
    yield
    for name, value in snapshot.items():
        setattr(im_module, name, value)
    for name in [name for name in vars(im_module) if name.isupper() and name not in snapshot]:
        delattr(im_module, name)


class TestConnectivityCheckResolution:
    # Verifies no connectivity setting is frozen into the function signature where a config file cannot reach it
    def test_connectivity_defaults_are_not_bound_at_import(self, im_module):
        assert im_module.check_internet.__defaults__ == (None, None), "resolving these at import time would freeze them before any config file loads"

    # Verifies a config-file URL and timeout reach the startup check rather than the built-in defaults
    def test_configured_url_and_timeout_reach_the_request(self, im_module, monkeypatch):
        recorded = {}
        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://probe.example/ping")
        monkeypatch.setattr(im_module, "CHECK_INTERNET_TIMEOUT", 17)
        monkeypatch.setattr(im_module.req, "get", lambda url, **kwargs: recorded.update(url=url, **kwargs))

        assert im_module.check_internet() is True
        assert recorded["url"] == "https://probe.example/ping"
        assert recorded["timeout"] == 17

    # Verifies an explicit argument still wins over the resolved global, so callers keep full control
    @pytest.mark.parametrize("url,timeout", [("https://explicit.example", 3), ("https://other.example", 9)])
    def test_explicit_arguments_win(self, im_module, monkeypatch, url, timeout):
        recorded = {}
        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://global.example")
        monkeypatch.setattr(im_module, "CHECK_INTERNET_TIMEOUT", 99)
        monkeypatch.setattr(im_module.req, "get", lambda target, **kwargs: recorded.update(url=target, **kwargs))

        assert im_module.check_internet(url, timeout) is True
        assert (recorded["url"], recorded["timeout"]) == (url, timeout)

    # Verifies a later change to the global is observed, which is the whole point of resolving at call time
    def test_a_later_global_change_is_observed(self, im_module, monkeypatch):
        seen = []
        monkeypatch.setattr(im_module.req, "get", lambda url, **kwargs: seen.append(url))

        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://first.example")
        im_module.check_internet()
        monkeypatch.setattr(im_module, "CHECK_INTERNET_URL", "https://second.example")
        im_module.check_internet()

        assert seen == ["https://first.example", "https://second.example"]


class TestLivenessCounterRecomputation:
    # Verifies a changed check interval rescales the liveness cadence rather than keeping the import-time ratio
    @pytest.mark.parametrize("check_interval,liveness_interval,expected", [(300, 43200, 144.0), (600, 43200, 72.0), (3600, 21600, 6.0)])
    def test_recompute_follows_the_effective_interval(self, im_module, monkeypatch, check_interval, liveness_interval, expected):
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", check_interval)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_INTERVAL", liveness_interval)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_COUNTER", 0)

        im_module.recompute_liveness_check_counter()

        assert im_module.LIVENESS_CHECK_COUNTER == expected

    # Verifies a disabled liveness interval switches the counter off instead of dividing by it
    @pytest.mark.parametrize("check_interval,liveness_interval", [(300, 0), (0, 43200), (0, 0)])
    def test_disabled_settings_switch_the_counter_off(self, im_module, monkeypatch, check_interval, liveness_interval):
        monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", check_interval)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_INTERVAL", liveness_interval)
        monkeypatch.setattr(im_module, "LIVENESS_CHECK_COUNTER", 99)

        im_module.recompute_liveness_check_counter()

        assert im_module.LIVENESS_CHECK_COUNTER == 0


class TestPerCheckReporting:
    # Verifies the per-check lines stay debug traces, since two verbose blocks per cycle buried the events worth reading
    def test_the_check_boundaries_are_debug_only_traces(self):
        source = (Path(__file__).resolve().parents[1] / "instagram_monitor.py").read_text(encoding="utf-8")

        assert 'verbose_print(f"Starting check #' not in source
        assert 'verbose_print(f"Check #' not in source
        assert 'debug_print("Starting check"' in source
        assert 'debug_print("Completed check"' in source


class TestWebhookDestination:
    # Drives the real command line up to the monitoring call and returns the webhook state startup settled on
    def webhook_state_after_startup(self, im_module, monkeypatch, tmp_path, webhook_url):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text('LOCAL_TIMEZONE = "UTC"\nDISABLE_LOGGING = True\nWEBHOOK_ENABLED = True\nWEBHOOK_PROVIDER = "ntfy"\n' + f'WEBHOOK_URL = "{webhook_url}"\n', encoding="utf-8")
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--config-file", str(config), "--env-file", "none", "--no-color"])
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda *args, **kwargs: True)
        monkeypatch.setattr(im_module, "instagram_monitor_user", Mock(side_effect=SystemExit(99)))

        with pytest.raises(SystemExit) as exc:
            im_module.run_main()

        assert exc.value.code == 99
        return im_module.WEBHOOK_ENABLED

    # Verifies an unedited webhook destination switches the channel off instead of being treated as configured
    def test_a_placeholder_webhook_url_switches_the_channel_off(self, im_module, monkeypatch, tmp_path, restored_globals):
        assert self.webhook_state_after_startup(im_module, monkeypatch, tmp_path, "your_webhook_url") is False

    # Verifies a real destination still leaves the webhook channel on
    def test_a_configured_webhook_url_keeps_the_channel_on(self, im_module, monkeypatch, tmp_path, restored_globals):
        assert self.webhook_state_after_startup(im_module, monkeypatch, tmp_path, "https://ntfy.sh/some-topic") is True


class TestSecretReporting:
    # Confirms an unedited placeholder is never reported as a loaded secret, whichever layer recorded it
    def test_placeholder_secrets_are_not_reported_as_loaded(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SECRET_SOURCES", {"WEBHOOK_URL": "dotenv file", "SMTP_PASSWORD": "configuration file or command line"})
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "your_webhook_url")
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "your_smtp_password")

        from_file, from_environment, from_settings = im_module.doctor_secret_sources(None)

        assert "WEBHOOK_URL" not in from_file + from_environment + from_settings
        assert "SMTP_PASSWORD" not in from_file + from_environment + from_settings


class TestConfigLoadReporting:
    # Verifies the settings count is a debug trace rather than a verbose line, since it says nothing a user acts on
    def test_the_config_settings_count_is_a_debug_only_trace(self, im_module, tmp_path, monkeypatch, capsys):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text("CLEAR_SCREEN = False\nDISABLE_LOGGING = True\n", encoding="utf-8")
        namespace = {}

        monkeypatch.setattr(im_module, "VERBOSE_MODE", True)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        im_module.load_config_file(config, namespace=namespace)
        assert "settings from the configuration file" not in capsys.readouterr().out

        monkeypatch.setattr(im_module, "VERBOSE_MODE", False)
        monkeypatch.setattr(im_module, "DEBUG_MODE", True)
        im_module.load_config_file(config, namespace=namespace)
        assert "Configuration applied" in capsys.readouterr().out


class TestStartupScreenClearing:
    # Verifies only debug keeps the screen, since a cleared terminal loses the run being compared against
    @pytest.mark.parametrize(("flag", "expected"), (("--debug", False), ("--verbose", True)))
    def test_only_debug_mode_keeps_the_screen(self, im_module, monkeypatch, tmp_path, restored_globals, flag, expected):
        config = tmp_path / "instagram_monitor.conf"
        config.write_text('LOCAL_TIMEZONE = "UTC"\nDISABLE_LOGGING = True\nCLEAR_SCREEN = True\n', encoding="utf-8")
        cleared = []
        monkeypatch.setattr(im_module, "clear_screen", lambda enabled=True: cleared.append(bool(enabled)))
        monkeypatch.setattr(im_module, "CLEAR_SCREEN", True)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        monkeypatch.setattr(im_module, "VERBOSE_MODE", False)
        monkeypatch.setattr(im_module, "check_internet", lambda *args, **kwargs: True)
        monkeypatch.setattr(im_module, "instagram_monitor_user", Mock(side_effect=SystemExit(99)))
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--config-file", str(config), "--env-file", "none", "--no-color", flag])

        with pytest.raises(SystemExit):
            im_module.run_main()

        assert cleared == [expected]
