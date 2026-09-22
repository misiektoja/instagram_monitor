"""Offline tests for the jitter and back-off wrapper around every Instagram request.

The wrapper gives up after a few back-offs. What it raises then decides what every layer above does,
so a rate limit reported as a missing endpoint sends the auto follow list source to GraphQL and scans
the whole list again while Instagram is already throttling the account.
"""

from types import SimpleNamespace

import instaloader
import pytest

import instagram_monitor as im

FOLLOWERS_URL = "https://www.instagram.com/api/v1/friendships/12/followers/"


# Returns a response shaped the way the wrapper reads it
def _response(status, body=""):
    return SimpleNamespace(status_code=status, text=body, headers={})


@pytest.fixture
# Runs the real wrapper with jitter on, no serialization, no waiting and no breaker in the way
def wrapper(monkeypatch):
    monkeypatch.setattr(im, "ENABLE_JITTER", True, raising=False)
    monkeypatch.setattr(im, "MULTI_TARGET_SERIALIZE_HTTP", False, raising=False)
    monkeypatch.setattr(im, "SKIP_WRAP_MESSAGES", True, raising=False)
    monkeypatch.setattr(im, "JITTER_VERBOSE", False, raising=False)
    monkeypatch.setattr(im, "DEBUG_MODE", False, raising=False)
    monkeypatch.setattr(im, "CIRCUIT_BREAKER", False, raising=False)
    monkeypatch.setattr(im.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(im.random, "expovariate", lambda rate: 1.0)
    monkeypatch.setattr(im.random, "uniform", lambda low, high: 0)

    # Wraps a request that always answers with the given response and counts the attempts
    def build(response):
        attempts = []

        def request(*args, **kwargs):
            attempts.append(1)
            return response

        return im.instagram_wrap_request(request), attempts

    return build


class TestASpentBackoffBudgetKeepsItsRealCause:
    # A throttled request answered 429 four times is a rate limit, and the transport is what blocks it
    def test_repeated_throttling_is_reported_as_a_rate_limit(self, wrapper):
        wrapped, attempts = wrapper(_response(429, "Too Many Requests"))

        with pytest.raises(instaloader.exceptions.TooManyRequestsException) as error:
            wrapped("GET", FOLLOWERS_URL)

        assert len(attempts) == 4
        assert im.classify_failure_class(im.format_error_message(error.value)) == "rate_limit"

    # A checkpoint reply is Instagram acting against the account, so it has to classify as a challenge
    def test_the_first_checkpoint_is_reported_as_a_challenge(self, wrapper):
        wrapped, attempts = wrapper(_response(400, 'checkpoint_required'))

        with pytest.raises(instaloader.exceptions.AbortDownloadException) as error:
            wrapped("GET", FOLLOWERS_URL)

        assert len(attempts) == 1
        assert im.classify_failure_class(im.format_error_message(error.value)) == "challenge"
        assert im.is_session_flagged(im.format_error_message(error.value), None) is True

    # Neither one may look like a missing endpoint, or the auto list source rescans on the other surface
    @pytest.mark.parametrize(("status", "body"), [(429, "Too Many Requests"), (400, "checkpoint_required")])
    def test_neither_is_mistaken_for_a_retryable_endpoint_failure(self, wrapper, status, body):
        wrapped, _ = wrapper(_response(status, body))

        with pytest.raises(Exception) as error:
            wrapped("GET", FOLLOWERS_URL)

        assert im.rest_failure_is_recoverable(error.value) is False

    # A genuine 404 still means the endpoint is gone, which is the one case worth a second surface
    def test_a_real_missing_endpoint_is_still_retryable(self):
        assert im.rest_failure_is_recoverable(instaloader.exceptions.QueryReturnedNotFoundException("404 Not Found")) is True

    # An answer the wrapper is happy with is returned untouched after the back-off clears
    def test_a_request_that_recovers_returns_its_response(self, monkeypatch, wrapper):
        replies = [_response(429, "Too Many Requests"), _response(200, "ok")]
        monkeypatch.setattr(im, "_update_progress_bar", lambda resp: None, raising=False)

        def request(*args, **kwargs):
            return replies.pop(0)

        wrapped = im.instagram_wrap_request(request)

        assert wrapped("GET", FOLLOWERS_URL).status_code == 200


class TestTheAutoListSourceSeesTheRealCause:
    """The wrapper and the auto source were each correct on their own.

    The wrapper reported a spent back-off budget as a missing endpoint and the auto source treated a
    missing endpoint as reason to read the whole list over GraphQL, so a throttled or challenged
    account was answered with a second full scan on the other surface.
    """

    # Drives the real wrapper underneath the real auto source and returns what came back
    @staticmethod
    def _read_followers(monkeypatch, response):
        monkeypatch.setattr(im, "instaloader_copy_session", lambda *args, **kwargs: SimpleNamespace(headers={}, close=lambda: None), raising=False)
        monkeypatch.setattr(im, "log_activity", lambda *args, **kwargs: None, raising=False)

        def request(*args, **kwargs):
            return response

        wrapped = im.instagram_wrap_request(request)
        context = SimpleNamespace(is_logged_in=True, _session=SimpleNamespace(), request_timeout=1, get_json=lambda *args, **kwargs: wrapped("GET", FOLLOWERS_URL))
        graphql_scans = []

        def get_followers():
            graphql_scans.append(1)
            return iter([SimpleNamespace(username="from.graphql")])

        profile = SimpleNamespace(userid=12, username="target", get_followers=get_followers)
        return profile, graphql_scans, context

    @pytest.mark.parametrize(("status", "body", "expected"), [
        (429, "Too Many Requests", instaloader.exceptions.TooManyRequestsException),
        (400, "checkpoint_required", instaloader.exceptions.AbortDownloadException),
    ])
    def test_a_throttled_or_challenged_scan_is_never_repeated_over_graphql(self, wrapper, monkeypatch, status, body, expected):
        profile, graphql_scans, context = self._read_followers(monkeypatch, _response(status, body))

        with pytest.raises(expected):
            list(im.iter_auto_follow_list(SimpleNamespace(context=context), profile, "followers"))

        assert graphql_scans == []


# Stops before a successful second response can hide a checkpoint
def test_checkpoint_followed_by_success_never_retries(monkeypatch, wrapper):
    replies = [_response(400, "checkpoint_required"), _response(200, "ok")]
    attempts = []
    monkeypatch.setattr(im, "CIRCUIT_BREAKER", True)
    im.ACCOUNT_BREAKER_MEMORY.clear()

    # Returns a success only if the wrapper incorrectly retries the checkpoint
    def request(*args, **kwargs):
        attempts.append(1)
        return replies.pop(0)

    with pytest.raises(instaloader.exceptions.AbortDownloadException):
        im.instagram_wrap_request(request)("GET", FOLLOWERS_URL)
    assert len(attempts) == 1
    assert len(replies) == 1
