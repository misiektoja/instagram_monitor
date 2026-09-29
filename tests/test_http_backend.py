"""Integration tests that drive the curl_cffi transport adapter against a loopback server."""

import gzip
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
    # The Instaloader transport module receives the shim without relying on a publicly typed requests export
    def test_instaloader_context_receives_the_requests_shim(self, im_module, monkeypatch):
        from instaloader import instaloadercontext

        monkeypatch.setattr(instaloadercontext, "requests", requests)
        monkeypatch.setattr(im_module, "_CURL_CFFI_BACKEND_INSTALLED", False)

        im_module._install_http_backend()

        assert isinstance(instaloadercontext.__dict__["requests"], im_module._RequestsBackendShim)
        assert im_module._CURL_CFFI_BACKEND_INSTALLED is True

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


# Serves loopback requests over kept-alive HTTP/1.1, recording each client port and the headers it sent
class _KeepAliveHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list = []

    def do_GET(self):
        type(self).seen.append((self.client_address[1], self.headers))
        body = b'{"status": "ok"}'
        if self.path.startswith("/api/v1/gzip"):
            body = gzip.compress(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if self.path.startswith("/api/v1/gzip"):
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Set-Cookie", "rur=fresh; Path=/")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


@pytest.fixture
def keepalive_server(im_module, monkeypatch):
    if not im_module._CURL_CFFI_AVAILABLE:
        pytest.skip("curl_cffi is not installed")
    monkeypatch.setattr(im_module, "HTTP_BACKEND", "curl_cffi")
    monkeypatch.setattr(im_module, "CURL_CFFI_IMPERSONATE", "chrome")
    handler = type("Handler", (_KeepAliveHandler,), {"seen": []})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", handler.seen
    server.shutdown()
    thread.join(timeout=5)


# Returns a plain requests session sending through a fresh curl_cffi adapter
def _adapter_session(im_module):
    session = requests.Session()
    session.mount("http://", im_module._CurlCffiHTTPAdapter())
    return session


class TestInstagramWebHeaders:
    GRAPHQL = "https://www.instagram.com/graphql/query"
    REST = "https://www.instagram.com/api/v1/friendships/1/following/?count=25"

    # A GraphQL POST carries fetch() metadata and an Origin rather than the address-bar headers curl_cffi fills in
    def test_a_graphql_post_is_sent_as_a_background_request(self, im_module):
        sent = {"authority": "www.instagram.com", "scheme": "https", "accept": "*/*", "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-US,en;q=0.8", "x-csrftoken": "token", "Content-Length": "84"}

        headers = im_module.curl_cffi_request_headers("POST", self.GRAPHQL, sent, True, "chrome")

        assert not {"authority", "scheme", "accept-encoding", "accept-language"} & {key.lower() for key in headers}
        assert headers["Origin"] == "https://www.instagram.com"
        assert headers["Content-Length"] == "84"
        assert (headers["Sec-Fetch-Site"], headers["Sec-Fetch-Mode"], headers["Sec-Fetch-Dest"]) == ("same-origin", "cors", "empty")
        assert headers["Sec-Fetch-User"] is None and headers["Upgrade-Insecure-Requests"] is None
        assert headers["priority"] == "u=1, i"

    # A read carries no length and no Origin, and a header already set in another case is replaced rather than doubled
    def test_a_rest_read_drops_the_length_and_the_origin(self, im_module):
        sent = {"Content-Length": "0", "Origin": "https://www.instagram.com", "Sec-Fetch-Mode": "navigate"}

        headers = im_module.curl_cffi_request_headers("GET", self.REST, sent, False, "chrome")

        assert "Content-Length" not in headers and "Origin" not in headers
        assert [key for key in headers if key.lower() == "sec-fetch-mode"] == ["Sec-Fetch-Mode"]
        assert headers["Sec-Fetch-Mode"] == "cors"

    # A page load keeps the navigation headers curl_cffi sends, since that is what a browser sends for one
    def test_a_page_load_keeps_the_navigation_headers(self, im_module):
        headers = im_module.curl_cffi_request_headers("GET", "https://www.instagram.com/", {"authority": "www.instagram.com", "Origin": "https://www.instagram.com"}, False, "chrome")

        assert headers == {}

    # The legacy __a=1 form of a web endpoint is a background request too
    def test_the_legacy_json_query_counts_as_a_background_request(self, im_module):
        headers = im_module.curl_cffi_request_headers("GET", "https://www.instagram.com/explore/locations/1/?__a=1&__d=dis", {}, False, "chrome")

        assert headers["Sec-Fetch-Mode"] == "cors"

    # Requests outside Instagram's web app keep exactly the headers they were given
    @pytest.mark.parametrize("url", ["https://i.instagram.com/api/v1/users/1/info/", "https://scontent.cdninstagram.com/v/t51/pic.jpg"])
    def test_other_hosts_are_left_alone(self, im_module, url):
        sent = {"authority": "x", "Content-Length": "0", "Accept-Encoding": "gzip, deflate"}

        assert im_module.curl_cffi_request_headers("GET", url, sent, False, "chrome") == sent

    # The priority header is set only for targets curl_cffi sends one for, matching what each target does on the wire
    @pytest.mark.parametrize("target, sends", [("chrome", True), ("chrome_android", True), ("chrome124", True), ("chrome131_android", True), ("chrome133a", True), ("chrome123", False), ("chrome99_android", False), ("edge", False), ("edge101", False), ("firefox", False), ("safari", False)])
    def test_the_priority_header_follows_the_target(self, im_module, target, sends):
        headers = im_module.curl_cffi_request_headers("GET", self.REST, {}, False, target)

        assert im_module.impersonates_chrome_priority(target) is sends
        assert ("priority" in headers) is sends

    # On the wire the navigation-only headers are gone and curl_cffi's own encodings are offered and decoded
    def test_the_wire_carries_the_background_request_headers(self, im_module, monkeypatch, keepalive_server):
        base, seen = keepalive_server
        monkeypatch.setattr(im_module, "INSTAGRAM_WEB_HOSTS", frozenset({"127.0.0.1"}))
        session = _adapter_session(im_module)
        session.headers.update({"authority": "www.instagram.com", "scheme": "https", "Accept-Encoding": "gzip, deflate", "Content-Length": "0", "Origin": "https://www.instagram.com"})

        response = session.get(f"{base}/api/v1/gzip", timeout=10)

        assert response.json() == {"status": "ok"}
        received = seen[-1][1]
        for absent in ("Sec-Fetch-User", "Upgrade-Insecure-Requests", "authority", "scheme", "Content-Length", "Origin"):
            assert absent not in received, absent
        assert received["Sec-Fetch-Mode"] == "cors" and received["Sec-Fetch-Site"] == "same-origin"
        assert "zstd" in received["Accept-Encoding"]
        assert "sec-ch-ua" in received

