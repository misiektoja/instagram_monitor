"""Offline tests for the BeHuman activity simulation guards."""

from types import SimpleNamespace

import pytest


# Builds a logged-out Instaloader stand-in so only the hashtag branch of the simulation can run
def make_anonymous_bot():
    return SimpleNamespace(context=SimpleNamespace(is_logged_in=False))


class TestHumanSimulationHashtags:
    # An empty hashtag list skips the browse action instead of aborting the whole simulation
    @pytest.mark.parametrize("hashtags", [[], (), None, "", ["", "   "]])
    def test_missing_hashtags_do_not_raise(self, im_module, monkeypatch, hashtags):
        monkeypatch.setattr(im_module, "MY_HASHTAGS", hashtags)
        monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 5)
        monkeypatch.setattr(im_module, "CHECK_POSTS_IN_HOURS_RANGE", False)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        monkeypatch.setattr(im_module, "BE_HUMAN_VERBOSE", False)

        for _ in range(50):
            im_module.simulate_human_actions(make_anonymous_bot(), 86400)

    # A configured hashtag is still browsed, so the guard does not disable the feature
    def test_configured_hashtags_are_still_browsed(self, im_module, monkeypatch):
        browsed = []
        monkeypatch.setattr(im_module, "MY_HASHTAGS", ["travel"])
        monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 5)
        monkeypatch.setattr(im_module, "CHECK_POSTS_IN_HOURS_RANGE", False)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        monkeypatch.setattr(im_module, "BE_HUMAN_VERBOSE", False)
        monkeypatch.setattr(im_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: None)
        bot = make_anonymous_bot()
        bot.get_hashtag_posts = lambda tag: browsed.append(tag) or iter([object()])

        im_module.simulate_human_actions(bot, 86400)

        assert browsed == ["travel"]

    # Blank entries are ignored while real hashtags remain selectable
    def test_blank_entries_are_ignored(self, im_module, monkeypatch):
        browsed = []
        monkeypatch.setattr(im_module, "MY_HASHTAGS", ["", "  ", "food"])
        monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 5)
        monkeypatch.setattr(im_module, "CHECK_POSTS_IN_HOURS_RANGE", False)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        monkeypatch.setattr(im_module, "BE_HUMAN_VERBOSE", False)
        monkeypatch.setattr(im_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: None)
        bot = make_anonymous_bot()
        bot.get_hashtag_posts = lambda tag: browsed.append(tag) or iter([object()])

        im_module.simulate_human_actions(bot, 86400)

        assert browsed == ["food"]


@pytest.fixture
# Makes every action of the simulation run on each call, without pauses
def every_action(im_module, monkeypatch):
    monkeypatch.setattr(im_module, "MY_HASHTAGS", ["travel"])
    monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 5)
    monkeypatch.setattr(im_module, "CHECK_POSTS_IN_HOURS_RANGE", False)
    monkeypatch.setattr(im_module, "DEBUG_MODE", False)
    monkeypatch.setattr(im_module, "BE_HUMAN_VERBOSE", False)
    monkeypatch.setattr(im_module.random, "random", lambda: 0.0)
    monkeypatch.setattr(im_module.time, "sleep", lambda seconds: None)


# Builds a signed-in Instaloader stand-in whose GraphQL readers record any call into the given list
def make_signed_in_bot(called):
    bot = SimpleNamespace(context=SimpleNamespace(is_logged_in=True))
    bot.get_explore_posts = lambda: called.append("graphql explore") or iter([object()])
    bot.get_hashtag_posts = lambda tag: called.append("graphql hashtag") or iter([object()])
    return bot


class TestSignedInSimulation:
    # Instagram refuses the GraphQL readers for signed-in sessions, so the actions use the web REST endpoints.
    # The hashtag action has no endpoint left and is not sent
    def test_actions_use_the_web_rest_endpoints(self, im_module, monkeypatch, every_action):
        called = []
        own_profile = SimpleNamespace(userid=1, username="me", get_followees=lambda: called.append("graphql followees") or iter([]))
        monkeypatch.setattr(im_module, "browse_explore_grid", lambda bot: called.append("explore grid") or 6, raising=False)
        monkeypatch.setattr(im_module.instaloader.Profile, "own_profile", staticmethod(lambda ctx: called.append("own profile") or own_profile))
        monkeypatch.setattr(im_module, "iter_rest_follow_list", lambda bot, profile, kind: called.append(f"rest {kind} of {profile.username}") or iter([SimpleNamespace(username="friend", userid=7)]))
        monkeypatch.setattr(im_module, "_profile_by_user_id", lambda ctx, username, user_id: called.append(f"visit {username} by id {user_id}"))

        im_module.simulate_human_actions(make_signed_in_bot(called), 86400)

        assert called == ["explore grid", "own profile", "own profile", "rest following of me", "visit friend by id 7"]

    # Only a bounded window of followees is pulled, so one profile visit cannot paginate a whole account
    def test_followee_visit_reads_a_bounded_window(self, im_module, monkeypatch, every_action):
        pulled = {"count": 0}

        def endless_followees(bot, profile, kind):
            while True:
                pulled["count"] += 1
                yield SimpleNamespace(username=f"followee{pulled['count']}", userid=pulled["count"])

        monkeypatch.setattr(im_module, "browse_explore_grid", lambda bot: 6, raising=False)
        monkeypatch.setattr(im_module.instaloader.Profile, "own_profile", staticmethod(lambda ctx: SimpleNamespace(userid=1, username="me")))
        monkeypatch.setattr(im_module, "iter_rest_follow_list", endless_followees)
        monkeypatch.setattr(im_module, "_profile_by_user_id", lambda ctx, username, user_id: None)

        im_module.simulate_human_actions(make_signed_in_bot([]), 86400)

        assert 0 < pulled["count"] <= im_module.BE_HUMAN_FOLLOWEE_SAMPLE


# Stands in for an Instaloader context that answers one REST request with a scripted reply
class _RestContext:
    request_timeout = 1

    # Starts with the JSON reply to hand out
    def __init__(self, reply):
        self._session = SimpleNamespace()
        self.reply = reply
        self.requests = []

    # Records the path, query and headers of the request and returns the scripted reply
    def get_json(self, path, params, session, response_headers=None):
        self.requests.append((path, dict(params), dict(session.headers)))
        return self.reply


class TestExploreGrid:
    # The grid is read from the web app's REST endpoint with the headers the web app adds on its Explore page
    def test_reads_the_grid_over_rest(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "instaloader_copy_session", lambda *args, **kwargs: SimpleNamespace(headers={}, close=lambda: None))
        context = _RestContext({"sectional_items": [{}, {}, {}]})

        assert im_module.browse_explore_grid(SimpleNamespace(context=context)) == 3

        (path, params, headers), = context.requests
        assert path == "api/v1/discover/web/explore_grid/"
        assert params == im_module.EXPLORE_GRID_PARAMS
        assert headers["Referer"] == "https://www.instagram.com/explore/"
        assert headers["X-IG-App-ID"] == im_module.INSTAGRAM_WEB_APP_ID

    # A reply without a section list means the endpoint changed, which must not pass as a successful action
    @pytest.mark.parametrize("reply", [{}, {"sectional_items": None}, []])
    def test_a_reply_without_sections_is_an_api_change(self, im_module, monkeypatch, reply):
        monkeypatch.setattr(im_module, "instaloader_copy_session", lambda *args, **kwargs: SimpleNamespace(headers={}, close=lambda: None))

        with pytest.raises(im_module.InstagramRestSchemaError):
            im_module.browse_explore_grid(SimpleNamespace(context=_RestContext(reply)))
