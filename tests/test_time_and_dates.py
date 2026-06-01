"""Tests for time formatting, timespan math and timezone conversion helpers."""

from datetime import datetime, timezone

import pytest


class TestDisplayTime:
    def test_zero_seconds(self, im_module):
        assert im_module.display_time(0) == "0 seconds"

    def test_negative_treated_as_zero(self, im_module):
        assert im_module.display_time(-10) == "0 seconds"

    def test_singular_unit_drops_plural_s(self, im_module):
        assert im_module.display_time(1) == "1 second"

    def test_minutes_and_seconds(self, im_module):
        assert im_module.display_time(90) == "1 minute, 30 seconds"

    def test_granularity_limits_components(self, im_module):
        # 1h 1m 1s but granularity 2 keeps only the two largest units
        assert im_module.display_time(3661, granularity=2) == "1 hour, 1 minute"

    def test_granularity_one(self, im_module):
        assert im_module.display_time(3661, granularity=1) == "1 hour"

    def test_float_input_is_truncated(self, im_module):
        assert im_module.display_time(59.9) == "59 seconds"


class TestCalculateTimespan:
    def test_integer_timestamps(self, im_module):
        assert im_module.calculate_timespan(1000, 1000 + 3661, granularity=2) == "1 hour, 1 minute"

    def test_order_independent(self, im_module):
        forward = im_module.calculate_timespan(1000, 4661, granularity=2)
        backward = im_module.calculate_timespan(4661, 1000, granularity=2)
        assert forward == backward

    def test_zero_difference(self, im_module):
        assert im_module.calculate_timespan(1000, 1000) == "0 seconds"

    def test_seconds_shown_under_a_minute(self, im_module):
        assert im_module.calculate_timespan(0, 45, show_seconds=True) == "45 seconds"

    def test_datetime_inputs(self, im_module):
        d1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        d2 = datetime(2024, 1, 1, 2, 30, 0, tzinfo=timezone.utc)
        assert im_module.calculate_timespan(d1, d2, granularity=2) == "2 hours, 30 minutes"

    def test_invalid_string_returns_empty(self, im_module):
        assert im_module.calculate_timespan("not-a-date", 1000) == ""

    def test_unsupported_type_returns_empty(self, im_module):
        assert im_module.calculate_timespan(object(), 1000) == ""


class TestFormatHour:
    def test_24h_default(self, im_module):
        assert im_module.format_hour(9) == "09:00"
        assert im_module.format_hour(23) == "23:00"

    def test_24h_without_minutes_still_shows_minutes(self, im_module):
        # In 24h mode the with_minutes flag intentionally returns the same string
        assert im_module.format_hour(9, with_minutes=False) == "09:00"

    def test_12h_morning(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "TIME_FORMAT_12H", True)
        assert im_module.format_hour(9) == "09:00 AM"

    def test_12h_midnight_and_noon(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "TIME_FORMAT_12H", True)
        assert im_module.format_hour(0) == "12:00 AM"
        assert im_module.format_hour(12) == "12:00 PM"

    def test_12h_without_minutes(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "TIME_FORMAT_12H", True)
        assert im_module.format_hour(15, with_minutes=False) == "03 PM"


class TestFormatHourRange:
    def test_24h_range(self, im_module):
        assert im_module.format_hour_range(0, 4) == "00:00 - 04:59"

    def test_12h_range(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "TIME_FORMAT_12H", True)
        assert im_module.format_hour_range(0, 13) == "12:00 AM - 01:59 PM"


class TestFormatHoursAsRanges:
    def test_empty_returns_none(self, im_module):
        assert im_module.format_hours_as_ranges([]) == "none"

    def test_single_hour(self, im_module):
        assert im_module.format_hours_as_ranges([5]) == "5"

    def test_contiguous_and_split_ranges(self, im_module):
        assert im_module.format_hours_as_ranges([0, 1, 2, 3, 11, 12, 13]) == "0-3, 11-13"

    def test_all_isolated(self, im_module):
        assert im_module.format_hours_as_ranges([1, 3, 5]) == "1, 3, 5"


class TestTimezoneConversions:
    def test_convert_utc_datetime_to_tz(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "Europe/Warsaw")
        # 2024-07-01 is summer time in Warsaw -> UTC+2
        dt_utc = datetime(2024, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
        result = im_module.convert_utc_datetime_to_tz_datetime(dt_utc)
        assert result is not None
        assert result.hour == 12

    def test_convert_naive_assumed_utc(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        naive = datetime(2024, 1, 1, 8, 0, 0)
        result = im_module.convert_utc_datetime_to_tz_datetime(naive)
        assert result is not None
        assert result.hour == 8

    def test_none_input_returns_none(self, im_module):
        assert im_module.convert_utc_datetime_to_tz_datetime(None) is None

    def test_convert_utc_str(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        result = im_module.convert_utc_str_to_tz_datetime("2024-01-01 08:00:00")
        assert result is not None
        assert result.year == 2024 and result.hour == 8

    def test_convert_bad_str_returns_none(self, im_module):
        assert im_module.convert_utc_str_to_tz_datetime("garbage") is None

    def test_convert_to_local_naive_strips_tzinfo(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        result = im_module.convert_to_local_naive(datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc))
        assert result is not None
        assert result.tzinfo is None
        assert result.hour == 8


class TestIsValidTimezone:
    def test_valid(self, im_module):
        assert im_module.is_valid_timezone("Europe/Warsaw") is True
        assert im_module.is_valid_timezone("UTC") is True

    def test_invalid(self, im_module):
        assert im_module.is_valid_timezone("Not/AZone") is False
        assert im_module.is_valid_timezone("Auto") is False


class TestGetHourMinFromTs:
    def test_int_timestamp_utc(self, im_module, monkeypatch):
        monkeypatch.setattr(im_module, "LOCAL_TIMEZONE", "UTC")
        # 1970-01-01 01:02:03 UTC
        assert im_module.get_hour_min_from_ts(3723, show_seconds=True) == "01:02:03"

    def test_unsupported_type_returns_empty(self, im_module):
        assert im_module.get_hour_min_from_ts(None) == ""
