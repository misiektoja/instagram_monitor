"""Tests for the action-oriented error hint classifier (no network)."""

from command_expectations import runtime_command
import ast
import inspect
import re
import smtplib
import threading
from unittest.mock import Mock

import pytest


KNOWN_ERRORS = [
    ("ConnectionException: 429 Too Many Requests", "rate-limiting"),
    ("JSONDecodeError: challenge_required", "challenge"),
    ("Instagram ... requires a challenge ... missing expected data", "challenge"),
    ("ConnectionException: Login required, redirected", "invalid or expired"),
    ("BadCredentialsException: Wrong password", "invalid or expired"),
    ("FileNotFoundError: Instagram session file for me not found", "No saved session"),
    ("ProfileNotExistsException: Profile xyz does not exist", "spelled correctly"),
    ("ConnectionException: HTTPSConnectionPool max retries exceeded", "the tool retries on its own"),
]


# Returns every tuple the runtime rule table returns, which is where each Instagram failure is described
def _rule_table_rows(im_module):
    return [node.value for node in ast.walk(ast.parse(inspect.getsource(im_module.classify_error_parts))) if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)]


# Returns every advice() call the context table makes, skipping the runtime delegation that forwards its own guide
def _context_advice_calls(im_module):
    source = inspect.getsource(im_module.classify_recovery_error)
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "advice" and len(node.args) == 5]
    return [node for node in calls if not (isinstance(node.args[4], ast.Name) and node.args[4].id == "guide")]


# Returns every print of a problem that does not already carry an action, as (line number, literal text)
def _problem_prints(im_module):
    source = inspect.getsource(im_module)
    lines = source.splitlines()
    problem = re.compile(r"(?i)\b(error|failed|failure|could not|cannot|unable|invalid|missing|not found|refused|denied|no such|warning)\b")
    fixers = ("print_fix_hint", "error_fix_hint", "To fix", "print_recovery_error", "print_recovery_advice", "render_recovery_error", "render_recovery_advice", "print_recovery_fix")
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"):
            continue
        text = _printed_text(node)
        if text is None or not problem.search(text):
            continue
        window = "\n".join(lines[max(0, node.lineno - 9):node.lineno + 8])
        if not any(fixer in window for fixer in fixers):
            found.append((node.lineno, text.strip()))
    return found


# Returns the literal text a print would produce, with every substitution shown as its own expression
def _printed_text(node):
    if not node.args:
        return None
    argument = node.args[0]
    if isinstance(argument, ast.Call) and isinstance(argument.func, ast.Name) and argument.func.id == "colorize" and len(argument.args) > 1:
        argument = argument.args[1]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    if isinstance(argument, ast.JoinedStr):
        parts = []
        for part in argument.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
            elif isinstance(part, ast.FormattedValue):
                parts.append("{" + ast.unparse(part.value) + "}")
        return "".join(parts)
    return None


# Reports whether an argument is one of the documentation constants rather than an empty placeholder
def _names_a_page(node):
    return isinstance(node, ast.Name) and node.id.endswith("_GUIDE_URL")


class TestErrorFixHint:
    @pytest.mark.parametrize("msg, needle", KNOWN_ERRORS)
    def test_known_errors_return_hint(self, im_module, msg, needle):
        assert needle in im_module.error_fix_hint(msg)

    # Every fix reads as one capitalised instruction with no trailing period, matching the sibling monitors
    @pytest.mark.parametrize("msg", [message for message, _ in KNOWN_ERRORS])
    def test_fix_text_uses_the_shared_sentence_style(self, im_module, msg):
        fix = im_module.classify_recovery_error(msg, is_logged_in=False).fix.splitlines()[0]

        assert fix[:1].isupper()
        assert not fix.endswith(".")

    # An unrecognized failure is still a failure the user has to act on, so it names the one action that always applies
    @pytest.mark.parametrize("msg", ["", None, "SomethingElse: totally unknown error"])
    def test_unknown_errors_still_name_an_action(self, im_module, msg):
        hint = im_module.error_fix_hint(msg)

        assert hint.startswith("To fix: Re-run with --debug")
        assert im_module.DIAGNOSTICS_GUIDE_URL in hint

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
        assert runtime_command("python3 instagram_monitor.py --import-browser-session --browser firefox") in hint
        assert runtime_command("instagram_monitor --import-browser-session") not in hint

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
        assert "check network access, DNS, firewall and proxy settings" in hint
        assert "cannot resolve Instagram's address" not in hint

    def test_dns_hint_mentions_recovery_is_automatic(self, im_module):
        assert "resumes on its own" in im_module.error_fix_hint("ConnectionException: Could not resolve host: x")

    def test_bad_request_does_not_map_to_session_hint(self, im_module):
        # A generic HTTP 400 does not prove that Instagram invalidated the account session
        hint = im_module.error_fix_hint("ConnectionException: 400 Bad Request")

        assert "invalid or expired" not in hint
        assert "check network access, DNS, firewall and proxy settings" in hint


class TestGuideLinkRelevance:
    def test_dns_hint_does_not_link_the_proxy_guide(self, im_module):
        # A machine with no proxy configured must not be sent to proxy setup docs
        hint = im_module.error_fix_hint("ConnectionException: Could not resolve host: www.instagram.com")
        assert im_module.PROXY_GUIDE_URL not in hint
        assert im_module.CONNECTION_GUIDE_URL in hint

    def test_unresolvable_proxy_still_links_the_proxy_guide(self, im_module):
        hint = im_module.error_fix_hint("ConnectionException: Could not resolve proxy: myproxy.local")
        assert im_module.PROXY_GUIDE_URL in hint
        assert "PROXY_URL" in hint

    def test_proxy_branch_wins_over_the_generic_dns_branch(self, im_module):
        hint = im_module.error_fix_hint("ConnectionException: Could not resolve proxy: myproxy.local")
        assert "cannot resolve Instagram's address" not in hint

    def test_generic_network_hint_links_the_connection_guide(self, im_module):
        hint = im_module.error_fix_hint("ConnectionException: HTTPSConnectionPool max retries exceeded")
        assert im_module.CONNECTION_GUIDE_URL in hint


