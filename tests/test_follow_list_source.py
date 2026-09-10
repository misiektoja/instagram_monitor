"""Offline tests for the follower and following list sources: the web REST endpoints and the GraphQL fallback."""

from types import SimpleNamespace
from unittest.mock import Mock
import re

import instaloader
import pytest


# Minimal stand-in for the copied requests session the REST reader sends its pages on
class FakeSession:
    # Starts with no headers and records whether the reader closed it
    def __init__(self):
        self.headers = {}
        self.closed = False

    # Marks the session closed
    def close(self):
        self.closed = True


# Scripted instaloader context that answers each get_json call from a prepared list of pages
class FakeContext:
    # Takes the pages to return in order, where a page may be a payload, a (payload, response headers) pair or an exception to raise
    def __init__(self, pages, logged_in=True):
        self.pages = list(pages)
        self.is_logged_in = logged_in
        self.request_timeout = 7
        self._session = SimpleNamespace()
        self.calls = []

    # Records the request then returns or raises the next scripted page
    def get_json(self, path, params, session=None, response_headers=None):
        self.calls.append({"path": path, "params": dict(params), "headers": dict(session.headers) if session is not None else {}})
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        payload, headers = page if isinstance(page, tuple) else (page, {})
        if response_headers is not None:
            response_headers.clear()
            response_headers.update(headers)
        return payload


# Builds one REST list page from usernames plus the cursor Instagram would return with it
def rest_page(usernames, next_max_id=None):
    payload = {"users": [{"pk": str(1000 + index), "username": name} for index, name in enumerate(usernames)], "status": "ok"}
    if next_max_id:
        payload["next_max_id"] = next_max_id
    return payload


# Builds a target profile stub with the two attributes the REST reader needs
def fake_profile(username="target.user", userid=987654):
    return SimpleNamespace(username=username, userid=userid, get_followers=Mock(), get_followees=Mock())


