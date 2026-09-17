"""Offline account recovery checks using the real Instaloader request path."""

from concurrent.futures import ThreadPoolExecutor
import json
import sys
import threading
from types import SimpleNamespace

import pytest
import requests

import instagram_monitor as im


@pytest.fixture
# Supplies a saved account and intercepts requests after real client and request-wrapper setup
def account(monkeypatch, tmp_path):
    snapshot = {name: value for name, value in vars(im).items() if name.isupper()}
    settings = {"SESSION_USERNAME": "saved.account", "SKIP_SESSION": False, "CIRCUIT_BREAKER": True, "IDENTITY_BUDGET_PER_DAY": 0, "OUTPUT_DIR": str(tmp_path), "WEB_DASHBOARD_ENABLED": False, "COLORED_OUTPUT": False, "PROXY_ENABLED": False, "ENABLE_JITTER": True, "WEB_DASHBOARD_STOP_EVENTS": {}, "WEB_DASHBOARD_MONITOR_THREADS": {}, "WEB_DASHBOARD_DATA": {"targets": {}, "session": {}}, "ACCOUNT_BREAKER_MEMORY": {}, "ACCOUNT_RECOVERY_ATTEMPTED": set(), "ACCOUNT_PAUSED_TARGETS": {}}
    for name, value in settings.items():
        monkeypatch.setattr(im, name, value)
    monkeypatch.setattr(im, "log_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(im, "update_ui_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(im, "get_browser_cookie_dict", lambda *args, **kwargs: {"sessionid": "synthetic-cookie"})
    state = SimpleNamespace(calls=[], outcome="saved.account", saves=[], after_request=None)

    # Loads synthetic session identity without reading the machine's saved credentials
    def load(bot, username, filename=None):
        bot.context.username = username
        bot.context._session.cookies.set("sessionid", "synthetic-cookie")

    # Records the real prepared request and returns a controlled Instagram response
    def send(session, request, **kwargs):
        state.calls.append((request, kwargs))
        assert kwargs.get("allow_redirects") is False
        if isinstance(state.outcome, Exception):
            raise state.outcome
        response = requests.Response()
        response.url = request.url
        response.status_code = state.outcome if isinstance(state.outcome, int) else 200
        response.reason = "test response"
        user = {"username": state.outcome} if isinstance(state.outcome, str) else None
        data = {"status": "ok", "data": {"user": user}} if response.status_code == 200 else {"status": "fail", "message": "challenge_required" if state.outcome == 400 else "request failed"}
        response._content = json.dumps(data).encode()
        if state.after_request:
            state.after_request()
        return response

    monkeypatch.setattr(im.instaloader.Instaloader, "load_session_from_file", load)
    monkeypatch.setattr(im.instaloader.Instaloader, "save_session_to_file", lambda bot, filename=None: state.saves.append((bot.context.username, filename)))
    monkeypatch.setattr(requests.sessions.Session, "send", send)
    yield state
    for name, value in snapshot.items():
        setattr(im, name, value)


# Leaves a durable stop while removing only state that would disappear on process restart
def restart_with_stop():
    im.record_identities_returned(17)
    im.trip_circuit_breaker("auth_expired")
    im.ACCOUNT_BREAKER_MEMORY.clear()
    im.ACCOUNT_RECOVERY_ATTEMPTED.clear()


# A successful restart verifies the account once and preserves its daily identity count
def test_restart_recovers_before_workers_and_keeps_budget(account):
    restart_with_stop()
    assert im.recover_account_on_startup()
    assert len(account.calls) == 1
    assert account.calls[0][1]["timeout"] == 30
    assert im.exposure_snapshot()["identities"] == 17
    assert im.circuit_breaker_state() is None
    assert im.recover_account_on_startup()
    assert len(account.calls) == 1


@pytest.mark.parametrize("outcome", ["saved.account", None, 429])
# Concurrent startup requests share one account probe even when the account check fails
def test_concurrent_starters_share_one_probe(account, outcome):
    restart_with_stop()
    account.outcome = outcome
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: im.recover_account_on_startup(), range(6)))
    assert results == [outcome == "saved.account"] * 6
    assert len(account.calls) == 1


@pytest.mark.parametrize("outcome", [None, "another.account", 302, 400, 401, 429, requests.Timeout("test connection timed out")])
# Rejected, challenged and unreachable sessions stay stopped without redirects or request retries
def test_failed_probe_stays_stopped_until_restart_or_session_replacement(account, outcome, capsys):
    restart_with_stop()
    account.outcome = outcome
    assert not im.recover_account_on_startup()
    assert not im.recover_account_on_startup()
    assert len(account.calls) == 1
    assert im.circuit_breaker_state() is not None
    assert "Monitoring remains paused" in capsys.readouterr().out


