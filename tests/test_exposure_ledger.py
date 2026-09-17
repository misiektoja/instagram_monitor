"""Offline tests for the identity exposure ledger, the daily budget and the account circuit breaker."""

import json
import threading

import pytest

import instagram_monitor as im

# Captured before the autouse ledger-isolation fixture can patch it, so the path test can check the real derivation
_REAL_EXPOSURE_STATE_PATH = im.exposure_state_path


class _FakeUser:
    def __init__(self, username):
        self.username = username


# Returns a resolver stub that always fails, standing in for a probe of the canonical public account
def _raises(message):
    def _resolve(bot, username):
        raise Exception(message)

    return _resolve


# Returns a generator of fake instaloader profiles, standing in for get_followers()
def _names(count):
    return (_FakeUser(f"user{index}") for index in range(count))


# Points the ledger at a temporary directory and gives every test a known session account
@pytest.fixture
def ledger(monkeypatch, tmp_path):
    monkeypatch.setattr(im, "exposure_state_path", _REAL_EXPOSURE_STATE_PATH, raising=False)
    monkeypatch.setattr(im, "OUTPUT_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(im, "SESSION_USERNAME", "testacct", raising=False)
    monkeypatch.setattr(im, "SKIP_SESSION", False, raising=False)
    monkeypatch.setattr(im, "CIRCUIT_BREAKER", True, raising=False)
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 0, raising=False)
    monkeypatch.setattr(im, "log_activity", lambda *args, **kwargs: None, raising=False)
    return im


@pytest.mark.parametrize(("message", "expected_class", "expected_group"), [
    ("429 Too Many Requests", "rate_limit", "A"),
    ("400 Bad Request - checkpoint_required", "challenge", "C"),
    ("Instagram may have detected automated checks", "challenge", "C"),
    ("401 Unauthorized", "auth_expired", "C"),
    ("400 Bad Request", "unknown", ""),
    ("TypeError: 'NoneType' object is not subscriptable", "schema_change", "B"),
    ("ProfileNotExistsException", "target_unavailable", ""),
    ("Could not resolve host", "dns_failure", ""),
    ("something entirely unexpected", "unknown", ""),
])
def test_failure_classes_map_to_reliability_groups(message, expected_class, expected_group):
    assert im.classify_failure_class(message) == expected_class
    assert im.failure_class_group(im.classify_failure_class(message)) == expected_group


# A status code is a whole number, so the 403 inside a user id or the 401 in a username must not classify the error
@pytest.mark.parametrize(("message", "expected_class"), [
    ("ConnectionException: JSON Query to api/v1/friendships/4030/following/: HTTP error code 500.", "network"),
    ("JSON Query to api/v1/friendships/4030/following/: HTTP error code 500.", "unknown"),
    ("JSON Query to api/v1/friendships/12340312/followers/: 404 Not Found", "target_unavailable"),
    ("Profile 401club does not exist", "target_unavailable"),
    ("JSON Query to api/v1/friendships/403/followers/: 429 Too Many Requests", "rate_limit"),
    ("JSON Query to api/v1/friendships/4030/followers/: 403 Forbidden", "auth_expired"),
    ("HTTP error code 401.", "auth_expired"),
])
def test_a_status_code_inside_a_number_does_not_classify(message, expected_class):
    assert im.classify_failure_class(message) == expected_class


def test_only_account_level_failures_are_group_c():
    assert im.is_account_level_failure("challenge") is True
    assert im.is_account_level_failure("auth_expired") is True
    assert im.is_account_level_failure("rate_limit") is False
    assert im.is_account_level_failure("schema_change") is False


# The classifier and the message table must stay in step, so every ordered class still produces a summary
@pytest.mark.parametrize("failure_class", im.FAILURE_CLASS_ORDER)
def test_every_ordered_class_has_matching_terms(failure_class):
    assert im.FAILURE_TERMS[failure_class]
    sample = im.FAILURE_TERMS[failure_class][0]
    # A retired endpoint is named by two terms together, since the endpoint alone says nothing about the failure
    if failure_class == "endpoint_retired":
        sample = f"{sample} {im.FAILURE_TERMS['action_block'][0]}"
    summary = im.classify_recovery_error(sample, is_logged_in=False).summary
    assert im.classify_failure_class(sample) == failure_class
    assert summary
    assert summary != "An unexpected error stopped the requested action"


def test_identities_are_counted(ledger):
    result = im.fetch_usernames_paginated(None, lambda: _names(30), 0, 0, 0, False, 30, "target")
    assert len(result) == 30
    assert result.complete is True
    assert im.exposure_snapshot()["identities"] == 30


def test_budget_caps_the_fetch_and_leaves_it_incomplete(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 40, raising=False)
    im.fetch_usernames_paginated(None, lambda: _names(30), 0, 0, 0, False, 30, "target")
    # The count Instagram reported fits what is left, but the list grew since it was read
    result = im.fetch_usernames_paginated(None, lambda: _names(100), 0, 0, 0, False, 10, "target")
    assert len(result) == 10
    assert result.complete is False
    assert im.identity_budget_remaining() == 0
    # An incomplete result must never overwrite a good baseline
    assert im.is_complete_username_baseline(result, 100) is False


# Instaloader's NodeIterator fetches its first page while it is being constructed, so names reach this process
# before anything can count or cap them. A plain generator produces one name per next() and hides that entirely
class EagerPageSource:
    # Takes the pages the endpoint would serve and fetches the first one immediately, as the real iterator does
    def __init__(self, pages):
        self.remaining = [list(page) for page in pages]
        self.served = []
        self.buffer = self._fetch_page()

    def _fetch_page(self):
        page = self.remaining.pop(0) if self.remaining else []
        self.served.extend(page)
        return page

    def __iter__(self):
        while True:
            while self.buffer:
                yield _FakeUser(self.buffer.pop(0))
            if not self.remaining:
                return
            self.buffer = self._fetch_page()


def test_the_budget_caps_what_a_page_source_returns(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 10, raising=False)
    source = EagerPageSource([[f"p1-{index}" for index in range(50)], [f"p2-{index}" for index in range(50)]])

    result = im.fetch_usernames_paginated(None, lambda: im._iter_accounted_follow_list(iter(source)), 0, 0, 0, False, 10, "target", identities_counted_at_source=True)

    assert len(result) == 10
    assert result.complete is False
    assert im.exposure_snapshot()["identities"] == 10


# Instagram served a whole page before the budget could stop it, so the ledger is short of the real exposure by the
# rest of that page. The REST source has no such gap: it caps the page size it asks for and records the page it got
def test_a_page_source_serves_more_than_the_ledger_records(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 10, raising=False)
    source = EagerPageSource([[f"p1-{index}" for index in range(50)], [f"p2-{index}" for index in range(50)]])

    im.fetch_usernames_paginated(None, lambda: im._iter_accounted_follow_list(iter(source)), 0, 0, 0, False, 10, "target", identities_counted_at_source=True)

    assert len(source.served) == 50, "the first page arrived before anything could count it"
    assert im.exposure_snapshot()["identities"] == 10
    assert len(source.served) > im.exposure_snapshot()["identities"], "the ledger under-counts a page source by the unread rest of its page"


