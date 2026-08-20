"""Integration tests that drive the curl_cffi transport adapter against a loopback server."""

import http.server
import threading

import pytest

import requests


# Serves one loopback endpoint that echoes request details and sets a cookie
class _EchoHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok": true, "path": "' + self.path.encode() + b'"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Set-Cookie", "sessionid=abc123; Path=/")
        self.send_header("X-Echo-Agent", self.headers.get("User-Agent", ""))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = self.rfile.read(length)
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        return


@pytest.fixture
def echo_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


class TestCurlCffiAdapter:
    # A session mounted with the adapter returns the response shape instaloader relies on
    def test_response_shape_survives_the_adapter(self, im_module, monkeypatch, echo_server):
        if not im_module._CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is not installed")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        session = requests.Session()
        session.mount("http://", im_module._CurlCffiHTTPAdapter())

        response = session.get(f"{echo_server}/api/v1/probe", timeout=10)

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["path"] == "/api/v1/probe"
        assert response.headers["Content-Type"] == "application/json"
        assert response.url.endswith("/api/v1/probe")
        assert response.text.startswith("{")

    # Cookies set by the server reach the session jar, which is how the Instagram session is maintained
    def test_cookies_reach_the_session_jar(self, im_module, monkeypatch, echo_server):
        if not im_module._CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is not installed")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        session = requests.Session()
        session.mount("http://", im_module._CurlCffiHTTPAdapter())

        session.get(f"{echo_server}/", timeout=10)

        assert session.cookies.get("sessionid") == "abc123"

    # A request body round-trips, covering the POST path used by iPhone API calls
    def test_request_body_round_trips(self, im_module, monkeypatch, echo_server):
        if not im_module._CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is not installed")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        session = requests.Session()
        session.mount("http://", im_module._CurlCffiHTTPAdapter())

        response = session.post(f"{echo_server}/upload", data=b"payload-bytes", timeout=10)

        assert response.status_code == 201
        assert response.content == b"payload-bytes"

    # Streaming reads work, which instaloader uses for media downloads
    def test_streamed_content_is_readable(self, im_module, monkeypatch, echo_server):
        if not im_module._CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is not installed")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        session = requests.Session()
        session.mount("http://", im_module._CurlCffiHTTPAdapter())

        response = session.get(f"{echo_server}/media", timeout=10, stream=True)

        assert b"".join(response.iter_content(chunk_size=8)).startswith(b'{"ok"')

    # With the requests backend selected the adapter passes straight through, preserving historical behavior
    def test_requests_backend_passes_through(self, im_module, monkeypatch, echo_server):
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "requests")
        session = requests.Session()
        session.mount("http://", im_module._CurlCffiHTTPAdapter())

        response = session.get(f"{echo_server}/plain", timeout=10)

        assert response.status_code == 200
        assert response.json()["path"] == "/plain"

    # A connection failure surfaces as the requests exception instaloader already handles
    def test_connection_failure_is_translated(self, im_module, monkeypatch):
        if not im_module._CURL_CFFI_AVAILABLE:
            pytest.skip("curl_cffi is not installed")
        monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
        session = requests.Session()
        session.mount("http://", im_module._CurlCffiHTTPAdapter())

        with pytest.raises(requests.exceptions.ConnectionError):
            session.get("http://127.0.0.1:1/unreachable", timeout=5)
