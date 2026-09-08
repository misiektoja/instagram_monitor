"""Tests for the action-oriented error hint classifier (no network)."""

import inspect
import smtplib

import pytest


KNOWN_ERRORS = [
    ("ConnectionException: 429 Too Many Requests", "rate-limiting"),
    ("JSONDecodeError: challenge_required", "challenge"),
    ("Instagram ... requires a challenge ... missing expected data", "challenge"),
    ("ConnectionException: Login required, redirected", "invalid or expired"),
    ("BadCredentialsException: Wrong password", "invalid or expired"),
    ("FileNotFoundError: Instagram session file for me not found", "No saved session"),
    ("ProfileNotExistsException: Profile xyz does not exist", "spelled correctly"),
    ("ConnectionException: HTTPSConnectionPool max retries exceeded", "network problem"),
]


class TestErrorFixHint:
    @pytest.mark.parametrize("msg, needle", KNOWN_ERRORS)
    def test_known_errors_return_hint(self, im_module, msg, needle):
        assert needle in im_module.error_fix_hint(msg)

    # Every fix reads as one capitalised instruction with no trailing period, matching the sibling monitors
    @pytest.mark.parametrize("msg", [message for message, _ in KNOWN_ERRORS])
    def test_fix_text_uses_the_shared_sentence_style(self, im_module, msg):
        _summary, fix, _guide = im_module.classify_error_message(msg)

        assert fix[:1].isupper()
        assert not fix.endswith(".")

    @pytest.mark.parametrize("msg", ["", None, "SomethingElse: totally unknown error"])
    def test_unknown_errors_return_empty(self, im_module, msg):
        assert im_module.error_fix_hint(msg) == ""

    def test_session_file_takes_priority_over_not_found(self, im_module):
        # A missing session file should give the session hint, not the profile-not-found hint
        hint = im_module.error_fix_hint("Instagram session file for me not found")
        assert "No saved session" in hint
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


class TestCurlNoiseStripping:
    RAW = ("JSON Query to api/v1/users/web_profile_info/: Failed to perform, curl: (6) "
           "Could not resolve host: www.instagram.com. "
           "See https://curl.se/libcurl/c/libcurl-errors.html first for more details.")

    def test_libcurl_doc_link_is_removed(self, im_module):
        assert "curl.se" not in im_module.strip_curl_noise(self.RAW)

    def test_libcurl_perform_wrapper_is_removed(self, im_module):
        cleaned = im_module.strip_curl_noise(self.RAW)
        assert "Failed to perform" not in cleaned
        assert "curl: (6)" not in cleaned

    def test_underlying_cause_survives(self, im_module):
        cleaned = im_module.strip_curl_noise(self.RAW)
        assert "Could not resolve host: www.instagram.com" in cleaned
        assert "api/v1/users/web_profile_info/" in cleaned

    def test_no_double_spaces_left_behind(self, im_module):
        assert "  " not in im_module.strip_curl_noise(self.RAW)

    def test_non_curl_messages_are_untouched(self, im_module):
        msg = "ProfileNotExistsException: Profile xyz does not exist"
        assert im_module.strip_curl_noise(msg) == msg

    def test_format_error_message_applies_stripping(self, im_module):
        class ConnectionException(Exception):
            pass

        msg = im_module.format_error_message(ConnectionException(self.RAW))
        assert msg.startswith("ConnectionException: ")
        assert "curl.se" not in msg


class TestDnsHint:
    @pytest.mark.parametrize("msg", [
        "ConnectionException: Could not resolve host: www.instagram.com",
        "ConnectionException: Temporary failure in name resolution",
        "ConnectionException: Name or service not known",
        "ConnectionException: nodename nor servname provided",
    ])
    def test_dns_errors_get_the_dns_hint(self, im_module, msg):
        hint = im_module.error_fix_hint(msg)
        assert "DNS" in hint
        assert "network problem" not in hint

    def test_dns_hint_beats_the_generic_network_branch(self, im_module):
        # "ConnectionException" alone matches the generic branch, so ordering must favour the DNS branch
        hint = im_module.error_fix_hint("ConnectionException: Could not resolve host: www.instagram.com")
        assert "cannot resolve" in hint

    def test_plain_network_errors_keep_the_generic_hint(self, im_module):
        hint = im_module.error_fix_hint("ConnectionException: HTTPSConnectionPool max retries exceeded")
        assert "network problem" in hint
        assert "DNS" not in hint

    def test_dns_hint_mentions_recovery_is_automatic(self, im_module):
        assert "resumes on its own" in im_module.error_fix_hint("ConnectionException: Could not resolve host: x")

    def test_bad_request_does_not_map_to_session_hint(self, im_module):
        # A generic HTTP 400 does not prove that Instagram invalidated the account session
        hint = im_module.error_fix_hint("ConnectionException: 400 Bad Request")

        assert "invalid or expired" not in hint
        assert "network problem" in hint