@pytest.fixture
# Replaces the session copier so no test builds a real requests session, and hands back the session the reader used
def rest_session(im_module, monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(im_module, "instaloader_copy_session", lambda *args, **kwargs: session)
    return session


class TestRestPagination:
    # The reader follows next_max_id until Instagram stops sending one
    def test_pages_until_the_cursor_runs_out(self, im_module, rest_session):
        context = FakeContext([rest_page(["a", "b"], "cursor-2"), rest_page(["c"], "cursor-3"), rest_page(["d"])])
        bot = SimpleNamespace(context=context)

        names = [profile.username for profile in im_module.iter_rest_follow_list(bot, fake_profile(), "followers")]

        assert names == ["a", "b", "c", "d"]
        assert [call["params"].get("max_id") for call in context.calls] == [None, "cursor-2", "cursor-3"]

    # An empty page ends the walk even when Instagram still offers a cursor
    def test_empty_page_ends_the_walk(self, im_module, rest_session):
        context = FakeContext([rest_page(["a"], "cursor-2"), rest_page([], "cursor-3")])
        bot = SimpleNamespace(context=context)

        names = [profile.username for profile in im_module.iter_rest_follow_list(bot, fake_profile(), "followers")]

        assert names == ["a"]
        assert len(context.calls) == 2

    # Followers and followings are read from their own endpoints
    @pytest.mark.parametrize("kind", ["followers", "following"])
    def test_each_kind_reads_its_own_endpoint(self, im_module, rest_session, kind):
        context = FakeContext([rest_page(["a"])])
        bot = SimpleNamespace(context=context)

        list(im_module.iter_rest_follow_list(bot, fake_profile(userid=42), kind))

        assert context.calls[0]["path"] == f"api/v1/friendships/42/{kind}/"

    # A direct REST read without governor accounting asks for the configured page size
    def test_page_size_is_the_configured_one(self, im_module, rest_session, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_REST_PAGE_SIZE", 12)
        context = FakeContext([rest_page(["a"], "cursor-2"), rest_page(["b"])])
        bot = SimpleNamespace(context=context)

        list(im_module.iter_rest_follow_list(bot, fake_profile(), "followers"))

        assert [call["params"]["count"] for call in context.calls] == [12, 12]

    # The copied session is closed even when the caller abandons the reader part way through
    def test_session_is_closed_when_the_caller_stops_early(self, im_module, rest_session):
        context = FakeContext([rest_page(["a", "b"], "cursor-2"), rest_page(["c"])])
        generator = im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(), "followers")

        assert next(generator).username == "a"
        generator.close()

        assert rest_session.closed is True

    # An unsupported kind is a programming error, not something to send to Instagram
    def test_unknown_kind_is_rejected(self, im_module, rest_session):
        with pytest.raises(ValueError):
            list(im_module.iter_rest_follow_list(SimpleNamespace(context=FakeContext([])), fake_profile(), "friends"))


class TestRestRequestShape:
    # The request carries the identifiers and fetch metadata Instagram's own front end sends
    def test_headers_match_the_web_app(self, im_module, rest_session):
        context = FakeContext([rest_page(["a"])])

        list(im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(username="Target.User"), "followers"))

        headers = context.calls[0]["headers"]
        assert headers["X-IG-App-ID"] == im_module.INSTAGRAM_WEB_APP_ID
        assert headers["X-ASBD-ID"] == im_module.INSTAGRAM_WEB_ASBD_ID
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert headers["Referer"] == "https://www.instagram.com/Target.User/"
        assert (headers["Sec-Fetch-Dest"], headers["Sec-Fetch-Mode"], headers["Sec-Fetch-Site"]) == ("empty", "cors", "same-origin")

    # A fresh session sends the placeholder claim a new browser sends
    def test_first_request_sends_the_placeholder_claim(self, im_module, rest_session):
        context = FakeContext([rest_page(["a"])])

        list(im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(), "followers"))

        assert context.calls[0]["headers"]["X-IG-WWW-Claim"] == "0"

    # A claim token Instagram issues is echoed back on the next request
    def test_issued_claim_token_is_echoed_on_the_next_page(self, im_module, rest_session):
        pages = [(rest_page(["a"], "cursor-2"), {"x-ig-set-www-claim": "hmac.AR1"}), rest_page(["b"])]
        context = FakeContext(pages)

        list(im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(), "followers"))

        assert context.calls[0]["headers"]["X-IG-WWW-Claim"] == "0"
        assert context.calls[1]["headers"]["X-IG-WWW-Claim"] == "hmac.AR1"

    # Header names arrive in whatever case the server used, so the lookup cannot be case sensitive
    def test_claim_header_is_read_case_insensitively(self, im_module):
        source_session = SimpleNamespace()
        im_module.remember_web_claim_token(source_session, {"X-IG-Set-WWW-Claim": "hmac.AR2"})

        assert im_module.web_claim_token(source_session) == "hmac.AR2"

    # A reply without a claim header leaves the stored token alone
    def test_missing_claim_header_keeps_the_current_token(self, im_module):
        source_session = SimpleNamespace()
        im_module.remember_web_claim_token(source_session, {"x-ig-set-www-claim": "hmac.AR3"})
        im_module.remember_web_claim_token(source_session, {"content-type": "application/json"})

        assert im_module.web_claim_token(source_session) == "hmac.AR3"

    # Separate logged-in sessions never echo each other's claim tokens
    def test_claim_token_is_scoped_to_its_source_session(self, im_module):
        first_session = SimpleNamespace()
        second_session = SimpleNamespace()

        im_module.remember_web_claim_token(first_session, {"x-ig-set-www-claim": "hmac.FIRST"})

        assert im_module.web_claim_token(first_session) == "hmac.FIRST"
        assert im_module.web_claim_token(second_session) == "0"


class TestRestNodes:
    # A list entry becomes a profile carrying both identifier spellings instaloader reads
    def test_entry_becomes_a_profile(self, im_module):
        profile = im_module.profile_from_rest_node(None, {"pk": 1234, "username": "Somebody"})

        assert isinstance(profile, instaloader.Profile)
        assert profile.username == "somebody"
        assert profile.userid == 1234

    # An entry Instagram sends with an id instead of a pk still resolves
    def test_id_only_entry_resolves(self, im_module):
        profile = im_module.profile_from_rest_node(None, {"id": "77", "username": "other"})

        assert profile is not None and profile.userid == 77

    # Unusable entries are skipped rather than turned into a profile with no identity
    @pytest.mark.parametrize("node", [None, {}, {"pk": "1"}, {"username": "no.id"}, {"username": "", "pk": "1"}, "not-a-dict"])
    def test_unusable_entries_are_skipped(self, im_module, node):
        assert im_module.profile_from_rest_node(None, node) is None

    # Skipping an unusable entry does not stop the page it arrived in
    def test_unusable_entry_does_not_stop_the_page(self, im_module, rest_session):
        payload = {"users": [{"pk": "1", "username": "good"}, {"pk": "2"}, {"pk": "3", "username": "also.good"}]}
        context = FakeContext([payload])

        names = [profile.username for profile in im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(), "followers")]

        assert names == ["good", "also.good"]


