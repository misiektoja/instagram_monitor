"""Offline tests for profile picture change workflows."""

import csv
import os
import uuid
from pathlib import Path


# Returns an isolated local artifact directory for one profile picture workflow test
def _profile_picture_artifact_dir() -> Path:
    artifact_dir = Path("local") / "test_artifacts" / "profile_picture_workflows" / uuid.uuid4().hex
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


# Writes bytes to a file and pins its modification time
def _write_payload(path: Path, payload: bytes, timestamp: int) -> None:
    path.write_bytes(payload)
    os.utime(path, (timestamp, timestamp))


# Returns rows from a CSV file using the monitor's expected encoding
def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.reader(csv_file))


# Disables optional terminal rendering and noisy output for profile picture tests
def _patch_quiet_output(im_module, monkeypatch) -> None:
    monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False, raising=False)
    monkeypatch.setattr(im_module, "RICH_AVAILABLE", False, raising=False)
    monkeypatch.setattr(im_module, "imgcat_exe", "", raising=False)
    monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)


class TestProfilePictureWorkflows:
    # Missing profile pictures are saved, copied and recorded in CSV
    def test_initial_profile_picture_download_writes_csv_and_copy(self, im_module, monkeypatch):
        artifact_dir = _profile_picture_artifact_dir()
        profile_pic = artifact_dir / "profile.jpg"
        csv_path = artifact_dir / "events.csv"
        saved_at = 1710000000
        logs = []
        _patch_quiet_output(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))
        monkeypatch.setattr(im_module, "save_pic_video", lambda url, file_name, custom_mdate_ts=0: _write_payload(Path(file_name), b"initial", saved_at) is None)

        im_module.detect_changed_profile_picture("target", "https://example.com/profile.jpg", str(profile_pic), str(artifact_dir / "profile.tmp.jpg"), str(artifact_dir / "profile.old.jpg"), "", str(csv_path), 60, False, 1)

        copied_files = list(artifact_dir.glob("instagram_target_profile_pic_20240309_1600.jpg"))
        rows = _read_csv_rows(csv_path)
        assert profile_pic.read_bytes() == b"initial"
        assert copied_files and copied_files[0].read_bytes() == b"initial"
        assert rows[1][1] == "Profile Picture Created"
        assert rows[1][2] == ""
        assert logs[0][0] == ("Profile picture saved",)
        assert logs[0][1] == {"user": "target", "level": "update"}

    # Existing profile picture changes replace current, preserve old and notify status channels
    def test_changed_profile_picture_moves_files_and_notifies(self, im_module, monkeypatch):
        artifact_dir = _profile_picture_artifact_dir()
        profile_pic = artifact_dir / "profile.jpg"
        profile_pic_tmp = artifact_dir / "profile.tmp.jpg"
        profile_pic_old = artifact_dir / "profile.old.jpg"
        csv_path = artifact_dir / "events.csv"
        emails = []
        webhooks = []
        logs = []
        _write_payload(profile_pic, b"old-picture", 1700000000)
        _patch_quiet_output(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "RECEIVER_EMAIL", "receiver@example.com", raising=False)
        monkeypatch.setattr(im_module, "SMTP_SSL", True, raising=False)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: emails.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "save_pic_video", lambda url, file_name, custom_mdate_ts=0: _write_payload(Path(file_name), b"new-picture", 1710000000) is None)

        im_module.detect_changed_profile_picture("target", "https://example.com/profile.jpg", str(profile_pic), str(profile_pic_tmp), str(profile_pic_old), "", str(csv_path), 60, True, 1)

        rows = _read_csv_rows(csv_path)
        assert profile_pic.read_bytes() == b"new-picture"
        assert profile_pic_old.read_bytes() == b"old-picture"
        assert rows[1][1] == "Profile Picture Changed"
        assert rows[1][2] != ""
        assert rows[1][3] != ""
        assert logs[0][0] == ("Profile picture changed",)
        assert logs[0][1] == {"user": "target"}
        assert emails[0][0][0].startswith("Instagram user target has changed profile picture")
        assert webhooks[0][0][0].endswith("target Profile Picture Changed")
        assert webhooks[0][1]["local_image_file"] == str(profile_pic)
        assert webhooks[0][1]["notification_type"] == "status"

    # Empty-template transitions detect profile picture removal without attaching an image
    def test_removed_profile_picture_records_removal_without_image(self, im_module, monkeypatch):
        artifact_dir = _profile_picture_artifact_dir()
        profile_pic = artifact_dir / "profile.jpg"
        profile_pic_tmp = artifact_dir / "profile.tmp.jpg"
        profile_pic_old = artifact_dir / "profile.old.jpg"
        empty_template = artifact_dir / "empty.jpg"
        csv_path = artifact_dir / "events.csv"
        webhooks = []
        logs = []
        _write_payload(profile_pic, b"old-picture", 1700000000)
        _write_payload(empty_template, b"empty-template", 1690000000)
        _patch_quiet_output(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "save_pic_video", lambda url, file_name, custom_mdate_ts=0: _write_payload(Path(file_name), b"empty-template", 1710000000) is None)

        im_module.detect_changed_profile_picture("target", "https://example.com/profile.jpg", str(profile_pic), str(profile_pic_tmp), str(profile_pic_old), str(empty_template), str(csv_path), 60, False, 1)

        rows = _read_csv_rows(csv_path)
        assert profile_pic.read_bytes() == b"empty-template"
        assert profile_pic_old.read_bytes() == b"old-picture"
        assert rows[1][1] == "Profile Picture Removed"
        assert rows[1][2] != ""
        assert rows[1][3] == ""
        assert logs[0][0] == ("Profile picture removed",)
        assert logs[0][1] == {"user": "target"}
        assert webhooks[0][0][0].endswith("target Profile Picture Removed")
        assert "local_image_file" not in webhooks[0][1]
        assert webhooks[0][1]["notification_type"] == "status"

    # Empty-template transitions detect a newly set profile picture with image attachment metadata
    def test_empty_profile_picture_becomes_set_picture(self, im_module, monkeypatch):
        artifact_dir = _profile_picture_artifact_dir()
        profile_pic = artifact_dir / "profile.jpg"
        profile_pic_tmp = artifact_dir / "profile.tmp.jpg"
        profile_pic_old = artifact_dir / "profile.old.jpg"
        empty_template = artifact_dir / "empty.jpg"
        csv_path = artifact_dir / "events.csv"
        webhooks = []
        logs = []
        _write_payload(profile_pic, b"empty-template", 1700000000)
        _write_payload(empty_template, b"empty-template", 1690000000)
        _patch_quiet_output(im_module, monkeypatch)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "save_pic_video", lambda url, file_name, custom_mdate_ts=0: _write_payload(Path(file_name), b"new-picture", 1710000000) is None)

        im_module.detect_changed_profile_picture("target", "https://example.com/profile.jpg", str(profile_pic), str(profile_pic_tmp), str(profile_pic_old), str(empty_template), str(csv_path), 60, False, 1)

        rows = _read_csv_rows(csv_path)
        assert profile_pic.read_bytes() == b"new-picture"
        assert not profile_pic_old.exists()
        assert rows[1][1] == "Profile Picture Created"
        assert rows[1][2] == ""
        assert rows[1][3] != ""
        assert logs[0][0] == ("Profile picture set",)
        assert logs[0][1] == {"user": "target"}
        assert webhooks[0][0][0].endswith("target Profile Picture Set")
        assert webhooks[0][1]["local_image_file"] == str(profile_pic)
        assert webhooks[0][1]["notification_type"] == "status"
