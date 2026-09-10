"""Tests for error classification and session/IP flag detection.

The flag probe normally resolves a canonical public account over the network.
Here profile_from_username_resilient is stubbed so the logic runs fully offline.
"""



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


class TestNotifyMonitoringError:
    # Captures thresholded channel delivery without contacting SMTP or webhook endpoints, each channel answering as told
    def _capture(self, im_module, monkeypatch, email_results=(0,), webhook_results=(0,)):
        calls = {"email": [], "webhook": []}
        monkeypatch.setattr(im_module, "send_email", lambda *a, **k: calls["email"].append((a, k)) or email_results[min(len(calls["email"]), len(email_results)) - 1])
        monkeypatch.setattr(im_module, "send_webhook", lambda *a, **k: calls["webhook"].append((a, k)) or webhook_results[min(len(calls["webhook"]), len(webhook_results)) - 1])
        monkeypatch.setattr(im_module, "ERROR_FAILURE_THRESHOLD", 2)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "ops@example.com", raising=False)
        monkeypatch.setattr(im_module, "SMTP_SSL", True, raising=False)
        return calls

    # Runs one failing check through the alert with the given error, keeping the state between calls
    def _notify(self, im_module, state, error, failure_count):
        advice = im_module.classify_recovery_error(error, is_logged_in=True)
        return im_module.notify_monitoring_error("targetuser", advice, error, failure_count, 60, state)

    def test_email_and_webhook_send_once_at_threshold(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        state = im_module.ErrorAlertState()

        results = [self._notify(im_module, state, "401 Unauthorized", failure_count) for failure_count in (1, 2, 3)]

        assert results == [False, True, False]
        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 1
        assert "failure #2, threshold: 2" in calls["email"][0][0][0]
        assert "failure #2, threshold: 2" in calls["webhook"][0][0][1]
        assert "To fix:" in calls["email"][0][0][1]

    def test_webhook_threshold_does_not_depend_on_email_toggle(self, im_module, monkeypatch):
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
        state = im_module.ErrorAlertState()

        for failure_count in (2, 3, 4):
            self._notify(im_module, state, "401 Unauthorized", failure_count)

        assert len(calls["email"]) == 1
        assert len(calls["webhook"]) == 2

    # A failure that changes category is a different failure, so it earns each channel a new alert
    def test_a_changed_failure_category_earns_a_new_alert(self, im_module, monkeypatch):
        calls = self._capture(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "ERROR_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", True)
        monkeypatch.setattr(im_module, "WEBHOOK_ERROR_NOTIFICATION", True)
        state = im_module.ErrorAlertState()

        self._notify(im_module, state, "401 Unauthorized", 2)
        self._notify(im_module, state, "401 Unauthorized", 3)
        self._notify(im_module, state, "The read operation timed out", 4)

        assert len(calls["email"]) == 2
        assert len(calls["webhook"]) == 2

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


class TestNotifySessionFlagged:
    """A flag is terminal and operator-actionable, so the alert must fire on detection regardless of ERROR_FAILURE_THRESHOLD."""

    # Replaces send_email/send_webhook with recorders and gives the email path valid-looking globals
    def _capture(self, im_module, monkeypatch):
        calls = {"email": [], "webhook": []}
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
