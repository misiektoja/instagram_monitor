"""Offline tests for the signed-in sessions Instaloader builds when it loads a session file or logs in."""

import io
import json
import os
import pickle
from types import SimpleNamespace

import instaloader
import pytest
import requests
from requests.adapters import HTTPAdapter
from requests.cookies import cookiejar_from_dict

PROXY_URL = "http://proxy.example.test:8080"
PROXIES = {"http": PROXY_URL, "https": PROXY_URL}
SESSION_COOKIES = {"csrftoken": "token", "sessionid": "session", "ds_user_id": "1"}


# Returns the JSON Instagram answers to each endpoint these tests reach, or None for an HTML page
def _reply_body(url, two_factor):
    if "graphql/query" in url:
        return {"data": {"user": {"username": "someone"}}, "status": "ok"}
    if "two_factor" in url:
        return {"status": "ok"}
    if "login/ajax" in url:
        if two_factor:
            return {"two_factor_required": True, "two_factor_info": {"two_factor_identifier": "identifier"}, "status": "fail"}
        return {"authenticated": True, "user": True, "userId": "1", "status": "ok"}
    return None


# Routes the run through a configured proxy with a dedicated certificate and records every request at the transport.
# Setting two_factor on the returned state makes the login reply ask for a second factor
@pytest.fixture
def proxied_transport(im_module, monkeypatch, tmp_path):
    # requests lets *_proxy and CA bundle environment variables override a session's own proxies and verify setting,
    # which would hide a missing one
    for name in [name for name in os.environ if name.lower().endswith("_proxy") or name in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE")]:
        monkeypatch.delenv(name, raising=False)
    certificate = tmp_path / "proxy-ca.pem"
    certificate.write_text("synthetic certificate\n", encoding="utf-8")
    monkeypatch.setattr(im_module, "PROXY_ENABLED", True)
    monkeypatch.setattr(im_module, "PROXY_URL", PROXY_URL)
    monkeypatch.setattr(im_module, "PROXY_CERT_PATH", str(certificate))
    monkeypatch.setattr(im_module, "VERIFY_SSL", True)
    monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
    monkeypatch.setattr(im_module, "ENABLE_JITTER", False)
    monkeypatch.setattr(im_module, "SKIP_WRAP_MESSAGES", True)
    transport = SimpleNamespace(sent=[], certificate=str(certificate), two_factor=False)

    # Answers each request as Instagram would and records the transport that received it
    def reply(name):
        # Stands in for the transport's send, which receives the proxies and verify setting requests resolved
        def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
            transport.sent.append({"transport": name, "url": request.url, "method": request.method, "proxies": dict(proxies or {}), "verify": verify})
            body = _reply_body(request.url, transport.two_factor)
            response = requests.Response()
            response.status_code = 200
            if body is None:
                response.headers["Content-Type"] = "text/html; charset=utf-8"
                response._content = b"<html></html>"
            else:
                response.headers["Content-Type"] = "application/json"
                response._content = json.dumps(body).encode()
            response.cookies = cookiejar_from_dict({"csrftoken": "token"})
            response.raw = io.BytesIO(response._content)
            response.encoding = "utf-8"
            response.request = request
            response.url = request.url
            return response
        return send

    monkeypatch.setattr(HTTPAdapter, "send", reply("requests"))
    monkeypatch.setattr(im_module._CurlCffiHTTPAdapter, "send", reply("curl_cffi"))
    return transport


# Returns an Instaloader built the way the monitor builds one, without pauses between requests
def _client(im_module):
    return im_module.instaloader_client(user_agent="Mozilla/5.0", sleep=False, quiet=True)


# Returns a client signed in from a saved session file, the way the monitor, Doctor and the dashboard load one
def _loaded_client(im_module, tmp_path):
    session_file = tmp_path / "session-someone"
    session_file.write_bytes(pickle.dumps(SESSION_COOKIES))
    bot = _client(im_module)
    bot.load_session_from_file("someone", str(session_file))
    return bot


# Asserts that every recorded request went out through the curl_cffi transport, the proxy and the expected verify setting
def _assert_proxied(sent, verify):
    assert sent
    for entry in sent:
        assert entry["transport"] == "curl_cffi", entry["url"]
        assert entry["proxies"] == PROXIES, entry["url"]
        assert entry["verify"] == verify, entry["url"]


# Asserts that the session the context installed carries the run's settings and passes the request wrapper
def _assert_installed_session_configured(bot, verify):
    session = bot.context._session
    assert session.proxies == PROXIES
    assert session.verify == verify
    assert session.__dict__.get("_instagram_monitor_wrapped") is True


class TestLoadedSession:
    # A request made with a loaded session file goes out through the proxy with the configured verify setting
    @pytest.mark.parametrize("verify_ssl", [True, False])
    def test_signed_in_request_uses_the_configured_proxy(self, im_module, proxied_transport, monkeypatch, tmp_path, verify_ssl):
        sent = proxied_transport.sent
        monkeypatch.setattr(im_module, "VERIFY_SSL", verify_ssl)
        expected_verify = proxied_transport.certificate if verify_ssl else False
        bot = _loaded_client(im_module, tmp_path)

        assert bot.test_login() == "someone"

        assert [entry["url"].split("?")[0] for entry in sent] == ["https://www.instagram.com/graphql/query"]
        _assert_proxied(sent, expected_verify)
        _assert_installed_session_configured(bot, expected_verify)

    # A request made directly on the loaded session passes the request wrapper, so configured jitter applies to it
    def test_loaded_session_passes_the_request_wrapper(self, im_module, proxied_transport, monkeypatch, tmp_path):
        sent = proxied_transport.sent
        sleeps = []
        monkeypatch.setattr(im_module, "ENABLE_JITTER", True)
        monkeypatch.setattr(im_module.random, "expovariate", lambda rate: 1.25)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: sleeps.append(seconds))
        im_module._thread_local.pbar = None
        bot = _loaded_client(im_module, tmp_path)

        bot.context._session.get("https://www.instagram.com/")

        assert sleeps == [1.25]
        _assert_proxied(sent, proxied_transport.certificate)

    # A stopped account sends no request with the loaded session, the same as for every other Instagram request
    def test_circuit_breaker_stops_a_loaded_session_request(self, im_module, proxied_transport, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "CIRCUIT_BREAKER", True)
        bot = _loaded_client(im_module, tmp_path)
        monkeypatch.setitem(im_module.ACCOUNT_BREAKER_MEMORY, im_module.exposure_account_name(), {"failure_class": "challenge"})

        with pytest.raises(instaloader.exceptions.AbortDownloadException):
            bot.context._session.get("https://www.instagram.com/")

        assert proxied_transport.sent == []

    # The account recovery check still sends a single request when the loaded session is wrapped as well as its copy
    def test_account_recovery_check_sends_one_request(self, im_module, proxied_transport, tmp_path):
        sent = proxied_transport.sent
        bot = _loaded_client(im_module, tmp_path)

        assert im_module.check_account_login(bot) == "someone"

        assert len(sent) == 1
        _assert_proxied(sent, proxied_transport.certificate)


