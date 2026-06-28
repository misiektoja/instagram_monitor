"""Offline tests for story detection workflows."""

import csv
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


# Returns an isolated local artifact directory for one story workflow test
def _story_artifact_dir() -> Path:
    artifact_dir = Path("local") / "test_artifacts" / "story_workflows" / uuid.uuid4().hex
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


# Returns rows from a CSV file using the monitor's expected encoding
def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.reader(csv_file))


# Applies deterministic monitor settings for a startup-only story workflow run
def _patch_startup_monitor_defaults(im_module, monkeypatch) -> None:
    monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC", raising=False)
    monkeypatch.setattr(im_module, "SESSION_USERNAME", "", raising=False)
    monkeypatch.setattr(im_module, "NEXT_OPERATION_DELAY", 0, raising=False)
    monkeypatch.setattr(im_module, "INSTA_CHECK_INTERVAL", 1, raising=False)
    monkeypatch.setattr(im_module, "RANDOM_SLEEP_DIFF_LOW", 0, raising=False)
    monkeypatch.setattr(im_module, "RANDOM_SLEEP_DIFF_HIGH", 0, raising=False)
    monkeypatch.setattr(im_module, "DETECT_CHANGED_PROFILE_PIC", False, raising=False)
    monkeypatch.setattr(im_module, "DOWNLOAD_THUMBNAILS", False, raising=False)
    monkeypatch.setattr(im_module, "DETECT_COLLAB_POSTS", False, raising=False)
    monkeypatch.setattr(im_module, "FOLLOWERS_CHURN_DETECTION", False, raising=False)
    monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False, raising=False)
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False, raising=False)
    monkeypatch.setattr(im_module, "RICH_AVAILABLE", False, raising=False)
    monkeypatch.setattr(im_module, "PROXY_ENABLED", False, raising=False)
    monkeypatch.setattr(im_module, "HOURS_VERBOSE", False, raising=False)
    monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "update_check_times", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "get_dashboard_config_data", lambda: {})
    monkeypatch.setattr(im_module, "randomize_number", lambda value, low, high: value)
    monkeypatch.setattr(im_module, "compute_next_check_with_hours_range", lambda now, sleep_time: (sleep_time, now))
    monkeypatch.setattr(im_module, "refresh_proxy_if_needed", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module.time, "sleep", lambda seconds: None)


class TestStoryWorkflows:
    # Startup story loading writes one CSV row and publishes last story dashboard metadata
    def test_startup_story_item_writes_csv_and_ui_update(self, im_module, monkeypatch):
        artifact_dir = _story_artifact_dir()
        csv_path = artifact_dir / "events.csv"
        updates = []
        story_item = SimpleNamespace(
            date_utc=datetime(2024, 3, 9, 16, 0, tzinfo=timezone.utc),
            expiring_utc=datetime(2024, 3, 10, 16, 0, tzinfo=timezone.utc),
            typename="GraphStoryImage",
            caption="story caption",
            caption_mentions=["friend"],
            caption_hashtags=["tag"],
            url="https://example.com/story.jpg",
            video_url="",
        )
        story = SimpleNamespace(itemcount=1, get_items=lambda: iter([story_item]))
        context = SimpleNamespace(is_logged_in=True, iphone_headers={}, _session=SimpleNamespace(request=lambda *args, **kwargs: None))
        fake_bot = SimpleNamespace(context=context, get_stories=lambda userids: iter([story]))
        fake_profile = SimpleNamespace(username="target", userid=123, followers=0, followees=0, biography="bio", is_private=False, followed_by_viewer=False, mediacount=0, profile_pic_url_no_iphone="https://example.com/profile.jpg", has_public_story=True)
        stop_event = threading.Event()
        stop_event.set()
        _patch_startup_monitor_defaults(im_module, monkeypatch)
        monkeypatch.setattr(im_module.instaloader, "Instaloader", lambda *args, **kwargs: fake_bot)
        monkeypatch.setattr(im_module.instaloader.Profile, "own_profile", lambda ctx: SimpleNamespace(username="session_user"))
        monkeypatch.setattr(im_module, "profile_from_username_resilient", lambda bot, username: fake_profile)
        monkeypatch.setattr(im_module, "get_total_reels_count", lambda user, bot, skip_session=False: 0)
        monkeypatch.setattr(im_module, "update_ui_data", lambda *args, **kwargs: updates.append((args, kwargs)))

        im_module.instagram_monitor_user("target", str(csv_path), skip_session=False, skip_followers=True, skip_followings=True, skip_getting_story_details=False, skip_getting_posts_details=True, get_more_post_details=False, stop_event=stop_event, user_root_path=str(artifact_dir), skip_follow_changes=True)

        rows = _read_csv_rows(csv_path)
        story_updates = [call for call in updates if call[1].get("targets", {}).get("target", {}).get("last_story")]
        last_story = story_updates[-1][1]["targets"]["target"]["last_story"]
        assert rows[1] == ["2024-03-09 16:00:00", "New Story Item", "", "Image"]
        assert last_story["type"] == "Image"
        assert last_story["caption"] == "story caption"
        assert last_story["url"] == "https://example.com/story.jpg"
        assert last_story["post_url"] == "https://www.instagram.com/stories/target/"
        assert last_story["timestamp_ts"] == 1710000000
