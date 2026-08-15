"""Tests for the offline follow relationship analysis (--analyze-follows).

The analysis reads the already-saved follower/following JSON lists and never
touches the network. These tests write temporary list files and assert on the
computed sets, the handling of missing/corrupt/partial data and the CLI output.
"""

import json
from pathlib import Path


# Writes a saved follow list file in the tool's [count, [usernames...]] format
def _write_list(path, usernames, count=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [len(usernames) if count is None else count, list(usernames)]
    path.write_text(json.dumps(payload), encoding="utf-8")


# Points OUTPUT_DIR at a temp dir and writes followers/followings lists for a user, returning the analysis
def _analyze(im_module, monkeypatch, tmp_path, user, followers, followings, followers_count=None, followings_count=None, is_multi=False):
    monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
    followers_file, followings_file = im_module.get_follow_list_paths(user, is_multi)
    if followers is not None:
        _write_list(followers_file, followers, followers_count)
    if followings is not None:
        _write_list(followings_file, followings, followings_count)
    return im_module.analyze_follows_for_user(user, is_multi)


class TestGetFollowListPaths:
    # Without OUTPUT_DIR the lists resolve to bare filenames in the working directory
    def test_paths_without_output_dir(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "", raising=False)
        followers_file, followings_file = im_module.get_follow_list_paths("alice")
        assert followers_file == "instagram_alice_followers.json"
        assert followings_file == "instagram_alice_followings.json"

    # A single monitored target stores its lists directly under OUTPUT_DIR/json
    def test_paths_with_output_dir_single_target(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "/data", raising=False)
        followers_file, followings_file = im_module.get_follow_list_paths("alice")
        assert followers_file.replace("\\", "/") == "/data/json/instagram_alice_followers.json"
        assert followings_file.replace("\\", "/") == "/data/json/instagram_alice_followings.json"

    # Several monitored targets nest their lists under OUTPUT_DIR/<user>/json
    def test_paths_with_output_dir_multiple_targets(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "/data", raising=False)
        followers_file, followings_file = im_module.get_follow_list_paths("alice", is_multi=True)
        assert followers_file.replace("\\", "/") == "/data/alice/json/instagram_alice_followers.json"
        assert followings_file.replace("\\", "/") == "/data/alice/json/instagram_alice_followings.json"


class TestAnalyzeFollowsForUser:
    def test_computes_mutual_not_following_back_and_fans(self, im_module, monkeypatch, tmp_path):
        result = _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["bob", "carol", "dave"],
            followings=["carol", "dave", "erin"],
        )
        assert result["available"] is True
        assert result["mutual"] == ["carol", "dave"]
        assert result["mutual_count"] == 2
        # followings - followers: alice follows erin, erin does not follow back
        assert result["not_following_back"] == ["erin"]
        # followers - followings: bob follows alice, alice does not follow back
        assert result["fans"] == ["bob"]

    def test_lists_are_sorted(self, im_module, monkeypatch, tmp_path):
        result = _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["zoe", "amy"],
            followings=[],
        )
        assert result["fans"] == ["amy", "zoe"]

    def test_empty_lists_analyze_to_empty_categories(self, im_module, monkeypatch, tmp_path):
        result = _analyze(im_module, monkeypatch, tmp_path, "alice", followers=[], followings=[])
        assert result["available"] is True
        assert result["mutual"] == []
        assert result["not_following_back"] == []
        assert result["fans"] == []

    # Lists saved while a different number of targets was monitored still resolve
    def test_falls_back_to_the_other_output_dir_layout(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        multi_followers, multi_followings = im_module.get_follow_list_paths("alice", is_multi=True)
        _write_list(multi_followers, ["bob", "carol"])
        _write_list(multi_followings, ["carol"])
        # Asked for the single-target layout, but only the per-user layout holds lists
        result = im_module.analyze_follows_for_user("alice", is_multi=False)
        assert result["available"] is True
        assert result["mutual"] == ["carol"]
        assert result["fans"] == ["bob"]

    def test_missing_files_report_note_and_are_unavailable(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        result = im_module.analyze_follows_for_user("ghost")
        assert result["available"] is False
        assert result["not_following_back"] == []
        assert result["fans"] == []
        assert any("Run the monitor once" in note for note in result["notes"])

    def test_one_missing_file_is_still_unavailable(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        followers_file, _ = im_module.get_follow_list_paths("alice")
        _write_list(followers_file, ["bob"])
        result = im_module.analyze_follows_for_user("alice")
        assert result["available"] is False
        assert any("followings" in note for note in result["notes"])

    def test_corrupt_file_reports_note_and_is_unavailable(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        followers_file, followings_file = im_module.get_follow_list_paths("alice")
        _write_list(followings_file, ["bob"])
        Path(followers_file).write_text("{ not valid json", encoding="utf-8")
        result = im_module.analyze_follows_for_user("alice")
        assert result["available"] is False
        assert any("unreadable or malformed" in note for note in result["notes"])

    def test_unexpected_json_shape_is_treated_as_corrupt(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        followers_file, followings_file = im_module.get_follow_list_paths("alice")
        _write_list(followings_file, ["bob"])
        Path(followers_file).write_text(json.dumps({"followers": ["bob"]}), encoding="utf-8")
        result = im_module.analyze_follows_for_user("alice")
        assert result["available"] is False
        assert any("unreadable or malformed" in note for note in result["notes"])

    def test_partial_list_reports_note_but_still_analyzes(self, im_module, monkeypatch, tmp_path):
        # Reported count (500) is larger than the saved handles (private / interrupted download)
        result = _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["bob", "carol"], followers_count=500,
            followings=["carol"],
        )
        assert result["available"] is True
        assert result["fans"] == ["bob"]
        assert any("partial" in note for note in result["notes"])

    def test_result_is_json_serializable(self, im_module, monkeypatch, tmp_path):
        result = _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["bob"],
            followings=["carol"],
        )
        # The Web Dashboard endpoint returns this dict straight to jsonify()
        assert json.loads(json.dumps(result))["user"] == "alice"


class TestRunFollowAnalysis:
    def test_prints_analysis_and_returns_zero(self, im_module, monkeypatch, tmp_path, capsys):
        _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["bob", "carol", "dave"],
            followings=["carol", "dave", "erin"],
        )
        rc = im_module.run_follow_analysis(["alice"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Target: alice" in out
        assert "Not following back (1)" in out
        assert "erin" in out
        assert "Fans (1)" in out
        assert "bob" in out
        # Profile links help the reader open the accounts straight from the output
        assert "https://www.instagram.com/erin/" in out

    def test_no_targets_returns_nonzero(self, im_module, capsys):
        rc = im_module.run_follow_analysis([])
        out = capsys.readouterr().out
        assert rc == 1
        assert "No target specified" in out

    def test_missing_data_target_returns_nonzero(self, im_module, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        rc = im_module.run_follow_analysis(["ghost"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "Run the monitor once" in out

    # Standalone actions print before stdout is wrapped, so masking has to happen at the point of display
    def test_privacy_substitutions_mask_handles_and_links(self, im_module, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("erin", "REDACTED")], raising=False)
        _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["bob"],
            followings=["erin"],
        )
        im_module.run_follow_analysis(["alice"])
        out = capsys.readouterr().out
        assert "erin" not in out
        assert "REDACTED" in out

    # One unusable target must not hide the targets that do have saved lists
    def test_mixed_targets_still_report_the_usable_one(self, im_module, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        followers_file, followings_file = im_module.get_follow_list_paths("alice", is_multi=True)
        _write_list(followers_file, ["bob"])
        _write_list(followings_file, ["carol"])
        rc = im_module.run_follow_analysis(["alice", "ghost"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Target: alice" in out
        assert "Target: ghost" in out
        assert "Run the monitor once" in out