class TestErrorSummary:
    @pytest.mark.parametrize("msg, summary", [
        ("ConnectionException: 429 Too Many Requests", "Instagram is rate-limiting anonymous requests from this IP"),
        ("JSONDecodeError: challenge_required", "Instagram is asking this session or IP to pass a challenge"),
        ('AbortDownloadException: 400 Bad Request - "fail" status, message "feedback_required" when accessing https://www.instagram.com/api/v1/users/web_profile_info/?username=x', "Instagram no longer answers the profile endpoint this lookup used"),
        ("FileNotFoundError: Instagram session file for me not found", "No saved Instagram session was found"),
        ("ConnectionException: Login required, redirected", "The saved Instagram session is invalid or expired"),
        ("ProfileNotExistsException: Profile xyz does not exist", "Instagram could not find the requested profile"),
        ("ConnectionException: HTTPSConnectionPool max retries exceeded", "Instagram could not be reached"),
    ])
    def test_known_errors_get_a_stable_summary(self, im_module, msg, summary):
        assert im_module.classify_recovery_error(msg, is_logged_in=False).summary == summary

    def test_an_unknown_error_gets_a_summary_a_fix_and_a_page(self, im_module):
        advice = im_module.classify_recovery_error("SomethingElse: totally unknown error", is_logged_in=False)
        assert advice.summary == "An unexpected error stopped the requested action"
        assert advice.fix == im_module.recovery_fix_with_guide("Re-run with --debug to see the technical cause", im_module.DIAGNOSTICS_GUIDE_URL)

    # A doctor row is built from the same classification, and a row with no fix is refused outright
    def test_an_unrecognized_failure_does_not_break_a_doctor_row(self, im_module):
        check = im_module.doctor_check_from_error("Session", "FAIL", "", "SomethingElse: totally unknown error")

        assert check.status == "FAIL"
        assert check.advice.fix == im_module.recovery_fix_with_guide("Re-run with --debug to see the technical cause", im_module.DIAGNOSTICS_GUIDE_URL)

    # Verifies the doctor row label comes from the classifier so no raw exception text reaches it
    def test_a_doctor_row_without_a_label_uses_the_summary(self, im_module):
        check = im_module.doctor_check_from_error("Session", "FAIL", "", "ConnectionException: Login required, redirected", True, "raw technical text")

        assert check.label == "The saved Instagram session is invalid or expired"
        assert check.detail == "raw technical text"
        assert "re-import" in check.advice.fix.casefold()


class TestTemporaryLimitAdvice:
    # Instagram's "Try Again Later" notice clears with time alone, so the advice must not send the reader to clear a checkpoint or re-import
    def test_a_temporary_limit_is_told_to_wait_rather_than_re_import(self, im_module):
        advice = im_module.classify_recovery_error('AbortDownloadException: 400 Bad Request - "fail" status, message "feedback_required"', is_logged_in=True)

        assert advice.code == "instagram.action_blocked"
        assert "several hours" in advice.fix
        assert "checkpoint" not in advice.fix.replace("not a checkpoint", "")
        assert "--import-browser-session" not in advice.fix
        assert im_module.ACTION_BLOCK_GUIDE_URL in advice.fix

    # The limit still acts against the account, so the breaker stops it like a challenge and names its own remedy
    def test_a_temporary_limit_stops_the_account_with_its_own_remedy(self, im_module):
        failure_class = im_module.classify_failure_class('400 Bad Request - "fail" status, message "feedback_required"')

        assert failure_class == "action_block"
        assert im_module.is_account_level_failure(failure_class) is True
        assert "re-importing the session does not lift" in im_module.breaker_recovery_hint(failure_class)


class TestSmtpErrorSummary:
    @pytest.mark.parametrize("error, summary", [
        (smtplib.SMTPAuthenticationError(535, b"auth failed"), "The SMTP server rejected the sign-in"),
        (ValueError("SMTP settings are incorrect"), "The SMTP settings are incomplete or invalid"),
        (OSError("connection refused"), "The SMTP server could not be reached"),
    ])
    def test_smtp_failures_get_a_stable_summary(self, im_module, error, summary):
        assert im_module.classify_smtp_error(error)[0] == summary


class TestAnonymousRateLimits:
    THROTTLE = 'ConnectionException: JSON Query to api/v1/users/web_profile_info/?username=x: 401 Unauthorized - "fail" status, message "Please wait a few minutes before you try again."'

    # An anonymous limit sits on the address and is often hit before the first request, so a slower run cannot clear it
    def test_an_anonymous_limit_points_at_the_address_and_a_session_login(self, im_module):
        advice = im_module.classify_recovery_error(self.THROTTLE, is_logged_in=False)

        assert advice.code == "instagram.rate_limited"
        assert "IP address" in advice.fix and "session login" in advice.fix
        assert "INSTA_CHECK_INTERVAL" not in advice.fix
        assert im_module.ANONYMOUS_RATE_LIMIT_GUIDE_URL in advice.fix
        assert advice.retryable is True

    # A signed-in run is limited per account, so the advice that reduces its own traffic still applies
    def test_a_signed_in_limit_keeps_the_interval_advice(self, im_module):
        advice = im_module.classify_recovery_error(self.THROTTLE, is_logged_in=True)

        assert advice.code == "instagram.rate_limited"
        assert "INSTA_CHECK_INTERVAL" in advice.fix
        assert im_module.ANTI_DETECTION_INTERVAL_GUIDE_URL in advice.fix

    # The advice is chosen by the run's mode, not by the address the request went to
    def test_the_run_mode_decides_the_advice(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "SESSION_USERNAME", "")
        monkeypatch.setattr(im_module, "SKIP_SESSION", True)
        assert "IP address" in im_module.classify_recovery_error(self.THROTTLE).fix

        monkeypatch.setattr(im_module, "SESSION_USERNAME", "someone")
        monkeypatch.setattr(im_module, "SKIP_SESSION", False)
        assert "INSTA_CHECK_INTERVAL" in im_module.classify_recovery_error(self.THROTTLE).fix


