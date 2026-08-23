"""Offline tests for shared cache eviction and probe deduplication behavior."""

import threading
import time



class TestFlaggedProbeDeduplication:
    # The probe network call must not run while the shared lock is held, or every other target stalls behind it
    def test_probe_runs_without_holding_the_lock(self, im_module, monkeypatch):
        observed = {}

        def slow_probe(bot):
            observed["lock_free_during_probe"] = im_module.FLAGGED_PROBE_LOCK.acquire(blocking=False)
            if observed["lock_free_during_probe"]:
                im_module.FLAGGED_PROBE_LOCK.release()
            return True

        monkeypatch.setattr(im_module, "_run_flagged_probe", slow_probe)

        assert im_module.probe_session_flagged(object()) is True
        assert observed["lock_free_during_probe"] is True

    # Concurrent targets share one probe result instead of each issuing their own request
    def test_concurrent_targets_share_one_probe(self, im_module, monkeypatch):
        calls = []
        barrier_released = threading.Event()

        def counted_probe(bot):
            calls.append(1)
            barrier_released.wait(2.0)
            return True

        monkeypatch.setattr(im_module, "_run_flagged_probe", counted_probe)
        results = []
        threads = [threading.Thread(target=lambda: results.append(im_module.probe_session_flagged(object()))) for _ in range(5)]
        for thread in threads:
            thread.start()
        time.sleep(0.2)
        barrier_released.set()
        for thread in threads:
            thread.join(timeout=5)

        assert len(calls) == 1
        assert results == [True] * 5

    # A cached verdict is reused inside the TTL without another request
    def test_cached_verdict_is_reused(self, im_module, monkeypatch):
        calls = []
        monkeypatch.setattr(im_module, "_run_flagged_probe", lambda bot: calls.append(1) or True)

        assert im_module.probe_session_flagged(object()) is True
        assert im_module.probe_session_flagged(object()) is True
        assert len(calls) == 1


class TestProgressBarOwnership:
    # A second target continues without a bar rather than blocking on the one already drawing
    def test_second_target_does_not_block_on_the_progress_bar(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
        acquired = im_module.PROGRESS_BAR_LOCK.acquire(blocking=False)
        assert acquired
        finished = threading.Event()

        def other_target():
            im_module._thread_local.__dict__.clear()
            im_module.setup_pbar(total_expected=10, title="* Downloading Followers")
            finished.set()

        thread = threading.Thread(target=other_target, daemon=True)
        try:
            thread.start()
            assert finished.wait(3.0), "setup_pbar blocked while another target owned the progress bar"
        finally:
            im_module.PROGRESS_BAR_LOCK.release()
            thread.join(timeout=3)


class TestDashboardMediaEviction:
    # A file the monitor keeps refreshing survives eviction ahead of one registered once
    def test_refreshed_entries_are_not_evicted_first(self, im_module, monkeypatch, tmp_path):
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_MEDIA_FILES", {})
        monkeypatch.setattr(im_module, "WEB_DASHBOARD_MEDIA_LIMIT", 3)
        files = []
        for index in range(3):
            path = tmp_path / f"item{index}.jpg"
            path.write_bytes(b"x")
            files.append(str(path))
        tokens = [im_module.register_dashboard_media_file(path) for path in files]

        # The oldest entry is refreshed, then a new item arrives and forces one eviction
        im_module.register_dashboard_media_file(files[0])
        newcomer = tmp_path / "item3.jpg"
        newcomer.write_bytes(b"x")
        im_module.register_dashboard_media_file(str(newcomer))

        assert tokens[0].split("/")[-1] in im_module.WEB_DASHBOARD_MEDIA_FILES
        assert tokens[1].split("/")[-1] not in im_module.WEB_DASHBOARD_MEDIA_FILES
        assert len(im_module.WEB_DASHBOARD_MEDIA_FILES) == 3
