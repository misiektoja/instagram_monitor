"""Tests for the startup summary block and the startup banner, driven through the real CLI path with no network call."""

import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# The rows shared with the sibling monitors, in the order every one of them prints
SHARED_ROW_ORDER = ("Targets", "Polling interval", "Notifications (email)", "Email transport", "Email recipient", "Notifications (webhook)", "Webhook provider", "Delivery confirmations", "Output logging", "Config", "Dotenv", "Liveness output", "CSV output", "Process id", "Python version", "Operating system", "Local timezone", "Install method", "Secrets from dotenv", "Secrets from environment", "Secrets from config file", "Secrets from command line", "TLS verification", "ASCII log separators", "Coloured output", "Verbose mode", "Debug mode")

SUMMARY_LINE_RE = re.compile(r"^\* *(?P<label>[^:]+): +\S")

# The banner draws a camera inside a box 18 columns wide and starts both wordmarks in the column beside it
BOX_WIDTH = 18
BODY_COLUMN = 21


@pytest.fixture(autouse=True)
# Restores every module setting, since these tests run the real startup path and it rewrites them in place
def restored_settings(im_module):
    snapshot = {name: value for name, value in vars(im_module).items() if name.isupper()}
    yield
    for name, value in snapshot.items():
        setattr(im_module, name, value)


# Runs the startup path far enough to print the summary and returns what the terminal was shown
def rendered_summary(im_module, monkeypatch, capsys, tmp_path, *extra_args):
    monkeypatch.chdir(tmp_path)
    # The startup path searches for a dotenv from the module's own directory, so a real one would decide these rows
    monkeypatch.setattr(im_module.sys, "argv", ["instagram_monitor.py", "target.user", "--env-file", "none", "--no-color", "--disable-logging", *extra_args])
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


# Verifies a run without a target reports the shared three-line block rather than dumping the whole help screen
def test_a_missing_target_reports_the_shared_error_block(im_module, tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(project_root / "instagram_monitor.py"), "--config-file", "none", "--env-file", "none", "--no-color"], cwd=tmp_path, capture_output=True, text=True, check=False)

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "* Error: At least one TARGET_USERNAME argument is required" in output
    assert f"To fix: {im_module.NO_TARGET_FIX}" in output
    assert f"Guide: {im_module.QUICK_START_GUIDE_URL}" in output
    assert "usage: instagram_monitor" not in output


# Verifies the selected Instagram banner remains exact and version independent
def test_selected_banner_exact_content(im_module):
    assert im_module.STARTUP_BANNER == r"""
 .---------------.    ___           _
|   O        .   |   |_ _|_ __  ___| |_ __ _  __ _ _ __ __ _ _ __ ___
|     .-----.    |    | || '_ \/ __| __/ _` |/ _` | '__/ _` | '_ ` _ \
|    |  ( )  |   |    | || | | \__ \ || (_| | (_| | | | (_| | | | | | |
|     '-----'    |   |___|_| |_|___/\__\__,_|\__, |_|  \__,_|_| |_| |_|
 '---------------'                           |___/
                      __  __             _ _
                     |  \/  | ___  _ __ (_) |_ ___  _ __
                     | |\/| |/ _ \| '_ \| | __/ _ \| '__|
                     | |  | | (_) | | | | | || (_) | |
                     |_|  |_|\___/|_| |_|_|\__\___/|_|"""


# Verifies the art is portable, bounded and free of trailing whitespace
def test_banner_ascii_width_and_whitespace(im_module):
    im_module.STARTUP_BANNER.encode("ascii")
    lines = im_module.STARTUP_BANNER.splitlines()

    assert max(map(len, lines)) <= 90
    assert all(line == line.rstrip() for line in lines)


# Verifies the Instagram wordmark matches the standard FIGlet rows at the shared body column
def test_banner_instagram_wordmark_rows(im_module):
    assert [line[BODY_COLUMN:] for line in im_module.STARTUP_BANNER.splitlines()[1:7]] == [
        ' ___           _',
        '|_ _|_ __  ___| |_ __ _  __ _ _ __ __ _ _ __ ___',
        " | || '_ \\/ __| __/ _` |/ _` | '__/ _` | '_ ` _ \\",
        ' | || | | \\__ \\ || (_| | (_| | | | (_| | | | | | |',
        '|___|_| |_|___/\\__\\__,_|\\__, |_|  \\__,_|_| |_| |_|',
        '                        |___/',
    ]


# Verifies the Monitor wordmark matches the standard FIGlet rows at the shared body column
def test_banner_monitor_wordmark_rows(im_module):
    assert [line[BODY_COLUMN:] for line in im_module.STARTUP_BANNER.splitlines()[7:12]] == [
        ' __  __             _ _',
        '|  \\/  | ___  _ __ (_) |_ ___  _ __',
        "| |\\/| |/ _ \\| '_ \\| | __/ _ \\| '__|",
        '| |  | | (_) | | | | | || (_) | |',
        '|_|  |_|\\___/|_| |_|_|\\__\\___/|_|',
    ]


# Verifies both wordmarks begin in the body column rather than one of them drifting a column away
def test_banner_wordmarks_share_the_body_column(im_module):
    lines = im_module.STARTUP_BANNER.splitlines()
    beside_box = [line[BOX_WIDTH:] for line in lines[1:7]]
    below_box = lines[7:12]

    assert BOX_WIDTH + min(len(row) - len(row.lstrip(" ")) for row in beside_box) == BODY_COLUMN
    assert min(len(row) - len(row.lstrip(" ")) for row in below_box) == BODY_COLUMN


# Verifies the camera keeps both side walls under the corners of its border rows
def test_banner_box_walls_stand_under_the_corners(im_module):
    lines = im_module.STARTUP_BANNER.splitlines()

    assert lines[1][:BOX_WIDTH] == " ." + "-" * (BOX_WIDTH - 3) + "."
    assert lines[6][:BOX_WIDTH] == " '" + "-" * (BOX_WIDTH - 3) + "'"
    for line in lines[2:6]:
        assert line[0] == "|" and line[BOX_WIDTH - 1] == "|", line[:BOX_WIDTH]


# Verifies the printed version stays dynamic and followed by one blank line
def test_banner_dynamic_version_line(im_module, monkeypatch, capsys):
    monkeypatch.setattr(im_module, "VERSION", "9.9-test")
    monkeypatch.setattr(im_module, "COLOR_ENABLED", False)

    im_module.print_startup_banner()

    assert capsys.readouterr().out == im_module.STARTUP_BANNER + "\n" + (" " * BODY_COLUMN) + "v9.9-test\n\n"
