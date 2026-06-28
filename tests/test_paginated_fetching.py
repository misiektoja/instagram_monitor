"""Offline workflow tests for paginated follower and following fetches."""

from types import SimpleNamespace


# Builds a generator of fake Instaloader username objects
def _fake_accounts(usernames):
    return iter(SimpleNamespace(username=username) for username in usernames)


class TestFetchUsernamesPaginated:
    # Basic fetching drains the generator when advanced batching is disabled
    def test_basic_fetch_drains_generator(self, im_module):
        result = im_module.fetch_usernames_paginated(None, lambda: _fake_accounts(["a", "b", "c"]), max_per_batch=1, total_limit=1, fetch_delay=0, advanced_fetch=False, estimated_limit=0, user="target")

        assert result == ["a", "b", "c"]

    # Advanced fetching stops exactly at total_limit even when the batch size is larger
    def test_advanced_fetch_respects_total_limit(self, im_module, monkeypatch):
        logs = []
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))

        result = im_module.fetch_usernames_paginated(None, lambda: _fake_accounts(["a", "b", "c", "d", "e"]), max_per_batch=50, total_limit=3, fetch_delay=0, advanced_fetch=True, estimated_limit=5, user="target")

        assert result == ["a", "b", "c"]
        assert logs[0][0] == ("Fetching 5 accounts in batches of 50 accounts with a 0 second delay",)
        assert logs[0][1] == {"user": "target"}

    # Stop events set before fetching return an empty partial result
    def test_stop_event_before_fetch_returns_empty(self, im_module):
        stop_event = SimpleNamespace(is_set=lambda: True)

        result = im_module.fetch_usernames_paginated(None, lambda: _fake_accounts(["a", "b"]), max_per_batch=1, total_limit=0, fetch_delay=0, advanced_fetch=True, estimated_limit=2, user="target", stop_event=stop_event)

        assert result == []

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
        assert stop_event.waits == [1]
        assert len(logs) == 1
