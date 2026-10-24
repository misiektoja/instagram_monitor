"""Offline tests for the fresh sessions Instaloader builds for page reads, raw downloads and HEAD requests."""

import io
import json
import os

import instaloader
import pytest
import requests
from requests.adapters import HTTPAdapter

PROXY_URL = "http://proxy.example.test:8080"


# Returns a profile page that embeds the profile the way Instagram renders it for a logged-out visitor
def _profile_page(username, pk):
    query = {"__bbox": {"result": {"data": {"xig_user_by_username": {"pk": pk, "username": username, "full_name": "Target", "is_private": False}}}}}
    return f'<html><script type="application/json">{json.dumps(query)}</script></html>'.encode()


# Routes the run through a configured proxy with a dedicated certificate and records every request at the transport
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
    sent = []

    # Answers each request with the profile page and records the transport that received it
    def reply(transport):
        # Stands in for the transport's send, which receives the proxies and verify setting requests resolved
        def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
            sent.append({"transport": transport, "url": request.url, "method": request.method, "proxies": dict(proxies or {}), "verify": verify})
            response = requests.Response()
            response.status_code = 200
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response._content = _profile_page("target", "77")
            response.raw = io.BytesIO(response._content)
            response.encoding = "utf-8"
            response.request = request
            response.url = request.url
            return response
        return send

    monkeypatch.setattr(HTTPAdapter, "send", reply("requests"))
    monkeypatch.setattr(im_module._CurlCffiHTTPAdapter, "send", reply("curl_cffi"))
    return sent, str(certificate)


# Returns an Instaloader built the way the monitor builds one, without pauses between requests
def _client(im_module):
    return im_module.instaloader_client(user_agent="Mozilla/5.0", sleep=False, quiet=True)


# Returns a client whose context reads public pages, skipping the test on an Instaloader that has no page reader
def _page_client(im_module):
    bot = _client(im_module)
    if not callable(getattr(bot.context, "get_page_data", None)):
        pytest.skip("this Instaloader reads profiles without the public profile page")
    return bot


class TestAnonymousSessions:
    # Instaloader 4.15.4 reads the public profile page with a new session, which must still use the configured proxy
    def test_profile_page_request_uses_the_configured_proxy(self, im_module, proxied_transport):
        sent, certificate = proxied_transport
        bot = _page_client(im_module)

        profile = instaloader.Profile.from_username(bot.context, "target")

        assert profile.userid == 77
        assert [entry["url"] for entry in sent] == ["https://www.instagram.com/target/"]
        assert sent[0]["transport"] == "curl_cffi"
        assert sent[0]["proxies"] == {"http": PROXY_URL, "https": PROXY_URL}
        assert sent[0]["verify"] == certificate

    # The page request passes the request wrapper, so the jitter configured for Instagram traffic applies to it
    def test_profile_page_request_passes_the_request_wrapper(self, im_module, proxied_transport, monkeypatch):
        sent, _ = proxied_transport
        sleeps = []
        monkeypatch.setattr(im_module, "ENABLE_JITTER", True)
        monkeypatch.setattr(im_module.random, "expovariate", lambda rate: 1.25)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: sleeps.append(seconds))
        im_module._thread_local.pbar = None
        bot = _page_client(im_module)

        bot.context.get_page_data("target/")

        assert len(sent) == 1
        assert sleeps == [1.25]

    # A stopped account sends no page request, the same as for every other Instagram request
    def test_circuit_breaker_stops_the_page_request(self, im_module, proxied_transport, monkeypatch):
        sent, _ = proxied_transport
        monkeypatch.setattr(im_module, "CIRCUIT_BREAKER", True)
        bot = _page_client(im_module)
        monkeypatch.setitem(im_module.ACCOUNT_BREAKER_MEMORY, im_module.exposure_account_name(), {"failure_class": "challenge"})

        with pytest.raises(instaloader.exceptions.AbortDownloadException):
            bot.context.get_page_data("target/")

        assert sent == []

    # Raw downloads and HEAD requests use the same factory, so they go out through the configured proxy too
    @pytest.mark.parametrize("method", ["get_raw", "head"])
    def test_raw_and_head_requests_use_the_configured_proxy(self, im_module, proxied_transport, method):
        sent, certificate = proxied_transport
        bot = _client(im_module)

        getattr(bot.context, method)("https://scontent.cdninstagram.com/v/t51/picture.jpg")

        assert len(sent) == 1
        assert sent[0]["transport"] == "curl_cffi"
        assert sent[0]["proxies"] == {"http": PROXY_URL, "https": PROXY_URL}
        assert sent[0]["verify"] == certificate

    # Installing the patch again keeps one layer, so a session is configured and wrapped once
    def test_patch_is_installed_once(self, im_module):
        from instaloader.instaloadercontext import InstaloaderContext

        installed = InstaloaderContext.get_anonymous_session
        im_module._install_anonymous_session_proxy_patch()

        assert InstaloaderContext.get_anonymous_session is installed
        assert getattr(installed, "_proxies_patched", False) is True