class TestGuideLinkRelevance:
    def test_dns_hint_does_not_link_the_proxy_guide(self, im_module):
        # A machine with no proxy configured must not be sent to proxy setup docs
        hint = im_module.error_fix_hint("ConnectionException: Could not resolve host: www.instagram.com")
        assert im_module.PROXY_GUIDE_URL not in hint
        assert im_module.CONNECTION_ERRORS_GUIDE_URL in hint

    def test_unresolvable_proxy_still_links_the_proxy_guide(self, im_module):
        hint = im_module.error_fix_hint("ConnectionException: Could not resolve proxy: myproxy.local")
        assert im_module.PROXY_GUIDE_URL in hint
        assert "PROXY_URL" in hint

    def test_proxy_branch_wins_over_the_generic_dns_branch(self, im_module):
        hint = im_module.error_fix_hint("ConnectionException: Could not resolve proxy: myproxy.local")
        assert "cannot resolve Instagram's address" not in hint

    def test_generic_network_hint_links_the_connection_guide(self, im_module):
        hint = im_module.error_fix_hint("ConnectionException: HTTPSConnectionPool max retries exceeded")
        assert im_module.CONNECTION_ERRORS_GUIDE_URL in hint


class TestErrorSummary:
    @pytest.mark.parametrize("msg, summary", [
        ("ConnectionException: 429 Too Many Requests", "Instagram is rate-limiting this account or IP"),
        ("JSONDecodeError: challenge_required", "Instagram is asking this session or IP to pass a challenge"),
        ("FileNotFoundError: Instagram session file for me not found", "No saved Instagram session was found"),
        ("ConnectionException: Login required, redirected", "The saved Instagram session is invalid or expired"),
        ("ProfileNotExistsException: Profile xyz does not exist", "Instagram could not find the requested profile"),
        ("ConnectionException: HTTPSConnectionPool max retries exceeded", "Instagram could not be reached"),
    ])
    def test_known_errors_get_a_stable_summary(self, im_module, msg, summary):
        assert im_module.classify_error_message(msg)[0] == summary

    def test_an_unknown_error_still_gets_a_summary_without_a_fix(self, im_module):
        summary, fix, guide = im_module.classify_error_message("SomethingElse: totally unknown error")
        assert summary == "An unexpected error stopped the requested action"
        assert (fix, guide) == ("", "")

    # Verifies the doctor row label comes from the classifier so no raw exception text reaches it
    def test_a_doctor_row_without_a_label_uses_the_summary(self, im_module):
        check = im_module.doctor_check_from_error("Session", "FAIL", "", "ConnectionException: Login required, redirected", True, "raw technical text")

        assert check.label == "The saved Instagram session is invalid or expired"
        assert check.detail == "raw technical text"
        assert "re-import" in check.fix.casefold()


class TestSmtpErrorSummary:
    @pytest.mark.parametrize("error, summary", [
        (smtplib.SMTPAuthenticationError(535, b"auth failed"), "The SMTP server rejected the sign-in"),
        (ValueError("SMTP settings are incorrect"), "The SMTP settings are incomplete or invalid"),
        (OSError("connection refused"), "The SMTP server could not be reached"),
    ])
    def test_smtp_failures_get_a_stable_summary(self, im_module, error, summary):
        assert im_module.classify_smtp_error(error)[0] == summary


