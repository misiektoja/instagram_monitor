"""Offline workflow tests for paginated follower and following fetches."""

from types import SimpleNamespace
import json
import os


# Builds a generator of fake Instaloader username objects
def _fake_accounts(usernames):
    return iter(SimpleNamespace(username=username) for username in usernames)


class TestFetchUsernamesPaginated:
    # Basic fetching drains the generator when advanced batching is disabled
    def test_basic_fetch_drains_generator(self, im_module):
        result = im_module.fetch_usernames_paginated(None, lambda: _fake_accounts(["a", "b", "c"]), max_per_batch=1, total_limit=1, fetch_delay=0, advanced_fetch=False, estimated_limit=0, user="target")

        assert result == ["a", "b", "c"]
        assert result.complete is True

    # Advanced fetching stops exactly at total_limit even when the batch size is larger
    def test_advanced_fetch_respects_total_limit(self, im_module, monkeypatch):
        logs = []
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))

        result = im_module.fetch_usernames_paginated(None, lambda: _fake_accounts(["a", "b", "c", "d", "e"]), max_per_batch=50, total_limit=3, fetch_delay=0, advanced_fetch=True, estimated_limit=5, user="target")

        assert result == ["a", "b", "c"]
        assert result.complete is False
        assert logs[0][0] == ("Fetching 5 accounts in batches of 50 accounts with a 0 second delay",)
        assert logs[0][1] == {"user": "target"}

    # Stop events set before fetching return an empty partial result
    def test_stop_event_before_fetch_returns_empty(self, im_module):
        stop_event = SimpleNamespace(is_set=lambda: True)

        result = im_module.fetch_usernames_paginated(None, lambda: _fake_accounts(["a", "b"]), max_per_batch=1, total_limit=0, fetch_delay=0, advanced_fetch=True, estimated_limit=2, user="target", stop_event=stop_event)

        assert result == []
        assert result.complete is False

    # Stop events set during the inter-batch wait return the already fetched batch
    def test_stop_event_during_fetch_delay_returns_partial(self, im_module, monkeypatch):
        logs = []

        class StopAfterWait:
            # Tracks wait calls and flips to stopped after the first wait
            def __init__(self):
                self.stopped = False
                self.waits = []

            # Returns whether the event has been set
            def is_set(self):
                return self.stopped

            # Records the wait interval and sets the event
            def wait(self, seconds):
                self.waits.append(seconds)
                self.stopped = True

        stop_event = StopAfterWait()
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))

        result = im_module.fetch_usernames_paginated(None, lambda: _fake_accounts(["a", "b", "c", "d"]), max_per_batch=2, total_limit=0, fetch_delay=5, advanced_fetch=True, estimated_limit=4, user="target", stop_event=stop_event)

        assert result == ["a", "b"]
        assert result.complete is False
        assert stop_event.waits == [1]
        assert len(logs) == 1

    # Baseline safety rejects partial lists and contradictory empty results
    def test_baseline_requires_complete_plausible_result(self, im_module):
        partial = im_module.PaginatedUsernameResult(["a"])
        partial.complete = False
        complete = im_module.PaginatedUsernameResult(["a"])
        complete.complete = True
        contradictory_empty = im_module.PaginatedUsernameResult()
        contradictory_empty.complete = True

        assert im_module.is_complete_username_baseline(partial, 1) is False
        assert im_module.is_complete_username_baseline(complete, 1) is True
        assert im_module.is_complete_username_baseline(contradictory_empty, 1) is False
        assert im_module.is_complete_username_baseline(contradictory_empty, 0) is True

    # A stalled browser dialog and a real unfollow both come back short. Instagram's own count is what
    # separates them, and the saved list is the second witness
    def test_a_list_short_of_the_count_may_not_shrink_the_saved_one(self, im_module, capsys):
        result = im_module.PaginatedUsernameResult([f"user{index}" for index in range(90)])
        result.complete = True

        im_module.reject_shrinking_username_baseline(result, 100, [f"user{index}" for index in range(100)], "followers", "target")

        assert result.complete is False
        assert im_module.is_complete_username_baseline(result, 100) is False
        assert "came back with 90 of about 100 while 100 were already saved" in capsys.readouterr().out

    # Accounts that really went away move the reported count too, so the smaller list is the truth and is saved
    def test_a_real_unfollow_the_count_agrees_with_is_saved(self, im_module):
        result = im_module.PaginatedUsernameResult([f"user{index}" for index in range(80)])
        result.complete = True

        im_module.reject_shrinking_username_baseline(result, 80, [f"user{index}" for index in range(100)], "followers", "target")

        assert result.complete is True

    # A count that lags behind a growing list is not a shortfall worth keeping the old baseline for
    def test_a_growing_list_behind_a_stale_count_is_saved(self, im_module):
        result = im_module.PaginatedUsernameResult([f"user{index}" for index in range(95)])
        result.complete = True

        im_module.reject_shrinking_username_baseline(result, 100, [f"user{index}" for index in range(90)], "followers", "target")

        assert result.complete is True

    # The first run has nothing to lose, and a list that was already unusable is left as it was
    def test_a_first_run_and_an_incomplete_list_are_left_alone(self, im_module):
        first_run = im_module.PaginatedUsernameResult(["a"])
        first_run.complete = True
        already_partial = im_module.PaginatedUsernameResult(["a"])
        already_partial.complete = False

        im_module.reject_shrinking_username_baseline(first_run, 100, [], "followers", "target")
        im_module.reject_shrinking_username_baseline(already_partial, 100, ["a", "b"], "followers", "target")

        assert first_run.complete is True
        assert already_partial.complete is False

    # Baseline writes replace the final JSON file without leaving a temporary sibling
    def test_save_username_baseline_is_atomic(self, im_module):
        local_dir = os.path.join(os.path.dirname(os.path.abspath(im_module.__file__)), "local")
        os.makedirs(local_dir, exist_ok=True)
        baseline_file = os.path.join(local_dir, "test_followers_baseline.json")
        try:
            im_module.save_username_baseline(baseline_file, 2, ["a", "b"])

            with open(baseline_file, encoding="utf-8") as handle:
                assert json.load(handle) == [2, ["a", "b"]]
            assert not [name for name in os.listdir(local_dir) if name.startswith(".test_followers_baseline.json.")]
        finally:
            if os.path.isfile(baseline_file):
                os.remove(baseline_file)
