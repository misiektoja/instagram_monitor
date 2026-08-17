"""Offline tests for bounded atomic media downloads."""

import tempfile
from pathlib import Path


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
