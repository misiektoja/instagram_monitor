"""Offline tests for Instagram-only request jitter and wrapping."""

from types import SimpleNamespace

import pytest


# Returns the minimal response shape consumed by the Instagram request wrapper
def _response(status_code=200, text=""):
    return SimpleNamespace(status_code=status_code, text=text, headers={})


class TestInstagramRequestClassification:
    # Only Instagram and its real subdomains are classified as Instagram traffic
    @pytest.mark.parametrize("url,expected", [("https://instagram.com/api", True), ("https://www.instagram.com/api", True), ("https://i.instagram.com/api", True), ("/api/v1/feed", True), ("https://notinstagram.com/hook", False), ("https://instagram.com.evil.example/hook", False), ("https://example.com/instagram.com", False)])
    def test_instagram_request_url_uses_hostname_boundaries(self, im_module, url, expected):
        assert im_module.is_instagram_request_url(url) is expected


class TestInstagramRequestWrapping:
    # External URLs bypass jitter backoff and global HTTP serialization
    def test_wrapped_session_bypasses_non_instagram_request(self, im_module, monkeypatch):
        calls = []
        sleeps = []
        session = SimpleNamespace(request=lambda *args, **kwargs: calls.append((args, kwargs)) or _response(status_code=429))
        monkeypatch.setattr(im_module, "ENABLE_JITTER", True)
        monkeypatch.setattr(im_module, "MULTI_TARGET_SERIALIZE_HTTP", True)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: sleeps.append(seconds))

        im_module.ensure_instagram_session_wrapped(session)
        result = session.request("POST", "https://hooks.example.com/status")

        assert result.status_code == 429
        assert len(calls) == 1
        assert sleeps == []

    # Instagram requests still receive configured human-like jitter on the wrapped session
    def test_wrapped_session_applies_jitter_to_instagram_request(self, im_module, monkeypatch):
        calls = []
        sleeps = []
        session = SimpleNamespace(request=lambda *args, **kwargs: calls.append((args, kwargs)) or _response())
        monkeypatch.setattr(im_module, "ENABLE_JITTER", True)
        monkeypatch.setattr(im_module, "MULTI_TARGET_SERIALIZE_HTTP", False)
        monkeypatch.setattr(im_module, "SKIP_WRAP_MESSAGES", True)
        monkeypatch.setattr(im_module.random, "expovariate", lambda rate: 1.25)
        monkeypatch.setattr(im_module.time, "sleep", lambda seconds: sleeps.append(seconds))
        im_module._thread_local.pbar = None

        im_module.ensure_instagram_session_wrapped(session)
        result = session.request("GET", "https://i.instagram.com/api/v1/feed")

        assert result.status_code == 200
        assert len(calls) == 1
        assert sleeps == [1.25]

    # Wrapping one Instaloader session does not patch Requests or another session
    def test_session_wrapping_is_local_and_idempotent(self, im_module):
        target_calls = []
        other_calls = []
        target = SimpleNamespace(request=lambda *args, **kwargs: target_calls.append((args, kwargs)) or _response())
        other = SimpleNamespace(request=lambda *args, **kwargs: other_calls.append((args, kwargs)) or _response())
        requests_method = im_module.req.Session.request

        im_module.ensure_instagram_session_wrapped(target)
        wrapped_method = target.request
        im_module.ensure_instagram_session_wrapped(target)
        other.request("GET", "https://example.com/media")

        assert target.request is wrapped_method
        assert getattr(target, "_instagram_monitor_wrapped") is True
        assert not hasattr(other, "_instagram_monitor_wrapped")
        assert im_module.req.Session.request is requests_method
        assert target_calls == []
        assert len(other_calls) == 1

    # Instaloader's copied iPhone API session inherits the scoped wrapper
    def test_instaloader_copy_session_is_wrapped(self, im_module):
        from instaloader import instaloadercontext

        source = im_module.req.Session()
        copied = instaloadercontext.copy_session(source)

        assert getattr(copied, "_instagram_monitor_wrapped") is True
        assert not hasattr(source, "_instagram_monitor_wrapped")