class TestRestSchemaFailures:
    # A reply with no user list means the endpoint changed shape
    @pytest.mark.parametrize("payload", [{"status": "ok"}, {"users": "nope"}, []])
    def test_missing_user_list_raises_a_schema_error(self, im_module, rest_session, payload):
        context = FakeContext([payload])

        with pytest.raises(im_module.InstagramRestSchemaError):
            list(im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(), "followers"))

    # A schema error is reported as an Instagram API change, so it never trips the account circuit breaker
    def test_schema_error_is_classified_as_an_api_change(self, im_module):
        message = im_module.format_error_message(im_module.InstagramRestSchemaError("Unexpected follower list reply while reading followers (no user list)"))
        failure_class = im_module.classify_failure_class(message)

        assert failure_class == "schema_change"
        assert im_module.failure_class_group(failure_class) == "B"
        assert im_module.is_account_level_failure(failure_class) is False

    # A cursor that stops advancing is stopped rather than paged for ever
    def test_stuck_cursor_raises_a_schema_error(self, im_module, rest_session):
        context = FakeContext([rest_page(["a"], "cursor-2"), rest_page(["b"], "cursor-2")])

        collected = []
        with pytest.raises(im_module.InstagramRestSchemaError):
            for entry in im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(), "followers"):
                collected.append(entry.username)

        assert collected == ["a", "b"]

    # A partial list stopped by a stuck cursor is never saved over the last complete baseline
    def test_stuck_cursor_leaves_the_baseline_alone(self, im_module, monkeypatch, rest_session):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "rest")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "note_instagram_failure", lambda *args, **kwargs: None)
        context = FakeContext([rest_page(["a"], "cursor-2"), rest_page(["b"], "cursor-2")])
        bot = SimpleNamespace(context=context)
        profile = fake_profile()

        with pytest.raises(im_module.InstagramRestSchemaError):
            im_module.fetch_usernames_paginated(bot, lambda: im_module.follow_list_generator(bot, profile, "followers"), max_per_batch=0, total_limit=0, fetch_delay=0, advanced_fetch=False, estimated_limit=0, user="target.user")

    # The message carries no account identifier, so a digit in a user id cannot be read as a status code
    def test_schema_error_message_carries_no_identifier(self, im_module, rest_session):
        context = FakeContext([{"status": "ok"}])

        with pytest.raises(im_module.InstagramRestSchemaError) as raised:
            list(im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(userid=404123401), "followers"))

        assert not re.search(r"\d", str(raised.value))


class TestSourceSelection:
    # The GraphQL source keeps using instaloader's own iterators
    @pytest.mark.parametrize("kind,method", [("followers", "get_followers"), ("following", "get_followees")])
    def test_graphql_source_uses_instaloader(self, im_module, monkeypatch, kind, method):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "graphql")
        profile = fake_profile()

        im_module.follow_list_generator(SimpleNamespace(context=FakeContext([], logged_in=True)), profile, kind)

        assert getattr(profile, method).call_count == 1

    # An anonymous session keeps the historical path, since neither surface lists followers without a login
    def test_anonymous_session_uses_instaloader(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "rest")
        profile = fake_profile()

        im_module.follow_list_generator(SimpleNamespace(context=FakeContext([], logged_in=False)), profile, "followers")

        assert profile.get_followers.call_count == 1

    # Asking for REST while logged out is still reported as a login problem rather than a silent empty list
    def test_rest_reader_requires_a_login(self, im_module, rest_session):
        context = FakeContext([], logged_in=False)

        with pytest.raises(instaloader.exceptions.LoginRequiredException):
            list(im_module.iter_rest_follow_list(SimpleNamespace(context=context), fake_profile(), "followers"))

    # The REST source reads over REST and never touches instaloader's iterators
    def test_rest_source_reads_over_rest(self, im_module, monkeypatch, rest_session):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "rest")
        context = FakeContext([rest_page(["a"])])
        profile = fake_profile()

        names = [entry.username for entry in im_module.follow_list_generator(SimpleNamespace(context=context), profile, "followers")]

        assert names == ["a"]
        assert profile.get_followers.call_count == 0

    # An unrecognised setting falls back to auto rather than stopping monitoring
    @pytest.mark.parametrize("configured,expected", [("auto", "auto"), ("REST", "rest"), (" graphql ", "graphql"), (" Browser ", "browser"), ("selenium", "auto"), ("", "auto")])
    def test_unknown_setting_falls_back_to_auto(self, im_module, monkeypatch, configured, expected):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", configured)

        assert im_module.active_follow_list_source() == expected