# A new failure during a running process cannot unlock itself through another worker start
def test_same_run_failure_does_not_probe_again(account):
    im.trip_circuit_breaker("challenge")
    assert not im.recover_account_on_startup()
    assert account.calls == []


# A response arriving after a newer account failure cannot clear that newer stop
def test_probe_does_not_clear_a_newer_failure(account):
    restart_with_stop()
    account.after_request = lambda: im.trip_circuit_breaker("challenge", error_msg="new failure")
    assert not im.recover_account_on_startup()
    state = im.circuit_breaker_state()
    assert state is not None and state["failure_class"] == "challenge"


# A local ledger failure prevents the probe and does not reset accumulated counts
def test_unwritable_ledger_remains_stopped(account, monkeypatch):
    restart_with_stop()

    # Simulates a write failure at the persistence boundary
    def fail(data):
        raise im.ExposureLedgerError("read-only ledger")

    monkeypatch.setattr(im, "_write_exposure_file", fail)
    assert not im.recover_account_on_startup()
    assert not account.calls
    assert im.exposure_snapshot()["identities"] == 17


# A successful probe cannot resume workers if clearing the stop fails to persist
def test_clear_failure_keeps_memory_stop(account, monkeypatch):
    restart_with_stop()
    original = im._write_exposure_file

    # Allows the preflight write but rejects the attempted stop removal
    def write(data):
        if data["accounts"]["saved.account"].get("breaker") is None:
            raise im.ExposureLedgerError("write failed")
        original(data)

    monkeypatch.setattr(im, "_write_exposure_file", write)
    assert not im.recover_account_on_startup()
    assert len(account.calls) == 1
    assert im.circuit_breaker_state() is not None


@pytest.mark.parametrize("dashboard", [False, True])
# Import validates new cookies once and releases the stop only after saving the session
def test_import_reuses_validation_to_recover(account, dashboard):
    im.record_identities_returned(17)
    im.trip_circuit_breaker("challenge")
    if dashboard:
        username = im.import_browser_session_dashboard("firefox", "synthetic.sqlite")
    else:
        username = im.import_session("firefox", "synthetic.sqlite", None)
    assert username == "saved.account"
    assert account.saves == [("saved.account", None)]
    assert len(account.calls) == 1
    assert im.circuit_breaker_state() is None
    assert im.exposure_snapshot()["identities"] == 17


# An import failure leaves the stopped account and its stored session untouched
def test_failed_import_does_not_clear_stop(account):
    im.trip_circuit_breaker("challenge")
    account.outcome = None
    with pytest.raises(im.CookieImportError):
        im.import_browser_session_dashboard("firefox", "synthetic.sqlite")
    assert not account.saves
    assert im.circuit_breaker_state() is not None


# A session file that could not be saved must not unlock a stopped account
def test_failed_session_save_does_not_clear_stop(account, monkeypatch):
    im.trip_circuit_breaker("challenge")

    # Rejects the imported session at the save boundary
    def fail(bot, filename=None):
        raise OSError("read-only session file")

    monkeypatch.setattr(im.instaloader.Instaloader, "save_session_to_file", fail)
    with pytest.raises(OSError):
        im.import_browser_session_dashboard("firefox", "synthetic.sqlite")
    assert im.circuit_breaker_state() is not None


# Recovery access belongs only to its checking thread and cannot authorize a second request
def test_probe_permission_is_thread_local_and_single_use(account):
    im.trip_circuit_breaker("challenge")
    calls = []
    request = im.instagram_wrap_request(lambda *args, **kwargs: calls.append(kwargs) or SimpleNamespace(status_code=200))

    # Tries ordinary work from another thread while the checking thread has recovery permission
    def blocked():
        with pytest.raises(im.instaloader.exceptions.AbortDownloadException):
            request("GET", "https://www.instagram.com/")

    # Exercises the exact request boundary inside the login check
    def check():
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(blocked).result()
        request("GET", "https://www.instagram.com/")
        with pytest.raises(im.instaloader.exceptions.AbortDownloadException):
            request("GET", "https://www.instagram.com/")
        return "saved.account"

    assert im.check_account_login(SimpleNamespace(test_login=check)) == "saved.account"
    assert len(calls) == 1
    blocked()


# Recovered targets restart after old workers exit while manually stopped targets remain stopped
def test_dashboard_restarts_only_account_paused_targets(account, monkeypatch):
    monkeypatch.setattr(im, "WEB_DASHBOARD_ENABLED", True)
    im.WEB_DASHBOARD_DATA["targets"] = {"paused": {}, "manual": {}}
    im.WEB_DASHBOARD_STOP_EVENTS.update({"paused": threading.Event(), "manual": threading.Event()})
    im.WEB_DASHBOARD_STOP_EVENTS["manual"].set()
    im.trip_circuit_breaker("challenge")
    assert im.ACCOUNT_PAUSED_TARGETS["saved.account"] == {"paused"}
    im.import_browser_session_dashboard("firefox", "synthetic.sqlite")
    started = []
    monkeypatch.setattr(im, "start_monitoring_for_target", lambda user: started.append(user))
    worker = im.resume_recovered_account_targets()
    assert worker is not None
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert started == ["paused"]


