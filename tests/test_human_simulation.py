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


class TestHumanSimulationFolloweeVisit:
    # Only a bounded window of followees is pulled, so one profile visit cannot paginate a whole account
    def test_followee_visit_reads_a_bounded_window(self, im_module, monkeypatch):
        pulled = {"count": 0}

        def endless_followees():
            while True:
                pulled["count"] += 1
                yield SimpleNamespace(username=f"followee{pulled['count']}")

        monkeypatch.setattr(im_module, "MY_HASHTAGS", [])
        monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 5)
        monkeypatch.setattr(im_module, "CHECK_POSTS_IN_HOURS_RANGE", False)
        monkeypatch.setattr(im_module, "DEBUG_MODE", False)
        monkeypatch.setattr(im_module, "BE_HUMAN_VERBOSE", False)
        monkeypatch.setattr(im_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(im_module.instaloader.Profile, "own_profile", staticmethod(lambda ctx: SimpleNamespace(get_followees=endless_followees)))
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, username: SimpleNamespace(username=username))
        bot = SimpleNamespace(context=SimpleNamespace(is_logged_in=True))
        bot.get_explore_posts = lambda: iter([object()])
        bot.get_hashtag_posts = lambda tag: iter([object()])

        im_module.simulate_human_actions(bot, 86400)

        assert pulled["count"] <= im_module.BE_HUMAN_FOLLOWEE_SAMPLE