class TestAutoFallback:
    # Auto reads over REST while REST works
    def test_auto_prefers_rest(self, im_module, monkeypatch, rest_session):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "auto")
        context = FakeContext([rest_page(["a", "b"])])
        profile = fake_profile()

        names = [entry.username for entry in im_module.follow_list_generator(SimpleNamespace(context=context), profile, "followers")]

        assert names == ["a", "b"]
        assert profile.get_followers.call_count == 0

    # A retired endpoint is retried on the older surface
    def test_retired_endpoint_retries_on_graphql(self, im_module, monkeypatch, rest_session, capsys):
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        context = FakeContext([instaloader.exceptions.QueryReturnedNotFoundException("404 Not Found")])
        profile = fake_profile()
        profile.get_followers.return_value = iter([SimpleNamespace(username="from.graphql")])

        names = [entry.username for entry in im_module.iter_auto_follow_list(SimpleNamespace(context=context), profile, "followers")]

        assert names == ["from.graphql"]
        assert "reading the list over GraphQL instead" in capsys.readouterr().out

    # A reply that no longer carries a user list is retried on the older surface
    def test_changed_reply_shape_retries_on_graphql(self, im_module, monkeypatch, rest_session, capsys):
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        context = FakeContext([{"status": "ok"}])
        profile = fake_profile()
        profile.get_followees.return_value = iter([SimpleNamespace(username="from.graphql")])

        names = [entry.username for entry in im_module.iter_auto_follow_list(SimpleNamespace(context=context), profile, "following")]

        assert names == ["from.graphql"]
        assert "reading the list over GraphQL instead" in capsys.readouterr().out

    # A fetch that already returned names is never repeated on the other surface, since those names already cost the account
    def test_partial_scan_is_never_retried(self, im_module, monkeypatch, rest_session):
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        context = FakeContext([rest_page(["a"], "cursor-2"), instaloader.exceptions.QueryReturnedNotFoundException("404 Not Found")])
        profile = fake_profile()

        generator = im_module.iter_auto_follow_list(SimpleNamespace(context=context), profile, "followers")

        assert next(generator).username == "a"
        with pytest.raises(instaloader.exceptions.QueryReturnedNotFoundException):
            next(generator)
        assert profile.get_followers.call_count == 0

    # A page with unusable profiles still exposed identities, so a later failure cannot trigger a second scan
    def test_exposed_invalid_entries_are_never_retried(self, im_module, monkeypatch, rest_session):
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        invalid_page = {"users": [{"pk": "1"}], "next_max_id": "cursor-2", "status": "ok"}
        context = FakeContext([invalid_page, instaloader.exceptions.QueryReturnedNotFoundException("404 Not Found")])
        profile = fake_profile()

        with pytest.raises(instaloader.exceptions.QueryReturnedNotFoundException):
            list(im_module.iter_auto_follow_list(SimpleNamespace(context=context), profile, "followers"))

        assert profile.get_followers.call_count == 0

    # Anything Instagram aimed at the account or the transport is reported, never answered with more requests
    @pytest.mark.parametrize("failure", [
        instaloader.exceptions.AbortDownloadException("challenge_required"),
        instaloader.exceptions.LoginRequiredException("Redirected to login page."),
        instaloader.exceptions.ConnectionException("JSON Query to api/v1/friendships: 429 Too Many Requests"),
        instaloader.exceptions.QueryReturnedBadRequestException("400 Bad Request"),
    ])
    def test_account_and_transport_failures_are_reported(self, im_module, monkeypatch, rest_session, failure):
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        context = FakeContext([failure])
        profile = fake_profile()

        with pytest.raises(type(failure)):
            list(im_module.iter_auto_follow_list(SimpleNamespace(context=context), profile, "followers"))
        assert profile.get_followers.call_count == 0


