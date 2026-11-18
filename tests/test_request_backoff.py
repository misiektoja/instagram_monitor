"""Offline tests for the jitter and back-off wrapper around every Instagram request."""

import io
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import instaloader
import pytest
import requests
from requests.adapters import HTTPAdapter

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
    """A spent back-off budget is a rate limit, so the auto source must not rescan the list over GraphQL."""

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


GRAPHQL_URL = "https://www.instagram.com/graphql/query"
WEB_APP_URL = "https://www.instagram.com/api/graphql"
REFUSED_BODY = '{"message": "feedback_required", "status": "fail"}'


# Stands in for a requests session holding a session cookie and scripted replies
class _Session:
    # Starts with the sessionid cookie value and the replies to hand out in order
    def __init__(self, sessionid, replies):
        self.cookies = SimpleNamespace(get_dict=lambda: {"sessionid": sessionid})
        self.replies = list(replies)
        self.sent = []

    # Records the query the request names and returns the next scripted reply
    def request(self, method, url, params=None, data=None, **kwargs):
        fields = params or data or {}
        self.sent.append(fields.get("query_hash") or fields.get("doc_id"))
        return self.replies.pop(0)


class TestARefusedGraphqlQueryIsNotSentAgain:
    # A refused query is remembered, so its next request is not sent and reads as an API change
    @pytest.mark.parametrize("jitter", [True, False])
    @pytest.mark.parametrize("method, field, key", [("GET", "params", "query_hash"), ("POST", "data", "doc_id")])
    def test_a_refused_query_is_not_sent_again(self, wrapper, monkeypatch, jitter, method, field, key):
        monkeypatch.setattr(im, "ENABLE_JITTER", jitter)
        session = _Session("signed-in", [_response(400, REFUSED_BODY)])
        wrapped = im.instagram_wrap_request(session.request, session)
        query = {field: {key: "followers", "variables": "{}"}}

        assert wrapped(method, GRAPHQL_URL, **query).status_code == 400
        with pytest.raises(instaloader.exceptions.AbortDownloadException) as error:
            wrapped(method, GRAPHQL_URL, **query)

        assert session.sent == ["followers"]
        failure_class = im.classify_failure_class(im.format_error_message(error.value))
        assert failure_class == "endpoint_retired"
        assert im.is_account_level_failure(failure_class) is False

    # Instagram refuses single queries, so one it has not refused, such as the comments list, is still sent
    def test_another_query_is_still_sent(self, wrapper):
        session = _Session("signed-in", [_response(400, REFUSED_BODY), _response(200, "{}")])
        wrapped = im.instagram_wrap_request(session.request, session)

        wrapped("GET", GRAPHQL_URL, params={"query_hash": "followers"})
        assert wrapped("GET", GRAPHQL_URL, params={"query_hash": "comments"}).status_code == 200

        assert session.sent == ["followers", "comments"]

    # Only a feedback_required reply marks a query as refused
    @pytest.mark.parametrize("status, body", [(200, "{}"), (400, '{"message": "Bad Request"}'), (500, "feedback_required")])
    def test_other_replies_keep_the_query(self, wrapper, status, body):
        session = _Session("signed-in", [_response(status, body), _response(200, "{}")])
        wrapped = im.instagram_wrap_request(session.request, session)

        wrapped("GET", GRAPHQL_URL, params={"query_hash": "followers"})
        wrapped("GET", GRAPHQL_URL, params={"query_hash": "followers"})

        assert session.sent == ["followers", "followers"]

    # The web app endpoint answers the query the older one refused, so it is never blocked
    def test_the_web_app_endpoint_is_still_called(self, wrapper):
        im.GRAPHQL_QUERIES_REFUSED.add("profile")
        session = _Session("signed-in", [_response(200, "{}")])

        im.instagram_wrap_request(session.request, session)("POST", WEB_APP_URL, data={"doc_id": "profile"})

        assert session.sent == ["profile"]

    # Instagram refuses signed-in sessions only, so an anonymous one neither sets nor obeys the stop
    def test_an_anonymous_session_keeps_the_query(self, wrapper):
        session = _Session("", [_response(400, REFUSED_BODY), _response(200, "{}")])
        wrapped = im.instagram_wrap_request(session.request, session)

        wrapped("GET", GRAPHQL_URL, params={"query_hash": "followers"})
        wrapped("GET", GRAPHQL_URL, params={"query_hash": "followers"})

        assert session.sent == ["followers", "followers"]
        assert im.GRAPHQL_QUERIES_REFUSED == set()

    # Instaloader replaces a session's request with a partial, so the stop is checked on the sessions it builds
    def test_the_stop_works_on_instaloader_sessions(self, monkeypatch):
        sent = []

        # Refuses the followers query, answers any other and records the query hash
        def send(self, request, **kwargs):
            query_hash = parse_qs(urlsplit(request.url).query)["query_hash"][0]
            sent.append(query_hash)
            response = requests.Response()
            response.status_code, response._content = (400, REFUSED_BODY.encode()) if query_hash == "followers" else (200, b'{"status": "ok"}')
            response.headers["Content-Type"] = "application/json"
            response.raw = io.BytesIO(response._content)
            response.encoding = "utf-8"
            response.request = request
            response.url = request.url
            return response

        monkeypatch.setattr(HTTPAdapter, "send", send)
        monkeypatch.setattr(im._CurlCffiHTTPAdapter, "send", send)
        monkeypatch.setattr(im, "SKIP_WRAP_MESSAGES", True)
        bot = im.instaloader_client(user_agent="Mozilla/5.0", max_connection_attempts=1, sleep=False, quiet=True)
        bot.context._session.cookies.set("sessionid", "signed-in", domain=".instagram.com")
        errors = []

        for _ in range(2):
            with pytest.raises(instaloader.exceptions.AbortDownloadException) as error:
                bot.context.graphql_query("followers", {"id": "12"})
            errors.append(str(error.value))
        assert bot.context.graphql_query("comments", {"shortcode": "abc"}) == {"status": "ok"}

        assert sent == ["followers", "comments"]
        assert "feedback_required" in errors[0]
        assert errors[1] == im.GRAPHQL_QUERY_REFUSED_ERROR
