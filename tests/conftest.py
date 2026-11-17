"""Shared pytest fixtures and import setup for the offline test suite, which never touches the network."""

import ipaddress
import os
import sys
from urllib.parse import urlsplit

# Put the in-repo source first on the import path, so tests never run against an installed copy
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
elif sys.path.index(_PROJECT_ROOT) != 0:
    sys.path.remove(_PROJECT_ROOT)
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
import urllib3.connectionpool
import urllib3.exceptions

import instagram_monitor as im

# Runs a pytest session inside a test, which is how the network guard's teardown failure is checked
pytest_plugins = ["pytester"]


# Fails fast if pytest accidentally imported an installed copy instead of the working tree
def _assert_in_repo_module() -> None:
    resolved = os.path.abspath(im.__file__)
    expected = os.path.join(_PROJECT_ROOT, "instagram_monitor.py")
    assert resolved == expected, (f"Tests imported the wrong instagram_monitor module.\n  imported: {resolved}\n  expected: {expected}\nAn installed copy is shadowing the working tree.")


_assert_in_repo_module()


# Exposes the imported module to every test
@pytest.fixture
def im_module():
    return im


_REAL_WIZARD_VERIFY_SMTP = im._wizard_verify_smtp
_REAL_LIST_FIREFOX_PROFILES = im.list_firefox_profiles
_REAL_LIST_CHROMIUM_PROFILES = im.list_chromium_profiles


# Restores the real profile enumeration for the tests that exercise it directly against a stubbed filesystem
@pytest.fixture
def real_browser_profiles(monkeypatch, deterministic_globals):
    monkeypatch.setattr(im, "list_firefox_profiles", _REAL_LIST_FIREFOX_PROFILES)
    monkeypatch.setattr(im, "list_chromium_profiles", _REAL_LIST_CHROMIUM_PROFILES)


@pytest.fixture(autouse=True)
# Keeps the wizard's mail server sign-in check offline, so a scripted setup run never opens a connection
def accepted_smtp_sign_in(monkeypatch):
    monkeypatch.setattr(im, "_wizard_verify_smtp", lambda values, password: None)


@pytest.fixture
# Restores the real sign-in check for the tests that exercise it directly against a stubbed SMTP class
def real_smtp_sign_in(monkeypatch, accepted_smtp_sign_in):
    monkeypatch.setattr(im, "_wizard_verify_smtp", _REAL_WIZARD_VERIFY_SMTP)


# Keeps the identity exposure ledger inside the test's temporary directory
@pytest.fixture(autouse=True)
def isolated_exposure_ledger(monkeypatch, tmp_path):
    ledger_path = tmp_path / "exposure" / im.EXPOSURE_STATE_FILENAME
    monkeypatch.setattr(im, "exposure_state_path", lambda: str(ledger_path), raising=False)
    return ledger_path


# Returns the host a URL or proxy address names, where a proxy may leave out its scheme
def _address_host(address) -> str:
    text = str(address)
    return urlsplit(text if "://" in text else "//" + text).hostname or ""


# Returns whether a host is this machine, the only place a test may send traffic
def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


# Refuses curl_cffi requests to any host but this machine and records each one. Needed because the curl_cffi
# adapter overrides HTTPAdapter.send, which a stubbed requests transport does not cover
def _guard_curl_cffi(monkeypatch, refused: list) -> None:
    curl_requests, curl_exceptions = im._curl_requests, im._curl_exceptions
    if curl_requests is None or curl_exceptions is None:
        return
    real_request = curl_requests.Session.request

    # Lets requests to local test servers through and fails the rest as a connection error, checking any proxy too
    def request(self, method, url, *args, **kwargs):
        proxies = kwargs.get("proxies") or {}
        addresses = [url, *(proxy for proxy in (kwargs.get("proxy"), *proxies.values()) if proxy)]
        hosts = [host for host in map(_address_host, addresses) if not _is_loopback_host(host)]
        if hosts:
            refused.append(f"curl_cffi request to {hosts[0]!r}")
            raise curl_exceptions.ConnectionError(f"The offline test suite refused a curl_cffi request to {hosts[0]!r}")
        return real_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(curl_requests.Session, "request", request)


# Refuses urllib3 requests to any host but this machine and records each one. A stubbed requests transport still
# answers, since the guard sits below HTTPAdapter.send
def _guard_urllib3(monkeypatch, refused: list) -> None:
    real_urlopen = urllib3.connectionpool.HTTPConnectionPool.urlopen

    # Checks the pool's host, the absolute URL a plain HTTP proxy receives and the proxy itself before sending
    def urlopen(self, method, url, *args, **kwargs):
        hosts = [str(self.host).strip("[]").lower()]
        if "://" in str(url):
            hosts.append(_address_host(url))
        proxy = getattr(self, "proxy", None)
        if proxy is not None:
            hosts.append(str(proxy.host or "").strip("[]").lower())
        outside = [host for host in hosts if not _is_loopback_host(host)]
        if outside:
            refused.append(f"requests call to {outside[0]!r}")
            raise urllib3.exceptions.ProtocolError(f"The offline test suite refused a requests call to {outside[0]!r}")
        return real_urlopen(self, method, url, *args, **kwargs)

    monkeypatch.setattr(urllib3.connectionpool.HTTPConnectionPool, "urlopen", urlopen)


