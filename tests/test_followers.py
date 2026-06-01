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

    def test_writes_csv_rows(self, im_module, capsys, tmp_path, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        csv_path = str(tmp_path / "follow.csv")
        _run(im_module, capsys, user="u", change_type="followers", old_list=["keep", "drop"], new_list=["keep", "join"], csv_file_name=csv_path)
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        types = {r[1] for r in rows[1:]}
        assert "Added Followers" in types
        assert "Removed Followers" in types
        # The added username lands in the New column, the removed one in the Old column
        added_rows = [r for r in rows[1:] if r[1] == "Added Followers"]
        removed_rows = [r for r in rows[1:] if r[1] == "Removed Followers"]
        assert added_rows[0][3] == "join"
        assert removed_rows[0][2] == "drop"
