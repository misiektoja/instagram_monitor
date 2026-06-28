"""Tests for the action-oriented error hint classifier (no network)."""

import pytest


class TestErrorFixHint:
    @pytest.mark.parametrize("msg, needle", [
        ("ConnectionException: 429 Too Many Requests", "rate-limiting"),
        ("JSONDecodeError: challenge_required", "challenge"),
        ("Instagram ... requires a challenge ... missing expected data", "challenge"),
        ("ConnectionException: Login required, redirected", "invalid or expired"),
        ("BadCredentialsException: Wrong password", "invalid or expired"),
        ("FileNotFoundError: Instagram session file for me not found", "no saved session"),
        ("ProfileNotExistsException: Profile xyz does not exist", "spelled correctly"),
        ("ConnectionException: HTTPSConnectionPool max retries exceeded", "network problem"),
    ])
    def test_known_errors_return_hint(self, im_module, msg, needle):
        assert needle in im_module.error_fix_hint(msg)

    @pytest.mark.parametrize("msg", ["", None, "SomethingElse: totally unknown error"])
    def test_unknown_errors_return_empty(self, im_module, msg):
        assert im_module.error_fix_hint(msg) == ""

    def test_session_file_takes_priority_over_not_found(self, im_module):
        # A missing session file should give the session hint, not the profile-not-found hint
        hint = im_module.error_fix_hint("Instagram session file for me not found")
        assert "no saved session" in hint
        assert "spelled correctly" not in hint

    def test_profile_not_found_adds_flag_note_when_logged_in(self, im_module):
        assert "flagged" in im_module.error_fix_hint("ProfileNotExistsException: not found", is_logged_in=True)
        assert "flagged" not in im_module.error_fix_hint("ProfileNotExistsException: not found", is_logged_in=False)

    def test_keyerror_data_via_format_error_message(self, im_module):
        # The real call sites pass format_error_message() output into error_fix_hint()
        msg = im_module.format_error_message(KeyError("data"))
        assert "challenge" in im_module.error_fix_hint(msg)