@pytest.mark.parametrize("skip_session", [False, True])
# Ordinary startup without an account stop does not add an account probe
def test_healthy_startup_needs_no_recovery_request(account, monkeypatch, skip_session):
    monkeypatch.setattr(im, "SKIP_SESSION", skip_session)
    assert im.recover_account_on_startup()
    assert not account.calls


@pytest.mark.parametrize("outcome", ["saved.account", None])
# The real CLI checks the account before entering a target and exits on a failed check
def test_cli_recovery_precedes_target_start(account, monkeypatch, tmp_path, outcome):
    restart_with_stop()
    account.outcome = outcome
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["instagram_monitor.py", "target", "--session-username", "saved.account", "--config-file", "none", "--env-file", "none", "--no-color", "--disable-logging", "--no-web-dashboard"])
    monkeypatch.setattr(im, "check_internet", lambda: True)
    monkeypatch.setattr(im, "start_dashboard_input_handler", lambda: None)
    monkeypatch.setattr(im, "clear_screen", lambda *args: None)
    monkeypatch.setattr(im, "DASHBOARD_ENABLED", False)
    monkeypatch.setattr(im.signal, "signal", lambda *args: None)
    entered = []

    # Records the account state seen at the worker boundary
    def monitor(*args, **kwargs):
        entered.append((len(account.calls), im.circuit_breaker_state()))

    monkeypatch.setattr(im, "instagram_monitor_user", monitor)
    previous_stdout = sys.stdout
    monkeypatch.setattr(im, "stdout_bck", previous_stdout)
    try:
        with pytest.raises(SystemExit) as stopped:
            im.run_main()
    finally:
        sys.stdout = previous_stdout
    assert stopped.value.code == (0 if outcome else 1)
    assert entered == ([(1, None)] if outcome else [])
    assert len(account.calls) == 1


# The dashboard import endpoint starts recovery automatically after the verified session is saved
def test_dashboard_import_resumes_without_another_action(account, monkeypatch):
    monkeypatch.setattr(im, "WEB_DASHBOARD_ENABLED", True)
    im.WEB_DASHBOARD_DATA["targets"] = {"target": {}}
    im.WEB_DASHBOARD_STOP_EVENTS["target"] = threading.Event()
    im.trip_circuit_breaker("challenge")
    monkeypatch.setattr(im, "resolve_offered_firefox_cookiefile", lambda path: path)
    monkeypatch.setattr(im, "print_cur_ts", lambda *args, **kwargs: None)
    started = threading.Event()
    monkeypatch.setattr(im, "start_monitoring_for_target", lambda user: started.set())
    app = im.create_web_dashboard_app()
    assert app is not None
    response = app.test_client().post("/api/session/firefox/import", json={"path": "synthetic.sqlite"})
    assert response.get_json()["success"]
    assert started.wait(timeout=2)
    assert im.circuit_breaker_state() is None
    assert len(account.calls) == 1


# Importing a different account does not release the previous account's stop
def test_import_recovery_is_account_scoped(account):
    im.trip_circuit_breaker("challenge")
    account.outcome = "other.account"
    assert im.import_browser_session_dashboard("firefox", "synthetic.sqlite") == "other.account"
    assert im.circuit_breaker_state() is not None


# A stop received while a request waits for serialization prevents that request from being sent
def test_waiting_request_observes_account_stop(account, monkeypatch):
    monkeypatch.setattr(im, "MULTI_TARGET_SERIALIZE_HTTP", True)
    monkeypatch.setattr(im, "ENABLE_JITTER", False)
    calls = []
    request = im.instagram_wrap_request(lambda *args, **kwargs: calls.append(1))

    # Trips the stop after the outer guard but before the serialized request starts
    class StopBeforeRequest:
        # Simulates a failure in the preceding serialized request
        def __enter__(self):
            im.trip_circuit_breaker("challenge")

        # Leaves exception handling to the request wrapper
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(im, "HTTP_SERIAL_LOCK", StopBeforeRequest())
    with pytest.raises(im.instaloader.exceptions.AbortDownloadException):
        request("GET", "https://www.instagram.com/")
    assert not calls


# Start All remembers requested targets while the account is paused without probing again
def test_start_all_queues_targets_for_session_recovery(account):
    im.WEB_DASHBOARD_DATA["targets"] = {"target": {}}
    im.trip_circuit_breaker("challenge")
    im.start_all_monitoring()
    assert im.ACCOUNT_PAUSED_TARGETS["saved.account"] == {"target"}
    assert not account.calls
