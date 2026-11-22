"""Offline tests for bounded atomic media downloads."""

import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / "local" / "test_artifacts" / "media_downloads"


class FakeMediaResponse:
    # Builds a deterministic streamed response for media download tests
    def __init__(self, status_code=200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.chunks = list(chunks or [])
        self.closed = False

    # Yields configured response chunks without contacting a server
    def iter_content(self, chunk_size):
        yield from self.chunks

    # Records that the downloader released the response
    def close(self):
        self.closed = True


class TestMediaDownloads:
    # A valid image replaces the destination only after the full stream is validated
    def test_valid_image_atomically_replaces_existing_file(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"\xff\xd8\xff\xe0" + (b"image-data" * 4) + b"\xff\xd9"
        response = FakeMediaResponse(headers={"content-type": "image/jpeg", "content-length": str(len(payload))}, chunks=[payload[:8], b"", payload[8:]])
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: response)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            destination = Path(directory_name) / "photo.jpg"
            destination.write_bytes(b"old-data")

            assert im_module.save_pic_video("https://cdninstagram.com/photo.jpg", str(destination), 1710000000) is True
            assert destination.read_bytes() == payload
            assert int(destination.stat().st_mtime) == 1710000000
            assert not list(destination.parent.glob(".*.tmp"))
        assert response.closed is True

    # AVIF images use an ISO media container but remain valid image downloads
    def test_avif_image_signature_is_accepted(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"\x00\x00\x00\x18ftypavif\x00\x00\x00\x00avifmif1"
        response = FakeMediaResponse(headers={"content-type": "image/avif", "content-length": str(len(payload))}, chunks=[payload])
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: response)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            destination = Path(directory_name) / "photo.avif"

            assert im_module.save_pic_video("https://cdninstagram.com/photo.avif", str(destination)) is True
            assert destination.read_bytes() == payload

    # A non-200 success code cannot erase or replace an existing destination
    def test_no_content_response_preserves_existing_file(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        response = FakeMediaResponse(status_code=204, headers={"content-type": "image/jpeg"})
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: response)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            destination = Path(directory_name) / "photo.jpg"
            destination.write_bytes(b"old-data")

            assert im_module.save_pic_video("https://cdninstagram.com/photo.jpg", str(destination)) is False
            assert destination.read_bytes() == b"old-data"
        assert response.closed is True

    # A truncated stream with a valid header is rejected using its declared length
    def test_truncated_stream_preserves_existing_file_and_removes_temp(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"\xff\xd8\xff\xe0truncated"
        response = FakeMediaResponse(headers={"content-type": "image/jpeg", "content-length": str(len(payload) + 10)}, chunks=[payload])
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: response)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            destination = Path(directory_name) / "photo.jpg"
            destination.write_bytes(b"old-data")

            assert im_module.save_pic_video("https://cdninstagram.com/photo.jpg", str(destination)) is False
            assert destination.read_bytes() == b"old-data"
            assert not list(destination.parent.glob(".*.tmp"))

    # An HTML error body returned with status 200 is rejected as invalid media
    def test_status_200_html_body_is_not_saved_as_media(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"<html>checkpoint</html>"
        response = FakeMediaResponse(headers={"content-type": "text/html", "content-length": str(len(payload))}, chunks=[payload])
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: response)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            destination = Path(directory_name) / "photo.jpg"

            assert im_module.save_pic_video("https://cdninstagram.com/photo.jpg", str(destination)) is False
            assert not destination.exists()
            assert not list(destination.parent.glob(".*.tmp"))

    # A streamed body that crosses the configured cap leaves the old file untouched
    def test_oversized_stream_preserves_existing_file(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"\xff\xd8\xff" + (b"x" * 20)
        response = FakeMediaResponse(headers={"content-type": "image/jpeg"}, chunks=[payload])
        monkeypatch.setattr(im_module, "MEDIA_DOWNLOAD_MAX_BYTES", 8)
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: response)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            destination = Path(directory_name) / "photo.jpg"
            destination.write_bytes(b"old-data")

            assert im_module.save_pic_video("https://cdninstagram.com/photo.jpg", str(destination)) is False
            assert destination.read_bytes() == b"old-data"
            assert not list(destination.parent.glob(".*.tmp"))


class TestMediaDownloadFailureReasons:
    # A refused download names the host and the HTTP status
    def test_refused_download_names_the_status(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: FakeMediaResponse(status_code=403))
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            reason = im_module.download_media("https://scontent.cdninstagram.com/photo.jpg?oh=signature", str(Path(directory_name) / "photo.jpg"))

        assert reason == "scontent.cdninstagram.com answered HTTP 403"

    # A reply that is not media names its content type
    def test_non_media_reply_names_its_content_type(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"<html>checkpoint</html>"
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: FakeMediaResponse(headers={"content-type": "text/html"}, chunks=[payload]))
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            reason = im_module.download_media("https://cdninstagram.com/photo.jpg", str(Path(directory_name) / "photo.jpg"))

        assert reason == "the reply is not an image or video (content type text/html)"

    # A short body names how much arrived
    def test_truncated_download_names_the_byte_counts(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"\xff\xd8\xff\xe0truncated"
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: FakeMediaResponse(headers={"content-type": "image/jpeg", "content-length": str(len(payload) + 10)}, chunks=[payload]))
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            reason = im_module.download_media("https://cdninstagram.com/photo.jpg", str(Path(directory_name) / "photo.jpg"))

        assert reason == f"the download stopped after {len(payload)} of {len(payload) + 10} bytes"

    # A file another process holds, as on Windows, is reported with the operating system error
    def test_locked_destination_names_the_file_error(self, im_module, monkeypatch):
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        payload = b"\xff\xd8\xff\xe0" + b"image-data" + b"\xff\xd9"

        # Fails the final rename the way Windows does while another process has the file open
        def locked_replace(source, destination):
            raise PermissionError(32, "The process cannot access the file because it is being used by another process")

        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: FakeMediaResponse(headers={"content-type": "image/jpeg"}, chunks=[payload]))
        monkeypatch.setattr(im_module.os, "replace", locked_replace)
        with tempfile.TemporaryDirectory(dir=ARTIFACT_ROOT) as directory_name:
            destination = Path(directory_name) / "photo.jpg"
            reason = im_module.download_media("https://cdninstagram.com/photo.jpg", str(destination))
            leftovers = list(destination.parent.glob(".*.tmp"))

        assert reason == "PermissionError: [Errno 32] The process cannot access the file because it is being used by another process"
        assert leftovers == []

    # A connection error drops the signed query string the CDN URL carries
    def test_connection_error_omits_the_signed_query(self, im_module, monkeypatch):
        url = "https://scontent.cdninstagram.com/v/photo.jpg?stp=dst-jpg&oh=00_signature&oe=6B037E49"

        # Raises the error requests gives when the server cannot be reached
        def unreachable(*args, **kwargs):
            raise im_module.req.exceptions.ConnectionError("HTTPSConnectionPool(host='scontent.cdninstagram.com', port=443): Max retries exceeded with url: /v/photo.jpg?stp=dst-jpg&oh=00_signature&oe=6B037E49")

        monkeypatch.setattr(im_module.req, "get", unreachable)
        reason = im_module.download_media(url, str(ARTIFACT_ROOT / "unused.jpg"))

        assert reason == "ConnectionError: HTTPSConnectionPool(host='scontent.cdninstagram.com', port=443): Max retries exceeded with url: /v/photo.jpg"

    # Debug mode prints why a media download failed
    def test_debug_mode_prints_the_failure_reason(self, im_module, monkeypatch, capsys):
        monkeypatch.setattr(im_module, "DEBUG_MODE", True)
        monkeypatch.setattr(im_module.req, "get", lambda *args, **kwargs: FakeMediaResponse(status_code=429))

        assert im_module.save_pic_video("https://scontent.cdninstagram.com/photo.jpg", str(ARTIFACT_ROOT / "unused.jpg")) is False
        assert "scontent.cdninstagram.com answered HTTP 429" in capsys.readouterr().out


class TestShortcodePathSafety:
    # A shortcode from the API reaches a filename, so anything outside its real alphabet is dropped
    @pytest.mark.parametrize("hostile,expected", [
        ("../../etc/passwd", "etcpasswd"),
        ("a/b", "ab"),
        ("..", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
        ("with space", "withspace"),
        ("C:\\evil", "Cevil"),
    ])
    def test_hostile_shortcodes_cannot_steer_a_path(self, im_module, hostile, expected):
        assert im_module.safe_media_shortcode(hostile) == expected

    # A genuine shortcode is preserved so saved media keeps its recognizable name
    @pytest.mark.parametrize("shortcode", ["CyR2f-Ap0Xk", "Bq_1-abcDEF", "abc123"])
    def test_real_shortcodes_are_preserved(self, im_module, shortcode):
        assert im_module.safe_media_shortcode(shortcode) == shortcode

    # An overlong value cannot produce an unbounded filename
    def test_length_is_bounded(self, im_module):
        assert len(im_module.safe_media_shortcode("a" * 500)) == 32
