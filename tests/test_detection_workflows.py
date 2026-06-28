"""Offline tests for user-visible detection workflows."""


class TestCountChangeWorkflows:
    # Post count changes send email, webhook, activity log and return one
    def test_posts_count_change_notifies_and_logs(self, im_module, monkeypatch):
        emails = []
        webhooks = []
        logs = []
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: emails.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        assert im_module.check_posts_counts("target", 7, 5, 60) == 1

        assert emails[0][0][0] == "Instagram user target posts number has changed! (5 -> 7)"
        assert webhooks[0][0][0].endswith("target Posts Count Changed")
        assert webhooks[0][0][1] == "User **target** posts count changed from **5** to **7** (+2)"
        assert webhooks[0][1] == {"color": 0x34495e, "notification_type": "status"}
        assert logs[0][0] == ("Posts changed: 5 -> 7",)
        assert logs[0][1] == {"user": "target", "level": "update"}

    # Unchanged post counts do not send notifications
    def test_posts_count_no_change_is_quiet(self, im_module, monkeypatch):
        emails = []
        webhooks = []
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: emails.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)

        assert im_module.check_posts_counts("target", 5, 5, 60) == 0

        assert emails == []
        assert webhooks == []

    # Reel count changes send status webhooks even when email notifications are disabled
    def test_reels_count_change_sends_webhook_without_email(self, im_module, monkeypatch):
        emails = []
        webhooks = []
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", False)
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: emails.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "print_cur_ts", lambda *args, **kwargs: None)

        assert im_module.check_reels_counts("target", 2, 5, 60) == 1

        assert emails == []
        assert webhooks[0][0][0].endswith("target Reels Count Changed")
        assert webhooks[0][0][1] == "User **target** reels count changed from **5** to **2** (-3)"
        assert webhooks[0][1] == {"color": 0x34495e, "notification_type": "status"}


class TestLeakedCollabWorkflow:
    # New leaked collab posts send email, webhook and dashboard update metadata
    def test_new_leaked_collab_notifies_and_returns_update(self, im_module, monkeypatch):
        emails = []
        webhooks = []
        logs = []
        post = {
            "shortcode": "ABC123",
            "owner": "public_owner",
            "is_video": False,
            "ts": 1710000000,
            "likes": 12,
            "comments": 3,
            "caption": "collab caption",
            "collaborators": ["private_user", "public_owner"],
            "display_url": "https://example.com/thumb.jpg",
        }
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        monkeypatch.setattr(im_module, "DOWNLOAD_THUMBNAILS", False)
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "")
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: emails.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))

        update = im_module.report_leaked_collab_post("private_user", "private_user", post, 300, "", "", None)

        assert update["type"] == "Leaked Collab Post"
        assert update["post_url"] == "https://www.instagram.com/p/ABC123/"
        assert update["caption"] == "collab caption"
        assert emails[0][0][0] == "Instagram private user private_user has a leaked collab post - Sat 09 Mar 16:00"
        assert webhooks[0][0][0].endswith("private_user Leaked Collab Post")
        assert webhooks[0][1]["notification_type"] == "status"
        assert webhooks[0][1]["image_url"] == "https://example.com/thumb.jpg"
        assert any(field["name"] == "Collaborators" for field in webhooks[0][1]["fields"])
        assert logs[0][0] == ("Leaked collab post detected",)
        assert logs[0][1] == {"user": "private_user", "level": "update", "details": {"url": "https://www.instagram.com/p/ABC123/"}}

    # Startup leaked collab baseline returns an update without sending notifications
    def test_startup_leaked_collab_baseline_is_quiet(self, im_module, monkeypatch):
        emails = []
        webhooks = []
        post = {"shortcode": "XYZ789", "owner": "public_owner", "is_video": True, "ts": 1710000000, "caption": ""}
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        monkeypatch.setattr(im_module, "DOWNLOAD_THUMBNAILS", False)
        monkeypatch.setattr(im_module, "STATUS_NOTIFICATION", True)
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "")
        monkeypatch.setattr(im_module, "send_email", lambda *args, **kwargs: emails.append((args, kwargs)) or 0)
        monkeypatch.setattr(im_module, "send_webhook", lambda *args, **kwargs: webhooks.append((args, kwargs)) or 0)

        update = im_module.report_leaked_collab_post("private_user", "private_user", post, 300, "", "", None, is_new=False)

        assert update["type"] == "Leaked Collab Reel"
        assert update["caption"] == "(empty)"
        assert emails == []
        assert webhooks == []
