"""Tests for error classification and session/IP flag detection.

The flag probe normally resolves a canonical public account over the network.
Here profile_from_username_resilient is stubbed so the logic runs fully offline.
"""

import pytest


class _FakeBot:
    """Stand-in for an instaloader bot; only its identity matters to the code under test."""

    pass


# Returns a resolver stub that always raises with the given message
def _raiser(message):
    def _inner(bot, username):
        raise Exception(message)

    return _inner


class TestFormatErrorMessage:
    def test_keyerror_data_maps_to_challenge_message(self, im_module):
        msg = im_module.format_error_message(KeyError("data"))
        assert "challenge" in msg.lower() or "shadow" in msg.lower()

    def test_other_keyerror_is_plain(self, im_module):
        assert im_module.format_error_message(KeyError("other")) == "KeyError: 'other'"

    def test_generic_exception_formatting(self, im_module):
        assert im_module.format_error_message(ValueError("boom")) == "ValueError: boom"


class TestIsProfileNotFoundError:
    def test_matches_trigger(self, im_module):
        assert im_module.is_profile_not_found_error("ProfileNotExistsException: gone") is True

    def test_no_match(self, im_module):
        assert im_module.is_profile_not_found_error("SomeOtherError: nope") is False


class TestIsSessionFlagged:
    def test_explicit_flag_trigger_short_circuits(self, im_module):
        # An unambiguous trigger returns True without ever probing the network
        assert im_module.is_session_flagged("checkpoint_required encountered", _FakeBot()) is True
        assert im_module.is_session_flagged("detected automated checks", _FakeBot()) is True

    def test_unrelated_error_is_not_flagged(self, im_module):
        assert im_module.is_session_flagged("ConnectionError: timeout", _FakeBot()) is False

    def test_profile_not_found_probes_and_reports_flagged(self, im_module, monkeypatch):
        # Probe of the canonical account also fails -> session is genuinely flagged
        monkeypatch.setattr(im_module, "profile_from_username_resilient", _raiser("ProfileNotExistsException: instagram missing"))
        assert im_module.is_session_flagged("ProfileNotExistsException: target gone", _FakeBot()) is True

    def test_profile_not_found_probes_and_reports_target_gone(self, im_module, monkeypatch):
        # Probe of the canonical account succeeds -> only the target is gone, session is fine
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, username: object())
        assert im_module.is_session_flagged("ProfileNotExistsException: target gone", _FakeBot()) is False


class TestProbeSessionFlagged:
    def test_none_bot_returns_false(self, im_module):
        assert im_module.probe_session_flagged(None) is False

    def test_verdict_is_cached_within_ttl(self, im_module, monkeypatch):
        calls = {"n": 0}

        def counting_resolver(bot, username):
            calls["n"] += 1
            raise Exception("ProfileNotExistsException: instagram missing")

        monkeypatch.setattr(im_module, "profile_from_username_resilient", counting_resolver)
        first = im_module.probe_session_flagged(_FakeBot())
        second = im_module.probe_session_flagged(_FakeBot())
        assert first is True and second is True
        # Cached after the first probe, so the resolver runs only once within the TTL
        assert calls["n"] == 1