# Only one page is ever fetched ahead, so the under-count is bounded by the page size rather than the whole list
def test_the_under_count_is_bounded_by_one_page(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 10, raising=False)
    source = EagerPageSource([[f"p{page}-{index}" for index in range(20)] for page in range(5)])

    im.fetch_usernames_paginated(None, lambda: im._iter_accounted_follow_list(iter(source)), 0, 0, 0, False, 10, "target", identities_counted_at_source=True)

    assert len(source.served) == 20, "the later pages were never requested"


# A spent budget never reaches the source at all, so no page is fetched and nothing is served
def test_a_spent_budget_never_constructs_the_page_source(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 10, raising=False)
    im.fetch_usernames_paginated(None, lambda: _names(10), 0, 0, 0, False, 10, "target")
    constructed = []

    def build():
        constructed.append(True)
        return im._iter_accounted_follow_list(iter(EagerPageSource([[f"p1-{index}" for index in range(50)]])))

    result = im.fetch_usernames_paginated(None, build, 0, 0, 0, False, 50, "target", identities_counted_at_source=True)

    assert len(result) == 0
    assert constructed == [], "a spent budget must not fetch a page it may not use"


def test_concurrent_fetches_share_one_atomic_budget(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 10, raising=False)
    start = threading.Barrier(3)
    results = [None, None]

    # Starts one fetch at the same time as the other worker
    def run_fetch(index):
        start.wait()
        results[index] = im.fetch_usernames_paginated(None, lambda: _names(10), 0, 0, 0, False, 10, f"target{index}")

    threads = [threading.Thread(target=run_fetch, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert sorted(len(result) for result in results if result is not None) == [0, 10]
    assert im.exposure_snapshot()["identities"] == 10


def test_spent_budget_skips_the_fetch_entirely(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 10, raising=False)
    im.fetch_usernames_paginated(None, lambda: _names(10), 0, 0, 0, False, 10, "target")
    assert im.identity_budget_exhausted() is True
    result = im.fetch_usernames_paginated(None, lambda: _names(50), 0, 0, 0, False, 50, "target")
    assert len(result) == 0


def test_no_budget_means_no_cap(ledger):
    assert im.identity_budget_remaining() is None
    assert im.identity_budget_exhausted() is False
    result = im.fetch_usernames_paginated(None, lambda: _names(500), 0, 0, 0, False, 500, "target")
    assert len(result) == 500


def test_account_level_failure_trips_the_breaker_and_blocks_fetching(ledger):
    assert im.circuit_breaker_tripped() is False
    im.note_instagram_failure("400 Bad Request - checkpoint_required", "target")
    assert im.circuit_breaker_tripped() is True
    result = im.fetch_usernames_paginated(None, lambda: _names(50), 0, 0, 0, False, 50, "target")
    assert len(result) == 0


def test_plain_bad_request_does_not_trip_the_breaker(ledger):
    im.note_instagram_failure("400 Bad Request", "target")
    assert im.circuit_breaker_tripped() is False


def test_breaker_sets_every_registered_target_event(ledger, monkeypatch):
    events = {"one": threading.Event(), "two": threading.Event()}
    monkeypatch.setattr(im, "WEB_DASHBOARD_STOP_EVENTS", events, raising=False)

    im.note_instagram_failure("challenge_required", "target")

    assert all(event.is_set() for event in events.values())


def test_challenge_stops_targets_when_the_ledger_write_fails(ledger, monkeypatch):
    stop_event = threading.Event()
    monkeypatch.setattr(im, "WEB_DASHBOARD_STOP_EVENTS", {"target": stop_event}, raising=False)

    # Simulates storage failing after Instagram has already challenged the account
    def reject_write(_data):
        raise im.ExposureLedgerError("write rejected")

    monkeypatch.setattr(im, "_write_exposure_file", reject_write, raising=False)
    im.note_instagram_failure("challenge_required", "target")
    memory_state = im._account_breaker_memory_state()

    assert stop_event.is_set()
    assert memory_state is not None and memory_state["failure_class"] == "challenge"


def test_persisted_breaker_blocks_monitor_before_client_creation(ledger, monkeypatch):
    im.note_instagram_failure("challenge_required", "target")
    with im.ACCOUNT_BREAKER_MEMORY_LOCK:
        im.ACCOUNT_BREAKER_MEMORY.clear()
    client_created = False

    # Fails the test if monitoring creates an Instagram client after loading the persisted stop
    def create_client(**_kwargs):
        nonlocal client_created
        client_created = True
        raise AssertionError("client must not be created")

    monkeypatch.setattr(im, "instaloader_client", create_client, raising=False)
    im._run_instagram_monitor_pass("target", "", False, True, True, True, True, False)

    assert client_created is False


# A 401 or 403 read from one request is confirmed against Instagram before every target is stopped
class TestExpiredSessionConfirmation:
    # Stands in for the probe fetch of the public account: it returns, or raises what the session answered
    @pytest.fixture
    def probe(self, monkeypatch):
        outcome = {"raise": None, "calls": 0}

        def fetch(bot, username):
            outcome["calls"] += 1
            if outcome["raise"] is not None:
                raise outcome["raise"]
            return object()

        monkeypatch.setattr(im, "profile_from_username_resilient", fetch, raising=False)
        return outcome

    def test_a_session_that_still_signs_in_keeps_the_breaker_armed(self, ledger, probe, capsys):
        im.note_instagram_failure("JSON Query to graphql/query: 403 Forbidden", "target", bot=object())

        assert probe["calls"] == 1
        assert im.circuit_breaker_tripped() is False
        assert im.exposure_snapshot()["failures"] == {"auth_expired": 1}
        assert "still signs in, so the circuit breaker stays armed" in capsys.readouterr().out

    def test_a_probe_that_is_also_rejected_trips_the_breaker(self, ledger, probe):
        probe["raise"] = RuntimeError("JSON Query to api/v1/users/web_profile_info/: 401 Unauthorized - login_required")
        im.note_instagram_failure("JSON Query to graphql/query: 403 Forbidden", "target", bot=object())

        assert im.circuit_breaker_tripped() is True

    def test_a_probe_that_cannot_reach_instagram_does_not_trip_the_breaker(self, ledger, probe, capsys):
        probe["raise"] = RuntimeError("ConnectionException: Max retries exceeded, connection timed out")
        im.note_instagram_failure("JSON Query to graphql/query: 403 Forbidden", "target", bot=object())

        assert im.circuit_breaker_tripped() is False
        assert "check did not complete, so the circuit breaker stays armed" in capsys.readouterr().out

    # Without a client there is nothing to probe with, so the classification stands as it did before
    def test_without_a_client_the_classification_is_trusted(self, ledger, probe):
        im.note_instagram_failure("JSON Query to graphql/query: 403 Forbidden", "target")

        assert probe["calls"] == 0
        assert im.circuit_breaker_tripped() is True

    # A challenge is never a false positive of a transient request, so it is not probed
    def test_a_challenge_is_not_probed(self, ledger, probe):
        im.note_instagram_failure("checkpoint_required", "target", bot=object())

        assert probe["calls"] == 0
        assert im.circuit_breaker_tripped() is True


def test_transport_and_schema_failures_do_not_trip_the_breaker(ledger):
    im.note_instagram_failure("429 Too Many Requests", "target")
    im.note_instagram_failure("TypeError: 'NoneType' object is not subscriptable", "target")
    assert im.circuit_breaker_tripped() is False
    assert im.exposure_snapshot()["failures"] == {"rate_limit": 1, "schema_change": 1}


@pytest.mark.parametrize(("failure_class", "expected"), [
    ("action_block", "several hours"),
    ("challenge", "complete the account verification"),
    ("auth_expired", "re-import the session"),
    ("ledger_unavailable", "account safety ledger"),
    ("unknown", "Resolve the account issue"),
])
def test_the_recovery_hint_matches_the_failure_class(ledger, failure_class, expected):
    hint = im.breaker_recovery_hint(failure_class)
    assert expected in hint
    assert "restart" in hint.lower()
    assert "--clear-breaker" not in hint


def test_a_stopped_target_is_told_how_to_recover_from_an_expired_session(ledger, capsys):
    im.note_instagram_failure("401 Unauthorized", "target")
    im.fetch_usernames_paginated(None, lambda: _names(5), 0, 0, 0, False, 5, "target")
    output = capsys.readouterr().out
    assert "auth_expired" in output
    assert "re-import the session" in output
    assert "clear the challenge" not in output


def test_breaker_is_cleared_explicitly(ledger):
    im.note_instagram_failure("challenge_required", "target")
    assert im.circuit_breaker_tripped() is True
    cleared = im.clear_circuit_breaker()
    assert cleared is not None and cleared["failure_class"] == "challenge"
    assert im.circuit_breaker_tripped() is False
    assert im.clear_circuit_breaker() is None


def test_disabling_the_breaker_leaves_fetching_alone(ledger, monkeypatch):
    monkeypatch.setattr(im, "CIRCUIT_BREAKER", False, raising=False)
    im.note_instagram_failure("checkpoint_required", "target")
    assert im.circuit_breaker_tripped() is False
    result = im.fetch_usernames_paginated(None, lambda: _names(5), 0, 0, 0, False, 5, "target")
    assert len(result) == 5


def test_mid_fetch_failure_banks_returned_names_before_propagating(ledger):
    def exploding():
        yield _FakeUser("a")
        yield _FakeUser("b")
        raise RuntimeError("400 Bad Request - challenge_required")

    with pytest.raises(RuntimeError):
        im.fetch_usernames_paginated(None, exploding, 0, 0, 0, False, 10, "target")

    # The two names Instagram already returned still cost the account
    assert im.exposure_snapshot()["identities"] == 2
    assert im.circuit_breaker_tripped() is True


# Counts durable ledger writes so a per-name source can be shown to bank names in groups
@pytest.fixture
def ledger_writes(monkeypatch):
    writes = []
    real_write = im._write_exposure_file
    monkeypatch.setattr(im, "_write_exposure_file", lambda data: (writes.append(1), real_write(data)), raising=False)
    return writes


class TestGraphqlNamesAreBankedInGroups:
    def test_a_full_list_costs_one_write_per_group_and_is_counted_exactly(self, ledger, ledger_writes):
        names = list(im._iter_accounted_follow_list(_names(60)))

        assert len(names) == 60
        assert im.exposure_snapshot()["identities"] == 60
        assert len(ledger_writes) == 3

    def test_a_partial_group_is_banked_when_the_source_ends(self, ledger, ledger_writes):
        list(im._iter_accounted_follow_list(_names(7)))

        assert im.exposure_snapshot()["identities"] == 7
        assert len(ledger_writes) == 1

    def test_names_before_a_failure_are_banked_before_it_propagates(self, ledger):
        def exploding():
            yield _FakeUser("a")
            yield _FakeUser("b")
            raise RuntimeError("HTTP error code 500.")

        with pytest.raises(RuntimeError):
            list(im._iter_accounted_follow_list(exploding()))

        assert im.exposure_snapshot()["identities"] == 2

    def test_an_abandoned_source_banks_what_it_yielded(self, ledger):
        source = im._iter_accounted_follow_list(_names(40))
        for _ in range(30):
            next(source)
        source.close()

        assert im.exposure_snapshot()["identities"] == 30

    # The group shrinks to the remaining budget, so the fetch loop reads an exact total at the moment it stops
    def test_the_budget_is_exact_where_the_fetch_stops(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 30, raising=False)
        result = im.fetch_usernames_paginated(None, lambda: im._iter_accounted_follow_list(_names(100)), 0, 0, 0, False, 30, "target", identities_counted_at_source=True)

        assert len(result) == 30
        assert result.complete is False
        assert im.exposure_snapshot()["identities"] == 30

    def test_a_ledger_that_dies_mid_group_stops_the_account_without_hiding_the_instagram_error(self, ledger, monkeypatch):
        def exploding():
            yield _FakeUser("a")
            raise RuntimeError("HTTP error code 500.")

        source = im._iter_accounted_follow_list(exploding())
        next(source)
        monkeypatch.setattr(im, "_write_exposure_file", lambda data: (_ for _ in ()).throw(im.ExposureLedgerError("write rejected")), raising=False)

        with pytest.raises(RuntimeError):
            next(source)
        memory_state = im._account_breaker_memory_state()

        assert memory_state is not None and memory_state["failure_class"] == "ledger_unavailable"


def test_ledger_survives_a_restart(ledger):
    im.fetch_usernames_paginated(None, lambda: _names(7), 0, 0, 0, False, 7, "target")
    im.note_instagram_failure("429 Too Many Requests", "target")
    # A fresh read is what a restarted process would do
    reread = im.exposure_snapshot()
    assert reread["identities"] == 7
    assert reread["failures"]["rate_limit"] == 1


def test_daily_counters_roll_over(ledger, monkeypatch):
    im.fetch_usernames_paginated(None, lambda: _names(9), 0, 0, 0, False, 9, "target")
    assert im.exposure_snapshot()["identities"] == 9
    monkeypatch.setattr(im, "_exposure_today", lambda: "2099-01-01", raising=False)
    assert im.exposure_snapshot()["identities"] == 0


def test_breaker_survives_the_daily_rollover(ledger, monkeypatch):
    im.note_instagram_failure("checkpoint_required", "target")
    monkeypatch.setattr(im, "_exposure_today", lambda: "2099-01-01", raising=False)
    assert im.circuit_breaker_tripped() is True


def test_each_account_has_its_own_ledger(ledger, monkeypatch):
    im.fetch_usernames_paginated(None, lambda: _names(12), 0, 0, 0, False, 12, "target")
    monkeypatch.setattr(im, "SESSION_USERNAME", "otheracct", raising=False)
    assert im.exposure_snapshot()["identities"] == 0
    monkeypatch.setattr(im, "SESSION_USERNAME", "testacct", raising=False)
    assert im.exposure_snapshot()["identities"] == 12


def test_anonymous_mode_uses_its_own_ledger_key(ledger, monkeypatch):
    monkeypatch.setattr(im, "SKIP_SESSION", True, raising=False)
    assert im.exposure_account_name() == "<anonymous>"


def test_exposure_summary_reports_state(ledger, tmp_path):
    im.fetch_usernames_paginated(None, lambda: _names(3), 0, 0, 0, False, 3, "target")
    im.note_instagram_failure("429 Too Many Requests", "target")
    text = "\n".join(im.exposure_summary_lines())
    assert "testacct" not in text
    assert "account redacted" in text
    assert f"Version:\t\t\t\t{im.VERSION}" in text
    assert "HTTP backend:" in text
    assert "Follow list source:" in text
    assert str(tmp_path) not in text
    assert "3" in text
    assert "rate_limit" in text
    assert "armed" in text

    im.note_instagram_failure("checkpoint_required", "target")
    tripped_text = "\n".join(im.exposure_summary_lines())
    assert "TRIPPED" in tripped_text
    assert "Restart or re-import" in tripped_text
    assert "testacct" not in tripped_text
    assert "checkpoint_required" not in tripped_text


def test_ledger_is_written_under_the_output_directory(ledger, tmp_path):
    im.fetch_usernames_paginated(None, lambda: _names(1), 0, 0, 0, False, 1, "target")
    assert im.exposure_state_path() == str(tmp_path / "instagram_monitor_exposure.json")
    assert (tmp_path / "instagram_monitor_exposure.json").is_file()


def test_a_corrupt_ledger_blocks_identity_fetching(ledger, tmp_path):
    (tmp_path / "instagram_monitor_exposure.json").write_text("{ not json", encoding="utf-8")
    generator_started = False

    # Records whether an identity source was opened despite an unreadable safety ledger
    def names():
        nonlocal generator_started
        generator_started = True
        return _names(4)

    with pytest.raises(im.ExposureLedgerError):
        im.exposure_snapshot()
    result = im.fetch_usernames_paginated(None, names, 0, 0, 0, False, 4, "target")
    memory_state = im._account_breaker_memory_state()

    assert result == []
    assert generator_started is False
    assert memory_state is not None and memory_state["failure_class"] == "ledger_unavailable"


def test_an_unwritable_ledger_blocks_identity_fetching(ledger, monkeypatch):
    generator_started = False

    # Simulates a durable write failure without opening an identity source
    def reject_write(_data):
        raise im.ExposureLedgerError("write rejected")

    # Records whether an identity source was opened after the ledger preflight failed
    def names():
        nonlocal generator_started
        generator_started = True
        return _names(4)

    monkeypatch.setattr(im, "_write_exposure_file", reject_write, raising=False)
    result = im.fetch_usernames_paginated(None, names, 0, 0, 0, False, 4, "target")
    memory_state = im._account_breaker_memory_state()

    assert result == []
    assert generator_started is False
    assert memory_state is not None and memory_state["failure_class"] == "ledger_unavailable"


def test_a_ledger_that_dies_mid_scan_stops_the_account(ledger, monkeypatch):
    reads = {'count': 0}

    # Answers the first few budget reads then fails, standing in for a ledger that dies during a scan
    def failing_remaining():
        reads['count'] += 1
        if reads['count'] > 3:
            raise im.ExposureLedgerError("read rejected")
        return 100

    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 100, raising=False)
    monkeypatch.setattr(im, "identity_budget_remaining", failing_remaining, raising=False)

    result = im.fetch_usernames_paginated(None, lambda: _names(6), 2, 0, 0, True, 6, "target")
    memory_state = im._account_breaker_memory_state()

    assert list(result) == ["user0", "user1"]
    assert result.complete is False
    assert memory_state is not None and memory_state["failure_class"] == "ledger_unavailable"


def test_an_unreadable_ledger_still_reports_the_breaker(ledger, monkeypatch):
    im.note_instagram_failure("checkpoint_required", "target")

    # Simulates the ledger becoming unreadable after the account was already stopped
    def reject_read():
        raise im.ExposureLedgerError("read rejected")

    monkeypatch.setattr(im, "_load_exposure_file", reject_read, raising=False)
    text = "\n".join(im.exposure_summary_lines())

    assert "Account safety ledger:" in text and "unavailable" in text
    assert "Circuit breaker:" in text and "TRIPPED" in text


def test_every_report_row_shares_one_value_column(ledger):
    for message in ("429 Too Many Requests", "could not resolve proxy", "unexpected follower list reply", "checkpoint_required"):
        im.note_instagram_failure(message, "target")

    columns = set()
    for line in im.exposure_summary_lines():
        label, _, value = line.partition(':')
        columns.add((len(label + ':') // 8 + len(value) - len(value.lstrip('\t'))) * 8)

    assert columns == {40}


def test_clear_breaker_reports_an_unwritable_ledger(ledger, monkeypatch, capsys, tmp_path):
    # Simulates a ledger that cannot be saved, which is exactly when the tool tells the user to clear the stop
    def reject_clear():
        raise im.ExposureLedgerError("The account safety ledger cannot be saved: PermissionError")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(im.sys, "argv", ["instagram_monitor.py", "--clear-breaker"])
    monkeypatch.setattr(im, "CLI_CONFIG_PATH", None, raising=False)
    monkeypatch.setattr(im, "find_config_file", lambda path=None: None, raising=False)
    monkeypatch.setattr(im, "clear_screen", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(im, "clear_circuit_breaker", reject_clear, raising=False)

    with pytest.raises(SystemExit) as raised:
        im.run_main()
    output = capsys.readouterr().out

    assert raised.value.code == 1
    assert "cannot be saved" in output
    assert "To fix: Restore write access" in output
    assert "Traceback" not in output


def test_clear_breaker_recovers_a_corrupt_ledger(ledger, tmp_path):
    (tmp_path / "instagram_monitor_exposure.json").write_text("{ not json", encoding="utf-8")
    breaker_state = im.circuit_breaker_state()
    assert breaker_state is not None and breaker_state["failure_class"] == "ledger_unavailable"

    cleared = im.clear_circuit_breaker()

    assert cleared is not None and cleared["failure_class"] == "ledger_unavailable"
    assert im.circuit_breaker_tripped() is False
    assert im.exposure_snapshot()["identities"] == 0


# A corrupt file found by --clear-breaker itself is still reported as the state that was removed, never as nothing to clear
def test_clear_breaker_names_a_corrupt_ledger_it_replaced(ledger, tmp_path, monkeypatch, capsys):
    (tmp_path / "instagram_monitor_exposure.json").write_text("{ not json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(im.sys, "argv", ["instagram_monitor.py", "--clear-breaker", "--no-color"])
    monkeypatch.setattr(im, "CLI_CONFIG_PATH", None, raising=False)
    monkeypatch.setattr(im, "find_config_file", lambda path=None: None, raising=False)
    monkeypatch.setattr(im, "clear_screen", lambda *args, **kwargs: None, raising=False)

    with pytest.raises(SystemExit) as raised:
        im.run_main()
    output = capsys.readouterr().out

    assert raised.value.code == 0
    assert "could not be used (The account safety ledger cannot be read: JSONDecodeError) and was replaced with a fresh one" in output
    assert "nothing to clear" not in output
    assert im.exposure_snapshot()["identities"] == 0


# The pasteable report keeps the path out, so the reason the ledger is unusable is printed under it
def test_exposure_report_says_why_the_ledger_is_unusable(ledger, tmp_path, monkeypatch, capsys):
    (tmp_path / "instagram_monitor_exposure.json").write_text("[1, 2]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(im.sys, "argv", ["instagram_monitor.py", "--exposure", "--no-color"])
    monkeypatch.setattr(im, "CLI_CONFIG_PATH", None, raising=False)
    monkeypatch.setattr(im, "find_config_file", lambda path=None: None, raising=False)
    monkeypatch.setattr(im, "clear_screen", lambda *args, **kwargs: None, raising=False)

    with pytest.raises(SystemExit):
        im.run_main()
    output = capsys.readouterr().out

    assert "Account safety ledger:" in output
    assert "* Error: The account safety ledger has an invalid structure" in output
    assert f"* Ledger path: {tmp_path / 'instagram_monitor_exposure.json'}" in output
    assert "To fix: Repair the file or restore access, then restart" in output


# A report pasted into an issue has to say whether impersonation actually ran, not only which backend was set
def test_exposure_summary_names_the_transport_fallback(ledger, monkeypatch, capsys):
    monkeypatch.setattr(im, "HTTP_BACKEND", "curl_cffi", raising=False)
    monkeypatch.setattr(im, "_CURL_CFFI_AVAILABLE", False, raising=False)
    monkeypatch.setattr(im, "_CURL_CFFI_UNAVAILABLE_WARNED", False, raising=False)

    backend = _backend_line()

    assert "requests" in backend and "not installed" in backend
    # Building the report must not print into the report
    assert capsys.readouterr().out == ""


# A deliberate stock transport is a different report from an impersonation that never happened
def test_exposure_summary_reports_a_chosen_requests_backend_plainly(ledger, monkeypatch):
    monkeypatch.setattr(im, "HTTP_BACKEND", "requests", raising=False)

    backend = _backend_line()

    assert backend.endswith("requests")
    assert "not installed" not in backend


# Auto is a setting, so the report has to name the browser the handshake actually presents
def test_exposure_summary_resolves_the_impersonation_target(ledger, monkeypatch):
    monkeypatch.setattr(im, "HTTP_BACKEND", "curl_cffi", raising=False)
    monkeypatch.setattr(im, "_CURL_CFFI_AVAILABLE", True, raising=False)
    monkeypatch.setattr(im, "CURL_CFFI_IMPERSONATE", "auto", raising=False)
    monkeypatch.setattr(im, "USER_AGENT", "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0", raising=False)

    assert "curl_cffi (impersonate: auto -> firefox)" in _backend_line()


# Returns the HTTP backend row of the exposure report
def _backend_line() -> str:
    return next(line for line in im.exposure_summary_lines() if line.startswith("HTTP backend")).expandtabs(40).strip()


class TestEveryAuthenticatedFailureReachesTheBreaker:
    # The flag check is the entry point every monitoring path already used, so recording has to happen there
    # rather than only inside the follow list fetch, which is the one place that called the classifier
    def test_an_expired_session_outside_the_list_fetch_arms_the_breaker(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "profile_from_username_resilient", _raises("LoginRequiredException: login_required"), raising=False)

        flagged = im.note_authenticated_failure("LoginRequiredException: login_required", "target", object())

        assert flagged is False
        assert im.circuit_breaker_tripped() is True
        assert im.exposure_snapshot()["failures"] == {"auth_expired": 1}

    # A session that still signs in means one mislabelled request, so the run continues and nothing is stopped
    def test_an_expired_session_the_probe_disproves_leaves_the_breaker_armed(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "profile_from_username_resilient", lambda bot, username: object(), raising=False)

        assert im.note_authenticated_failure("LoginRequiredException: login_required", "target", object()) is False
        assert im.circuit_breaker_tripped() is False

    # A challenge is reported as a flag, and left to the flagged session handler to record, so one challenge
    # arriving on one request is not counted twice in the ledger
    def test_a_challenge_is_reported_as_flagged_and_recorded_once(self, ledger):
        assert im.note_authenticated_failure("400 Bad Request - checkpoint_required", "target", object()) is True
        assert im.exposure_snapshot()["failures"] == {}

        im.notify_session_flagged("target", "flagged", "400 Bad Request - checkpoint_required")

        assert im.exposure_snapshot()["failures"] == {"challenge": 1}
        assert im.circuit_breaker_tripped() is True

    # A target that only looks gone because the session is flagged reads as a flag, not as a missing target
    def test_a_target_missing_only_because_the_session_is_flagged_is_reported_as_flagged(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "profile_from_username_resilient", _raises("ProfileNotExistsException: instagram missing"), raising=False)

        assert im.note_authenticated_failure("ProfileNotExistsException: target gone", "target", object()) is True
        assert im.exposure_snapshot()["failures"] == {}

    # A target that is genuinely gone says nothing about the account, so monitoring the others continues
    def test_a_genuinely_missing_target_leaves_the_account_alone(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "profile_from_username_resilient", lambda bot, username: object(), raising=False)

        assert im.note_authenticated_failure("ProfileNotExistsException: target gone", "target", object()) is False
        assert im.circuit_breaker_tripped() is False
        assert im.exposure_snapshot()["failures"] == {"target_unavailable": 1}

    # A transient fault is counted for the report but never stops the account
    def test_a_network_fault_is_counted_without_stopping_the_account(self, ledger):
        assert im.note_authenticated_failure("ConnectionError: timed out", "target", object()) is False
        assert im.circuit_breaker_tripped() is False
        assert im.exposure_snapshot()["failures"] == {"network": 1}

    # The flag triggers and the failure classifier are two tables naming one condition, so they have to agree
    @pytest.mark.parametrize("trigger", ["detected automated checks", "checkpoint_required", "challenge_required", "feedback_required"])
    def test_every_flag_trigger_is_classified_as_an_account_failure(self, ledger, trigger):
        assert im.is_session_flagged(trigger, object()) is True
        assert im.is_account_level_failure(im.classify_failure_class(trigger)) is True


# A ledger edited by hand or left half written by a full disk holds values no reader can trust. Every one of
# them has to stop the account rather than grant it budget, and none may escape as an error the caller does not expect
class TestAStoredLedgerValueNoReaderCanTrust:
    # Writes one hand-edited ledger payload for the test account and returns nothing
    @staticmethod
    def _write(tmp_path, record, extra=None):
        payload = {'version': im.EXPOSURE_STATE_VERSION, 'accounts': {'testacct': record}}
        payload.update(extra or {})
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps(payload), encoding="utf-8")

    # Returns a record that every reader accepts, so each test changes exactly one field
    @staticmethod
    def _healthy():
        return {'date': im._exposure_today(), 'identities': 3, 'failures': {'rate_limit': 1}, 'breaker': None}

    @pytest.mark.parametrize(("field", "value", "expected"), [
        ('identities', -50, "identities"),
        ('identities', "unknown", "identities"),
        ('identities', 2.5, "identities"),
        ('identities', True, "identities"),
        ('failures', ["challenge"], "failures"),
        ('failures', {'challenge': "many"}, "failures.challenge"),
        ('failures', {'challenge': -1}, "failures.challenge"),
        ('breaker', "tripped", "breaker"),
        ('breaker', {'failure_class': "challenge"}, "breaker.tripped_ts"),
        ('breaker', {'tripped_ts': 0, 'failure_class': "challenge"}, "breaker.tripped_ts"),
        ('date', 20990101, "date"),
        ('last_account_failure', "yesterday", "last_account_failure"),
        ('last_account_failure', {'ts': "yesterday"}, "last_account_failure.ts"),
        ('last_account_failure', {'ts': True}, "last_account_failure.ts"),
        ('last_account_failure', {'ts': 10 ** 30}, "last_account_failure.ts"),
        ('breaker', {'tripped_ts': 10 ** 30}, "breaker.tripped_ts"),
    ])
    def test_the_error_names_the_field_and_the_repair(self, ledger, tmp_path, field, value, expected):
        record = self._healthy()
        record[field] = value
        self._write(tmp_path, record)

        with pytest.raises(im.ExposureLedgerError) as raised:
            im.exposure_snapshot()

        assert f"'{expected}' field" in str(raised.value)
        assert "fresh ledger" in str(raised.value)

    # A count below zero used to buy budget back, reporting more names left than the daily limit allows
    def test_a_negative_count_stops_the_account_instead_of_granting_budget(self, ledger, tmp_path, monkeypatch):
        monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 10, raising=False)
        record = self._healthy()
        record['identities'] = -50
        self._write(tmp_path, record)

        result = im.fetch_usernames_paginated(None, lambda: _names(4), 0, 0, 0, False, 4, "target")
        memory_state = im._account_breaker_memory_state()

        assert result == []
        assert memory_state is not None and memory_state["failure_class"] == "ledger_unavailable"

    # A breaker stored as anything but a stop record read as untripped, so a stopped account resumed on its own
    def test_a_breaker_that_is_not_a_stop_record_keeps_the_account_stopped(self, ledger, tmp_path):
        record = self._healthy()
        record['breaker'] = "tripped"
        self._write(tmp_path, record)

        assert im.circuit_breaker_tripped() is True

    # The report documents a recovery path for an unusable ledger, so it must take it rather than raise
    def test_the_report_recovers_instead_of_raising(self, ledger, tmp_path):
        record = self._healthy()
        record['identities'] = "unknown"
        self._write(tmp_path, record)

        text = "\n".join(im.exposure_summary_lines())

        assert "Account safety ledger:" in text
        assert "unavailable" in text
        assert "Identities returned today" not in text

    # A record for another account is part of the same file, and one run rewrites all of them
    def test_another_account_with_a_bad_record_is_not_written_back(self, ledger, tmp_path):
        self._write(tmp_path, self._healthy(), extra={'accounts': {'testacct': self._healthy(), 'otheracct': {'identities': -1}}})

        with pytest.raises(im.ExposureLedgerError):
            im.exposure_snapshot()

    # Validation must reject what readers rely on without turning the file into a closed schema
    def test_fields_this_version_does_not_know_survive_a_write(self, ledger, tmp_path):
        record = self._healthy()
        record['future_field'] = {'kept': True}
        self._write(tmp_path, record, extra={'future_top': 7})

        im.record_identities_returned(2)
        written = json.loads((tmp_path / "instagram_monitor_exposure.json").read_text(encoding="utf-8"))

        assert written['accounts']['testacct']['future_field'] == {'kept': True}
        assert written['future_top'] == 7
        assert written['accounts']['testacct']['identities'] == 5


class TestAnAccountScopedCommandActsOnTheAccountTheUserNamed:
    """--clear-breaker and --exposure exit before the command line's session account has been applied.

    Both read the safety record of whatever the configuration named, or of the anonymous key when no
    configuration was loaded, so a run told the user nothing was tripped while the named account stayed
    stopped. The ledger itself was always correct, and so was every helper it went through.
    """

    # Trips the breaker for one account, then runs one one-shot command through the real command line
    @staticmethod
    def _run(monkeypatch, capsys, action, argv=(), account="chosen.account", connected=True):
        monkeypatch.setattr(im, "SESSION_USERNAME", account, raising=False)
        monkeypatch.setattr(im, "SKIP_SESSION", False, raising=False)
        monkeypatch.setattr(im, "CIRCUIT_BREAKER", True, raising=False)
        monkeypatch.setattr(im, "log_activity", lambda *args, **kwargs: None, raising=False)
        im.record_failure_event("challenge", "target", "400 checkpoint_required")
        assert im.circuit_breaker_tripped() is True
        monkeypatch.setattr(im, "SESSION_USERNAME", "", raising=False)
        monkeypatch.setattr(im, "check_internet", lambda *args, **kwargs: connected, raising=False)
        monkeypatch.setattr(im, "clear_screen", lambda *args, **kwargs: None, raising=False)
        monkeypatch.setattr(im.sys, "argv", ["instagram_monitor.py", "--config-file", "none", "--env-file", "none", "--no-color", action, *argv])
        capsys.readouterr()
        with pytest.raises(SystemExit) as exit_call:
            im.run_main()
        monkeypatch.setattr(im, "SESSION_USERNAME", account, raising=False)
        monkeypatch.setattr(im, "SKIP_SESSION", False, raising=False)
        return exit_call.value.code, capsys.readouterr().out

    # Naming the account on the command line has to reach the record the command clears
    def test_clear_breaker_clears_the_account_named_on_the_command_line(self, monkeypatch, capsys):
        code, output = self._run(monkeypatch, capsys, "--clear-breaker", ("--session-username", "chosen.account"))

        assert code == 0
        assert "Circuit breaker cleared for chosen.account" in output
        assert im.circuit_breaker_tripped() is False

    # Without the account there is nothing to act on, so the stop stays in place rather than being cleared blindly
    def test_clear_breaker_without_an_account_leaves_the_record_alone(self, monkeypatch, capsys):
        code, output = self._run(monkeypatch, capsys, "--clear-breaker")

        assert code == 0
        assert "not tripped for <anonymous>" in output
        assert im.circuit_breaker_tripped() is True

    # The report is the other half of the same promise, so it has to describe the same account
    def test_the_exposure_report_describes_the_account_named_on_the_command_line(self, monkeypatch, capsys):
        code, output = self._run(monkeypatch, capsys, "--exposure", ("--session-username", "chosen.account"))

        assert code == 0
        assert "TRIPPED" in output
        assert "challenge" in output
        # The report omits account names on purpose, so the mode is what says an account was resolved at all
        assert "authenticated" in output

    # An account asked to run without a session is anonymous, whatever the configuration named
    def test_skipping_the_session_reports_the_anonymous_record(self, monkeypatch, capsys):
        code, output = self._run(monkeypatch, capsys, "--exposure", ("--session-username", "chosen.account", "--skip-session"))

        assert code == 0
        assert "Session mode:" in output and "anonymous" in output
        assert "TRIPPED" not in output

    # The account is stopped and the connection is down, which is exactly when the reset is reached for
    def test_clear_breaker_works_with_no_connection(self, monkeypatch, capsys):
        code, output = self._run(monkeypatch, capsys, "--clear-breaker", ("--session-username", "chosen.account"), connected=False)

        assert code == 0
        assert "Circuit breaker cleared for chosen.account" in output
        assert im.circuit_breaker_tripped() is False

    # The report reads local state only, so an outage is no reason to refuse to print it
    def test_the_exposure_report_works_with_no_connection(self, monkeypatch, capsys):
        code, output = self._run(monkeypatch, capsys, "--exposure", ("--session-username", "chosen.account"), connected=False)

        assert code == 0
        assert "TRIPPED" in output


# Records eager iterator failures even when no name has been yielded
def test_iterator_construction_failure_is_recorded_once(ledger):
    failure = im.instaloader.exceptions.TooManyRequestsException("429 Too Many Requests")

    # Fails while constructing the source rather than while consuming it
    def construct():
        raise failure

    with pytest.raises(im.instaloader.exceptions.TooManyRequestsException):
        im.fetch_usernames_paginated(None, construct, 0, 0, 0, False, 1, "target")
    assert im.exposure_snapshot()["failures"] == {"rate_limit": 1}


# A scan that cannot finish would spend the whole remaining budget on a list that is discarded as
# incomplete, and would repeat that every day, so the reported count has to gate whether it starts
def test_a_scan_that_cannot_finish_is_never_started(ledger, monkeypatch, capsys):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 100, raising=False)

    result = im.fetch_usernames_paginated(None, lambda: _names(500), 0, 0, 0, False, 500, "target")

    assert len(result) == 0
    assert result.complete is False
    assert im.exposure_snapshot()["identities"] == 0, "no identity may be spent on a scan that cannot complete"
    assert "500 names are needed but only 100" in capsys.readouterr().out


# The guard measures what is left today, not the configured total, so an earlier scan narrows it
def test_the_guard_uses_the_remaining_budget_not_the_total(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 100, raising=False)
    im.fetch_usernames_paginated(None, lambda: _names(60), 0, 0, 0, False, 60, "target")

    result = im.fetch_usernames_paginated(None, lambda: _names(50), 0, 0, 0, False, 50, "target")

    assert len(result) == 0
    assert im.exposure_snapshot()["identities"] == 60


# A scan that fits has to run untouched, which is the whole point of picking a budget above normal use
def test_a_scan_that_fits_runs_in_full(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 2000, raising=False)

    result = im.fetch_usernames_paginated(None, lambda: _names(807), 0, 0, 0, False, 807, "target")

    assert len(result) == 807
    assert result.complete is True
    assert im.is_complete_username_baseline(result, 807) is True


# An unknown count cannot be checked ahead of time, so the scan still runs and the mid-scan cap covers it
def test_an_unknown_count_still_runs(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 40, raising=False)

    result = im.fetch_usernames_paginated(None, lambda: _names(100), 0, 0, 0, False, 0, "target")

    assert len(result) == 40
    assert result.complete is False


# The budget is off by configuration, so no scan may be gated on it
def test_no_budget_never_blocks_a_scan(ledger, monkeypatch):
    monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 0, raising=False)

    result = im.fetch_usernames_paginated(None, lambda: _names(5000), 0, 0, 0, False, 5000, "target")

    assert len(result) == 5000
    assert result.complete is True


# The shipped default has to clear one full scan of a normal account rather than stop it
def test_the_default_budget_clears_a_typical_account():
    assert im.IDENTITY_BUDGET_PER_DAY >= 1600, "the default must clear followers and followings of a typical account"


# Returns one labelled row of the exposure report with its padding removed
def _report_row(label: str) -> str:
    return next(line for line in im.exposure_summary_lines() if line.startswith(f"{label}:")).expandtabs(40).split(":", 1)[1].strip()


# Runs --exposure the way the command line does and returns its exit code with the printed report
def _run_exposure_command(monkeypatch, capsys, directory):
    monkeypatch.chdir(directory)
    monkeypatch.setattr(im.sys, "argv", ["instagram_monitor.py", "--exposure", "--no-color"])
    monkeypatch.setattr(im, "CLI_CONFIG_PATH", None, raising=False)
    monkeypatch.setattr(im, "find_config_file", lambda path=None: None, raising=False)
    monkeypatch.setattr(im, "clear_screen", lambda *args, **kwargs: None, raising=False)
    with pytest.raises(SystemExit) as raised:
        im.run_main()
    return raised.value.code, capsys.readouterr().out


class TestExposureLedgerWritability:
    # The report reads the ledger while monitoring writes it, so a file this user cannot save reads as healthy
    def test_an_unwritable_ledger_is_not_reported_as_healthy(self, ledger, tmp_path, monkeypatch):
        path = tmp_path / "instagram_monitor_exposure.json"
        path.write_text(json.dumps({'version': 1, 'accounts': {}}), encoding="utf-8")
        monkeypatch.setattr(im.os, "access", lambda target, mode: False if str(target) == str(path) else True)

        assert "NOT writable" in _report_row("Account safety ledger")

    # The file is replaced through a temporary file in its own directory, so the directory decides, not the file
    def test_a_writable_file_in_an_unwritable_directory_cannot_be_saved(self, ledger, tmp_path, monkeypatch):
        path = tmp_path / "instagram_monitor_exposure.json"
        path.write_text(json.dumps({'version': 1, 'accounts': {}}), encoding="utf-8")
        monkeypatch.setattr(im.os, "access", lambda target, mode: str(target) != str(tmp_path))

        assert im.exposure_ledger_is_writable() is False
        assert "NOT writable" in _report_row("Account safety ledger")

    # A report that cannot be acted on is not a successful command
    def test_the_command_fails_when_the_ledger_cannot_be_saved(self, ledger, tmp_path, monkeypatch, capsys):
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': {}}), encoding="utf-8")
        monkeypatch.setattr(im, "exposure_ledger_is_writable", lambda: False, raising=False)

        code, output = _run_exposure_command(monkeypatch, capsys, tmp_path)

        assert code == 1
        assert "* Error: The account safety ledger cannot be saved" in output
        assert "To fix: Restore write access to that path" in output


class TestExposureLedgerPresence:
    # Nothing recorded and a healthy day print the same counters, so the report has to say which it is
    def test_a_missing_ledger_is_reported_as_not_created_yet(self, ledger):
        assert _report_row("Account safety ledger").startswith("not created yet")

    def test_an_existing_ledger_is_reported_as_in_use(self, ledger, tmp_path):
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': {}}), encoding="utf-8")

        assert _report_row("Account safety ledger").startswith("in use")

    # The path was printed only on failure, so a healthy report never said which file it had read
    def test_the_ledger_path_is_printed_when_nothing_is_wrong(self, ledger, tmp_path, monkeypatch, capsys):
        code, output = _run_exposure_command(monkeypatch, capsys, tmp_path)

        assert code == 0
        assert f"* Ledger path: {tmp_path / 'instagram_monitor_exposure.json'}" in output
        assert "* Error:" not in output


class TestExposureBreakerSetting:
    # A stop outlives the setting that made it, so reporting the stored record verbatim contradicts the setting
    def test_a_stored_stop_is_not_reported_as_enforced_when_the_breaker_is_off(self, ledger, tmp_path, monkeypatch):
        monkeypatch.setattr(im, "CIRCUIT_BREAKER", False, raising=False)
        record = {'date': im._exposure_today(), 'identities': 0, 'failures': {}, 'breaker': {'tripped_ts': 1758000000, 'failure_class': 'action_block'}}
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': {'testacct': record}}), encoding="utf-8")

        row = _report_row("Circuit breaker")

        assert row.startswith("disabled")
        assert "TRIPPED" not in row
        assert "kept but not enforced" in row

    def test_a_disabled_breaker_with_no_stop_reads_as_disabled(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "CIRCUIT_BREAKER", False, raising=False)

        assert _report_row("Circuit breaker") == "disabled"

    # Every target sharing the account stops with it, and the report never said so
    def test_a_tripped_breaker_says_the_targets_are_paused(self, ledger, tmp_path):
        record = {'date': im._exposure_today(), 'identities': 0, 'failures': {}, 'breaker': {'tripped_ts': 1758000000, 'failure_class': 'action_block'}}
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': {'testacct': record}}), encoding="utf-8")

        assert _report_row("Monitored targets") == "every target using this account is paused"

    def test_the_paused_target_count_is_reported_when_it_is_known(self, ledger, tmp_path, monkeypatch):
        monkeypatch.setattr(im, "ACCOUNT_PAUSED_TARGETS", {"testacct": {"one", "two"}}, raising=False)
        record = {'date': im._exposure_today(), 'identities': 0, 'failures': {}, 'breaker': {'tripped_ts': 1758000000, 'failure_class': 'action_block'}}
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': {'testacct': record}}), encoding="utf-8")

        assert _report_row("Monitored targets") == "2 paused"


class TestExposureOtherAccounts:
    # One ledger holds every account that shares the output directory, and a stop on any of them is worth knowing
    def test_other_accounts_are_counted_without_being_named(self, ledger, tmp_path):
        today = im._exposure_today()
        accounts = {
            'testacct': {'date': today, 'identities': 0, 'failures': {}, 'breaker': None},
            'other_one': {'date': today, 'identities': 4, 'failures': {}, 'breaker': {'tripped_ts': 1758000000, 'failure_class': 'challenge'}},
            'other_two': {'date': today, 'identities': 2, 'failures': {}, 'breaker': None},
        }
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': accounts}), encoding="utf-8")

        row = _report_row("Other accounts in this ledger")

        assert row == "2 (1 stopped)"
        assert "other_one" not in "\n".join(im.exposure_summary_lines())

    def test_a_ledger_with_only_this_account_reports_none(self, ledger, tmp_path):
        record = {'date': im._exposure_today(), 'identities': 0, 'failures': {}, 'breaker': None}
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': {'testacct': record}}), encoding="utf-8")

        assert _report_row("Other accounts in this ledger") == "none"


class TestExposureRecordErrors:
    # One bad record stops every account in the file, so the reader has to be told which one to repair
    def test_an_invalid_record_names_the_account_it_belongs_to(self, ledger, tmp_path):
        today = im._exposure_today()
        accounts = {
            'testacct': {'date': today, 'identities': 0, 'failures': {}, 'breaker': None},
            'other_one': {'date': today, 'identities': -5, 'failures': {}, 'breaker': None},
        }
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': accounts}), encoding="utf-8")

        with pytest.raises(im.ExposureLedgerError) as raised:
            im.exposure_snapshot()

        assert "'identities' field for account 'other_one'" in str(raised.value)


class TestExposureBudgetRow:
    # A raw count answers neither how much is left nor how long the wait is
    def test_the_budget_row_says_how_much_is_left_and_when_it_resets(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "IDENTITY_BUDGET_PER_DAY", 2000, raising=False)
        im.record_identities_returned(150)

        assert _report_row("Identities returned today") == "150 of 2000 (1850 left), resets at local midnight"

    def test_no_budget_still_says_when_the_count_resets(self, ledger):
        im.record_identities_returned(10)

        assert _report_row("Identities returned today") == "10 (no budget set), resets at local midnight"


class TestExposureCrossProcessLock:
    # Two monitors sharing an output directory each read the same daily total and write back a count that lost the
    # other's identities, so a budget meant to cap the day is silently doubled
    def test_two_processes_do_not_lose_each_others_identities(self, tmp_path):
        import subprocess
        import sys

        root = im.os.path.dirname(im.__file__)
        worker = tmp_path / "worker.py"
        worker.write_text(
            "import sys\n"
            "root, directory = sys.argv[1], sys.argv[2]\n"
            "sys.path.insert(0, root)\n"
            "sys.argv = ['instagram_monitor.py']\n"
            "import instagram_monitor as im\n"
            "im.SESSION_USERNAME = 'testacct'\n"
            "im.SKIP_SESSION = False\n"
            "im.OUTPUT_DIR = directory\n"
            "for _ in range(4):\n"
            "    im.record_identities_returned(25)\n",
            encoding="utf-8",
        )
        workers = [subprocess.Popen([sys.executable, str(worker), root, str(tmp_path)]) for _ in range(3)]
        for process in workers:
            assert process.wait() == 0

        stored = json.loads((tmp_path / "instagram_monitor_exposure.json").read_text(encoding="utf-8"))

        assert stored['accounts']['testacct']['identities'] == 300

    # A machine that cannot provide a lock must still record, since the lock is protection and not a precondition
    def test_a_lock_that_cannot_be_taken_does_not_stop_the_write(self, ledger, monkeypatch):
        monkeypatch.setattr(im, "_acquire_exposure_file_lock", lambda timeout=0.0: None, raising=False)

        im.record_identities_returned(5)

        assert im.exposure_snapshot()["identities"] == 5

    # The lock is only taken while a cycle is in progress, so a second cycle in the same run must not block
    def test_the_lock_is_released_after_every_cycle(self, ledger):
        for _ in range(3):
            im.record_identities_returned(1)

        assert im.exposure_snapshot()["identities"] == 3


class TestExposureCommandExitCode:
    # An unusable ledger printed an error and still reported success, so a script could not tell the two apart
    def test_an_unusable_ledger_fails_the_command(self, ledger, tmp_path, monkeypatch, capsys):
        (tmp_path / "instagram_monitor_exposure.json").write_text("[1, 2]", encoding="utf-8")

        code, output = _run_exposure_command(monkeypatch, capsys, tmp_path)

        assert code == 1
        assert "* Error: The account safety ledger has an invalid structure" in output

    def test_a_healthy_ledger_succeeds(self, ledger, tmp_path, monkeypatch, capsys):
        (tmp_path / "instagram_monitor_exposure.json").write_text(json.dumps({'version': 1, 'accounts': {}}), encoding="utf-8")

        code, output = _run_exposure_command(monkeypatch, capsys, tmp_path)

        assert code == 0
        assert "* Error:" not in output
