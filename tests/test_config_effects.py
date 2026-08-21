"""Verifies config-file settings actually reach the code that consumes them (no network)."""

import pytest


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
