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

    # Session recovery hints use the unified browser import command
    def test_session_hints_use_browser_import_command(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "pip")
        hint = im_module.error_fix_hint("ConnectionException: Login required, redirected")
        assert "--import-browser-session --browser firefox" in hint
        assert "--import-firefox-session" not in hint
        assert im_module.SESSION_IMPORT_GUIDE_URL in hint

    # Manual script recovery uses the matching portable command
    def test_session_hints_match_manual_install(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "_wizard_install_method", lambda: "manual")
        monkeypatch.setattr(im_module, "system", lambda: "Linux")
        monkeypatch.setattr(im_module.sys, "executable", "/usr/bin/python3")
        hint = im_module.error_fix_hint("ConnectionException: Login required, redirected")
        assert "python3 instagram_monitor.py --import-browser-session --browser firefox" in hint
        assert "instagram_monitor --import-browser-session" not in hint

    # Printed recovery hints have no leading spaces or tabs
    def test_printed_hint_is_flush_left(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        im_module.print_fix_hint("ConnectionException: 429 Too Many Requests")
        output = capsys.readouterr().out
        assert "\nGuide:" in output
        assert not any(line.startswith((" ", "\t")) for line in output.splitlines())
