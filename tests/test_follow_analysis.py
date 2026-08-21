"""Tests for the offline follow relationship analysis (--analyze-follows).

The analysis reads the already-saved follower/following JSON lists and never
touches the network. These tests write temporary list files and assert on the
computed sets, the handling of missing/corrupt/partial data and the CLI output.
"""

import json
import os
from pathlib import Path

import pytest


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

    # Unsafe path input is rejected before any filesystem path is constructed
    def test_rejects_invalid_username(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", "/data", raising=False)
        with pytest.raises(ValueError, match="Instagram username"):
            im_module.get_follow_list_paths("../victim")


class TestAnalyzeFollowsForUser:
    def test_computes_mutual_not_following_back_and_fans(self, im_module, monkeypatch, tmp_path):
        result = _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["bob", "carol", "dave"],
            followings=["carol", "dave", "erin"],
        )
        assert result["available"] is True
        assert result["mutual_count"] == 2
        # followings - followers: alice follows erin, erin does not follow back
        assert result["not_following_back"] == ["erin"]
        assert result["not_following_back_count"] == 1
        # followers - followings: bob follows alice, alice does not follow back
        assert result["fans"] == ["bob"]
        assert result["fans_count"] == 1

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
        assert result["mutual_count"] == 0
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
        assert result["mutual_count"] == 1
        assert result["fans"] == ["bob"]

    # When both layouts are complete the newer coherent pair wins over the requested layout
    def test_selects_newest_coherent_output_layout(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        flat_followers, flat_followings = im_module.get_follow_list_paths("alice", is_multi=False)
        nested_followers, nested_followings = im_module.get_follow_list_paths("alice", is_multi=True)
        _write_list(flat_followers, ["oldfan"])
        _write_list(flat_followings, [])
        _write_list(nested_followers, ["newfan"])
        _write_list(nested_followings, [])
        os.utime(flat_followers, (100, 100))
        os.utime(flat_followings, (100, 100))
        os.utime(nested_followers, (200, 200))
        os.utime(nested_followings, (200, 200))

        result = im_module.analyze_follows_for_user("alice", is_multi=False)

        assert result["fans"] == ["newfan"]
        assert result["followers_file"] == nested_followers

    # A malformed newer pair does not hide an older complete valid pair
    def test_falls_back_from_corrupt_newer_layout(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        flat_followers, flat_followings = im_module.get_follow_list_paths("alice", is_multi=False)
        nested_followers, nested_followings = im_module.get_follow_list_paths("alice", is_multi=True)
        _write_list(flat_followers, ["validfan"])
        _write_list(flat_followings, [])
        _write_list(nested_followers, ["bad handle"])
        _write_list(nested_followings, [])
        os.utime(flat_followers, (100, 100))
        os.utime(flat_followings, (100, 100))
        os.utime(nested_followers, (200, 200))
        os.utime(nested_followings, (200, 200))

        result = im_module.analyze_follows_for_user("alice", is_multi=True)

        assert result["available"] is True
        assert result["fans"] == ["validfan"]
        assert result["followers_file"] == flat_followers
        assert any("older complete pair" in note for note in result["notes"])

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

    # Invalid list entries are rejected instead of reaching profile links or response HTML
    @pytest.mark.parametrize("entry", ["../victim", "bad handle", 42, None])
    def test_invalid_saved_username_is_treated_as_corrupt(self, im_module, monkeypatch, tmp_path, entry):
        result = _analyze(im_module, monkeypatch, tmp_path, "alice", followers=[entry], followings=[])
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

    # Large differences retain exact totals while bounding serialized member lists
    def test_bounds_relationship_lists_and_preserves_counts(self, im_module, monkeypatch, tmp_path):
        result = _analyze(im_module, monkeypatch, tmp_path, "alice", followers=[f"fan{i}" for i in range(10)], followings=[f"out{i}" for i in range(8)])
        result = im_module.analyze_follows_for_user("alice", list_limit=3)
        assert result["fans"] == ["fan0", "fan1", "fan2"]
        assert result["fans_count"] == 10
        assert result["fans_truncated"] is True
        assert result["not_following_back"] == ["out0", "out1", "out2"]
        assert result["not_following_back_count"] == 8
        assert result["not_following_back_truncated"] is True

    # Snapshot timestamps and material skew are surfaced with the analysis
    def test_reports_snapshot_freshness_and_skew(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        followers_file, followings_file = im_module.get_follow_list_paths("alice")
        _write_list(followers_file, ["bob"])
        _write_list(followings_file, ["bob"])
        os.utime(followers_file, (100, 100))
        os.utime(followings_file, (7300, 7300))

        result = im_module.analyze_follows_for_user("alice")

        assert result["followers_saved_at"] == "1970-01-01T00:01:40+00:00"
        assert result["followings_saved_at"] == "1970-01-01T02:01:40+00:00"
        assert result["snapshot_skew_seconds"] == 7200
        assert any("snapshots are" in note for note in result["notes"])

    def test_result_is_json_serializable(self, im_module, monkeypatch, tmp_path):
        result = _analyze(
            im_module, monkeypatch, tmp_path, "alice",
            followers=["bob"],
            followings=["carol"],
        )
        # The Web Dashboard endpoint returns this dict straight to jsonify()
        assert json.loads(json.dumps(result))["user"] == "alice"


class TestFollowAnalysisDashboard:
    # Creates a Flask client for the repository dashboard template
    def _client(self, im_module, monkeypatch, targets):
        template_dir = str(Path(im_module.__file__).resolve().parent / "templates")
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_TEMPLATE_DIR", template_dir)
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_DATA", {"targets": {target: {} for target in targets}})
        app = im_module.create_web_dashboard_app()
        assert app is not None
        return app.test_client()

    # The endpoint rejects path-like usernames before touching saved files
    def test_rejects_path_traversal_username(self, im_module, monkeypatch):
        client = self._client(im_module, monkeypatch, ["alice"])
        response = client.get("/api/follow-analysis/..%5C..%5Cvictim")
        assert response.status_code == 400

    # The endpoint exposes analysis only for an active configured dashboard target
    def test_rejects_unconfigured_target(self, im_module, monkeypatch):
        client = self._client(im_module, monkeypatch, ["alice"])
        response = client.get("/api/follow-analysis/bob")
        assert response.status_code == 404

    # Privacy substitutions cover the modal identity and local paths stay private
    def test_masks_payload_and_omits_filesystem_paths(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("alice", "MASKED")], raising=False)
        _analyze(im_module, monkeypatch, tmp_path, "alice", followers=["bob"], followings=[])
        client = self._client(im_module, monkeypatch, ["alice"])

        response = client.get("/api/follow-analysis/alice")

        assert response.status_code == 200
        analysis = response.get_json()["analysis"]
        assert analysis["user"] == "MASKED"
        assert "followers_file" not in analysis
        assert "followings_file" not in analysis
        assert "searched_directory" not in analysis

    # Missing-data responses do not reveal the local output directory
    def test_missing_payload_omits_searched_directory(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        client = self._client(im_module, monkeypatch, ["alice"])

        response = client.get("/api/follow-analysis/alice")

        assert response.status_code == 200
        payload = response.get_data(as_text=True)
        assert str(tmp_path) not in payload
        assert "searched_directory" not in response.get_json()["analysis"]

    # The API preserves full totals while bounding each serialized relationship list
    def test_api_bounds_large_relationship_lists(self, im_module, monkeypatch, tmp_path):
        _analyze(im_module, monkeypatch, tmp_path, "alice", followers=[f"fan{i}" for i in range(501)], followings=[])
        client = self._client(im_module, monkeypatch, ["alice"])

        response = client.get("/api/follow-analysis/alice")

        analysis = response.get_json()["analysis"]
        assert response.status_code == 200
        assert analysis["fans_count"] == 501
        assert len(analysis["fans"]) == 500
        assert analysis["fans_truncated"] is True

    # The dashboard keeps target values inert and renders the masked API identity
    def test_template_uses_safe_action_dispatch_and_api_identity(self):
        template = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
        assert "handleTargetAction(this, 'analysis')" in template
        assert "showFollowAnalysis('${escapeHtml(name)}')" not in template
        assert "renderFollowAnalysis(data.analysis)" in template
        assert "renderFollowAnalysis(username" not in template


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

    # Privacy substitutions also cover a missing target's searched directory
    def test_missing_data_path_masks_target_username(self, im_module, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(im_module, "OUTPUT_DIR", str(tmp_path), raising=False)
        monkeypatch.setattr(im_module, "PRIVACY_SUBSTITUTIONS", [("alice", "MASKED")], raising=False)
        rc = im_module.run_follow_analysis(["alice", "ghost"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "alice" not in out
        assert "MASKED" in out

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
