"""Offline tests for the tool's patches on Instaloader methods."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from instaloader.instaloadercontext import InstaloaderContext
from instaloader.structures import Post, Profile

PROFILE_QUERY = "27937681195819736"
POST_QUERY = "27128499623469141"
REELS_QUERY = "28971369649196954"
STORIES_QUERY = "29341065465524437"

# Start page of a signed-in session, with the web app tokens
SIGNED_IN_PAGE = '<script>["DTSGInitialData",[],{"token":"dtsg-token"}],["LSD",[],{"token":"lsd-token"}],{"IG_USER_EIMU":"42"}</script>'

# Start page of a visitor, without fb_dtsg
SIGNED_OUT_PAGE = '<script>["LSD",[],{"token":"lsd-token"}],{"IG_USER_EIMU":"0"}</script>'


# Replaces Instaloader's doc_id query with a recorder under the tool's patch. Returns the recorded calls and
# an uninitialised context to query through
def _patched_query(im_module, monkeypatch, reply=None):
    calls = []

    def original(self, doc_id, variables, referer=None, web_api=False):
        calls.append((doc_id, variables, referer, web_api))
        return reply if reply is not None else {"data": {}}

    monkeypatch.setattr(InstaloaderContext, "doc_id_graphql_query", original)
    monkeypatch.setattr(im_module, "_INSTALOADER_GRAPHQL_PROFILE_PATCH_APPLIED", False)
    im_module._apply_instaloader_graphql_profile_patch()
    return calls, InstaloaderContext.__new__(InstaloaderContext)


class TestTheGraphqlPatchPassesEveryArgument:
    # Instaloader 4.16 passes web_api as a fourth positional argument for posts and reels
    def test_a_positional_web_api_reaches_instaloader(self, im_module, monkeypatch):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query("29104886249145907", {"first": 12}, "https://www.instagram.com/target/", True)

        assert calls == [("29104886249145907", {"first": 12}, "https://www.instagram.com/target/", True)]

    # Callers may name the argument instead
    def test_a_keyword_web_api_reaches_instaloader(self, im_module, monkeypatch):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query("29104886249145907", {"first": 12}, referer=None, web_api=True)

        assert calls == [("29104886249145907", {"first": 12}, None, True)]

    # Older Instaloader releases still ask for the retired profile query, which the patch moves to the working one
    def test_the_retired_profile_query_is_still_rewritten(self, im_module, monkeypatch):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query("25980296051578533", {"id": "77"})

        doc_id, variables, referer, web_api = calls[0]
        assert doc_id == "27937681195819736"
        assert variables["id"] == "77" and variables["enable_integrity_filters"] is True
        assert (referer, web_api) == (None, True)


class TestSignedInQueriesUseTheWebAppEndpoint:
    # graphql/query refuses both queries for signed-in sessions
    @pytest.mark.parametrize("doc_id", [PROFILE_QUERY, POST_QUERY])
    def test_the_profile_and_post_queries_are_moved(self, im_module, monkeypatch, doc_id):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query(doc_id, {"id": "77"})

        assert calls == [(doc_id, {"id": "77"}, None, True)]

    # web_api passed by position or by name is overridden
    @pytest.mark.parametrize("arguments, keywords", [((None, False), {}), ((), {"web_api": False}), ((None,), {"web_api": False})])
    def test_an_explicit_legacy_endpoint_is_overridden(self, im_module, monkeypatch, arguments, keywords):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query(PROFILE_QUERY, {"id": "77"}, *arguments, **keywords)

        assert calls == [(PROFILE_QUERY, {"id": "77"}, None, True)]

    # Instaloader reads a profile by id through this query
    def test_a_signed_in_profile_read_reaches_the_web_app_endpoint(self, im_module, monkeypatch):
        calls, context = _patched_query(im_module, monkeypatch, {"data": {"user": {"username": "target", "pk": "77", "follower_count": 5}}})
        context.username = "session.account"

        profile = Profile(context, {"username": "target", "id": "77"})
        profile._obtain_metadata()

        assert [(doc_id, web_api) for doc_id, _, _, web_api in calls] == [(PROFILE_QUERY, True)]
        assert profile.followers == 5


# Returns a client signed in as user 42 that records queries and start page loads. A legacy query fails the test
def _signed_in_client(im_module, monkeypatch, replies=None, page=SIGNED_IN_PAGE, user_id="42"):
    queries, pages = [], []

    def doc_id_graphql_query(self, doc_id, variables, referer=None, web_api=False):
        queries.append((doc_id, variables, web_api))
        reply = (replies or {})[doc_id]
        if isinstance(reply, Exception):
            raise reply
        return reply

    def get_page(self, session, path):
        pages.append(path)
        if isinstance(page, Exception):
            raise page
        return page

    monkeypatch.setattr(InstaloaderContext, "doc_id_graphql_query", doc_id_graphql_query)
    monkeypatch.setattr(InstaloaderContext, "_get_page", get_page)
    monkeypatch.setattr(InstaloaderContext, "graphql_query", lambda self, query_hash, *args, **kwargs: pytest.fail(f"the legacy query {query_hash} was sent to graphql/query"))
    bot = im_module.instaloader.Instaloader(sleep=False, quiet=True, iphone_support=False)
    bot.context.username = "session.account"
    bot.context._session.cookies.set("sessionid", "synthetic-session")
    if user_id:
        bot.context._session.cookies.set("ds_user_id", user_id)
    return bot, queries, pages


class TestTheLoginCheckAvoidsTheRefusedEndpoint:
    # The start page proves the sign-in and the profile query names the account
    def test_a_signed_in_session_reports_its_username(self, im_module, monkeypatch):
        bot, queries, pages = _signed_in_client(im_module, monkeypatch, {PROFILE_QUERY: {"data": {"user": {"username": "session.account"}}}})

        assert bot.test_login() == "session.account"
        assert pages == [""]
        assert [(doc_id, variables["id"], web_api) for doc_id, variables, web_api in queries] == [(PROFILE_QUERY, "42", True)]

    # The profile query answers visitors too, so the check stops at a signed-out start page
    def test_a_signed_out_start_page_is_not_logged_in(self, im_module, monkeypatch):
        bot, queries, pages = _signed_in_client(im_module, monkeypatch, page=SIGNED_OUT_PAGE)

        assert bot.test_login() is None
        assert pages == [""]
        assert queries == []

    # Kept tokens say nothing about the session now
    def test_every_check_reads_the_start_page_again(self, im_module, monkeypatch):
        bot, _, pages = _signed_in_client(im_module, monkeypatch, {PROFILE_QUERY: {"data": {"user": {"username": "session.account"}}}})

        assert bot.test_login() == "session.account"
        assert bot.test_login() == "session.account"
        assert pages == ["", ""]

    # No account id cookie means no sign-in
    def test_cookies_without_an_account_id_send_no_request(self, im_module, monkeypatch):
        bot, queries, pages = _signed_in_client(im_module, monkeypatch, user_id="")

        assert bot.test_login() is None
        assert (pages, queries) == ([], [])

    # A failed check returns None instead of raising
    def test_a_failed_check_is_not_logged_in(self, im_module, monkeypatch, capsys):
        refusal = im_module.instaloader.exceptions.ConnectionException("HTTP 500 when accessing https://www.instagram.com/api/graphql")
        bot, _, _ = _signed_in_client(im_module, monkeypatch, {PROFILE_QUERY: refusal})

        assert bot.test_login() is None
        assert "HTTP 500" in capsys.readouterr().err

    # The own profile is read by id, not through the refused query
    def test_the_own_profile_is_read_by_id(self, im_module, monkeypatch):
        bot, queries, _ = _signed_in_client(im_module, monkeypatch, {PROFILE_QUERY: {"data": {"user": {"username": "session.account", "pk": "42"}}}})

        profile = Profile.own_profile(bot.context)

        assert profile.username == "session.account"
        assert [(doc_id, variables["id"]) for doc_id, variables, _ in queries] == [(PROFILE_QUERY, "42")]

    # No session means no own profile
    def test_the_own_profile_needs_a_session(self, im_module, monkeypatch):
        bot, _, _ = _signed_in_client(im_module, monkeypatch)
        bot.context.username = None

        with pytest.raises(im_module.instaloader.exceptions.LoginRequiredException):
            Profile.own_profile(bot.context)


class TestWebAppTokensAreReadAgain:
    # Tokens past the age limit are read from a fresh start page
    def test_old_tokens_are_replaced(self, im_module, monkeypatch):
        bot, _, pages = _signed_in_client(im_module, monkeypatch)
        clock = [1000.0]
        monkeypatch.setattr(im_module.time, "monotonic", lambda: clock[0])

        first = bot.context._web_api_tokens()
        clock[0] += im_module.INSTALOADER_WEB_API_TOKEN_MAX_AGE - 1
        assert bot.context._web_api_tokens() is first
        assert pages == [""]

        clock[0] += 2
        assert bot.context._web_api_tokens() == first
        assert pages == ["", ""]


# Returns the naive UTC time Instaloader reports for a timestamp
def _utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)


# Returns a profile with loaded metadata, so reading it sends no request
def _loaded_profile(context, **fields):
    profile = Profile(context, {"username": "target", "id": "77", **fields})
    profile._has_full_metadata = True
    return profile


class TestReelsUseTheWebAppQuery:
    REPLY = {"data": {"fetch__XDTUserDict": {"clips_connection": {"edges": [{"node": {"media": {"code": "REEL1"}}}, {"node": {"media": {"code": "REEL2"}}}], "page_info": {"has_next_page": False, "end_cursor": None}}}}}

    # Instaloader's own reels query is refused or comes back empty when signed in
    def test_a_signed_in_reel_list_comes_from_the_reels_tab_query(self, im_module, monkeypatch):
        bot, queries, _ = _signed_in_client(im_module, monkeypatch, {REELS_QUERY: self.REPLY})
        monkeypatch.setattr(Post, "from_shortcode", classmethod(lambda cls, context, shortcode: SimpleNamespace(shortcode=shortcode, date_local=datetime(2026, 11, 1))))

        reels = list(_loaded_profile(bot.context).get_reels())

        assert [reel.shortcode for reel in reels] == ["REEL1", "REEL2"]
        (doc_id, variables, web_api), = queries
        assert (doc_id, web_api) == (REELS_QUERY, True)
        assert variables["id"] == "77" and variables["data"]["target_user_id"] == "77"


class TestStoriesUseTheWebAppQueries:
    IMAGE = {"pk": "900", "media_type": 1, "taken_at": 1790000000, "expiring_at": 1790086400, "user": {"pk": "77"}, "caption": {"text": "Hello @friend #tag"}, "image_versions2": {"candidates": [{"url": "https://cdn.invalid/large.jpg", "width": 1080, "height": 1920}, {"url": "https://cdn.invalid/small.jpg", "width": 320, "height": 568}]}}
    VIDEO = {"pk": "901", "media_type": 2, "taken_at": 1790000100, "expiring_at": 1790086500, "user": {"pk": "77"}, "caption": None, "image_versions2": {"candidates": [{"url": "https://cdn.invalid/frame.jpg", "width": 720, "height": 1280}]}, "video_versions": [{"url": "https://cdn.invalid/best.mp4"}, {"url": "https://cdn.invalid/low.mp4"}]}

    # Returns a story query reply for one account with the given items
    def _reels(self, *items):
        return {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": [{"id": "77", "user": {"pk": "77", "id": "77", "username": "target"}, "seen": 0, "latest_reel_media": 1790000100, "items": list(items)}]}}}

    # latest_reel_media in the profile tells whether a story exists
    @pytest.mark.parametrize("latest, expected", [(1790000000, True), (0, False), (None, False)])
    def test_a_story_is_read_from_the_profile(self, im_module, monkeypatch, latest, expected):
        bot, queries, _ = _signed_in_client(im_module, monkeypatch)

        assert _loaded_profile(bot.context, latest_reel_media=latest).has_public_story is expected
        assert queries == []

    # Story items keep the fields the tool prints
    def test_story_items_come_from_the_web_app_query(self, im_module, monkeypatch):
        bot, queries, _ = _signed_in_client(im_module, monkeypatch, {STORIES_QUERY: self._reels(self.IMAGE, self.VIDEO)})

        story = next(bot.get_stories(userids=[77]))
        video, image = list(story.get_items())

        (doc_id, variables, web_api), = queries
        assert (doc_id, web_api, variables["reel_ids_arr"]) == (STORIES_QUERY, True, ["77"])
        assert story.itemcount == 2
        assert (image.typename, image.url, image.caption) == ("GraphStoryImage", "https://cdn.invalid/large.jpg", "Hello @friend #tag")
        assert (image.caption_mentions, image.caption_hashtags) == (["friend"], ["tag"])
        assert (image.date_utc, image.expiring_utc) == (_utc(1790000000), _utc(1790086400))
        assert (video.typename, video.video_url, video.caption) == ("GraphStoryVideo", "https://cdn.invalid/best.mp4", None)

    # An account without a story is absent from the reply
    def test_an_account_without_a_story_yields_nothing(self, im_module, monkeypatch):
        bot, _, _ = _signed_in_client(im_module, monkeypatch, {STORIES_QUERY: {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": []}}}})

        assert next(bot.get_stories(userids=[77]), None) is None

    # Instagram fails the query above 35 accounts, so a longer list is split
    def test_a_long_list_is_asked_in_parts(self, im_module, monkeypatch):
        bot, queries, _ = _signed_in_client(im_module, monkeypatch, {STORIES_QUERY: {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": []}}}})

        assert list(bot.get_stories(userids=list(range(1, 46)))) == []
        assert [len(variables["reel_ids_arr"]) for _, variables, _ in queries] == [30, 15]

    # A reply without story data raises instead of reading as no story
    def test_a_reply_without_story_data_is_an_error(self, im_module, monkeypatch):
        bot, _, _ = _signed_in_client(im_module, monkeypatch, {STORIES_QUERY: {"data": {"xdt_api__v1__feed__reels_media": None}}})

        with pytest.raises(im_module.instaloader.exceptions.BadResponseException):
            next(bot.get_stories(userids=[77]))

    # Stories need a session
    def test_stories_need_a_session(self, im_module, monkeypatch):
        bot, _, _ = _signed_in_client(im_module, monkeypatch)
        bot.context.username = None

        with pytest.raises(im_module.instaloader.exceptions.LoginRequiredException):
            bot.get_stories(userids=[77])