# Keeps every test off the network. A request to another host fails as a connection error and fails the test at
# teardown. A test that expects a refusal requests this fixture and clears the list it yields
@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    refused: list = []
    _guard_curl_cffi(monkeypatch, refused)
    _guard_urllib3(monkeypatch, refused)
    yield refused
    if refused:
        pytest.fail(f"Refused network access during the test: {', '.join(refused)}. Stub the transport the code under test sends through", pytrace=False)


# Resets the handful of module-level globals the helpers read so each test starts from a known, deterministic baseline
@pytest.fixture(autouse=True)
def deterministic_globals(monkeypatch, tmp_path):
    monkeypatch.setattr(im, "LOCAL_TIMEZONE", "UTC", raising=False)
    monkeypatch.setattr(im, "TIME_FORMAT_12H", False, raising=False)
    monkeypatch.setattr(im, "PRIVACY_SUBSTITUTIONS", [], raising=False)
    monkeypatch.setattr(im, "PRIVACY_SUBSTITUTIONS_INVALID_WARNED", False, raising=False)
    monkeypatch.setattr(im, "DEBUG_MODE", False, raising=False)
    monkeypatch.setattr(im, "VERBOSE_MODE", False, raising=False)
    monkeypatch.setattr(im, "CHECK_POSTS_IN_HOURS_RANGE", False, raising=False)
    monkeypatch.setattr(im, "MIN_H1", 0, raising=False)
    monkeypatch.setattr(im, "MAX_H1", 0, raising=False)
    monkeypatch.setattr(im, "MIN_H2", 0, raising=False)
    monkeypatch.setattr(im, "MAX_H2", 0, raising=False)
    monkeypatch.setattr(im, "WEBHOOK_ENABLED", False, raising=False)
    monkeypatch.setattr(im, "WEBHOOK_URL", "", raising=False)
    monkeypatch.setattr(im, "WEBHOOK_PROVIDER", "discord", raising=False)
    monkeypatch.setattr(im, "WEBHOOK_HEADERS", {}, raising=False)
    monkeypatch.setattr(im, "NTFY_ACCESS_TOKEN", "", raising=False)
    monkeypatch.setattr(im, "DAILY_HUMAN_HITS", 5, raising=False)
    # The real CLI path leaves these set, and every account-scoped helper keys off them
    monkeypatch.setattr(im, "SESSION_USERNAME", "", raising=False)
    monkeypatch.setattr(im, "SKIP_SESSION", False, raising=False)
    # A run leaves these identity settings on the module, so they are reset for the next test
    monkeypatch.setattr(im, "USER_AGENT", "", raising=False)
    monkeypatch.setattr(im, "USER_AGENT_MOBILE", "", raising=False)
    monkeypatch.setattr(im, "HTTP_BACKEND", "curl_cffi", raising=False)
    monkeypatch.setattr(im, "CURL_CFFI_IMPERSONATE", "auto", raising=False)
    monkeypatch.setattr(im, "FOLLOW_LIST_SOURCE", "auto", raising=False)
    monkeypatch.setattr(im, "FOLLOW_LIST_BROWSER_CHANNEL", "chromium", raising=False)
    # Setup and the dashboard both write these, and the wizard snapshots the module to build its baseline
    monkeypatch.setattr(im, "SKIP_FOLLOWERS", False, raising=False)
    monkeypatch.setattr(im, "SKIP_FOLLOWINGS", False, raising=False)
    # Stubbed, so no test reads the real browsers and cookie databases of the machine running the suite
    monkeypatch.setattr(im, "list_firefox_profiles", lambda: [], raising=False)
    monkeypatch.setattr(im, "list_chromium_profiles", lambda browser: [], raising=False)
    im._WIZARD_BROWSER_SESSION_COUNTS.clear()
    # A run that reported a broken proxy leaves the record on the module, where Doctor would read it in a later test
    im.PROXY_STARTUP_ERRORS.clear()
    # Resolved user ids are reused for the whole run, so one test's target must not answer for another's
    im.USER_ID_CACHE.clear()
    # Resolved ids outlive a run in a file, so each test is given its own rather than the working directory's
    im.USER_ID_CACHE_LOADED = False
    # A search path one test saw retired must still be asked by the next
    im.USER_SEARCH_RETIRED = False
    monkeypatch.setattr(im, "user_id_cache_path", lambda: str(tmp_path / "instagram_monitor_user_ids.json"), raising=False)
    # A reels count established for one test's posts count must not answer for another's
    im.REELS_COUNT_CACHE.clear()
    # Set by the first startup notice a test prints, and read by the Doctor notice to decide its leading blank line
    im.CONSOLE_OUTPUT_PRINTED = False
    # Drop any cached flag-probe verdict between tests
    with im.FLAGGED_PROBE_LOCK:
        im.FLAGGED_PROBE_CACHE["ts"] = 0.0
        im.FLAGGED_PROBE_CACHE["flagged"] = False
    # Drop the flag-alert de-dup timestamp so each test starts able to alert
    with im.FLAGGED_NOTIFY_LOCK:
        im.FLAGGED_NOTIFY_STATE["ts"] = 0.0
    # Drop in-memory account stops so one safety test cannot block another test's request path
    with im.ACCOUNT_BREAKER_MEMORY_LOCK:
        im.ACCOUNT_BREAKER_MEMORY.clear()
        im.ACCOUNT_RECOVERY_ATTEMPTED.clear()
        im.ACCOUNT_PAUSED_TARGETS.clear()
    # load_dotenv writes into os.environ and nothing removes it, so loaded secrets would leak into later tests
    for secret in im.SECRET_KEYS:
        monkeypatch.delenv(secret, raising=False)
    yield
