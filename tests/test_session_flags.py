"""Tests for error classification and session/IP flag detection.

The flag probe normally resolves a canonical public account over the network.
Here profile_from_username_resilient is stubbed so the logic runs fully offline.
"""

import threading
import time

import pytest


class _Bot:
    """Stand-in for an instaloader bot exposing only the mobile JSON call."""

    def __init__(self, iphone_json):
        self.context = type("Context", (), {"get_iphone_json": staticmethod(iphone_json)})()


class _Profile:
    """Stand-in for an instaloader profile exposing only what the reels count needs."""

    def __init__(self, get_reels):
        self.userid = 123
        self.get_reels = get_reels


class _FakeBot:
    """Stand-in for an instaloader bot; only its identity matters to the code under test."""

    pass


# Returns a resolver stub that always raises with the given message
def _raiser(message):
    def _inner(bot, username):
        raise Exception(message)

    return _inner


# Configures usable local delivery settings for tests that replace the network transports
def _configure_delivery_settings(im_module, monkeypatch):
    for name, value in (("SMTP_HOST", "smtp.example.com"), ("SMTP_PORT", 587), ("SMTP_USER", "sender@example.com"), ("SMTP_PASSWORD", "test-password"), ("SENDER_EMAIL", "sender@example.com"), ("RECEIVER_EMAIL", "ops@example.com"), ("WEBHOOK_URL", "https://discord.com/api/webhooks/1/token"), ("WEBHOOK_PROVIDER", "discord")):
        monkeypatch.setattr(im_module, name, value)


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

    # Instaloader stops on three account-level replies, so each one is a flag whichever endpoint returned it
    def test_every_instaloader_abort_reply_is_a_flag_trigger(self, im_module):
        for message in ("feedback_required", "checkpoint_required", "challenge_required"):
            error = f'AbortDownloadException: 400 Bad Request - "fail" status, message "{message}" when accessing https://i.instagram.com/api/v1/feed/reels_media/?reel_ids=123'
            assert im_module.is_session_flagged(error, _FakeBot()) is True

    def test_profile_not_found_probes_and_reports_flagged(self, im_module, monkeypatch):
        # Probe of the canonical account also fails -> session is genuinely flagged
        monkeypatch.setattr(im_module, "profile_from_username_resilient", _raiser("ProfileNotExistsException: instagram missing"))
        assert im_module.is_session_flagged("ProfileNotExistsException: target gone", _FakeBot()) is True

    def test_profile_not_found_probes_and_reports_target_gone(self, im_module, monkeypatch):
        # Probe of the canonical account succeeds -> only the target is gone, session is fine
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, username: object())
        assert im_module.is_session_flagged("ProfileNotExistsException: target gone", _FakeBot()) is False


