"""Offline tests for the monitoring restart loop used when live settings change."""

import sys


# Returns the current call depth so a restart can be shown to reuse the caller's frame
def stack_depth() -> int:
    depth = 0
    frame = sys._getframe()
    while frame is not None:
        depth += 1
        frame = frame.f_back
    return depth


class TestMonitorRestartLoop:
    # Repeated live settings changes restart the monitor without consuming stack, so a long dashboard
    # session cannot exhaust the recursion limit the way a re-entrant restart would
    def test_repeated_restarts_do_not_grow_the_stack(self, im_module, monkeypatch):
        depths = []
        remaining = {"restarts": 400}

        def fake_pass(user, csv_file_name, *args, **kwargs):
            depths.append(stack_depth())
            if remaining["restarts"]:
                remaining["restarts"] -= 1
                return im_module._MonitorRestart(csv_file_name, False)
            return "finished"

        monkeypatch.setattr(im_module, "_run_instagram_monitor_pass", fake_pass)

        result = im_module.instagram_monitor_user("target", "out.csv", True, True, True, True, True, False)

        assert result == "finished"
        assert len(depths) == 401
        assert max(depths) == min(depths)

    # A restart re-reads live settings so a pass never resumes with the flags it started with
    def test_restart_refreshes_settings_from_globals(self, im_module, monkeypatch):
        seen = []
        remaining = {"restarts": 1}

        def fake_pass(user, csv_file_name, skip_session, skip_followers, skip_followings, skip_getting_story_details, skip_getting_posts_details, get_more_post_details, wait_for_prev_user=None, signal_loading_complete=None, stop_event=None, user_root_path=None, manual_recheck=False, skip_follow_changes=False):
            seen.append({"csv": csv_file_name, "skip_session": skip_session, "skip_followers": skip_followers, "skip_follow_changes": skip_follow_changes, "manual_recheck": manual_recheck})
            if remaining["restarts"]:
                remaining["restarts"] -= 1
                return im_module._MonitorRestart("refreshed.csv", True)
            return None

        monkeypatch.setattr(im_module, "_run_instagram_monitor_pass", fake_pass)
        monkeypatch.setattr(im_module, "SKIP_SESSION", True)
        monkeypatch.setattr(im_module, "SKIP_FOLLOWERS", True)
        monkeypatch.setattr(im_module, "SKIP_FOLLOW_CHANGES", True)

        im_module.instagram_monitor_user("target", "original.csv", False, False, False, False, False, False, skip_follow_changes=False, manual_recheck=False)

        assert seen[0] == {"csv": "original.csv", "skip_session": False, "skip_followers": False, "skip_follow_changes": False, "manual_recheck": False}
        assert seen[1] == {"csv": "refreshed.csv", "skip_session": True, "skip_followers": True, "skip_follow_changes": True, "manual_recheck": True}
