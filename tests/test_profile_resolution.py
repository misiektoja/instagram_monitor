"""Offline tests for resolving a profile without the endpoint Instagram retired for signed-in sessions."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import requests


# Returns one entry of a search reply
def _search_user(username, pk):
    return {"user": {"username": username, "pk": pk}}


# Returns a session carrying the cookie Instagram writes for the signed-in account
def _session_of(user_id):
    session = requests.Session()
    if user_id is not None:
        session.cookies.set("ds_user_id", user_id)
    return session


# Builds a context that records every request and answers from a scripted reply table. The GraphQL reply is a
# mutable dict shared with the caller, so a test can change a field and read the profile again
def _context(im_module, logged_in=True, search_users=(), graphql=None, username=None, session=None):
    calls = []
    graphql_user = graphql if graphql is not None else {"data": {"user": {"username": "target", "pk": "77", "follower_count": 5, "following_count": 6, "media_count": 7, "is_private": False}}}

    def get_json(path, params, *args, **kwargs):
        calls.append((path, dict(params or {})))
        if "topsearch" in path:
            return {"users": list(search_users)}
        raise AssertionError(f"unexpected request to {path}")

    def doc_id_graphql_query(doc_id, variables, referer=None):
        calls.append((f"graphql/{doc_id}", dict(variables)))
        return graphql_user

    return SimpleNamespace(is_logged_in=logged_in, username=username, get_json=get_json, doc_id_graphql_query=doc_id_graphql_query, request_timeout=30, iphone_support=False, profile_id_cache={}, _session=session), calls


class TestSearchResolvesTheUserId:
    # Search answers with near matches too, so an entry for another account must not be read as the target
    def test_only_the_exact_name_is_accepted(self, im_module):
        context, _ = _context(im_module, search_users=[_search_user("target.fan", "11"), _search_user("target", "77")])

        assert im_module.user_id_from_search(context, "target") == "77"

    # A reply with no entry for the requested name resolves to nothing rather than to the closest account
    def test_a_missing_account_resolves_to_nothing(self, im_module):
        context, _ = _context(im_module, search_users=[_search_user("someone.else", "11")])

        assert im_module.user_id_from_search(context, "target") is None

    # Instagram reports the name in its own casing, and the target is matched whatever casing either side uses
    def test_the_match_ignores_casing(self, im_module):
        context, _ = _context(im_module, search_users=[_search_user("Target", "77")])

        assert im_module.user_id_from_search(context, "TARGET") == "77"


class TestTheUserIdIsResolvedOncePerRun:
    # A monitored target is looked up every cycle, so re-resolving its id would spend a request on an answer that
    # cannot change
    def test_a_second_lookup_sends_no_request(self, im_module):
        context, calls = _context(im_module, search_users=[_search_user("target", "77")])

        assert im_module.resolve_user_id(context, "target") == "77"
        assert im_module.resolve_user_id(context, "target") == "77"
        assert len(calls) == 1

    # A name that resolved to nothing is not cached, since the account may appear in search later
    def test_an_unresolved_name_is_not_cached(self, im_module):
        context, calls = _context(im_module, search_users=[])

        assert im_module.resolve_user_id(context, "target") is None
        assert im_module.resolve_user_id(context, "target") is None
        assert len(calls) == 2


class TestASignedInLookupAvoidsTheRetiredEndpoint:
    # Instagram answers feedback_required on web_profile_info for every signed-in session, so the lookup resolves
    # the id through search and reads the profile over GraphQL instead
    def test_the_profile_is_read_over_graphql(self, im_module, monkeypatch):
        context, calls = _context(im_module, search_users=[_search_user("target", "77")])
        monkeypatch.setattr(im_module.instaloader.Profile, "from_username", classmethod(lambda cls, ctx, name: pytest.fail("the retired endpoint was used")))

        profile = im_module.profile_from_username_resilient(SimpleNamespace(context=context), "target")

        assert profile.userid == 77
        assert [path for path, _ in calls] == ["web/search/topsearch/", "graphql/27937681195819736"]
        assert calls[1][1]["id"] == "77"

    # Search does not list every account, so a target it cannot find still falls back rather than being reported gone
    def test_a_name_search_cannot_find_falls_back(self, im_module, monkeypatch):
        context, calls = _context(im_module, search_users=[])
        monkeypatch.setattr(im_module.instaloader.Profile, "from_username", classmethod(lambda cls, ctx, name: SimpleNamespace(username=name, fallback=True)))

        profile = im_module.profile_from_username_resilient(SimpleNamespace(context=context), "target")

        assert profile.fallback is True
        assert [path for path, _ in calls] == ["web/search/topsearch/"]

    # Runs without a login still read the mobile endpoint, which Instagram kept answering
    def test_an_anonymous_lookup_keeps_the_mobile_endpoint(self, im_module, monkeypatch):
        context, calls = _context(im_module, logged_in=False)
        seen = []
        monkeypatch.setattr(im_module, "_profile_from_web_profile_info", lambda bot, username: seen.append(username) or SimpleNamespace(username=username))

        profile = im_module.profile_from_username_resilient(SimpleNamespace(context=context), "target")

        assert profile.username == "target"
        assert seen == ["target"]
        assert calls == []


class TestTheSignedInAccountIsNotSearchedFor:
    # The session's own cookies carry the id of the account it is signed in as, so a search for it would spend a
    # request on a known answer
    def test_the_own_id_comes_from_the_session(self, im_module):
        context, calls = _context(im_module, username="owner", session=_session_of("101"))

        assert im_module.resolve_user_id(context, "Owner") == "101"
        assert calls == []
        assert im_module.stored_user_id("owner") == "101"

    # Every other name is still resolved through search, whatever the session is signed in as
    def test_another_name_is_still_searched_for(self, im_module):
        context, calls = _context(im_module, username="owner", session=_session_of("101"), search_users=[_search_user("target", "77")])

        assert im_module.resolve_user_id(context, "target") == "77"
        assert [path for path, _ in calls] == ["web/search/topsearch/"]

    # A session that lacks the cookie, or carries something other than a number in it, falls back to search
    @pytest.mark.parametrize("cookie", [None, "", "not-a-number"])
    def test_a_missing_or_malformed_cookie_falls_back_to_search(self, im_module, cookie):
        context, calls = _context(im_module, username="owner", session=_session_of(cookie), search_users=[_search_user("owner", "101")])

        assert im_module.resolve_user_id(context, "owner") == "101"
        assert [path for path, _ in calls] == ["web/search/topsearch/"]

    # A context without a session, which is what the offline tests and the setup paths build, resolves like any other
    def test_a_context_without_a_session_falls_back_to_search(self, im_module):
        context, calls = _context(im_module, username="owner", search_users=[_search_user("owner", "101")])

        assert im_module.resolve_user_id(context, "owner") == "101"
        assert len(calls) == 1


class TestTheGraphqlReadGoesThroughInstaloader:
    # The profile is a real Instaloader one with only the network replaced, so the fields the monitor reads go
    # through Instaloader's own normalization of the GraphQL reply rather than a stub of it
    def test_the_full_metadata_is_read_through_the_real_profile(self, im_module):
        graphql = {"data": {"user": {"username": "owner", "pk": "101", "full_name": "Owner", "biography": "Owner bio", "follower_count": 12, "following_count": 7, "media_count": 3, "is_private": False, "is_verified": False, "profile_pic_url_hd": "https://example.org/avatar.jpg"}}}
        context, calls = _context(im_module, username="owner", session=_session_of("101"), graphql=graphql)

        profile = im_module.profile_from_username_resilient(SimpleNamespace(context=context), "owner")

        assert isinstance(profile, im_module.instaloader.Profile)
        assert profile._has_full_metadata
        assert (profile.userid, profile.followers, profile.followees, profile.mediacount) == (101, 12, 7, 3)
        assert (profile.full_name, profile.biography) == ("Owner", "Owner bio")
        assert profile.profile_pic_url_no_iphone == "https://example.org/avatar.jpg"
        assert [path for path, _ in calls] == ["graphql/27937681195819736"]

    # Only the id is kept between checks. The counts are what the monitor watches, so every check reads them again
    def test_every_check_reads_fresh_counts(self, im_module):
        graphql = {"data": {"user": {"username": "owner", "pk": "101", "follower_count": 12, "following_count": 7, "media_count": 3, "is_private": False}}}
        context, calls = _context(im_module, username="owner", session=_session_of("101"), graphql=graphql)
        bot = SimpleNamespace(context=context)

        first = im_module.profile_from_username_resilient(bot, "owner")
        graphql["data"]["user"]["follower_count"] = 13
        second = im_module.profile_from_username_resilient(bot, "owner")

        assert first is not second
        assert (first.followers, second.followers) == (12, 13)
        assert [path for path, _ in calls] == ["graphql/27937681195819736", "graphql/27937681195819736"]


class TestARetiredEndpointDoesNotStopTheAccount:
    RETIRED = 'AbortDownloadException: 400 Bad Request - "fail" status, message "feedback_required" when accessing https://www.instagram.com/api/v1/users/web_profile_info/?username=target'

    # The retired endpoint refuses whatever the account is doing, so reading it as an account action would stop a
    # session every other endpoint still answers
    def test_it_is_not_an_account_level_failure(self, im_module):
        failure_class = im_module.classify_failure_class(self.RETIRED)

        assert failure_class == "endpoint_retired"
        assert im_module.is_account_level_failure(failure_class) is False
        assert im_module.is_session_flagged(self.RETIRED, None) is False

    # The same reply from an endpoint Instagram did not retire is still the account-level limit it has always been
    def test_the_same_reply_elsewhere_still_stops_the_account(self, im_module):
        message = 'AbortDownloadException: 400 Bad Request - "fail" status, message "feedback_required" when accessing https://www.instagram.com/api/v1/friendships/77/followers/'

        assert im_module.classify_failure_class(message) == "action_block"
        assert im_module.is_session_flagged(message, None) is True

    # Only the refusal that marks the retirement is excused, so an expired session on that path is still reported
    def test_another_failure_on_that_path_keeps_its_own_meaning(self, im_module):
        message = "ConnectionException: JSON Query to api/v1/users/web_profile_info/: 401 Unauthorized - login_required"

        assert im_module.classify_failure_class(message) == "auth_expired"

    # The reader is told the account is healthy, since the old wording sent them to wait out a limit that is not there
    def test_the_advice_says_the_account_is_not_blocked(self, im_module):
        advice = im_module.classify_recovery_error(self.RETIRED, is_logged_in=True)

        assert advice.code == "instagram.endpoint_retired"
        assert "not blocked" in advice.fix


class TestTheReelsCountIsReused:
    # Instagram stopped answering the endpoint that reports the count, so the fallback walks the whole reel list.
    # A posts count that has not moved means that walk would arrive at the number already on hand
    def test_an_unchanged_posts_count_reuses_the_count(self, im_module, monkeypatch):
        walks = []
        monkeypatch.setattr(im_module, "_count_total_reels", lambda user, bot, skip_session: walks.append(user) or 7)

        first = im_module.get_total_reels_count("target", None, False, 20)
        second = im_module.get_total_reels_count("target", None, False, 20)

        assert (first, second) == (7, 7)
        assert walks == ["target"]

    # A posts count that moved means a reel may have been added or removed, so the number is established again
    def test_a_changed_posts_count_counts_again(self, im_module, monkeypatch):
        counts = iter([7, 8])
        monkeypatch.setattr(im_module, "_count_total_reels", lambda user, bot, skip_session: next(counts))

        assert im_module.get_total_reels_count("target", None, False, 20) == 7
        assert im_module.get_total_reels_count("target", None, False, 21) == 8

    # Targets are counted in their own threads, so one target's count must never answer for another's
    def test_each_target_keeps_its_own_count(self, im_module, monkeypatch):
        counts = {"one": 3, "two": 9}
        monkeypatch.setattr(im_module, "_count_total_reels", lambda user, bot, skip_session: counts[user])

        assert im_module.get_total_reels_count("one", None, False, 20) == 3
        assert im_module.get_total_reels_count("two", None, False, 20) == 9
        assert im_module.get_total_reels_count("one", None, False, 20) == 3

    # A reel counts towards the posts number, so posting one moves that number and the list is read again
    def test_a_new_reel_moves_the_posts_count_and_counts_again(self, im_module, monkeypatch):
        counts = iter([1, 2])
        monkeypatch.setattr(im_module, "_count_total_reels", lambda user, bot, skip_session: next(counts))

        assert im_module.get_total_reels_count("target", None, False, 2) == 1
        assert im_module.get_total_reels_count("target", None, False, 3) == 2

    # A caller with no posts count to compare has nothing to reuse against, so it always counts
    def test_a_missing_posts_count_always_counts(self, im_module, monkeypatch):
        walks = []
        monkeypatch.setattr(im_module, "_count_total_reels", lambda user, bot, skip_session: walks.append(user) or 7)

        im_module.get_total_reels_count("target", None, False, None)
        im_module.get_total_reels_count("target", None, False, None)

        assert len(walks) == 2


class TestResolvedIdsOutliveTheRun:
    # A name keeps its id for as long as the account exists, so resolving it again after a restart would spend a
    # request on an answer the previous run already wrote down
    def test_a_stored_id_is_read_back_without_a_request(self, im_module):
        context, calls = _context(im_module, search_users=[_search_user("target", "77")])
        assert im_module.resolve_user_id(context, "target") == "77"

        im_module.USER_ID_CACHE.clear()
        im_module.USER_ID_CACHE_LOADED = False

        assert im_module.resolve_user_id(context, "target") == "77"
        assert len(calls) == 1

    # The file only saves a lookup, so one this run cannot read must leave it resolving names rather than failing
    def test_an_unreadable_file_is_ignored(self, im_module):
        Path(im_module.user_id_cache_path()).write_text("{ not json", encoding="utf-8")
        im_module.USER_ID_CACHE.clear()
        im_module.USER_ID_CACHE_LOADED = False
        context, calls = _context(im_module, search_users=[_search_user("target", "77")])

        assert im_module.resolve_user_id(context, "target") == "77"
        assert len(calls) == 1

    # A file written by a different version may hold anything, so it is not read as this version's shape
    def test_another_version_is_ignored(self, im_module):
        Path(im_module.user_id_cache_path()).write_text('{"version": 99, "ids": {"target": "11"}}', encoding="utf-8")
        im_module.USER_ID_CACHE.clear()
        im_module.USER_ID_CACHE_LOADED = False
        context, _ = _context(im_module, search_users=[_search_user("target", "77")])

        assert im_module.resolve_user_id(context, "target") == "77"

    # A freed username can be taken by another account, so an id is trusted only while it answers to the name it
    # was stored for. The stored one is dropped and the name looked up again rather than monitoring a stranger
    def test_an_id_answering_to_another_name_is_dropped(self, im_module, monkeypatch):
        im_module.remember_user_id("target", "11")
        context, calls = _context(im_module, search_users=[_search_user("target", "77")])
        built = []

        def profile(ctx, username, user_id):
            built.append(user_id)
            return None if user_id == "11" else SimpleNamespace(username=username, userid=int(user_id))

        monkeypatch.setattr(im_module, "_profile_by_user_id", profile)

        resolved = im_module.profile_from_username_resilient(SimpleNamespace(context=context), "target")

        assert resolved.userid == 77
        assert built == ["11", "77"]
        assert im_module.stored_user_id("target") == "77"


class TestReelsAreOptional:
    # Instagram stopped answering the endpoint that reports a reel count, so reading the list is the only way left
    # and it is both expensive and often refused. A run that does not need reels should not pay for that
    def test_the_latest_post_lookup_reads_no_reels_by_default(self, im_module, monkeypatch):
        walked = []
        profile = SimpleNamespace(get_posts=lambda: iter(()), get_reels=lambda: walked.append("reels") or iter(()))
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, user: profile)

        assert im_module.latest_post_reel("target", None) is None
        assert walked == []

    # Turning reels on is what makes the tool read them, so the setting has to reach the lookup
    def test_the_latest_post_lookup_reads_reels_when_they_are_wanted(self, im_module, monkeypatch):
        walked = []
        profile = SimpleNamespace(get_posts=lambda: iter(()), get_reels=lambda: walked.append("reels") or iter(()))
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, user: profile)
        monkeypatch.setattr(im_module, "FETCH_REELS", True, raising=False)

        assert im_module.latest_post_reel("target", None) is None
        assert walked == ["reels"]

    # The default has to be off, since that is what keeps a check working while the endpoint is refusing
    def test_reels_are_off_unless_asked_for(self, im_module):
        assert im_module.FETCH_REELS is False


class TestSetupAsksAboutReels:
    # Runs a connection section that records which questions were asked and returns scripted answers
    def _section(self, im_module, monkeypatch, answers):
        import tests.test_setup_wizard as wizard_tests

        with wizard_tests.make_test_directory() as directory_name:
            state = wizard_tests.make_setup_state(im_module, Path(directory_name))
            state.logged_in = True
            asked = wizard_tests.scripted_connection_choices(im_module, monkeypatch, answers)
            monkeypatch.setattr(im_module, "_wizard_collect_identity_budget", lambda state: None)
            im_module._wizard_collect_connection_section(state)
            return state, asked

    # The answer that keeps a check working while Instagram refuses the reel list is the one Enter selects
    def test_the_safe_answer_is_the_default(self, im_module, monkeypatch):
        _, asked = self._section(im_module, monkeypatch, {"collect": 2, "reels": 0})

        assert asked["reels"]["options"] == ["No, leave reels alone", "Yes, monitor reels"]
        assert asked["reels"]["default"] == 0

    # A reader turning reels on should be told what it costs, so the warning sits on the answer that turns them on
    def test_the_question_warns_what_reels_cost(self, im_module, monkeypatch):
        seen = {}

        def ask(question, options, default_index=0):
            seen["options"] = list(options)
            return 0

        monkeypatch.setattr(im_module, "_wizard_ask_choice", ask)
        im_module._wizard_collect_reels(SimpleNamespace(config_values={}))

        assert "refuses" in seen["options"][1][1]
        assert "counts towards the posts number" in seen["options"][0][1]

    # Answering yes is what records the setting, so a run that wants reel notifications gets them
    def test_answering_yes_records_the_setting(self, im_module, monkeypatch):
        state, _ = self._section(im_module, monkeypatch, {"collect": 2, "reels": 1})

        assert state.config_values["FETCH_REELS"] is True

    # Reels do not depend on the follower lists, so a counts-only setup is still asked about them
    def test_a_counts_only_setup_is_still_asked(self, im_module, monkeypatch):
        state, asked = self._section(im_module, monkeypatch, {"collect": 0, "reels": 1})

        assert "reels" in asked
        assert state.config_values["FETCH_REELS"] is True