class TestProgressAndSummary:
    # The progress bar reads names from the REST reply shape as well as the GraphQL one
    def test_progress_bar_reads_the_rest_shape(self, im_module):
        assert im_module.extract_usernames_safely(rest_page(["a", "b"], "cursor-2")) == ["a", "b"]

    # A malformed REST reply yields no names instead of raising inside the request wrapper
    @pytest.mark.parametrize("payload", [{"users": "nope"}, {"users": [{"pk": "1"}]}, {"users": []}])
    def test_malformed_rest_shape_yields_no_names(self, im_module, payload):
        assert im_module.extract_usernames_safely(payload) == []

    # A value that names no source is reported next to the fallback rather than replaced in silence
    def test_an_unknown_setting_is_named_in_the_summary(self, im_module, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--no-color", "--disable-logging"])
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "selenium")
        monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "find_config_file", lambda path=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: True)
        monkeypatch.setattr(im_module, "start_dashboard_input_handler", Mock(side_effect=SystemExit(0)))

        with pytest.raises(SystemExit):
            im_module.run_main()

        rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("* Follow list source:")]
        assert rows == ["* Follow list source:           auto (REST, GraphQL on failure) (FOLLOW_LIST_SOURCE 'selenium' is not a known source)"]

    def test_an_unknown_setting_is_a_doctor_warning(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "selenium")

        assert im_module.unrecognised_follow_list_source() == "selenium"
        check = next(check for check in im_module.doctor_check_configuration([]) if check.label == "FOLLOW_LIST_SOURCE names no known source")
        assert check.status == "WARN"
        assert check.detail == "'selenium' is ignored and follower lists are read over auto (REST, GraphQL on failure)"
        assert "Set FOLLOW_LIST_SOURCE to auto, rest, graphql or browser" in check.advice.fix

    def test_a_known_setting_raises_no_warning(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", " REST ")

        assert im_module.unrecognised_follow_list_source() is None
        assert not any(check.label == "FOLLOW_LIST_SOURCE names no known source" for check in im_module.doctor_check_configuration([]))

    # The startup summary names the surface in use
    @pytest.mark.parametrize("configured,expected", [("auto", "auto (REST, GraphQL on failure)"), ("rest", "REST"), ("graphql", "GraphQL")])
    def test_summary_names_the_surface(self, im_module, monkeypatch, configured, expected):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", configured)

        assert im_module.follow_list_source_display() == expected

    # The shipped configuration template offers the setting and defaults to auto
    def test_template_ships_the_setting(self, im_module):
        parsed = im_module.parse_config_content(im_module.CONFIG_BLOCK, "<built-in>")

        assert parsed["FOLLOW_LIST_SOURCE"] == "auto"

    # The command line flag reaches the summary, so a run can be pinned to one surface without editing the config
    def test_flag_selects_the_surface(self, im_module, monkeypatch, capsys, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--no-color", "--disable-logging", "--follow-list-source", "graphql"])
        monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)
        monkeypatch.setattr(im_module, "find_config_file", lambda path=None: None)
        monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "check_internet", lambda: True)
        monkeypatch.setattr(im_module, "start_dashboard_input_handler", Mock(side_effect=SystemExit(0)))

        with pytest.raises(SystemExit):
            im_module.run_main()

        rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("* Follow list source:")]
        assert rows == ["* Follow list source:           GraphQL"]


class TestGovernorStillApplies:
    # The daily identity budget caps a REST fetch and leaves the truncated list unusable as a baseline
    def test_budget_caps_a_rest_fetch(self, im_module, monkeypatch, rest_session):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "rest")
        monkeypatch.setattr(im_module, "IDENTITY_BUDGET_PER_DAY", 3)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        context = FakeContext([rest_page(["a", "b"], "cursor-2"), rest_page(["c", "d"], "cursor-3"), rest_page(["e"])])
        bot = SimpleNamespace(context=context)
        profile = fake_profile()

        result = im_module.fetch_usernames_paginated(bot, lambda: im_module.follow_list_generator(bot, profile, "followers", record_exposure=True), max_per_batch=0, total_limit=0, fetch_delay=0, advanced_fetch=False, estimated_limit=0, user="target.user", identities_counted_at_source=True)

        assert result == ["a", "b", "c"]
        assert result.complete is False
        assert im_module.is_complete_username_baseline(result, 5) is False
        assert context.calls[1]["params"]["count"] == 1
        assert im_module.exposure_snapshot()["identities"] == 4

    # Names returned before a REST failure are still counted against the account
    def test_names_before_a_failure_are_counted(self, im_module, monkeypatch, rest_session):
        monkeypatch.setattr(im_module, "FOLLOW_LIST_SOURCE", "rest")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        monkeypatch.setattr(im_module, "note_instagram_failure", lambda *args, **kwargs: None)
        context = FakeContext([rest_page(["a", "b"], "cursor-2"), instaloader.exceptions.ConnectionException("JSON Query to api/v1/friendships: 429 Too Many Requests")])
        bot = SimpleNamespace(context=context)
        profile = fake_profile()

        with pytest.raises(instaloader.exceptions.ConnectionException):
            im_module.fetch_usernames_paginated(bot, lambda: im_module.follow_list_generator(bot, profile, "followers", record_exposure=True), max_per_batch=0, total_limit=0, fetch_delay=0, advanced_fetch=False, estimated_limit=0, user="target.user", identities_counted_at_source=True)

        assert im_module.exposure_snapshot()["identities"] == 2