class TestOutageReporting:
    # Every classified failure carries a stable code, so a repeat can be recognized without re-reading its text
    @pytest.mark.parametrize("msg, code", [
        ("ConnectionException: 429 Too Many Requests", "instagram.rate_limited"),
        ("JSONDecodeError: challenge_required", "instagram.challenge"),
        ("FileNotFoundError: Instagram session file for me not found", "session.missing"),
        ("ConnectionException: Login required, redirected", "session.expired"),
        ("ProfileNotExistsException: Profile xyz does not exist", "target.not_found"),
        ("ConnectionException: HTTPSConnectionPool max retries exceeded", "network.unavailable"),
        ("SomethingElse: totally unknown error", "unknown"),
    ])
    def test_known_errors_get_a_stable_recovery_code(self, im_module, msg, code):
        advice = im_module.classify_recovery_error(msg)

        assert advice.code == code
        assert advice.summary == im_module.classify_error_message(msg)[0]

    # A repeated failure prints its fix once, so a long outage does not repeat the same paragraph every check
    def test_a_repeated_failure_prints_its_fix_once(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        tracker = im_module.RecoveryHintTracker()

        im_module.print_fix_hint("ConnectionException: 429 Too Many Requests", tracker)
        first = capsys.readouterr().out
        im_module.print_fix_hint("ConnectionException: 429 Too Many Requests", tracker)
        second = capsys.readouterr().out
        tracker.reset()
        im_module.print_fix_hint("ConnectionException: 429 Too Many Requests", tracker)
        third = capsys.readouterr().out

        assert "To fix: " in first
        assert second == ""
        assert third == first

    # A lasting failure is reported once and then only on the liveness cadence
    def test_the_outage_reporter_reports_once_then_on_the_cadence(self, im_module):
        reporter = im_module.OutageReporter()
        advice = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")

        assert reporter.failed(advice, 3) == "full"
        assert [reporter.failed(advice, 3) for _ in range(3)] == ["", "", "degraded"]
        assert reporter.recovered() is not None
        assert reporter.recovered() is None

    # The summary keeps its every-check cadence when the liveness banner is switched off
    def test_the_outage_reporter_keeps_repeating_without_a_liveness_banner(self, im_module):
        reporter = im_module.OutageReporter()
        advice = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")

        assert reporter.failed(advice, 0) == "full"
        assert [reporter.failed(advice, 0) for _ in range(2)] == ["repeat", "repeat"]

    # A failure category that changes is reported in full again rather than hidden by the previous one
    def test_a_changed_failure_category_is_reported_in_full(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        reporter = im_module.OutageReporter()
        limited = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")
        expired = im_module.classify_recovery_error("ConnectionException: Login required, redirected")

        assert reporter.failed(limited, 5) == "full"
        assert reporter.failed(limited, 5) == ""
        assert reporter.failed(expired, 5) == "full"

        im_module.print_outage_liveness("misiektoja", expired, int(im_module.time.time()) - 60)
        im_module.print_outage_recovery("misiektoja", 60)

        output = capsys.readouterr().out
        assert f"* Monitoring degraded for misiektoja. {expired.summary} since " in output
        assert "Liveness check, timestamp:" in output
        assert "* Monitoring recovered for misiektoja after 1 minute" in output

    # Both loop failure paths route through the outage reporter, so neither repeats itself every check
    def test_the_loop_routes_its_failures_through_the_outage_reporter(self, im_module):
        module_source = inspect.getsource(im_module)
        start = module_source.index("def _run_instagram_monitor_pass(")
        source = module_source[start:module_source.index("\ndef ", start)]

        assert source.count("outage.failed(") == 2
        assert source.count("print_outage_liveness(user, ") == 2
        assert "print_outage_recovery(user, outage_lasted)" in source
        assert source.count("print_fix_hint(error_msg, recovery_hint_tracker)") == 2

    # Every reported loop failure uses the line shape shared with the sibling monitors
    def test_reported_failures_use_the_shared_line_shape(self, im_module):
        module_source = inspect.getsource(im_module)
        start = module_source.index("def _run_instagram_monitor_pass(")
        source = module_source[start:module_source.index("\ndef ", start)]

        assert source.count('print(f"* Error: {error_msg} (retrying in {display_time(r_sleep_time)})")') == 2
        assert "* Error, retrying in " not in source, "the report line must carry its retry note in parentheses"
        assert 'print(f"Retrying in ' not in source, "the retry note belongs on the report line, not on one of its own"
        assert "* Session might not be valid anymore" not in source, "advice belongs on a To fix line, not on a second starred line"

    # A fix hint reports whether it printed, so a second piece of advice cannot repeat what is already on screen
    def test_a_printed_fix_hint_reports_itself(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        tracker = im_module.RecoveryHintTracker()

        assert im_module.print_fix_hint("ConnectionException: 429 Too Many Requests", tracker) is True
        assert im_module.print_fix_hint("ConnectionException: 429 Too Many Requests", tracker) is False
        assert im_module.print_fix_hint("SomethingElse: totally unknown error") is False

        assert capsys.readouterr().out.count("To fix: ") == 1

    # The session hint is suppressed when the classifier already printed a fix for the same failure
    def test_the_session_hint_gives_way_to_a_classified_fix(self, im_module):
        module_source = inspect.getsource(im_module)
        start = module_source.index("def _run_instagram_monitor_pass(")
        source = module_source[start:module_source.index("\ndef ", start)]

        assert "fix_hint_printed = print_fix_hint(error_msg, recovery_hint_tracker)" in source
        assert "if not fix_hint_printed and outage_outcome in (\"full\", \"repeat\") and (" in source
        assert source.count("session_recovery_command()") == 2
