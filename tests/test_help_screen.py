"""Tests the --help screen: the shared argument group names, the task-grouped examples and the startup banner."""

import subprocess
import sys
from pathlib import Path

import pytest

import instagram_monitor as monitor


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Returns the rendered help screen of the working-tree script
@pytest.fixture(scope="module")
def help_screen():
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / "instagram_monitor.py"), "--help"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    return result.stdout


# Verifies the argument groups carry the names and the order shared with the sibling monitors
def test_the_argument_groups_use_the_shared_names_in_order(help_screen):
    titles = ['Configuration & dotenv files', 'Session login credentials', 'Browser session import', 'Email notifications', 'Webhook notifications', 'Intervals & timers', 'Features & output']

    positions = []
    for title in titles:
        marker = f"\n{title}:\n"
        assert marker in help_screen, f"the '{title}' group is missing"
        positions.append(help_screen.index(marker))

    assert positions == sorted(positions), "the argument groups are not in the shared order"


# Verifies email and webhook alerts are named apart rather than sharing one 'Notifications' group
def test_the_notification_groups_are_named_apart(help_screen):
    assert "\nEmail notifications:\n" in help_screen
    assert "\nWebhook notifications:\n" in help_screen
    assert "\nNotifications:\n" not in help_screen.split("Examples:")[0]


# Verifies the examples are grouped by what the reader is trying to do and end with the guide link
def test_the_examples_are_grouped_by_task(help_screen):
    examples = help_screen.split("Examples:", 1)[1]
    headings = ['Getting started', 'Full detail (stories, reels, follower churn)', 'Notifications', 'Information and diagnostics']

    positions = []
    for heading in headings:
        marker = f"\n{heading}:\n"
        assert marker in examples, f"the '{heading}' example group is missing"
        positions.append(examples.index(marker))

    assert positions == sorted(positions), "the example groups are not in the intended order"
    assert examples.rstrip().endswith(f"Guide: {monitor.QUICK_START_GUIDE_URL}")


# Verifies every example command is introduced by a comment saying what it is for
def test_every_example_command_has_a_comment(help_screen):
    lines = [line for line in help_screen.split("Examples:", 1)[1].splitlines() if line.startswith("  ")]

    assert lines, "no example lines were rendered"
    for index, line in enumerate(lines):
        if not line.startswith("  #"):
            assert lines[index - 1].startswith("  #"), f"the example '{line.strip()}' has no comment above it"


# Verifies the help screen shows exactly one startup banner
def test_help_shows_one_startup_banner(help_screen):
    assert help_screen.count(" .-------------.") == 1


# Verifies the terminal truncation width is settable from the command line, as in the sibling monitors
def test_the_truncate_flag_is_offered(help_screen):
    assert "--truncate N" in help_screen
    assert "use 999 to auto-detect terminal width" in help_screen


# Verifies both file flags advertise the `none` sentinel, since either can switch its own discovery off
def test_both_file_flags_advertise_the_none_sentinel(help_screen):
    compact = " ".join(help_screen.split())

    assert "Location of the optional config file (auto-search if not set, disable with 'none')" in compact
    assert "Path to optional dotenv file (auto-search if not set, disable with 'none')" in compact
