"""Tests for check-interval scheduling and the CHECK_POSTS_IN_HOURS_RANGE window logic."""

from datetime import datetime

import pytest


def _enable_hours(monkeypatch, im_module, min1, max1, min2, max2):
    monkeypatch.setattr(im_module, "CHECK_POSTS_IN_HOURS_RANGE", True)
    monkeypatch.setattr(im_module, "MIN_H1", min1)
    monkeypatch.setattr(im_module, "MAX_H1", max1)
    monkeypatch.setattr(im_module, "MIN_H2", min2)
    monkeypatch.setattr(im_module, "MAX_H2", max2)


class TestHoursToCheck:
    def test_full_day_when_range_disabled(self, im_module):
        # baseline fixture leaves CHECK_POSTS_IN_HOURS_RANGE False
        assert im_module.hours_to_check() == list(range(24))

    def test_two_ranges_union_and_sorted(self, im_module, monkeypatch):
        _enable_hours(monkeypatch, im_module, 0, 4, 11, 23)
        assert im_module.hours_to_check() == [0, 1, 2, 3, 4] + list(range(11, 24))

    def test_overlapping_ranges_deduped(self, im_module, monkeypatch):
        _enable_hours(monkeypatch, im_module, 8, 12, 10, 14)
        assert im_module.hours_to_check() == [8, 9, 10, 11, 12, 13, 14]

    def test_both_ranges_zero_means_empty(self, im_module, monkeypatch):
        _enable_hours(monkeypatch, im_module, 0, 0, 0, 0)
        assert im_module.hours_to_check() == []

    def test_inverted_range_yields_no_hours_from_that_range(self, im_module, monkeypatch):
        # MAX < MIN produces an empty range for that band
        _enable_hours(monkeypatch, im_module, 20, 5, 0, 0)
        assert im_module.hours_to_check() == []


class TestNextAllowedDatetime:
    def test_returns_none_for_empty_allowed(self, im_module):
        assert im_module._next_allowed_datetime_at_or_after(datetime(2024, 1, 1, 8, 0), []) is None

    def test_already_in_window_returns_same(self, im_module):
        planned = datetime(2024, 1, 1, 2, 30)
        assert im_module._next_allowed_datetime_at_or_after(planned, [0, 1, 2, 3]) == planned

    def test_pushes_to_next_window_preserving_offset(self, im_module):
        # 08:30 is disallowed; next allowed hour is 11, keep the 30-min offset
        planned = datetime(2024, 1, 1, 8, 30)
        result = im_module._next_allowed_datetime_at_or_after(planned, list(range(11, 24)))
        assert result == datetime(2024, 1, 1, 11, 30)

    def test_wraps_to_next_day(self, im_module):
        # 22:15 disallowed, only hour 3 allowed -> next day 03:15
        planned = datetime(2024, 1, 1, 22, 15)
        result = im_module._next_allowed_datetime_at_or_after(planned, [3])
        assert result == datetime(2024, 1, 2, 3, 15)


class TestComputeNextCheckWithHoursRange:
    def test_range_disabled_is_plain_sleep(self, im_module):
        now = datetime(2024, 1, 1, 8, 0, 0)
        sleep_s, next_dt = im_module.compute_next_check_with_hours_range(now, 1800)
        assert sleep_s == 1800
        assert next_dt == datetime(2024, 1, 1, 8, 30, 0)

    def test_negative_base_sleep_clamped(self, im_module):
        now = datetime(2024, 1, 1, 8, 0, 0)
        sleep_s, _ = im_module.compute_next_check_with_hours_range(now, -100)
        assert sleep_s == 1

    def test_planned_time_pushed_into_window(self, im_module, monkeypatch):
        _enable_hours(monkeypatch, im_module, 0, 4, 11, 23)
        now = datetime(2024, 1, 1, 8, 0, 0)
        # planned 08:30 -> push to 11:30 -> 3.5h = 12600s
        sleep_s, next_dt = im_module.compute_next_check_with_hours_range(now, 1800)
        assert sleep_s == 12600
        assert next_dt == datetime(2024, 1, 1, 11, 30, 0)

    def test_misconfigured_window_returns_backoff_label(self, im_module, monkeypatch):
        _enable_hours(monkeypatch, im_module, 0, 0, 0, 0)
        now = datetime(2024, 1, 1, 8, 0, 0)
        sleep_s, label = im_module.compute_next_check_with_hours_range(now, 60)
        assert sleep_s == 300
        assert isinstance(label, str) and "No allowed hours" in label


class TestProbabilityForCycle:
    def test_full_day_fraction(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 5)
        # 5 hits/day, sleep = 1/5 of a day -> probability 1.0
        assert im_module.probability_for_cycle(86400 // 5) == pytest.approx(1.0)

    def test_capped_at_one(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 5)
        assert im_module.probability_for_cycle(86400) == 1.0

    def test_scales_with_window_size(self, im_module, monkeypatch):
        # Restricting allowed hours shrinks the denominator, raising probability
        monkeypatch.setattr(im_module, "DAILY_HUMAN_HITS", 1)
        full = im_module.probability_for_cycle(3600)
        _enable_hours(monkeypatch, im_module, 0, 5, 0, 0)  # 6 allowed hours
        windowed = im_module.probability_for_cycle(3600)
        assert windowed > full

    def test_zero_allowed_hours_returns_zero(self, im_module, monkeypatch):
        _enable_hours(monkeypatch, im_module, 0, 0, 0, 0)
        assert im_module.probability_for_cycle(3600) == 0.0


class TestRandomizeNumber:
    def test_within_expected_bounds(self, im_module):
        for _ in range(200):
            val = im_module.randomize_number(5400, 900, 180)
            assert 4500 <= val <= 5580

    def test_small_number_does_not_go_negative(self, im_module):
        # When number <= diff_low the low bound is the number itself
        for _ in range(200):
            val = im_module.randomize_number(100, 900, 50)
            assert 100 <= val <= 150
