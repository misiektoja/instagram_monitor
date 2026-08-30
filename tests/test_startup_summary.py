"""Tests for the startup summary block, driven through the real CLI path with no network call."""

import re
from unittest.mock import Mock

import pytest

# The rows shared with the sibling monitors, in the order every one of them prints
SHARED_ROW_ORDER = ("Targets", "Polling interval", "Notifications (email)", "Notifications (webhook)", "Output logging", "Config", "Dotenv", "Liveness output", "CSV output", "Local timezone", "Install method", "Secrets from dotenv", "Secrets from environment", "Secrets from config file", "TLS verification", "ASCII log separators", "Coloured output", "Verbose mode", "Debug mode")

SUMMARY_LINE_RE = re.compile(r"^\* (?P<label>[^:]+): +\S")


# Runs the startup path far enough to print the summary and returns what the terminal was shown
def rendered_summary(im_module, monkeypatch, capsys, tmp_path, *extra_args):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--no-color", "--disable-logging", *extra_args])
    monkeypatch.setattr(im_module, "CLI_CONFIG_PATH", None)
    monkeypatch.setattr(im_module, "DASHBOARD_ENABLED", False)
    monkeypatch.setattr(im_module, "WEB_DASHBOARD_ENABLED", False)
    monkeypatch.setattr(im_module, "find_config_file", lambda path=None: None)
    monkeypatch.setattr(im_module, "clear_screen", lambda *args, **kwargs: None)
    monkeypatch.setattr(im_module, "check_internet", lambda: True)
    monkeypatch.setattr(im_module, "start_dashboard_input_handler", Mock(side_effect=SystemExit(0)))

    with pytest.raises(SystemExit):
        im_module.run_main()
    return capsys.readouterr().out


# Verifies the shared rows keep the order every sibling monitor prints them in
def test_the_shared_summary_rows_match_the_sibling_tools(im_module, monkeypatch, capsys, tmp_path):
    output = rendered_summary(im_module, monkeypatch, capsys, tmp_path, "--verbose")

    printed = [match.group("label") for line in output.splitlines() if (match := SUMMARY_LINE_RE.match(line))]
    assert [label for label in printed if label in SHARED_ROW_ORDER] == list(SHARED_ROW_ORDER)


# Verifies every label fits the column the sibling monitors align their values in
def test_every_summary_value_starts_in_the_shared_column(im_module, monkeypatch, capsys, tmp_path):
    output = rendered_summary(im_module, monkeypatch, capsys, tmp_path, "--verbose")

    rows = [line for line in output.splitlines() if SUMMARY_LINE_RE.match(line)]
    assert rows
    for line in rows:
        assert "\t" not in line, line
        assert line[32] != " ", f"value column is not where the sibling monitors put it: {line!r}"


# Verifies the concise view stays short and ends by naming the flags that reveal the rest
def test_the_concise_view_points_at_the_diagnostic_modes(im_module, monkeypatch, capsys, tmp_path):
    output = rendered_summary(im_module, monkeypatch, capsys, tmp_path)

    assert "* More details:" in output and "use --verbose or --debug" in output
    assert "* Install method:" not in output
    assert "* Secrets from dotenv:" not in output
