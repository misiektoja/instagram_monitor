"""Offline tests for resolving a profile without the endpoint Instagram retired for signed-in sessions."""

from types import SimpleNamespace

import pytest


# Returns one entry of a search reply
def _search_user(username, pk):
    return {"user": {"username": username, "pk": pk}}


# Builds a context that records every request and answers from a scripted reply table
def _context(im_module, logged_in=True, search_users=(), graphql=None):
    calls = []

    def get_json(path, params, *args, **kwargs):
        calls.append((path, dict(params or {})))
        if "topsearch" in path:
            return {"users": list(search_users)}
        raise AssertionError(f"unexpected request to {path}")

    def doc_id_graphql_query(doc_id, variables, referer=None):
        calls.append((f"graphql/{doc_id}", dict(variables)))
        return graphql if graphql is not None else {"data": {"user": {"username": "target", "pk": "77", "follower_count": 5, "following_count": 6, "media_count": 7, "is_private": False}}}

    return SimpleNamespace(is_logged_in=logged_in, get_json=get_json, doc_id_graphql_query=doc_id_graphql_query, request_timeout=30, iphone_support=False, profile_id_cache={}, _session=None), calls


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

    # A reel added in the same interval a post is removed leaves the posts count where it was, so a count that has
    # been reused for long enough is established again rather than trusted until that number moves
    def test_a_count_is_not_reused_forever(self, im_module, monkeypatch):
        walks = []
        monkeypatch.setattr(im_module, "_count_total_reels", lambda user, bot, skip_session: walks.append(user) or 7)

        for _ in range(im_module.REELS_COUNT_MAX_REUSE + 2):
            im_module.get_total_reels_count("target", None, False, 20)

        assert len(walks) == 2

    # A caller with no posts count to compare has nothing to reuse against, so it always counts
    def test_a_missing_posts_count_always_counts(self, im_module, monkeypatch):
        walks = []
        monkeypatch.setattr(im_module, "_count_total_reels", lambda user, bot, skip_session: walks.append(user) or 7)

        im_module.get_total_reels_count("target", None, False, None)
        im_module.get_total_reels_count("target", None, False, None)

        assert len(walks) == 2
