"""Tests for CSV initialization/writing and byte-wise image comparison (filesystem only)."""

import csv
import os

import pytest


class TestInitCsvFile:
    def test_creates_file_with_header(self, im_module, tmp_path):
        csv_path = str(tmp_path / "out.csv")
        im_module.init_csv_file(csv_path)
        assert os.path.isfile(csv_path)
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["Date", "Type", "Old", "New"]

    def test_creates_missing_parent_directories(self, im_module, tmp_path):
        csv_path = str(tmp_path / "nested" / "deep" / "out.csv")
        im_module.init_csv_file(csv_path)
        assert os.path.isfile(csv_path)

    def test_does_not_overwrite_existing_content(self, im_module, tmp_path):
        csv_path = tmp_path / "out.csv"
        csv_path.write_text("EXISTING DATA\n", encoding="utf-8")
        im_module.init_csv_file(str(csv_path))
        assert csv_path.read_text(encoding="utf-8") == "EXISTING DATA\n"

    def test_reheaders_empty_file(self, im_module, tmp_path):
        csv_path = tmp_path / "out.csv"
        csv_path.write_text("", encoding="utf-8")
        im_module.init_csv_file(str(csv_path))
        assert csv_path.read_text(encoding="utf-8").startswith('"Date"')


class TestWriteCsvEntry:
    def test_lazily_creates_and_appends(self, im_module, tmp_path):
        csv_path = str(tmp_path / "out.csv")
        im_module.write_csv_entry(csv_path, "2024-01-01 10:00:00", "New Post", "", "https://example/p/1")
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["Date", "Type", "Old", "New"]
        assert rows[1] == ["2024-01-01 10:00:00", "New Post", "", "https://example/p/1"]

    def test_multiple_entries_accumulate(self, im_module, tmp_path):
        csv_path = str(tmp_path / "out.csv")
        im_module.write_csv_entry(csv_path, "t1", "Added Followers", "", "alice")
        im_module.write_csv_entry(csv_path, "t2", "Removed Followers", "bob", "")
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 3  # header + 2 entries
        assert rows[1][1] == "Added Followers"
        assert rows[2][3] == ""


class TestReportLeakedCollabPost:
    def test_new_detection_writes_csv_and_returns_dashboard_update(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "DOWNLOAD_THUMBNAILS", False)
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "WEBHOOK_ENABLED", False)
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "")
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
        csv_path = str(tmp_path / "collab.csv")
        post = {"shortcode": "ABC123", "owner": "public_owner", "is_video": False, "ts": 1710000000, "likes": 12, "comments": 3, "caption": "collab caption", "collaborators": ["private_user"], "display_url": "https://example.com/thumb.jpg"}

        update = im_module.report_leaked_collab_post("private_user", "private_user", post, 300, "", "", None, csv_file_name=csv_path)

        assert update["type"] == "Leaked Collab Post"
        assert update["caption"] == "collab caption"
        assert update["post_url"] == "https://www.instagram.com/p/ABC123/"
        assert update["timestamp_ts"] == 1710000000
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[1] == ["2024-03-09 16:00:00", "New Leaked Collab Post", "", "collab caption"]

    def test_startup_baseline_returns_update_without_csv(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "DOWNLOAD_THUMBNAILS", False)
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "")
        csv_path = str(tmp_path / "collab.csv")
        post = {"shortcode": "XYZ789", "owner": "public_owner", "is_video": True, "ts": 1710000000, "caption": "", "display_url": "https://example.com/thumb.jpg"}

        update = im_module.report_leaked_collab_post("private_user", "private_user", post, 0, "", "", None, is_new=False, csv_file_name=csv_path)

        assert update["type"] == "Leaked Collab Reel"
        assert update["caption"] == "(empty)"
        assert update["post_url"] == "https://www.instagram.com/reel/XYZ789/"
        assert not os.path.exists(csv_path)


class TestCompareImages:
    def test_identical_files_match(self, im_module, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        payload = b"\x89PNG\r\n" + b"binary-content" * 100
        a.write_bytes(payload)
        b.write_bytes(payload)
        assert im_module.compare_images(str(a), str(b)) is True

    def test_different_files_do_not_match(self, im_module, tmp_path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"content-one")
        b.write_bytes(b"content-two-different-length")
        assert im_module.compare_images(str(a), str(b)) is False

    def test_missing_file_returns_false(self, im_module, tmp_path):
        a = tmp_path / "a.bin"
        a.write_bytes(b"x")
        assert im_module.compare_images(str(a), str(tmp_path / "missing.bin")) is False
        assert im_module.compare_images(str(tmp_path / "missing.bin"), str(a)) is False

    def test_real_empty_profile_pic_matches_itself(self, im_module):
        # The repo ships an empty-profile-pic template; it must compare equal to itself
        root = os.path.dirname(os.path.abspath(im_module.__file__))
        template = os.path.join(root, "instagram_profile_pic_empty.jpg")
        if not os.path.isfile(template):
            pytest.skip("empty profile pic template not present")
        assert im_module.compare_images(template, template) is True