class TestNotifyMonitoringError:
    # Captures thresholded channel delivery without contacting SMTP or webhook endpoints, each channel answering as told
    def _capture(self, im_module, monkeypatch, email_results=(0,), webhook_results=(0,)):
        calls = {"email": [], "webhook": []}
        _configure_delivery_settings(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "send_email", lambda *a, **k: calls["email"].append((a, k)) or email_results[min(len(calls["email"]), len(email_results)) - 1])
        monkeypatch.setattr(im_module, "send_webhook", lambda *a, **k: calls["webhook"].append((a, k)) or webhook_results[min(len(calls["webhook"]), len(webhook_results)) - 1])
        monkeypatch.setattr(im_module, "ERROR_ALERT_AFTER_SECONDS", 300)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "ops@example.com", raising=False)
        monkeypatch.setattr(im_module, "SMTP_SSL", True, raising=False)
        return calls

    # Runs one failing check through the alert with the given error, keeping the state between calls
    def _notify(self, im_module, state, error, failure_count, lasted=600):
        advice = im_module.classify_recovery_error(error, is_logged_in=True)
        return im_module.notify_monitoring_error("targetuser", advice, int(time.time()) - lasted, failure_count, 60, state)

    # A failure the tool can retry away waits until it has lasted ERROR_ALERT_AFTER_SECONDS, then alerts each channel once
    def test_email_and_webhook_send_once_after_the_alert_delay(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        state = im_module.ErrorAlertState()

        results = [self._notify(im_module, state, "The read operation timed out", failure_count, lasted) for failure_count, lasted in ((1, 0), (2, 299), (3, 300), (4, 3600))]

        assert results == [False, False, True, False]
        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 1
        assert calls["email"][0][0][0].startswith("Instagram Monitor error: ")
        assert "(user: targetuser)" in calls["email"][0][0][0]
        assert "Failed checks in a row: 3" in calls["email"][0][0][1]
        assert "Failing since: " in calls["email"][0][0][1]
        assert "To fix:" in calls["email"][0][0][1]

    # An unavailable channel is not recorded as a failed attempt and can send when its settings are corrected
    def test_unavailable_channels_wait_silently_for_valid_settings(self, im_module, monkeypatch, capsys):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "")
        state = im_module.ErrorAlertState()

        assert self._notify(im_module, state, "401 Unauthorized", 1) is False
        assert calls == {"email": [], "webhook": []}
        assert (state.email_failures, state.webhook_failures) == (0, 0)
        assert capsys.readouterr().out == ""

        monkeypatch.setattr(im_module, "SMTP_PASSWORD", "test-password")
        monkeypatch.setattr(im_module, "WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")

        assert self._notify(im_module, state, "401 Unauthorized", 2) is True
        assert len(calls["email"]) == len(calls["webhook"]) == 1

    # A failure that cannot clear on its own, such as an expired session, is alerted on the first failing check
    def test_a_failure_the_tool_cannot_retry_away_alerts_at_once(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)

        assert im_module.classify_recovery_error("401 Unauthorized", is_logged_in=True).retryable is False
        assert self._notify(im_module, im_module.ErrorAlertState(), "401 Unauthorized", 1, 0) is True
        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 1

    def test_webhook_alert_does_not_depend_on_email_toggle(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)

        assert self._notify(im_module, im_module.ErrorAlertState(), "401 Unauthorized", 2) is True
        assert calls["email"] == []
        assert len(calls["webhook"]) == 1

    # Each channel is tracked on its own, so the one that failed is retried while the one that landed is left alone
    def test_a_failed_channel_is_retried_and_a_delivered_one_is_not(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch, email_results=(0,), webhook_results=(1, 0))
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "ERROR_ALERT_RETRY_SECONDS", 0)
        state = im_module.ErrorAlertState()

        for failure_count in (2, 3, 4):
            self._notify(im_module, state, "401 Unauthorized", failure_count)

        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 2

    # A channel that failed is held for five minutes, then for twice the previous wait, so a broken mail server is
    # not dialled on every failing check of a long outage, and the hold is said once per failed attempt
    def test_a_failed_channel_backs_off_before_it_is_tried_again(self, im_module, monkeypatch, capsys):
        calls = self._capture(im_module, monkeypatch, email_results=(1, 1, 0), webhook_results=(0,))
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)
        monkeypatch.setattr(im_module, "ERROR_ALERT_RETRY_SECONDS", 300)
        monkeypatch.setattr(im_module, "ERROR_ALERT_RETRY_MAX_SECONDS", 3600)
        clock = {"now": 1_000_000}
        monkeypatch.setattr(im_module.time, "time", lambda: clock["now"])
        state = im_module.ErrorAlertState()
        advice = im_module.classify_recovery_error("401 Unauthorized", is_logged_in=True)

        attempts = []
        for offset in (0, 60, 299, 300, 600, 899, 900, 1200):
            clock["now"] = 1_000_000 + offset
            im_module.notify_monitoring_error("targetuser", advice, 1_000_000, 1, 60, state)
            attempts.append(len(calls["email"]))

        assert attempts == [1, 1, 1, 2, 2, 2, 3, 3]
        assert state.email_sent is True
        assert state.email_failures == 0
        printed = capsys.readouterr().out
        assert "* The email alert is on hold for 5 minutes after 1 attempt, then tried again" in printed
        assert "* The email alert is on hold for 10 minutes after 2 attempts, then tried again" in printed

    # The wait stops growing at the cap, so a server that stays down is still tried every hour
    def test_the_backoff_is_capped(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "ERROR_ALERT_RETRY_SECONDS", 300)
        monkeypatch.setattr(im_module, "ERROR_ALERT_RETRY_MAX_SECONDS", 3600)
        state = im_module.ErrorAlertState()

        for _ in range(6):
            state.record("webhook", True, False, 0)

        assert state.webhook_failures == 6
        assert state.webhook_retry_at == 3600
        assert state.pending("webhook", True, 3599) is False
        assert state.pending("webhook", True, 3600) is True

    # A delivery clears the hold, and a new outage starts each channel afresh
    def test_a_delivery_or_a_reset_clears_the_hold(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "ERROR_ALERT_RETRY_SECONDS", 300)
        state = im_module.ErrorAlertState()
        state.record("email", True, False, 0)
        state.record("email", True, True, 300)

        assert (state.email_sent, state.email_failures, state.email_retry_at) == (True, 0, 0)

        state.record("webhook", True, False, 0)
        state.reset()

        assert (state.webhook_failures, state.webhook_retry_at) == (0, 0)
        assert state.pending("webhook", True, 0) is True

    # One outage earns one alert per channel, however the failure changes, until a check succeeds again
    def test_a_changed_failure_category_does_not_earn_a_second_alert(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        state = im_module.ErrorAlertState()

        self._notify(im_module, state, "401 Unauthorized", 2)
        self._notify(im_module, state, "401 Unauthorized", 3)
        self._notify(im_module, state, "The read operation timed out", 4)

        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 1

    # A run that recovered and fails again is in a new outage, which deserves its own alert
    def test_a_reset_state_alerts_again(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        state = im_module.ErrorAlertState()

        self._notify(im_module, state, "401 Unauthorized", 2)
        state.reset()
        self._notify(im_module, state, "401 Unauthorized", 2)

        assert len(calls["email"]) == 2
        assert len(calls["webhook"]) == 2


class TestOneOutageIsOneAlertWhateverItsSubtype:
    """The console groups every network failure of one outage through outage_family, the alert did not.

    Comparing the exact code meant an internet outage alternating between an unresolved host and a timeout
    earned a fresh alert on every check and cleared the hold of a channel that was failing to deliver, so a
    broken mail server was dialled again on each one. The console reported a single outage throughout.
    """

    # Drives the console reporter and the alert over one run of failures, sharing a clock and an alert state
    @staticmethod
    def _run(im_module, monkeypatch, errors, delivered=True):
        clock = {"now": 1_000_000}
        sent = []
        _configure_delivery_settings(im_module, monkeypatch)
        monkeypatch.setattr(im_module.time, "time", lambda: clock["now"])
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "ERROR_ALERT_AFTER_SECONDS", 0)
        monkeypatch.setattr(im_module, "ERROR_ALERT_RETRY_SECONDS", 300)
        monkeypatch.setattr(im_module, "webhook_event_enabled", lambda event: False)
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: sent.append(args[0]) or (0 if delivered else 1))
        reporter, state = im_module.OutageReporter(), im_module.ErrorAlertState()
        reports = []
        for error in errors:
            advice = im_module.classify_recovery_error(error, is_logged_in=True)
            reports.append(reporter.failed(advice))
            im_module.notify_monitoring_error("targetuser", advice, reporter.since, reporter.failures, 60, state)
            clock["now"] += 360
        return reports, sent, state

    # The console says one outage, so the operator must not receive an alert for each subtype it flaps through
    def test_a_flapping_outage_alerts_once(self, im_module, monkeypatch):
        reports, sent, _ = self._run(im_module, monkeypatch, ["Temporary failure in name resolution", "The read operation timed out"] * 2)

        assert reports == ["full", "", "", ""]
        assert len(sent) == 1

    # The hold has to survive the subtype changing, or the growing wait never applies to a flapping outage
    def test_a_flapping_outage_holds_a_failing_channel_like_a_steady_one(self, im_module, monkeypatch):
        _, flapping_sent, flapping_state = self._run(im_module, monkeypatch, ["Temporary failure in name resolution", "The read operation timed out"] * 3, delivered=False)
        _, steady_sent, steady_state = self._run(im_module, monkeypatch, ["Temporary failure in name resolution"] * 6, delivered=False)

        assert len(flapping_sent) == len(steady_sent)
        assert flapping_state.email_failures == steady_state.email_failures > 1

    # A failure from another family is still the same outage, so the console reports the change while the alert is not repeated
    def test_a_failure_from_another_family_is_reported_without_a_second_alert(self, im_module, monkeypatch):
        reports, sent, _ = self._run(im_module, monkeypatch, ["Temporary failure in name resolution", "The read operation timed out", "429 Too Many Requests"])

        assert reports == ["full", "", "changed"]
        assert len(sent) == 1