class TestLogin:
    # The login page request and the password request use the proxy, and so does the session login installs
    def test_login_requests_use_the_configured_proxy(self, im_module, proxied_transport):
        sent = proxied_transport.sent
        bot = _client(im_module)

        bot.login("someone", "password")

        assert [(entry["method"], entry["url"]) for entry in sent] == [("GET", "https://www.instagram.com/"), ("POST", "https://www.instagram.com/api/v1/web/accounts/login/ajax/")]
        _assert_proxied(sent, proxied_transport.certificate)
        _assert_installed_session_configured(bot, proxied_transport.certificate)

    # Login keeps Instaloader's own pacing, while the session it installs gets the request wrapper
    def test_login_installs_a_wrapped_session_without_wrapping_its_own_requests(self, im_module, proxied_transport, monkeypatch):
        sent = proxied_transport.sent
        sleeps = []
        monkeypatch.setattr(im_module, "ENABLE_JITTER", True)
        monkeypatch.setattr(im_module.random, "expovariate", lambda rate: 1.25)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: sleeps.append(seconds))
        im_module._thread_local.pbar = None
        bot = _client(im_module)

        bot.login("someone", "password")
        assert sleeps == []
        bot.context._session.get("https://www.instagram.com/")

        assert len(sent) == 3
        assert sleeps == [1.25]

    # Every request of a two-factor login uses the proxy, and the session it installs is configured and wrapped
    def test_two_factor_login_uses_the_configured_proxy(self, im_module, proxied_transport):
        sent = proxied_transport.sent
        proxied_transport.two_factor = True
        bot = _client(im_module)

        with pytest.raises(instaloader.exceptions.TwoFactorAuthRequiredException):
            bot.login("someone", "password")
        bot.two_factor_login("123456")

        assert [entry["url"] for entry in sent][-1] == "https://www.instagram.com/accounts/login/ajax/two_factor/"
        assert len(sent) == 3
        _assert_proxied(sent, proxied_transport.certificate)
        _assert_installed_session_configured(bot, proxied_transport.certificate)


class TestPatchInstallation:
    # Installing the patch again keeps one layer, so a session is wrapped once
    def test_patch_is_installed_once(self, im_module):
        from instaloader.instaloadercontext import InstaloaderContext

        installed = {name: getattr(InstaloaderContext, name) for name in ("load_session", "login", "two_factor_login")}
        im_module._install_signed_in_session_wrapper_patch()

        for name, method in installed.items():
            assert getattr(InstaloaderContext, name) is method
            assert getattr(method, "_session_wrapper_patched", False) is True
