"""Offline tests for curl_cffi impersonation target validation."""

import pytest


class TestImpersonateValidation:
    # The default and explicit auto values are always accepted
    @pytest.mark.parametrize("target", ["auto", "AUTO", "", None, "  "])
    def test_auto_is_accepted(self, im_module, target):
        assert im_module.validate_impersonate_target(target) is None

    # A target curl_cffi does not know is refused before it can break every Instagram request
    def test_unknown_target_is_refused(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {"chrome", "safari", "firefox", "edge"})

        error = im_module.validate_impersonate_target("not-a-real-browser")

        assert error is not None
        assert "not-a-real-browser" in error

    # A supported target passes validation unchanged
    @pytest.mark.parametrize("target", ["chrome", "SAFARI", " firefox "])
    def test_supported_targets_are_accepted(self, im_module, monkeypatch, target):
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: {"chrome", "safari", "firefox", "edge"})

        assert im_module.validate_impersonate_target(target) is None

    # A curl_cffi build that does not expose its target list must not block an otherwise valid value
    def test_unknown_target_list_does_not_block(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "curl_cffi_supported_impersonate_targets", lambda: set())

        assert im_module.validate_impersonate_target("chrome131_android") is None

    # The installed curl_cffi advertises the common browser families
    def test_installed_targets_include_common_browsers(self, im_module):
        supported = im_module.curl_cffi_supported_impersonate_targets()

        if not supported:
            pytest.skip("installed curl_cffi does not expose its impersonation targets")
        assert {"chrome", "safari", "firefox", "edge"} <= supported

    # An impersonation failure names the real cause instead of blaming the network
    def test_error_hint_names_the_impersonation_target(self, im_module):
        hint = im_module.error_fix_hint("ConnectionError: Impersonating not-a-real-browser is not supported")

        assert "curl_cffi can impersonate" in hint
        assert "internet connection" not in hint
