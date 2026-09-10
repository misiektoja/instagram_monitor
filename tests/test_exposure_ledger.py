"""Offline tests for the identity exposure ledger, the daily budget and the account circuit breaker."""

import threading

import pytest

import instagram_monitor as im

# Captured before the autouse ledger-isolation fixture can patch it, so the path test can check the real derivation
_REAL_EXPOSURE_STATE_PATH = im.exposure_state_path


class _FakeUser:
    def __init__(self, username):
        self.username = username


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
    summary, _fix, _guide = im.classify_error_message(sample)
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
    result = im.fetch_usernames_paginated(None, lambda: _names(100), 0, 0, 0, False, 100, "target")
    assert len(result) == 10
    assert result.complete is False
    assert im.identity_budget_remaining() == 0
    # An incomplete result must never overwrite a good baseline
    assert im.is_complete_username_baseline(result, 100) is False


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


def test_transport_and_schema_failures_do_not_trip_the_breaker(ledger):
    im.note_instagram_failure("429 Too Many Requests", "target")
    im.note_instagram_failure("TypeError: 'NoneType' object is not subscriptable", "target")
    assert im.circuit_breaker_tripped() is False
    assert im.exposure_snapshot()["failures"] == {"rate_limit": 1, "schema_change": 1}


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
    assert "--clear-breaker" in tripped_text
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

    # Answers the first two budget reads then fails, standing in for a ledger that dies during a scan
    def failing_remaining():
        reads['count'] += 1
        if reads['count'] > 2:
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
