"""Tests for follower/following diffing, logging and CSV side effects.

compare_and_log_follower_changes prints and logs as a side effect; those are
captured/ignored here. We assert on its returned formatting strings and on the
CSV rows it writes.
"""

import csv

import pytest


def _run(im_module, capsys, **kwargs):
    result = im_module.compare_and_log_follower_changes(**kwargs)
    capsys.readouterr()  # swallow the console output the function prints
    return result


class TestCompareAndLogFollowerChanges:
    def test_no_change_returns_all_empty(self, im_module, capsys):
        result = _run(im_module, capsys, user="u", change_type="followers", old_list=["a", "b"], new_list=["a", "b"], csv_file_name="")
        assert all(s == "" for s in result)

    def test_single_addition(self, im_module, capsys):
        added_list, removed_list, _, _, added_webhook, removed_webhook, *_ = _run(im_module, capsys, user="u", change_type="followers", old_list=["a", "b"], new_list=["a", "b", "c"], csv_file_name="")
        assert "c" in added_list
        assert "https://www.instagram.com/c/" in added_list
        assert removed_list == ""
        assert "c" in added_webhook
        assert removed_webhook == ""

    def test_single_removal(self, im_module, capsys):
        added_list, removed_list, *_ = _run(im_module, capsys, user="u", change_type="followings", old_list=["a", "b"], new_list=["a"], csv_file_name="")
        assert added_list == ""
        assert "b" in removed_list

    def test_webhook_text_escapes_markdown(self, im_module, capsys):
        # Usernames with markdown-significant chars must be escaped in the webhook variant
        result = _run(im_module, capsys, user="u", change_type="followers", old_list=[], new_list=["a_b"], csv_file_name="")
        added_webhook = result[4]
        assert r"a\_b" in added_webhook

    # Added and removed usernames keep the order from their source lists
    def test_diff_output_preserves_source_order(self, im_module, capsys):
        added_list, removed_list, *_ = _run(im_module, capsys, user="u", change_type="followers", old_list=["keep", "drop_b", "drop_a"], new_list=["join_b", "keep", "join_a"], csv_file_name="")
        assert removed_list.index("drop_b") < removed_list.index("drop_a")
        assert added_list.index("join_b") < added_list.index("join_a")

    # Duplicate usernames in source data are reported once while preserving first-seen order
    def test_diff_output_deduplicates_source_duplicates(self, im_module, capsys):
        added_list, removed_list, *_ = _run(im_module, capsys, user="u", change_type="followers", old_list=["keep", "drop", "drop"], new_list=["join", "join", "keep"], csv_file_name="")
        assert removed_list.count("- drop ") == 1
        assert added_list.count("- join ") == 1

    def test_writes_csv_rows(self, im_module, capsys, tmp_path, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        csv_path = str(tmp_path / "follow.csv")
        _run(im_module, capsys, user="u", change_type="followers", old_list=["keep", "drop"], new_list=["keep", "join"], csv_file_name=csv_path)
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert [r[1] for r in rows[1:]] == ["Removed Followers", "Added Followers"]
        # The added username lands in New and the removed one lands in Old
        assert rows[1][2] == "drop"
        assert rows[2][3] == "join"


class TestShouldNotifyFollowChange:
    # Complete comparisons suppress count-only noise while unavailable or partial comparisons preserve count alerts
    @pytest.mark.parametrize("count_changed,added_list,removed_list,list_comparison_complete,expected", [(True, "", "", True, False), (False, "", "", True, False), (True, "", "", False, True), (False, "- joined", "", True, True), (False, "", "- left", True, True), (False, "- joined", "", False, True), (False, "", "", False, False)])
    def test_notification_evidence(self, im_module, count_changed, added_list, removed_list, list_comparison_complete, expected):
        assert im_module.should_notify_follow_change(count_changed, added_list, removed_list, list_comparison_complete) is expected


class TestFollowerListChangeReporting:
    # A churn change with an unchanged total is reported, which the previous ordering made unreachable
    def test_list_change_with_unchanged_count_is_reported(self, im_module, monkeypatch, tmp_path):
        logged = []
        monkeypatch.setattr(im_module, "log_activity", lambda message, **kwargs: logged.append(message))

        added, removed, *_ = im_module.compare_and_log_follower_changes("target", "followers", ["alice", "bob"], ["alice", "carol"], "")

        assert added and removed
        # The report guard reads exactly these values, so a same-count churn now satisfies it
        assert bool(added or removed) is True
        assert any("Removed follower: bob" in entry for entry in logged)
        assert any("Added follower: carol" in entry for entry in logged)
