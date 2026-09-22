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


# Verifies the examples open with the wizard, the one command a first-time reader can run knowing nothing
def test_the_wizard_is_the_first_example(help_screen):
    block = help_screen.split("Examples:", 1)[1]
    first = [line.strip() for line in block.splitlines() if line.startswith("  ")][:2]

    # The example names the running interpreter, which is not always called python3
    assert first == ["# Guided setup, recommended for the first run", f"{monitor._wizard_cmd_prefix('manual')} --setup"]


# Verifies the one-line description carries the repository link in the form the sibling monitors print
def test_the_description_links_the_repository(help_screen):
    header = help_screen.split("positional arguments:", 1)[0]

    assert "[ https://github.com/misiektoja/instagram_monitor/ ]" in header


# Verifies every example command is introduced by a comment saying what it is for
def test_every_example_command_has_a_comment(help_screen):
    lines = [line for line in help_screen.split("Examples:", 1)[1].splitlines() if line.startswith("  ")]

    assert lines, "no example lines were rendered"
    for index, line in enumerate(lines):
        if not line.startswith("  #"):
            assert lines[index - 1].startswith("  #"), f"the example '{line.strip()}' has no comment above it"


# Verifies the help screen shows exactly one startup banner
def test_help_shows_one_startup_banner(help_screen):
    assert help_screen.count(monitor.STARTUP_BANNER.strip("\n").splitlines()[0]) == 1


# Verifies the terminal truncation width is settable from the command line, as in the sibling monitors
def test_the_truncate_flag_is_offered(help_screen):
    assert "--truncate N" in help_screen
    assert "use 999 to auto-detect terminal width" in help_screen


# Verifies both file flags advertise the `none` sentinel, since either can switch its own discovery off
def test_both_file_flags_advertise_the_none_sentinel(help_screen):
    compact = " ".join(help_screen.split())

    assert "Location of the optional config file (auto-search if not set, disable with 'none')" in compact
    assert "Path to optional dotenv file (auto-search if not set, disable with 'none')" in compact


# The one sentence each shared one-shot flag uses across the sibling monitors
SHARED_FLAG_HELP = {
    "--setup": "Run the guided setup and write a ready-to-run configuration",
    "--doctor": "Run read-only preflight checks and report what is ready and what is not",
    "--set-webhook-url": "Save a Discord or ntfy webhook URL through a hidden prompt",
    "--set-smtp-password": "Enter the SMTP password privately, check it against the mail server and save it to the dotenv file",
    "--send-test-email": "Send test email to verify SMTP settings",
    "--send-test-webhook": "Send one test webhook without starting monitoring",
}


# Verifies each shared one-shot flag describes itself with the sentence the sibling monitors use
def test_the_shared_flags_use_the_shared_help_sentences(help_screen):
    compact = " ".join(help_screen.split())

    for flag, sentence in SHARED_FLAG_HELP.items():
        assert f"{flag} {sentence}" in compact, f"the '{flag}' help sentence has drifted from the shared wording"