class TestNotifySessionFlagged:
    """A flag is terminal and operator-actionable, so the alert must fire on detection regardless of the error alert delay."""

    # Replaces send_email/send_webhook with recorders and gives the email path valid-looking globals
    def _capture(self, im_module, monkeypatch):
        calls = {"email": [], "webhook": []}
        _configure_delivery_settings(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "send_email", lambda *a, **k: calls["email"].append((a, k)))
        monkeypatch.setattr(im_module, "send_webhook", lambda *a, **k: calls["webhook"].append((a, k)))
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "ops@example.com", raising=False)
        monkeypatch.setattr(im_module, "SMTP_SSL", True, raising=False)
        return calls

    def test_emails_and_webhooks_when_error_notification_on(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        im_module.notify_session_flagged("targetuser", "Session flagged.", "KeyError: data")
        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 1
        # The triggering error is carried in the email body for the operator
        assert "KeyError: data" in calls["email"][0][0][1]
        # Sent as an error, past the switch the shared helper already applied
        assert calls["webhook"][0][1]["notification_type"] == "error"
        assert calls["webhook"][0][1]["force"] is True

    def test_email_suppressed_when_error_notification_off(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", False, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        im_module.notify_session_flagged("targetuser", "Session flagged.", "KeyError: data")
        # Email honors the error-notification toggle while the webhook follows its own switch
        assert calls["email"] == []
        assert len(calls["webhook"]) == 1

    def test_the_webhook_follows_its_own_switch(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", False)
        im_module.notify_session_flagged("targetuser", "Session flagged.", "KeyError: data")
        assert len(calls["email"]) == 1
        assert calls["webhook"] == []

    def test_concurrent_flags_alert_once_within_window(self, im_module, monkeypatch):
        # One shared session flag trips every target thread, but only the first alert within the window goes out
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True, raising=False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        for target in ("user_a", "user_b", "user_c"):
            im_module.notify_session_flagged(target, "Session flagged.", "KeyError: data")
        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 1


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


class TestHandleFlaggedSession:
    _STORY_CHALLENGE = 'AbortDownloadException: 400 Bad Request - "fail" status, message "challenge_required" when accessing https://i.instagram.com/api/v1/feed/reels_media/?reel_ids=123'

    # Keeps the flagged flow offline and quiet: no alert delivery, no dashboard writes and no process exit
    def _quiet(self, im_module, monkeypatch):
        calls = {"notify": [], "exit": [], "reload": []}
        monkeypatch.setattr(im_module, "notify_session_flagged", lambda user, err_str, error_msg: calls["notify"].append((user, error_msg)))
        monkeypatch.setattr(im_module, "signal_handler", lambda sig, frame, message=None: calls["exit"].append(message))
        monkeypatch.setattr(im_module, "reload_session_after_refresh", lambda bot, user: calls["reload"].append(user))
        monkeypatch.setattr(im_module, "update_ui_data", lambda *a, **k: None)
        monkeypatch.setattr(im_module, "update_check_times", lambda *a, **k: None)
        monkeypatch.setattr(im_module, "log_activity", lambda *a, **k: None)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_STOP_EVENTS", {})
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        return calls

    # Without the Web Dashboard a flag alerts once and ends the process, so the caller stops its target
    def test_without_the_web_dashboard_it_alerts_and_exits(self, im_module, monkeypatch, capsys):
        calls = self._quiet(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)

        assert im_module.handle_flagged_session("targetuser", self._STORY_CHALLENGE, _FakeBot(), None, 0) is False
        assert calls["notify"] == [("targetuser", self._STORY_CHALLENGE)]
        assert calls["exit"] == [""]
        assert calls["reload"] == []
        out = capsys.readouterr().out
        assert "has been flagged" in out
        assert "To fix:" in out

    # With the Web Dashboard a target that is stopped while it waits does not resume
    def test_a_stop_while_waiting_ends_the_target(self, im_module, monkeypatch):
        calls = self._quiet(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True)
        stop_event = threading.Event()
        stop_event.set()

        assert im_module.handle_flagged_session("targetuser", "checkpoint_required", _FakeBot(), stop_event, 0) is False
        assert calls["exit"] == []
        assert calls["reload"] == []

    # A session re-imported from the Web Dashboard is reloaded into the bot and the target resumes
    def test_a_session_refresh_reloads_and_resumes(self, im_module, monkeypatch):
        calls = self._quiet(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True)
        monkeypatch.setattr(im_module, "wait_for_session_refresh", lambda observed, timeout=1.0: observed + 1)

        assert im_module.handle_flagged_session("targetuser", "checkpoint_required", _FakeBot(), threading.Event(), 0) is True
        assert calls["reload"] == ["targetuser"]
        assert calls["exit"] == []

    # A caller that restarts its pass after the refresh skips the in-place reload
    def test_a_restarting_caller_skips_the_reload(self, im_module, monkeypatch):
        calls = self._quiet(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", True)
        monkeypatch.setattr(im_module, "wait_for_session_refresh", lambda observed, timeout=1.0: observed + 1)

        assert im_module.handle_flagged_session("targetuser", "checkpoint_required", _FakeBot(), threading.Event(), 0, reload_session=False) is True
        assert calls["reload"] == []


class TestAChallengeOnALowerEndpointIsNotSwallowed:
    """The mobile reels helper falls back to an anonymous scan when its own endpoint fails.

    A challenge is about the account, so falling back would send a second request while Instagram
    is already refusing the session, and the caller would never see the challenge at all.
    """

    # Builds a bot whose mobile endpoint fails with the given message and records every call made
    @staticmethod
    def _bot(im_module, monkeypatch, message, calls):
        def iphone_json(*args, **kwargs):
            calls.append("mobile")
            raise im_module.instaloader.exceptions.AbortDownloadException(message)

        def reels():
            calls.append("fallback")
            return iter([])

        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, username: _Profile(reels))
        return _Bot(iphone_json)

    def test_a_challenge_reaches_the_caller_instead_of_a_second_request(self, im_module, monkeypatch):
        calls = []
        bot = self._bot(im_module, monkeypatch, "400 checkpoint_required", calls)

        with pytest.raises(im_module.instaloader.exceptions.AbortDownloadException):
            im_module.get_total_reels_count("target", bot, False)

        assert calls == ["mobile"]

    def test_an_expired_session_reaches_the_caller_too(self, im_module, monkeypatch):
        calls = []
        bot = self._bot(im_module, monkeypatch, "401 Unauthorized", calls)

        with pytest.raises(im_module.instaloader.exceptions.AbortDownloadException):
            im_module.get_total_reels_count("target", bot, False)

        assert calls == ["mobile"]

    # An endpoint that simply did not answer says nothing about the account, so the fallback still runs
    def test_an_endpoint_failure_still_falls_back(self, im_module, monkeypatch):
        calls = []
        bot = self._bot(im_module, monkeypatch, "404 Not Found", calls)

        assert im_module.get_total_reels_count("target", bot, False) == 0
        assert calls == ["mobile", "fallback"]


class TestMonitoringRecoveryAlert:
    # Captures channel delivery without contacting SMTP or webhook endpoints
    @staticmethod
    def _capture(im_module, monkeypatch):
        sent = {"email": [], "webhook": []}
        _configure_delivery_settings(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "send_email", lambda *a, **k: sent["email"].append(a) or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *a, **k: sent["webhook"].append(a) or 0)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "ops@example.com", raising=False)
        monkeypatch.setattr(im_module, "SMTP_SSL", True, raising=False)
        monkeypatch.setattr(im_module, "webhook_event_enabled", lambda event: False)
        return sent

    # A recovery alert answers the failure alert, so it goes only where that failure alert was delivered
    def test_a_channel_that_was_never_alerted_hears_nothing(self, im_module, monkeypatch):
        sent = self._capture(im_module, monkeypatch)
        state = im_module.ErrorAlertState()

        assert im_module.notify_monitoring_recovery("targetuser", state) is False
        assert sent["email"] == [] and sent["webhook"] == []

    # The channel that carried the failure alert is told the failure ended, naming how long it lasted and what it was
    def test_the_alerted_channel_is_told_the_failure_ended(self, im_module, monkeypatch):
        sent = self._capture(im_module, monkeypatch)
        state = im_module.ErrorAlertState()
        advice = im_module.classify_recovery_error("The read operation timed out", is_logged_in=True)
        state.remember(advice, int(time.time()) - 514)
        state.record("email", True, True, int(time.time()))

        assert im_module.notify_monitoring_recovery("targetuser", state) is True
        assert len(sent["email"]) == 1
        subject, body = sent["email"][0][0], sent["email"][0][1]
        assert subject.startswith("Instagram Monitor recovered: monitoring targetuser resumed after ")
        assert "Monitoring recovered for targetuser after " in body
        assert advice.summary in body
        assert sent["webhook"] == []