class TestOutageReporting:
    # Every classified failure carries a stable code, so a repeat can be recognized without re-reading its text
    @pytest.mark.parametrize("msg, code", [
        ("ConnectionException: 429 Too Many Requests", "instagram.rate_limited"),
        ("JSONDecodeError: challenge_required", "instagram.challenge"),
        ('AbortDownloadException: 400 Bad Request - "fail" status, message "feedback_required"', "instagram.action_blocked"),
        ("FileNotFoundError: Instagram session file for me not found", "session.missing"),
        ("ConnectionException: Login required, redirected", "session.expired"),
        ("ProfileNotExistsException: Profile xyz does not exist", "target.not_found"),
        ("ConnectionException: HTTPSConnectionPool max retries exceeded", "network.unavailable"),
        ("SomethingElse: totally unknown error", "unknown"),
    ])
    def test_known_errors_get_a_stable_recovery_code(self, im_module, msg, code):
        advice = im_module.classify_recovery_error(msg)

        assert advice.code == code
        assert advice.summary == im_module.classify_error_parts(msg)[1]

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

    # A lasting failure is reported once and then only once the reminder interval has passed
    def test_the_outage_reporter_reports_once_then_on_the_cadence(self, im_module, monkeypatch):
        clock = [1000000.0]
        monkeypatch.setattr(im_module.time, "time", lambda: clock[0])
        monkeypatch.setattr(im_module, "OUTAGE_REMINDER_SECONDS", 180)
        reporter = im_module.OutageReporter()
        advice = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")

        assert reporter.failed(advice) == "full"
        outcomes = []
        for _ in range(3):
            clock[0] += 60
            outcomes.append(reporter.failed(advice))

        assert outcomes == ["", "", "reminder"]
        assert reporter.recovered() is not None
        assert reporter.recovered() is None

    # Verifies a category change mid-outage keeps the outage start, so the alert delay and the reminder still elapse
    def test_an_outage_that_changes_category_keeps_its_start(self, im_module, monkeypatch):
        clock = [1000000.0]
        monkeypatch.setattr(im_module.time, "time", lambda: clock[0])
        reporter = im_module.OutageReporter()
        first = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")
        second = im_module.classify_recovery_error(OSError(24, "Too many open files"), context="runtime")
        assert first.code != second.code

        assert reporter.failed(first) == "full"
        for index in range(60):
            clock[0] += 15
            reporter.failed(second if index % 2 else first)

        assert reporter.since == 1000000
        assert reporter.recovered() == 900

    # The reminder follows the clock, so a run that retries faster than it polls does not remind more often
    def test_the_outage_reminder_follows_the_clock_not_the_check_count(self, im_module, monkeypatch):
        clock = [1000000.0]
        monkeypatch.setattr(im_module.time, "time", lambda: clock[0])
        reporter = im_module.OutageReporter()
        advice = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")

        monkeypatch.setattr(im_module, "OUTAGE_REMINDER_SECONDS", 900)
        assert reporter.failed(advice) == "full"
        outcomes = []
        for _ in range(60):
            clock[0] += 15
            outcomes.append(reporter.failed(advice))

        assert outcomes.count("reminder") == 1

    # The reminder keeps its own clock when the liveness banner is switched off, so a lasting failure is neither
    # silenced nor repeated every check
    def test_the_outage_reporter_reminds_on_its_own_clock_without_a_liveness_banner(self, im_module, monkeypatch):
        clock = [1000000.0]
        monkeypatch.setattr(im_module.time, "time", lambda: clock[0])
        monkeypatch.setattr(im_module, "LIVENESS_REMINDER_SECONDS", 0)
        monkeypatch.setattr(im_module, "OUTAGE_REMINDER_SECONDS", 60)
        reporter = im_module.OutageReporter()
        advice = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")

        assert reporter.failed(advice) == "full"
        clock[0] += 59
        assert reporter.failed(advice) == ""
        clock[0] += 1
        assert reporter.failed(advice) == "reminder"
        assert reporter.failed(advice) == ""

    # An internet outage classifies as a DNS failure on one check and as unreachable on the next, and it is one outage
    def test_an_internet_outage_that_flaps_is_one_outage(self, im_module, monkeypatch):
        clock = [1000000.0]
        monkeypatch.setattr(im_module.time, "time", lambda: clock[0])
        reporter = im_module.OutageReporter()
        dns = im_module.classify_recovery_error("ConnectionException: Temporary failure in name resolution")
        unreachable = im_module.classify_recovery_error("ConnectionException: HTTPSConnectionPool max retries exceeded")
        assert (dns.code, unreachable.code) == ("network.dns", "network.unavailable")
        assert im_module.outage_family(dns.code) == im_module.outage_family(unreachable.code) == "network"

        assert reporter.failed(dns) == "full"
        outcomes = []
        for index in range(60):
            clock[0] += 15
            outcomes.append(reporter.failed(unreachable if index % 2 else dns))

        assert set(outcomes) == {""}
        assert reporter.recovered() == 900

    # A reported outage that starts failing differently is still one outage, so the change is one line, not a second report
    def test_a_changed_retryable_category_is_noted_in_one_line(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        reporter = im_module.OutageReporter()
        limited = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")
        unreachable = im_module.classify_recovery_error("ConnectionException: HTTPSConnectionPool max retries exceeded")
        assert limited.retryable and unreachable.retryable

        assert reporter.failed(limited) == "full"
        assert reporter.failed(unreachable) == "changed"
        assert reporter.failed(unreachable) == ""

        im_module.print_outage_change("misiektoja", unreachable)
        im_module.print_outage_liveness("misiektoja", unreachable, reporter.since, reporter.failures)

        output = capsys.readouterr().out
        assert f"* Monitoring failure changed for misiektoja. {unreachable.summary}\n" in output
        assert f"* Monitoring degraded for misiektoja. {unreachable.summary} since " in output
        assert ", 3 failed checks\n" in output

    # A failure category that changes is reported in full again rather than hidden by the previous one
    def test_a_changed_failure_category_is_reported_in_full(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        reporter = im_module.OutageReporter()
        limited = im_module.classify_recovery_error("ConnectionException: 429 Too Many Requests")
        expired = im_module.classify_recovery_error("ConnectionException: Login required, redirected")

        assert reporter.failed(limited) == "full"
        assert reporter.failed(limited) == ""
        assert not expired.retryable
        assert reporter.failed(expired) == "full", "a failure nothing can retry away is a new report rather than a note"

        im_module.print_outage_liveness("misiektoja", expired, int(im_module.time.time()) - 60)
        im_module.print_outage_recovery("misiektoja", 60)

        output = capsys.readouterr().out
        assert f"* Monitoring degraded for misiektoja. {expired.summary} since " in output
        assert "Liveness check, timestamp:" in output
        assert "* Monitoring recovered for misiektoja after 1 minute" in output

    # A fix hint reports whether it printed, so a second piece of advice cannot repeat what is already on screen
    def test_a_printed_fix_hint_reports_itself(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        tracker = im_module.RecoveryHintTracker()

        assert im_module.print_fix_hint("ConnectionException: 429 Too Many Requests", tracker) is True
        assert im_module.print_fix_hint("ConnectionException: 429 Too Many Requests", tracker) is False
        assert im_module.print_fix_hint("SomethingElse: totally unknown error") is True

        assert capsys.readouterr().out.count("To fix: ") == 2

    # The liveness banner explains itself without --verbose, so a plain run never prints a bare timestamp
    def test_the_liveness_banner_explains_itself_without_diagnostics(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        monkeypatch.setattr(im_module, "VERBOSE_MODE", False)

        im_module.print_liveness_banner("Monitoring healthy for misiektoja. No tracked change since the last check")

        lines = capsys.readouterr().out.splitlines()
        assert lines[0] == "* Monitoring healthy for misiektoja. No tracked change since the last check"
        assert lines[1].startswith("Liveness check, timestamp:")


# The three loop failure paths each report their own way, so a check that only reads the source cannot tell whether
# they still meet at the outage reporter. These run the pass instead
class TestTheLoopFailurePaths:
    # Runs one monitoring pass, letting the startup fetch succeed and failing the given number of loop checks
    @staticmethod
    def _drive(im_module, monkeypatch, thread_output=(), profile_error=None, posts_error=None, checks=1, recovers=False, liveness_seconds=0):
        reporter_calls = []
        alerts = []
        stop_event = threading.Event()
        seen = {"profile": 0, "posts": 0, "checks": 0}
        real_failed = im_module.OutageReporter.failed

        def failed(self, advice):
            outcome = real_failed(self, advice)
            reporter_calls.append({"code": advice.code, "since": self.since, "failures": self.failures, "outcome": outcome})
            return outcome

        def alert(user, advice, since, count, sleep_time, state):
            alerts.append({"code": advice.code, "since": since, "count": count, "detail": advice.detail})

        # The startup pass runs before the loop and a failure there ends the process, so only loop checks fail
        def profile(bot, user):
            seen["profile"] += 1
            if seen["profile"] > 1:
                seen["checks"] += 1
                if seen["checks"] >= checks + int(recovers):
                    stop_event.set()
                if profile_error is not None and not (recovers and seen["checks"] > checks):
                    raise profile_error
            return Mock(followers=1, followees=1, biography="", is_private=False, followed_by_viewer=False, mediacount=seen["profile"], has_public_story=False, userid=1)

        def posts(user, bot):
            seen["posts"] += 1
            if posts_error is not None and seen["posts"] > 1:
                raise posts_error
            return None

        def thread_lines():
            return list(thread_output) if seen["profile"] > 1 else []

        bot = Mock()
        bot.context.is_logged_in = False
        clock = [float(int(im_module.time.time()))]
        monkeypatch.setattr(im_module.time, "time", lambda: clock[0])
        # The loop re-reads these from the module every iteration, so the positional arguments alone do not hold
        for name, value in (("INSTA_CHECK_INTERVAL", 1), ("RANDOM_SLEEP_DIFF_LOW", 0), ("RANDOM_SLEEP_DIFF_HIGH", 0), ("NEXT_OPERATION_DELAY", 0), ("WEB_DASHBOARD_ENABLED", False), ("SESSION_USERNAME", ""), ("SKIP_SESSION", True), ("SKIP_FOLLOWERS", True), ("SKIP_FOLLOWINGS", True), ("SKIP_FOLLOW_CHANGES", True), ("SKIP_GETTING_STORY_DETAILS", True), ("SKIP_GETTING_POSTS_DETAILS", posts_error is None), ("GET_MORE_POST_DETAILS", False), ("DETECT_COLLAB_POSTS", False), ("LIVENESS_REMINDER_SECONDS", liveness_seconds)):
            monkeypatch.setattr(im_module, name, value, raising=False)
        monkeypatch.setattr(im_module.OutageReporter, "failed", failed)
        monkeypatch.setattr(im_module, "notify_monitoring_error", alert)
        monkeypatch.setattr(im_module, "get_thread_output", thread_lines)
        monkeypatch.setattr(im_module, "instaloader_client", lambda **kwargs: bot)
        monkeypatch.setattr(im_module, "profile_from_username_resilient", profile)
        monkeypatch.setattr(im_module, "latest_post_mobile", posts)

        # Reports the stop the harness asked for rather than always interrupting, so more than one check can run.
        # The wait also advances the clock, which is what makes a timed reminder deterministic here
        def wait(seconds, event=None):
            clock[0] += seconds
            return stop_event.is_set()

        monkeypatch.setattr(im_module, "interruptible_sleep", wait)

        im_module._run_instagram_monitor_pass("target", "", True, True, True, True, posts_error is None, False, stop_event=stop_event)
        return reporter_calls, alerts

    # The alert delay counts from the first failing check, which only holds if every path reports the same outage
    @pytest.mark.parametrize("path,kwargs", [("main", {"profile_error": RuntimeError("500 Server Error")}), ("redirect", {"thread_output": ["HTTP redirect from https://instagram.com/x"]}), ("posts", {"posts_error": RuntimeError("503 Service Unavailable")})])
    def test_every_failure_path_reports_one_outage_and_alerts_from_its_start(self, im_module, monkeypatch, capsys, path, kwargs):
        reporter_calls, alerts = self._drive(im_module, monkeypatch, **kwargs)
        capsys.readouterr()

        assert len(reporter_calls) == 1, f"the {path} path did not reach the outage reporter"
        assert len(alerts) == 1
        assert alerts[0]["since"] == reporter_calls[0]["since"] > 0, "the alert must carry the outage start, not its own clock reading"
        assert alerts[0]["count"] == 1

    # A second failing check keeps the first outage rather than restarting the clock the alert delay counts against
    def test_a_second_failing_check_keeps_the_first_outage_start(self, im_module, monkeypatch, capsys):
        reporter_calls, alerts = self._drive(im_module, monkeypatch, profile_error=RuntimeError("500 Server Error"), checks=2)
        capsys.readouterr()

        assert [call["failures"] for call in reporter_calls] == [1, 2]
        assert reporter_calls[0]["since"] == reporter_calls[1]["since"]
        assert [alert["since"] for alert in alerts] == [reporter_calls[0]["since"]] * 2
        assert [alert["count"] for alert in alerts] == [1, 2]

    # The retry note belongs in parentheses on the report line, not on a line of its own or a second starred line
    def test_the_report_line_carries_its_retry_note_in_parentheses(self, im_module, monkeypatch, capsys):
        self._drive(im_module, monkeypatch, profile_error=RuntimeError("500 Server Error"))

        printed = capsys.readouterr().out
        reported = [line for line in printed.splitlines() if line.startswith("* Error: ")]
        assert reported, "the failure was never reported"
        assert re.search(r"^\* Error: .+ \(retrying in .+\)$", reported[0]), reported[0]
        assert "* Error, retrying in " not in printed
        assert not re.search(r"^Retrying in ", printed, re.MULTILINE)
        assert "* Session might not be valid anymore" not in printed

    # A reported outage is closed on screen once a check succeeds, so it is never left open
    def test_a_check_that_succeeds_after_a_failure_announces_the_recovery(self, im_module, monkeypatch, capsys):
        recoveries = []
        monkeypatch.setattr(im_module, "print_outage_recovery", lambda user, lasted, alert_state=None: recoveries.append(user))

        self._drive(im_module, monkeypatch, profile_error=RuntimeError("500 Server Error"), recovers=True)
        capsys.readouterr()

        assert recoveries == ["target"]

    # The banner speaks for a check that said nothing, so a check that reported the end of an outage restarts
    # the quiet clock instead of being contradicted by the line under it
    def test_a_check_that_reported_a_recovery_does_not_claim_it_was_quiet(self, im_module, monkeypatch, capsys):
        self._drive(im_module, monkeypatch, profile_error=RuntimeError("500 Server Error"), checks=3, recovers=True, liveness_seconds=2)

        output = capsys.readouterr().out
        assert "* Monitoring recovered for target after " in output, "the check under test reported no recovery"
        assert "Monitoring healthy for" not in output

    # A run that never recovers must not claim it did
    def test_a_run_that_only_fails_announces_no_recovery(self, im_module, monkeypatch, capsys):
        recoveries = []
        monkeypatch.setattr(im_module, "print_outage_recovery", lambda user, lasted, alert_state=None: recoveries.append(user))

        self._drive(im_module, monkeypatch, profile_error=RuntimeError("500 Server Error"), checks=2)
        capsys.readouterr()

        assert recoveries == []


# Every failure the user can see is built from one closed set of codes, so a message stays testable and deduplicable
class TestRecoveryCodeSet:
    def test_recovery_codes_are_stable(self, im_module):
        assert im_module.RECOVERY_CODES == frozenset({
            "instagram.rate_limited", "instagram.endpoint_retired", "instagram.action_blocked", "instagram.challenge", "instagram.empty_data", "instagram.browser_dialog",
            "session.missing", "session.expired",
            "target.missing", "target.not_found",
            "config.missing", "config.invalid", "config.insecure", "config.impersonate_unsupported",
            "dependency.missing",
            "secret.missing",
            "proxy.unresolved",
            "network.dns", "network.unavailable",
            "smtp.invalid", "smtp.authentication", "smtp.connection",
            "webhook.invalid", "webhook.rejected", "webhook.rate_limited", "webhook.connection",
            "file.unreadable", "file.unwritable", "file.exists",
            "dashboard.unavailable",
            "resource.exhausted",
            "unknown",
        })

    def test_a_code_outside_the_set_is_refused(self, im_module):
        with pytest.raises(ValueError, match="Unsupported recovery code"):
            im_module.make_recovery_advice("instagram.invented", "summary", "fix", False)

    # A declared code nothing can produce is a dead branch, so every one is driven from a real failure
    def test_every_declared_code_is_reachable(self, im_module):
        failures = [
            ("ConnectionException: 429 Too Many Requests", "runtime"),
            ("JSONDecodeError: challenge_required", "runtime"),
            ('AbortDownloadException: 400 Bad Request - "fail" status, message "feedback_required"', "runtime"),
            ('AbortDownloadException: 400 Bad Request - "fail" status, message "feedback_required" when accessing https://www.instagram.com/api/v1/users/web_profile_info/?username=x', "runtime"),
            ("FileNotFoundError: Instagram session file for me not found", "runtime"),
            ("ConnectionException: Login required, redirected", "runtime"),
            ("ProfileNotExistsException: Profile xyz does not exist", "runtime"),
            ("RuntimeError: impersonate target chrome999 is not supported", "runtime"),
            ("ConnectionException: Could not resolve proxy: myproxy.local", "runtime"),
            ("ConnectionException: Could not resolve host: www.instagram.com", "runtime"),
            ("ConnectionException: HTTPSConnectionPool max retries exceeded", "runtime"),
            ("RuntimeError: Instagram returned empty data for posts", "runtime"),
            ("BrowserFollowListError: Instagram's follower list dialog could not be read", "runtime"),
            ("SomethingElse: totally unknown error", "runtime"),
            ("PROXY_URL is not set", "config_missing"),
            ("--identity-budget cannot be negative", "config"),
            ("The dotenv file could not be written", "secret"),
            ("Config file 'instagram_monitor.conf' already exists", "file_exists"),
            ("No such file or directory", "file_read"),
            ("Permission denied", "file_write"),
            ("invalid port number in SMTP_PORT", "smtp_config"),
            (smtplib.SMTPAuthenticationError(535, b"auth failed"), "email"),
            (ValueError("SMTP settings are incorrect"), "email"),
            (OSError("connection refused"), "email"),
            ("WEBHOOK_PROVIDER must be discord or ntfy", "webhook_config"),
            (RuntimeError("429 Too Many Requests"), "webhook"),
            (RuntimeError("connection refused"), "webhook"),
            (RuntimeError("500 Internal Server Error"), "webhook"),
            (RuntimeError("Could not resolve proxy: myproxy.local"), "proxy"),
            (RuntimeError("Firefox cookies were not found"), "session"),
            (OSError("Port 7862 is in use"), "dashboard"),
            (OSError(24, "Too many open files"), "runtime"),
        ]
        produced = {im_module.classify_recovery_error(failure, context=context).code for failure, context in failures}
        produced.add(im_module.missing_dependency_advice("rich", "The Terminal Dashboard cannot start", "pip install rich").code)
        # The doctor builds a few rows outside the classifier, such as the TLS and missing-target rows, so their codes count as reachable too
        produced.update(node.args[0].value for node in ast.walk(ast.parse(inspect.getsource(im_module))) if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "make_recovery_advice" and node.args and isinstance(node.args[0], ast.Constant))

        assert im_module.RECOVERY_CODES - produced == set()

    # Every branch of the rule table names the page that covers it, so no failure leaves the user without somewhere to read
    def test_every_failure_names_a_page(self, im_module):
        guideless = [ast.unparse(row.elts[0]) for row in _rule_table_rows(im_module) if not _names_a_page(row.elts[3])]
        guideless += [ast.unparse(call.args[0]) for call in _context_advice_calls(im_module) if not _names_a_page(call.args[4])]

        assert guideless == []

    # The guard above is only worth its name while it still finds the rows and the calls it inspects
    def test_the_guide_guard_still_inspects_the_source(self, im_module):
        rows = _rule_table_rows(im_module)
        calls = _context_advice_calls(im_module)

        assert len(rows) == 15, "the runtime rule table lost or gained a row"
        assert all(len(row.elts) == 5 for row in rows)
        assert len(calls) >= 15, "the context table lost branches"
        assert all(len(call.args) == 5 for call in calls)

    # Whether waiting can clear a failure decides what the tool says next, so it is carried rather than re-derived
    @pytest.mark.parametrize("msg, retryable", [
        ("ConnectionException: 429 Too Many Requests", True),
        ("ConnectionException: HTTPSConnectionPool max retries exceeded", True),
        ("ConnectionException: Login required, redirected", False),
        ("ProfileNotExistsException: Profile xyz does not exist", False),
        ("ConnectionException: Could not resolve proxy: myproxy.local", False),
    ])
    def test_a_failure_says_whether_retrying_can_clear_it(self, im_module, msg, retryable):
        assert im_module.classify_recovery_error(msg).retryable is retryable

    # Advice reaches the console, the log and the alert channels, so no secret the run holds may travel with it
    def test_a_secret_never_travels_in_advice_text(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/topsecrettoken")

        advice = im_module.make_recovery_advice("unknown", "Posting to https://discord.com/api/webhooks/1/topsecrettoken failed", "Check the address", False, "SMTP_PASSWORD=hunter2pass")

        assert "topsecrettoken" not in advice.summary
        assert "hunter2pass" not in advice.detail


# Anything the tool reports as a problem goes through the classifier, so it carries an action and a page
class TestEveryProblemIsReported:
    # Each entry is a printed line the block would make worse, with the reason it stays a plain print
    EXEMPT = {
        "* Error: Failed to send test email. Check the error message above.": "the failing send already printed its own block",
        "* Error: Test webhook notification failed. Check the error message above.": "the failing send already printed its own block",
        "* Cannot clear the screen contents": "cosmetic, and the run continues unchanged",
        "* Warning: Configured webhook provider did not match the URL. Using ": "self-correcting, and the line says what was used instead",
        "* Warning: Backslashes in ": "carries its own instruction in the same sentence",
        "* Continuing after an account-level action ": "advice text rather than a failure report",
        "* BeHuman ": "one step of the human simulation, which reports its own outcome as a whole",
        "* Warning: Could not apply custom mobile user-agent patch": "an Instaloader internal the user cannot act on, and the next line says what is used instead",
        "* Error: {error_msg} (retrying in ": "the monitoring loop prints its fix through print_fix_hint, which throttles repeats",
        "* Warning: {warning}": "the warning text carries its own reason and threshold",
        "* Warning: It is not easy to be a human": "the simulation is best effort and the run continues",
        "Installation could not start: ": "a wizard question follows, offering the way out",
        "Chromium browser support could not be installed. Choose Firefox or another login method.": "names the alternative in the same sentence",
        "Setup needs a writable dotenv file and cannot use 'none'.": "the wizard re-asks the question straight after",
        "Could not find Firefox cookies at ": "names the command to import later in the same sentence",
        "{label} import failed: ": "the wizard offers the other login methods straight after",
        "{fails} check(s) failed, ": "the doctor summary, which reports rows that carried their own fixes",
        "All critical checks passed with ": "the doctor summary, which reports rows that carried their own fixes",
        "Setup cannot start: --setup requires a config destination.": "names the flag and the replacement in the same sentence",
        "Setup cannot start: --setup requires a dotenv destination.": "names the flag and the replacement in the same sentence",
        "CRITICAL ERROR ENCOUNTERED": "the full traceback follows, which is the technical cause the fix line would point at",
        "The Web Dashboard may have disconnected due to this error.": "a consequence of the crash reported above it",
        "* Error: Python version ": "runs before the module is loaded, so it prints its action and page as literals",
        "* Error: Web Dashboard templates not found": "followed by the searched paths and a numbered list of the four ways to fix it",
        "* Monitoring failure changed for {target}. {advice.summary}": "a one-line note on a classified outage that already had its full report",
    }

    def test_every_reported_problem_carries_an_action(self, im_module):
        bare = [text for _lineno, text in _problem_prints(im_module) if not any(text.startswith(prefix) for prefix in self.EXEMPT)]

        assert bare == []

    # The guard above is only worth its name while it still finds the prints it inspects
    def test_the_routing_guard_still_inspects_the_source(self, im_module):
        assert len(_problem_prints(im_module)) >= 25, "the problem-print scan stopped finding its subjects"

    # The helper is what puts a fix under every one of those call sites, so it has to be the one in use
    def test_the_recovery_block_is_the_reporting_path(self, im_module):
        source = inspect.getsource(im_module)

        assert source.count("print_recovery_error(") > 60
        assert source.count("missing_dependency_advice(") > 4

    # The block is two lines: what went wrong, then the one action that clears it
    def test_the_block_prints_the_summary_then_the_action(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)

        im_module.print_recovery_error("The check interval must be greater than 0", context="config")

        lines = capsys.readouterr().out.splitlines()
        assert lines[0] == "* Error: The check interval must be greater than 0"
        assert lines[1].startswith("To fix: Correct the value")
        assert lines[2] == f"Guide: {im_module.CONFIG_GUIDE_URL}"

    # A problem the run recovers from keeps its own label, so a warning is not reported as a failure
    def test_a_warning_keeps_its_label(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)

        im_module.print_recovery_error("dotenv file '/nope/.env' does not exist", context="dotenv_missing", label="Warning")

        assert capsys.readouterr().out.splitlines()[0].startswith("* Warning: dotenv file")

    # An optional library is only actionable with the command that installs it into this interpreter
    def test_a_missing_library_names_the_command_that_installs_it(self, im_module):
        advice = im_module.missing_dependency_advice("rich", "The Terminal Dashboard cannot start", im_module.pip_install_command("rich"))

        assert advice.code == "dependency.missing"
        assert "'rich' library is missing" in advice.summary
        assert "-m pip install rich" in advice.fix
        assert im_module.INSTALLATION_GUIDE_URL in advice.fix

    # A secret the run holds can appear in the text a failing call carries, so the summary is cleaned as well
    def test_the_summary_a_call_site_supplies_is_cleaned(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "colorize", lambda theme, text: text)
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/topsecrettoken")

        im_module.print_recovery_error("Sending the webhook failed: https://discord.com/api/webhooks/1/topsecrettoken refused", context="webhook")

        assert "topsecrettoken" not in capsys.readouterr().out


# A local resource limit reads as a remote failure unless it is recognized before the context rules run
class TestLocalResourceLimits:
    # The limit is this process running out of descriptors, so nothing about Instagram or the network explains it
    def test_a_file_descriptor_limit_is_not_reported_as_a_service_failure(self, im_module):
        advice = im_module.classify_recovery_error(OSError(24, "Too many open files"))

        assert advice.code == "resource.exhausted"
        assert "not an Instagram problem" in advice.summary
        assert "ulimit -n" in advice.fix
        assert advice.retryable is False

    # Verifies the descriptor limit is matched as a whole errno, so errno 240 or 241 in a message is not mistaken for it
    def test_a_neighbouring_errno_is_not_a_file_descriptor_limit(self, im_module):
        assert im_module.is_too_many_open_files(RuntimeError("[Errno 24] Too many open files")) is True
        assert im_module.is_too_many_open_files(RuntimeError("[Errno 240] something else")) is False
        assert im_module.is_too_many_open_files(RuntimeError("[Errno 241] something else")) is False

    # The limit usually surfaces wrapped in whatever call hit it, so the whole chain is walked
    @pytest.mark.parametrize("context", ["runtime", "file_write", "webhook", "email", "config"])
    def test_the_limit_is_found_through_the_cause_chain(self, im_module, context):
        try:
            try:
                raise OSError(24, "Too many open files")
            except OSError as inner:
                raise RuntimeError("the request could not be sent") from inner
        except RuntimeError as outer:
            assert im_module.classify_recovery_error(outer, context=context).code == "resource.exhausted"

    # Walking a chain must end even when an exception refers back to itself
    def test_the_chain_walk_ends_on_a_cycle(self, im_module):
        first = RuntimeError("first")
        second = RuntimeError("second")
        first.__cause__ = second
        second.__cause__ = first

        assert len(list(im_module.iter_exc_chain(first))) == 8

    # A remote failure that merely mentions files is not the local limit
    def test_an_unrelated_failure_is_not_mistaken_for_the_limit(self, im_module):
        assert im_module.is_too_many_open_files(OSError(2, "No such file or directory")) is False
        assert im_module.is_too_many_open_files(None) is False


class TestTheRecoveryPrinterContracts:
    # One concept carried three names across this family, and this tool held the family name over the other
    # contract: render_recovery_error(exc, ...) raised AttributeError here while it classified in five siblings
    def test_the_recovery_printers_share_one_contract(self, im_module):
        advice_first = ("advice", "debug", "retry_note", "with_fix", "label")
        error_first = ("error", "context", "debug", "detail", "retry_note", "with_fix", "label")

        assert tuple(inspect.signature(im_module.render_recovery_advice).parameters) == advice_first + ("summary",)
        assert tuple(inspect.signature(im_module.render_recovery_error).parameters) == error_first + ("summary", "is_logged_in")
        # This tool's own parameters follow the shared ones, so a call written for a sibling still means the same thing
        assert tuple(inspect.signature(im_module.print_recovery_advice).parameters) == advice_first + ("summary",)
        assert tuple(inspect.signature(im_module.print_recovery_error).parameters) == error_first + ("summary", "is_logged_in")

    # The advice pair prints what the caller built, so a summary the classifier would never produce survives the trip
    def test_the_advice_printer_does_not_reclassify(self, im_module, capsys):
        im_module.DEBUG_MODE = False
        advice = im_module.make_recovery_advice("network.unavailable", "a summary no rule produces", "a fix of its own", True)

        returned = im_module.print_recovery_advice(advice)

        assert capsys.readouterr().out == "* Error: a summary no rule produces\nTo fix: a fix of its own\n"
        assert returned is advice

    # The error pair classifies an exception the way every sibling does, rather than treating it as the headline
    def test_the_error_printer_classifies_an_exception(self, im_module, capsys):
        im_module.DEBUG_MODE = False

        returned = im_module.print_recovery_error(ConnectionError("connection refused"), context="runtime")

        assert capsys.readouterr().out.startswith(f"* Error: {returned.summary}\n")

    # A caller that writes its own headline keeps it, which is why the summary slot exists at all
    def test_a_caller_written_headline_survives_the_classifier(self, im_module, capsys):
        im_module.DEBUG_MODE = False

        im_module.print_recovery_error("Could not write the CSV entry to '/tmp/x.csv'", context="file_write")

        printed = capsys.readouterr().out
        assert printed.startswith("* Error: Could not write the CSV entry to '/tmp/x.csv'\n")
        assert "To fix: " in printed

    # Both front doors reach the same renderer, so the retry note, the label and a suppressed fix behave the same way
    def test_both_front_doors_render_the_same_line(self, im_module):
        im_module.DEBUG_MODE = False
        error = ConnectionError("connection refused")
        advice = im_module.classify_recovery_error(error, "runtime")

        through_advice = im_module.render_recovery_advice(advice, retry_note="retrying in 5 minutes", with_fix=False, label="Warning")
        through_error = im_module.render_recovery_error(error, "runtime", retry_note="retrying in 5 minutes", with_fix=False, label="Warning")

        assert through_advice == through_error
        assert through_advice == f"* Warning: {advice.summary} (retrying in 5 minutes)"

    # A carried advice is the classifier's own answer, so re-reading its message text would be a second opinion
    def test_a_carried_advice_is_not_reclassified_from_its_message(self, im_module):
        advice = im_module.make_recovery_advice("instagram.rate_limited", "Instagram is rate limiting this session", "Wait it out", True)

        assert im_module.classify_recovery_error(im_module.RecoveryError(advice)) is advice


# A detail that only repeats the summary spends a line saying nothing, so the block drops it and keeps a real one
def test_a_detail_repeating_the_summary_is_dropped(im_module):
    repeated = im_module.make_recovery_advice("unknown", "the same sentence twice", "a fix", False, "the same sentence twice")
    differing = im_module.make_recovery_advice("unknown", "the summary", "a fix", False, "the raw cause")

    assert "Technical detail:" not in im_module.render_recovery_advice(repeated, debug=True)
    assert "Technical detail: the raw cause" in im_module.render_recovery_advice(differing, debug=True)


# A run that already prints the technical cause cannot be told to re-run for it
def test_the_unrecognized_failure_fix_follows_the_diagnostic_mode(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    plain = im_module.classify_recovery_error(Exception("a wholly unfamiliar failure"), "runtime").fix
    monkeypatch.setattr(im_module, "DEBUG_MODE", True)
    debugging = im_module.classify_recovery_error(Exception("a wholly unfamiliar failure"), "runtime").fix

    assert "--debug" in plain
    assert "--debug" not in debugging
