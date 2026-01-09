#!/usr/bin/env python3
"""
Author: Michal Szymanski <misiektoja-github@rm-rf.ninja>
v2.1

OSINT tool implementing real-time tracking of Instagram users activities and profile changes:
https://github.com/misiektoja/instagram_monitor/

Python pip3 requirements:

instaloader
requests
python-dateutil
pytz
tzlocal (optional)
python-dotenv (optional)
tqdm
"""

VERSION = "2.1"

# ---------------------------
# CONFIGURATION SECTION START
# ---------------------------

CONFIG_BLOCK = """
# Session login (mode 2) is required for some features such as retrieving the list of followings/followers
# or detailed posts/reels/stories info
#
# The tool still works without login (mode 1), but in a limited way
#
# For session login (mode 2), you'll need to log in with your Instagram username and password
#
# Provide the username below (or use the -u flag)
SESSION_USERNAME = ""

# Provide the password using one of the following methods:
#   - Log in via Firefox web browser and import session cookie: instagram_monitor --import-firefox-session
#   - Log in using instaloader: instaloader -l <SESSION_USERNAME>
#   - Pass it at runtime with -p / --session-password
#   - Set it as an environment variable (e.g. export SESSION_PASSWORD=...)
#   - Add it to ".env" file (SESSION_PASSWORD=...) for persistent use
# Fallback:
#   - Hard-code it in the code or config file
SESSION_PASSWORD = ""

# SMTP settings for sending email notifications
# If left as-is, no notifications will be sent
#
# Provide the SMTP_PASSWORD secret using one of the following methods:
#   - Set it as an environment variable (e.g. export SMTP_PASSWORD=...)
#   - Add it to ".env" file (SMTP_PASSWORD=...) for persistent use
# Fallback:
#   - Hard-code it in the code or config file
SMTP_HOST = "your_smtp_server_ssl"
SMTP_PORT = 587
SMTP_USER = "your_smtp_user"
SMTP_PASSWORD = "your_smtp_password"
SMTP_SSL = True
SENDER_EMAIL = "your_sender_email"
RECEIVER_EMAIL = "your_receiver_email"

# Whether to send an email on new post/reel/story, bio change, new follow, profile pic or visibility change
# Can also be enabled via the -s flag
STATUS_NOTIFICATION = False

# Whether to send an email on new followers
# Only applies if STATUS_NOTIFICATION / -s is enabled
# Can also be enabled via the -m flag
FOLLOWERS_NOTIFICATION = False

# Whether to send an email on errors
# Can also be disabled via the -e flag
ERROR_NOTIFICATION = True

# How often to check for user activity; in seconds
# Can also be set using the -c flag
INSTA_CHECK_INTERVAL = 5400  # 1,5 hours

# To avoid captcha checks and bot detection, the actual INSTA_CHECK_INTERVAL interval is randomized using the values below
# Final interval = INSTA_CHECK_INTERVAL ± RANDOM_SLEEP_DIFF
# Can also be set using -i (low) and -j (high) flags
RANDOM_SLEEP_DIFF_LOW = 900  # -15 min (-i)
RANDOM_SLEEP_DIFF_HIGH = 180  # +3 min (-j)

# Set your local time zone so that Instagram timestamps are converted accordingly (e.g. 'Europe/Warsaw')
# Use this command to list all time zones supported by pytz:
#   python3 -c "import pytz; print('\\n'.join(pytz.all_timezones))"
# If set to 'Auto', the tool will try to detect your local time zone automatically (requires tzlocal)
LOCAL_TIMEZONE = 'Auto'

# Notify when the user's profile picture changes? (via console and email if STATUS_NOTIFICATION / -s is enabled).
# If enabled, the current profile picture is saved as:
#   - instagram_<username>_profile_pic.jpeg (initial)
#   - instagram_<username>_profile_pic_YYmmdd_HHMM.jpeg (on change)
# The binary JPEGs are compared to detect changes
# Can also be disabled by using -k flag
DETECT_CHANGED_PROFILE_PIC = True

# Location of the optional file with the empty profile picture template
PROFILE_PIC_FILE_EMPTY = "instagram_profile_pic_empty.jpeg"

# If you have 'imgcat' installed, you can set its path below to display profile pictures directly in your terminal
# If you specify only the binary name, it will be auto-searched in your PATH
# Leave empty to disable this feature
IMGCAT_PATH = "imgcat"

# Skip session login (no list of followers/followings and detailed posts/reels/stories info will be fetched)
# Can also be enabled via the -l flag
SKIP_SESSION = False

# Do not fetch followers list (only relevant if session login is used and SKIP_SESSION is False)
# Can also be enabled via the -f flag
SKIP_FOLLOWERS = False

# Do not fetch followings list (only relevant if session login is used and SKIP_SESSION is False)
# Can also be enabled via the -g flag
SKIP_FOLLOWINGS = False

# Do not fetch detailed story info (like story date, expiry, images/videos etc.)
# Only relevant if session login is used and SKIP_SESSION is False
# Can also be enabled via the -r flag
SKIP_GETTING_STORY_DETAILS = False

# Do not fetch detailed post/reel info (like post/reel date, number of likes, comments, description,
# tagged users, location, images/videos etc.)
# Can also be enabled via the -w flag
SKIP_GETTING_POSTS_DETAILS = False

# Fetch extra post details (list of comments and likes)
# Only relevant if session login is used and SKIP_SESSION is False
# Can also be enabled via the -t flag
GET_MORE_POST_DETAILS = False

# Make the tool behave more like a human by performing random feed / profile / hashtag / followee actions
# Used only with session login (mode 2), always disabled without login (anonymous mode 1)
BE_HUMAN = False

# Approximate number of simulated human actions to perform per 24 hours
DAILY_HUMAN_HITS = 5

# List of hashtags to browse
MY_HASHTAGS = ["travel", "food", "nature"]

# Set to True to enable verbose output during human simulation actions
BE_HUMAN_VERBOSE = False

# Whether to enable human-like HTTP jitter and back-off wrapper
ENABLE_JITTER = False

# Set to True to enable verbose output for HTTP jitter/back-off wrappers
JITTER_VERBOSE = False

# Optional: specify web browser user agent manually
#
# For session login using Firefox cookies, ensure this matches your Firefox web browser's user agent
#
# Some examples:
# Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0
# Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0
#
# Leave empty to auto-generate it randomly
# Can also be set using the --user-agent flag
USER_AGENT = ""

# Optional: specify mobile device user agent manually
#
# Some examples:
# Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0
# Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0
#
# Leave empty to auto-generate it randomly
# Can also be set using the --user-agent-mobile flag
USER_AGENT_MOBILE = ""

# How often to print a "liveness check" message to the output; in seconds
# Set to 0 to disable
LIVENESS_CHECK_INTERVAL = 43200  # 12 hours

# URL used to verify internet connectivity at startup
CHECK_INTERNET_URL = 'https://www.instagram.com/'

# Timeout used when checking initial internet connectivity; in seconds
CHECK_INTERNET_TIMEOUT = 5

# Limit fetching updates to specific hours of the day?
# If True, the tool will only fetch updates within the defined hour ranges below
#
# Notes:
# - The configured ranges are treated as hour buckets (HH:00..HH:59)
# - Overlapping ranges are allowed
# - Invalid hours (outside 0-23) are ignored
CHECK_POSTS_IN_HOURS_RANGE = False

# Set to True to enable verbose output for performing updates during certain hours
HOURS_VERBOSE = False

# First range of hours to check (if CHECK_POSTS_IN_HOURS_RANGE is True)
# Example: check from 00:00 to 04:59
# To disable this range, set both MIN and MAX to 0
MIN_H1 = 0
MAX_H1 = 4

# Second range of hours to check
# Example: check from 11:00 to 23:59
# To disable this range, set both MIN and MAX to 0
MIN_H2 = 11
MAX_H2 = 23

# Delay for fetching other data to avoid captcha checks and detection of automated tools
NEXT_OPERATION_DELAY = 0.7

# CSV file to write all activities and profile changes
# Can also be set using the -b flag
CSV_FILE = ""

# Location of the optional dotenv file which can keep secrets
# If not specified it will try to auto-search for .env files
# To disable auto-search, set this to the literal string "none"
# Can also be set using the --env-file flag
DOTENV_FILE = ""

# Default Firefox cookie directories by OS
FIREFOX_MACOS_COOKIE = "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite"
FIREFOX_WINDOWS_COOKIE = "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite"
FIREFOX_LINUX_COOKIE = "~/.mozilla/firefox/*/cookies.sqlite"

# Base name for the log file. Output will be saved to instagram_monitor_<username>.log
# Can include a directory path to specify the location, e.g. ~/some_dir/instagram_monitor
INSTA_LOGFILE = "instagram_monitor"

# Optional: specify directory layout for generated files
# If set, all downloaded files (images, videos, json, logs) will be saved under this directory
#
# Structure (single-target example):
#   OUTPUT_DIR/
#     logs/
#     images/
#     videos/
#     json/
#
# Structure (multi-target example):
#   OUTPUT_DIR/
#     logs/           (Shared logs)
#     username1/
#       images/
#       videos/
#       json/
#     username2/
#     ...
#
# Can also be set via the --output-dir flag
OUTPUT_DIR = ""

# Whether to disable logging to instagram_monitor_<username>.log
# Can also be disabled via the -d flag
DISABLE_LOGGING = False

# Width of horizontal line
HORIZONTAL_LINE = 113

# Whether to clear the terminal screen after starting the tool
CLEAR_SCREEN = True

# Value used by signal handlers to increase/decrease user activity check interval (INSTA_CHECK_INTERVAL); in seconds
INSTA_CHECK_SIGNAL_VALUE = 300  # 5 min

# Enable debug mode for verbose output (can also be enabled via --debug flag)
# Shows detailed information for every check, API responses, timing info
DEBUG_MODE = False

# When enabled, fetches the full list of followers and followings every check (not just when the count changes) and
# compares usernames to detect who followed/unfollowed even when counts remain the same
# This is useful for detecting when someone unfollows and someone else follows in the same interval, keeping the count unchanged
DETAILED_FOLLOWER_LOGGING = False

# ----------------------------
# Multi-target monitoring mode
# ----------------------------
# If you pass multiple targets on CLI (e.g. instagram_monitor user1 user2), the tool will run them in one process
# You can optionally define defaults here too:
#
# TARGET_USERNAMES = ["user1", "user2"]
#
# CLI targets take precedence over TARGET_USERNAMES
TARGET_USERNAMES = []

#
# When monitoring multiple targets in one process, this controls how long (in seconds) to wait between starting each
# target's monitoring loop to spread requests in time
#
# - Set to 0 to auto-spread targets evenly across INSTA_CHECK_INTERVAL
# - You can override via --targets-stagger flag
MULTI_TARGET_STAGGER = 0

#
# Adds a small random jitter (seconds) to each target start time to avoid perfectly periodic patterns
MULTI_TARGET_STAGGER_JITTER = 5

#
# If True, serializes all HTTP calls (via a global lock) across targets. Recommended for multi-target mode.
MULTI_TARGET_SERIALIZE_HTTP = True

# ----------------------------
# Terminal Dashboard Settings
# ----------------------------

# Enable terminal dashboard (live view)
# Set to False to use traditional text output
# Can be enabled via --dashboard flag
DASHBOARD_ENABLED = False

# ----------------------------
# Web Dashboard Settings
# ----------------------------
# Enable web-based dashboard (runs on localhost)
# Can be enabled via --web-dashboard flag
WEB_DASHBOARD_ENABLED = False

# Port for the web dashboard server
WEB_DASHBOARD_PORT = 8000

# Host for the web dashboard server (use '0.0.0.0' to allow external access, it is not recommended!)
WEB_DASHBOARD_HOST = '127.0.0.1'

# Template directory for web dashboard
# If empty, the tool will auto-detect the templates directory relative to the script location
# For pip-installed packages, templates should be in the package directory
# Can also be set via --web-dashboard-template-dir flag
WEB_DASHBOARD_TEMPLATE_DIR = ""

# ----------------------------
# Webhook Integration
# ----------------------------
# Discord API limits (for reference and validation)
DISCORD_FIELD_VALUE_LIMIT = 1024
DISCORD_FIELD_NAME_LIMIT = 256
DISCORD_EMBED_DESCRIPTION_LIMIT = 4096
DISCORD_EMBED_TITLE_LIMIT = 256
DISCORD_MAX_FIELDS = 25

# Enable webhook notifications (Discord-compatible)
WEBHOOK_ENABLED = False

# Webhook URL (Discord webhook URL or compatible endpoint)
# For Discord: Right-click channel -> Edit Channel -> Integrations -> Webhooks -> Copy Webhook URL
WEBHOOK_URL = ""

# Webhook username to display (leave empty for default)
WEBHOOK_USERNAME = "Instagram Monitor"

# Webhook avatar URL (leave empty for default)
WEBHOOK_AVATAR_URL = ""

# Send webhook on status changes (new posts/reels/stories, bio, profile pic, visibility)
WEBHOOK_STATUS_NOTIFICATION = True

# Send webhook on follower changes
WEBHOOK_FOLLOWERS_NOTIFICATION = True

# Send webhook on errors
WEBHOOK_ERROR_NOTIFICATION = False
"""

# -------------------------
# CONFIGURATION SECTION END
# -------------------------

# Default dummy values so linters shut up
# Do not change values below - modify them in the configuration section or config file instead
SESSION_USERNAME = ""
SESSION_PASSWORD = ""
SMTP_HOST = ""
SMTP_PORT = 0
SMTP_USER = ""
SMTP_PASSWORD = ""
SMTP_SSL = False
SENDER_EMAIL = ""
RECEIVER_EMAIL = ""
STATUS_NOTIFICATION = False
FOLLOWERS_NOTIFICATION = False
ERROR_NOTIFICATION = False
INSTA_CHECK_INTERVAL = 0
RANDOM_SLEEP_DIFF_LOW = 0
RANDOM_SLEEP_DIFF_HIGH = 0
LOCAL_TIMEZONE = ""
DETECT_CHANGED_PROFILE_PIC = False
PROFILE_PIC_FILE_EMPTY = ""
IMGCAT_PATH = ""
SKIP_SESSION = False
SKIP_FOLLOWERS = False
SKIP_FOLLOWINGS = False
SKIP_GETTING_STORY_DETAILS = False
SKIP_GETTING_POSTS_DETAILS = False
GET_MORE_POST_DETAILS = False
USER_AGENT = ""
USER_AGENT_MOBILE = ""
BE_HUMAN = False
DAILY_HUMAN_HITS = 0
MY_HASHTAGS = []
BE_HUMAN_VERBOSE = False
ENABLE_JITTER = False
JITTER_VERBOSE = False
LIVENESS_CHECK_INTERVAL = 0
CHECK_INTERNET_URL = ""
CHECK_INTERNET_TIMEOUT = 0
CHECK_POSTS_IN_HOURS_RANGE = False
HOURS_VERBOSE = False
MIN_H1 = 0
MAX_H1 = 0
MIN_H2 = 0
MAX_H2 = 0
NEXT_OPERATION_DELAY = 0
CSV_FILE = ""
DOTENV_FILE = ""
FIREFOX_MACOS_COOKIE = ""
FIREFOX_WINDOWS_COOKIE = ""
FIREFOX_LINUX_COOKIE = ""
INSTA_LOGFILE = ""
OUTPUT_DIR = ""
DISABLE_LOGGING = False
HORIZONTAL_LINE = 0
CLEAR_SCREEN = False
INSTA_CHECK_SIGNAL_VALUE = 0
TARGET_USERNAMES = []
MULTI_TARGET_STAGGER = 0
MULTI_TARGET_STAGGER_JITTER = 0
MULTI_TARGET_SERIALIZE_HTTP = False
WEBHOOK_ENABLED = False
WEBHOOK_URL = ""
WEBHOOK_USERNAME = "Instagram Monitor"
WEBHOOK_AVATAR_URL = ""
WEBHOOK_STATUS_NOTIFICATION = True
WEBHOOK_FOLLOWERS_NOTIFICATION = True
WEBHOOK_ERROR_NOTIFICATION = False
DEBUG_MODE = False
DASHBOARD_ENABLED = False
WEB_DASHBOARD_ENABLED = False
WEB_DASHBOARD_PORT = 8000
WEB_DASHBOARD_HOST = '127.0.0.1'
WEB_DASHBOARD_TEMPLATE_DIR = ""
DETAILED_FOLLOWER_LOGGING = False

exec(CONFIG_BLOCK, globals())

# Default name for the optional config file
DEFAULT_CONFIG_FILENAME = "instagram_monitor.conf"

# List of secret keys to load from env/config
SECRET_KEYS = ("SESSION_PASSWORD", "SMTP_PASSWORD")

# Default value for network-related timeouts in functions
FUNCTION_TIMEOUT = 15

# Computed later once final INSTA_CHECK_INTERVAL is known (config/env/CLI) and updated on SIGTRAP/SIGABRT
LIVENESS_CHECK_COUNTER = 0

stdout_bck = None
last_output = []
csvfieldnames = ['Date', 'Type', 'Old', 'New']

imgcat_exe = ""

CLI_CONFIG_PATH = None

# To solve the issue: 'SyntaxError: f-string expression part cannot include a backslash'
nl_ch = "\n"

# Progress Bar control items
START_TIME = 0
NAME_COUNT = 1
WRAPPER_COUNT = 0
pbar = None

# Global tracking for last/next check times
LAST_CHECK_TIME = None
NEXT_CHECK_TIME = None
CHECK_COUNT = 0

# Global state for debug mode manual check trigger (thread-safe Event)
# Will be initialized after threading is imported
MANUAL_CHECK_TRIGGERED = None  # type: ignore[assignment]
DEBUG_INPUT_THREAD = None

# Dashboard components (initialized later)
DASHBOARD_CONSOLE = None
DASHBOARD_LIVE = None
DASHBOARD_MODE = 'user'
DASHBOARD_DATA = {}

# Web Dashboard global state
WEB_DASHBOARD_APP = None
WEB_DASHBOARD_THREAD = None
WEB_DASHBOARD_DATA = {
    'version': VERSION,
    'targets': {},
    'config': {},
    'check_count': 0,
    'last_check': None,
    'next_check': None,
    'dashboard_mode': 'user',
    'uptime': None,
    'start_time': None,
    'activities': [],
    'is_monitoring': False,
    'session': {'username': None, 'active': False}
}
WEB_DASHBOARD_MONITOR_THREADS = {}  # Active monitoring threads by username
WEB_DASHBOARD_STOP_EVENTS = {}  # Stop events for each monitoring thread
WEB_DASHBOARD_RECHECK_EVENTS = {}  # Recheck events for each monitoring thread

import sys
import signal


# Early signal handler to catch Ctrl+C during imports/initialization
def _startup_sigint_handler(signum, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, _startup_sigint_handler)

if sys.version_info < (3, 9):
    print("* Error: Python version 3.9 or higher required !")
    sys.exit(1)

import time
import string
import json
import os
from os.path import expanduser, dirname, basename
from datetime import datetime, timezone, timedelta
from dateutil import relativedelta
from dateutil.parser import isoparse, parse
import calendar
import requests as req
import shutil
import shutil
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import argparse
import csv
import random
try:
    import pytz
except ModuleNotFoundError:
    raise SystemExit("Error: Couldn't find the pytz library !\n\nTo install it, run:\n    pip3 install pytz\n\nOnce installed, re-run this tool")
try:
    from tzlocal import get_localzone
except ImportError:
    get_localzone = None
import platform
from platform import system
import re
import ipaddress
from itertools import zip_longest
import subprocess
import threading
import hashlib

# Initialize the web dashboard data lock now that threading is imported
# Important: this lock is acquired from multiple call-sites that can nest (e.g. helpers called inside other locked
# regions). Use an RLock to avoid self-deadlocks that would freeze the web dashboard API
WEB_DASHBOARD_DATA_LOCK = threading.RLock()

# Initialize manual check trigger event (thread-safe)
MANUAL_CHECK_TRIGGERED: threading.Event = threading.Event()

try:
    import instaloader
    from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
    raise SystemExit("Error: Couldn't find the instaloader library !\n\nTo install it, run:\n    pip3 install instaloader\n\nOnce installed, re-run this tool. For more help, visit:\nhttps://instaloader.github.io/")

from instaloader.exceptions import PrivateProfileNotFollowedException
from html import escape
from itertools import islice
from typing import Optional, Tuple, Any, Callable, List
from glob import glob
import sqlite3
from sqlite3 import OperationalError, connect
from pathlib import Path
from functools import wraps
import traceback
try:
    from tqdm import tqdm
except ModuleNotFoundError:
    raise SystemExit("Error: Couldn't find the tqdm library !\n\nTo install it, run:\n    pip3 install tqdm\n\nOnce installed, re-run this tool")

try:
    from rich.console import Console  # type: ignore
    from rich.table import Table  # type: ignore
    from rich.panel import Panel  # type: ignore
    from rich.layout import Layout  # type: ignore
    from rich.text import Text  # type: ignore
    from rich.live import Live  # type: ignore
    from rich import box  # type: ignore
    RICH_AVAILABLE = True
except ImportError:
    Console = None  # type: ignore
    Table = None  # type: ignore
    Panel = None  # type: ignore
    Layout = None  # type: ignore
    Text = None  # type: ignore
    Live = None  # type: ignore
    box = None  # type: ignore
    RICH_AVAILABLE = False

try:
    from flask import Flask, render_template, jsonify, request as flask_request  # type: ignore
    import jinja2
    FLASK_AVAILABLE = True
except ImportError:
    Flask = None  # type: ignore
    render_template = None  # type: ignore
    jsonify = None  # type: ignore
    flask_request = None  # type: ignore
    jinja2 = None  # type: ignore
    FLASK_AVAILABLE = False


# Global lock to avoid interleaved output when using multi-target threading
STDOUT_LOCK = threading.Lock()

# Global lock for serializing HTTP calls (used by multi-target mode / optional)
# Must be re-entrant because requests' request() calls send() internally and we may wrap both
HTTP_SERIAL_LOCK = threading.RLock()

# Global lock for session file load/save (Instaloader session file is shared across targets)
SESSION_FILE_LOCK = threading.Lock()

# Whether requests Session methods have already been monkey-patched
REQUESTS_PATCHED = False

# Per-thread output buffers for redirect/session detection (multi-target safe)
LAST_OUTPUT_BY_THREAD = {}

# Thread-local storage for progress bar state (multi-target safe)
_thread_local = threading.local()


# ===========================
# Web Dashboard Flask Server
# ===========================

# Helper function to run Flask app with suppressed startup messages
def run_flask_quietly(app, host, port, debug=False, use_reloader=False, threaded=True):
    import sys

    # Filter class that suppresses Flask startup messages but allows errors through
    class FilteredWriter:
        def __init__(self, original_stream):
            self.original = original_stream

        def write(self, s):
            # Filter out Flask/werkzeug startup messages
            if isinstance(s, str):
                # Suppress common Flask startup messages
                if any(msg in s for msg in [
                    "* Serving Flask app",
                    "* Debug mode:",
                    " * Running on",
                    "WARNING: This is a development server",
                    "Press CTRL+C to quit",
                    "Address already in use"
                ]):
                    return  # Suppress these messages
                # Suppress Flask's port-in-use message, but not our formatted version (which contains asterisks)
                if "is in use by another program" in s and "*" not in s:
                    return
                # Allow everything else (errors, warnings, etc.) through
            self.original.write(s)

        def flush(self):
            self.original.flush()

        def __getattr__(self, name):
            # Delegate all other attributes to the original stream
            return getattr(self.original, name)

    # Wrap stdout and stderr with filters
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    filtered_stdout = FilteredWriter(old_stdout)
    filtered_stderr = FilteredWriter(old_stderr)

    try:
        sys.stdout = filtered_stdout
        sys.stderr = filtered_stderr

        # Run Flask (startup messages will be filtered)
        try:
            app.run(host=host, port=port, debug=debug, use_reloader=use_reloader, threaded=threaded)
        except (OSError, SystemExit) as e:
            # Restore streams first so the error prints correctly
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            # Check if this is a port-in-use error
            is_port_error = (
                (isinstance(e, OSError) and "Address already in use" in str(e)) or
                (isinstance(e, SystemExit) and e.code == 1)
            )

            if is_port_error:
                print("*" * HORIZONTAL_LINE)
                print(f"* Error: Port {port} is in use by another program. Either identify and stop that program or start the server with a different port.\n")
                print(f"* Web Dashboard will NOT be available!")
                print("*" * HORIZONTAL_LINE)
            else:
                raise e
    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# Creates and configures the Flask web application
def create_web_dashboard_app():
    """
    Note: Web Dashboard is intended for localhost use only as current implementation does not have CSRF protection
    (like Flask-WTF) or authentication
    """
    global WEB_DASHBOARD_TEMPLATE_DIR
    if not FLASK_AVAILABLE:
        return None

    # Type guard: Flask is available at this point
    assert Flask is not None
    assert render_template is not None
    assert jsonify is not None
    assert flask_request is not None

    import logging
    # Suppress Flask and werkzeug logging more aggressively
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)  # Only show errors, suppress info/debug/warning
    # Also suppress Flask's own logger
    flask_log = logging.getLogger('flask')
    flask_log.setLevel(logging.ERROR)

    # Suppress Flask startup messages by setting environment variable
    os.environ['FLASK_ENV'] = 'production'
    # Note: We don't set WERKZEUG_RUN_MAIN here because it causes issues when use_reloader=False
    # The FilteredWriter in run_flask_quietly() will handle suppressing startup messages

    # Determine template directory
    template_dir = None
    candidate_dirs = []  # For error messages

    # If explicitly set via config or CLI, use that
    if WEB_DASHBOARD_TEMPLATE_DIR:
        template_dir = os.path.expanduser(WEB_DASHBOARD_TEMPLATE_DIR)
        candidate_dirs = [template_dir]  # For error message
        if not os.path.isdir(template_dir):
            print("\n" + "*" * HORIZONTAL_LINE)
            print(f"* Error: Web Dashboard template directory not found: {template_dir}\n")
            print(f"  Please check the WEB_DASHBOARD_TEMPLATE_DIR setting or --web-dashboard-template-dir flag")
            print(f"  The directory must exist and contain index.html\n")
            print(f"* Web Dashboard will NOT be available!")
            print("*" * HORIZONTAL_LINE)
            return None
    else:
        # Auto-detect: try script directory first (for direct execution)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidate_dirs = [
            os.path.join(script_dir, 'templates'),
        ]

        # For pip-installed packages, also check package directory
        # Try to find templates in common package locations
        try:
            import importlib.util
            spec = importlib.util.find_spec('instagram_monitor')
            if spec and spec.origin:
                package_dir = os.path.dirname(spec.origin)
                package_template_dir = os.path.join(package_dir, 'templates')
                if package_template_dir not in candidate_dirs:  # Avoid duplicates
                    candidate_dirs.append(package_template_dir)
        except (ImportError, AttributeError, ValueError):
            pass

        # Try each candidate directory
        for candidate in candidate_dirs:
            index_path = os.path.join(candidate, 'index.html')
            if os.path.isdir(candidate) and os.path.isfile(index_path):
                template_dir = candidate
                break

    # Verify template directory was found
    if not template_dir:
        print("\n" + "*" * HORIZONTAL_LINE)
        print(f"* Error: Web Dashboard templates not found\n")
        print(f"  The tool searched for templates in the following locations:")
        for candidate in candidate_dirs:
            print(f"     - {candidate}")
        print()
        print(f"  To fix this, you can:")
        print(f"    1. Ensure templates/ directory exists in the script directory")
        print(f"    2. Set WEB_DASHBOARD_TEMPLATE_DIR in your config file")
        print(f"    3. Use --web-dashboard-template-dir flag to specify the template directory")
        print(f"    4. If installed via pip, ensure the package includes the templates directory\n")
        print(f"* Web Dashboard will NOT be available!")
        print("*" * HORIZONTAL_LINE)
        return None

    # Final verification that index.html exists
    index_path = os.path.join(template_dir, 'index.html')
    if not os.path.isfile(index_path):
        print("\n" + "*" * HORIZONTAL_LINE)
        print(f"* Error: Template file 'index.html' not found in: {template_dir}\n")
        print(f"  The template directory exists, but is missing the required index.html file\n")
        print(f"* Web Dashboard will NOT be available!")
        print("*" * HORIZONTAL_LINE)
        return None

    app = Flask(__name__, template_folder=template_dir)

    # Update global variable so it shows in dashboard
    WEB_DASHBOARD_TEMPLATE_DIR = template_dir

    @app.route('/')
    def index():  # type: ignore
        return render_template('index.html')  # type: ignore[misc]

    @app.route('/api/status')
    def api_status():  # type: ignore
        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
            data = WEB_DASHBOARD_DATA.copy()
            # Calculate uptime
            if data.get('start_time'):
                uptime_delta = datetime.now() - data['start_time']
                hours, remainder = divmod(int(uptime_delta.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                data['uptime'] = f"{hours}h {minutes}m {seconds}s"
            return jsonify(data)  # type: ignore

    # Catch TemplateNotFound specifically to show friendly error
    if jinja2 is not None:
        @app.errorhandler(jinja2.exceptions.TemplateNotFound)  # type: ignore
        def handle_template_not_found(e):
            return f"""
            <html>
                <body style="font-family: sans-serif; background: #111; color: #ff6b6b; padding: 40px; text-align: center;">
                    <h1 style="font-size: 24px; margin-bottom: 16px;">⚠️ Template Not Found</h1>
                    <p style="font-size: 16px; color: #ddd;">The application could not find the required template file: <strong>{e.name}</strong></p>  # type: ignore
                    <div style="background: #222; padding: 20px; border-radius: 8px; margin: 30px auto; max-width: 600px; text-align: left; font-family: monospace; color: #aaa;">
                        <strong>Configured Template Directory:</strong><br>
                        <span style="color: #4ec9b0;">{template_dir}</span>
                    </div>
                    <p style="color: #888;">Please verify that the directory exists and contains 'index.html'.</p>
                </body>
            </html>
            """, 500

    @app.route('/api/mode', methods=['POST'])
    def api_set_mode():  # type: ignore
        global DASHBOARD_MODE
        data = flask_request.get_json()  # type: ignore
        if data and 'mode' in data:
            DASHBOARD_MODE = data['mode']
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                WEB_DASHBOARD_DATA['dashboard_mode'] = DASHBOARD_MODE
            return jsonify({'success': True, 'mode': DASHBOARD_MODE})  # type: ignore
        return jsonify({'success': False}), 400  # type: ignore

    @app.route('/api/trigger-check', methods=['POST'])
    def api_trigger_check():  # type: ignore
        global MANUAL_CHECK_TRIGGERED
        data = flask_request.get_json(silent=True) or {}  # type: ignore
        target = data.get('target')

        if target:
            target = target.strip().lower()
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                if target in WEB_DASHBOARD_RECHECK_EVENTS:
                    WEB_DASHBOARD_RECHECK_EVENTS[target].set()
                    msg = f"Recheck triggered for {target}"
                    success = True
                else:
                    msg = f"Recheck failed: target {target} not running"
                    success = False
        else:
            # Trigger all
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                for t_event in WEB_DASHBOARD_RECHECK_EVENTS.values():
                    t_event.set()
            MANUAL_CHECK_TRIGGERED.set()  # type: ignore
            msg = "Recheck all triggered"
            success = True

        add_web_dashboard_activity(msg)
        return jsonify({'success': success, 'message': msg})  # type: ignore

    @app.route('/api/targets', methods=['GET', 'POST'])  # type: ignore[misc]
    def api_targets():  # type: ignore[return]
        global WEB_DASHBOARD_DATA
        if flask_request.method == 'GET':  # type: ignore
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                return jsonify({'targets': WEB_DASHBOARD_DATA.get('targets', {})})  # type: ignore
        elif flask_request.method == 'POST':  # type: ignore
            data = flask_request.get_json()  # type: ignore
            if not data or 'username' not in data:
                return jsonify({'success': False, 'error': 'Username required'}), 400  # type: ignore
            username = data['username'].strip().lower()
            if not username:
                return jsonify({'success': False, 'error': 'Username required'}), 400  # type: ignore
            start_now = data.get('start', False)

            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                if username in WEB_DASHBOARD_DATA['targets']:
                    return jsonify({'success': False, 'error': 'Target already exists'}), 400  # type: ignore
                WEB_DASHBOARD_DATA['targets'][username] = {
                    'followers': None,
                    'following': None,
                    'posts': None,
                    'status': 'Idle',
                    'added': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'last_checked': None
                }

            add_web_dashboard_activity(f"Added target: {username}")

            # Start monitoring if requested
            if start_now:
                start_monitoring_for_target(username)

            return jsonify({'success': True, 'username': username})  # type: ignore

    @app.route('/api/targets/<username>', methods=['DELETE'])
    def api_delete_target(username):  # type: ignore
        global WEB_DASHBOARD_DATA
        username = username.strip().lower()

        # Stop monitoring if running
        stop_monitoring_for_target(username)

        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
            if username in WEB_DASHBOARD_DATA['targets']:
                del WEB_DASHBOARD_DATA['targets'][username]
                removed = True
            else:
                removed = False

        if removed:
            add_web_dashboard_activity(f"Removed target: {username}")
            return jsonify({'success': True})  # type: ignore
        return jsonify({'success': False, 'error': 'Target not found'}), 404  # type: ignore

    @app.route('/api/monitoring/start', methods=['POST'])
    def api_start_monitoring():  # type: ignore
        data = flask_request.get_json(silent=True) or {}  # type: ignore
        target = data.get('target')

        if target:
            success = start_monitoring_for_target(target)
        else:
            # Start all targets
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                targets_to_start = list(WEB_DASHBOARD_DATA['targets'].keys())
            for t in targets_to_start:
                start_monitoring_for_target(t)
            success = True

        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
            WEB_DASHBOARD_DATA['is_monitoring'] = True
        return jsonify({'success': success})  # type: ignore

    @app.route('/api/monitoring/stop', methods=['POST'])
    def api_stop_monitoring():  # type: ignore
        data = flask_request.get_json(silent=True) or {}  # type: ignore[union-attr]
        target = data.get('target')

        if target:
            stop_monitoring_for_target(target)
        else:
            # Stop all targets
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore[union-attr]
                targets_to_stop = list(WEB_DASHBOARD_DATA['targets'].keys())
            for t in targets_to_stop:
                stop_monitoring_for_target(t)

        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
            # Check if any monitors still running
            active = any(t.is_alive() for t in WEB_DASHBOARD_MONITOR_THREADS.values())
            WEB_DASHBOARD_DATA['is_monitoring'] = active
        return jsonify({'success': True})  # type: ignore

    @app.route('/api/settings', methods=['GET', 'POST'])  # type: ignore[misc]
    def api_settings():  # type: ignore[return]
        global INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH
        global STATUS_NOTIFICATION, FOLLOWERS_NOTIFICATION, ERROR_NOTIFICATION, WEBHOOK_ENABLED, WEBHOOK_URL
        global DETAILED_FOLLOWER_LOGGING, DEBUG_MODE, SESSION_USERNAME
        global SKIP_GETTING_STORY_DETAILS, SKIP_GETTING_POSTS_DETAILS, GET_MORE_POST_DETAILS
        global ENABLE_JITTER, DETECT_CHANGED_PROFILE_PIC, SKIP_SESSION, CLI_CONFIG_PATH
        global DOTENV_FILE, WEB_DASHBOARD_TEMPLATE_DIR, LOCAL_TIMEZONE, OUTPUT_DIR, CSV_FILE

        if flask_request.method == 'GET':  # type: ignore
            return jsonify({  # type: ignore
                'check_interval': INSTA_CHECK_INTERVAL,
                'random_low': RANDOM_SLEEP_DIFF_LOW,
                'random_high': RANDOM_SLEEP_DIFF_HIGH,
                'email_notifications': STATUS_NOTIFICATION,
                'follower_notifications': FOLLOWERS_NOTIFICATION,
                'error_notifications': ERROR_NOTIFICATION,
                'webhook_enabled': WEBHOOK_ENABLED,
                'webhook_url': WEBHOOK_URL,
                'detailed_logging': DETAILED_FOLLOWER_LOGGING,
                'debug_mode': DEBUG_MODE,
                'session_username': SESSION_USERNAME,
                # New fields
                'skip_stories': SKIP_GETTING_STORY_DETAILS,
                'skip_posts': SKIP_GETTING_POSTS_DETAILS,
                'get_more_post_details': GET_MORE_POST_DETAILS,
                'enable_jitter': ENABLE_JITTER,
                'profile_pic_changes': DETECT_CHANGED_PROFILE_PIC,
                'skip_session_login': SKIP_SESSION,
                'config_file': CLI_CONFIG_PATH or "None",
                'dotenv_file': DOTENV_FILE or "None",
                'template_dir': WEB_DASHBOARD_TEMPLATE_DIR or "Auto",
                'local_timezone': LOCAL_TIMEZONE,
                'csv_file': "Enabled" if CSV_FILE else "Disabled",
                'output_dir': OUTPUT_DIR or "-"
            })
        elif flask_request.method == 'POST':  # type: ignore
            data = flask_request.get_json()  # type: ignore
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400  # type: ignore

            if 'check_interval' in data:
                INSTA_CHECK_INTERVAL = max(300, int(data['check_interval']))
            if 'random_low' in data:
                RANDOM_SLEEP_DIFF_LOW = max(0, int(data['random_low']))
            if 'random_high' in data:
                RANDOM_SLEEP_DIFF_HIGH = max(0, int(data['random_high']))
            if 'email_notifications' in data:
                STATUS_NOTIFICATION = bool(data['email_notifications'])
            if 'follower_notifications' in data:
                FOLLOWERS_NOTIFICATION = bool(data['follower_notifications'])
            if 'webhook_enabled' in data:
                WEBHOOK_ENABLED = bool(data['webhook_enabled'])
            if 'webhook_url' in data:
                webhook_url = data['webhook_url']
                if webhook_url and not validate_webhook_url(webhook_url):
                    return jsonify({'success': False, 'error': 'Invalid webhook URL format. Must be HTTPS URL.'}), 400  # type: ignore
                WEBHOOK_URL = webhook_url
            if 'detailed_logging' in data:
                DETAILED_FOLLOWER_LOGGING = bool(data['detailed_logging'])
            if 'debug_mode' in data:
                DEBUG_MODE = bool(data['debug_mode'])

            add_web_dashboard_activity("Settings updated from web dashboard")
            return jsonify({'success': True})  # type: ignore

    @app.route('/api/session', methods=['GET', 'POST'])  # type: ignore[misc]
    def api_session():  # type: ignore[return]
        global SESSION_USERNAME, SKIP_SESSION

        if flask_request.method == 'GET':  # type: ignore
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                return jsonify(WEB_DASHBOARD_DATA.get('session', {}))  # type: ignore
        elif flask_request.method == 'POST':  # type: ignore
            data = flask_request.get_json()  # type: ignore
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400  # type: ignore

            username = data.get('username', '').strip()
            method = data.get('method', 'firefox')

            if username:
                SESSION_USERNAME = username
                SKIP_SESSION = False
                with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                    WEB_DASHBOARD_DATA['session'] = {'username': username, 'active': False, 'method': method}
                add_web_dashboard_activity(f"Session configured for: {username}")
                return jsonify({'success': True, 'message': f'Session set for {username}'})  # type: ignore
            return jsonify({'success': False, 'error': 'Username required'}), 400  # type: ignore

    @app.route('/api/session/test', methods=['POST'])
    def api_test_session():  # type: ignore
        if not SESSION_USERNAME:
            return jsonify({'success': False, 'error': 'No session configured'})  # type: ignore

        try:
            L = Instaloader()
            L.load_session_from_file(SESSION_USERNAME)
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                WEB_DASHBOARD_DATA['session']['active'] = True
            add_web_dashboard_activity(f"Session test successful: {SESSION_USERNAME}")
            return jsonify({'success': True, 'username': SESSION_USERNAME})  # type: ignore
        except Exception as e:
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                WEB_DASHBOARD_DATA['session']['active'] = False
            return jsonify({'success': False, 'error': str(e)})  # type: ignore

    @app.route('/api/activity/clear', methods=['POST'])
    def api_clear_activity():  # type: ignore
        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
            WEB_DASHBOARD_DATA['activities'] = []
        return jsonify({'success': True})  # type: ignore

    return app


# Starts monitoring for a specific target in standalone mode
def start_monitoring_for_target(username):
    global WEB_DASHBOARD_MONITOR_THREADS, WEB_DASHBOARD_STOP_EVENTS

    if username in WEB_DASHBOARD_MONITOR_THREADS and WEB_DASHBOARD_MONITOR_THREADS[username].is_alive():
        return False  # Already monitoring

    stop_event = threading.Event()
    WEB_DASHBOARD_STOP_EVENTS[username] = stop_event

    def _monitor_runner(user, stop_evt):
        global WEB_DASHBOARD_RECHECK_EVENTS
        try:
            recheck_event = threading.Event()
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                 WEB_DASHBOARD_RECHECK_EVENTS[user] = recheck_event

            add_web_dashboard_activity(f"Started monitoring: {user}")
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore[union-attr]
                if user in WEB_DASHBOARD_DATA['targets']:
                    WEB_DASHBOARD_DATA['targets'][user]['status'] = 'Starting'

            # Run the actual monitoring (with stop event check)
            instagram_monitor_user(
                user,
                "",  # No CSV file
                SKIP_SESSION,
                SKIP_FOLLOWERS,
                SKIP_FOLLOWINGS,
                SKIP_GETTING_STORY_DETAILS,
                SKIP_GETTING_POSTS_DETAILS,
                GET_MORE_POST_DETAILS,
                stop_event=stop_evt,
                user_root_path=OUTPUT_DIR
            )
        except Exception as e:
            add_web_dashboard_activity(f"Error monitoring {user}: {str(e)}")
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                if user in WEB_DASHBOARD_DATA['targets']:
                    WEB_DASHBOARD_DATA['targets'][user]['status'] = 'Error'
        finally:
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                if user in WEB_DASHBOARD_RECHECK_EVENTS:
                    del WEB_DASHBOARD_RECHECK_EVENTS[user]

    t = threading.Thread(target=_monitor_runner, args=(username, stop_event), daemon=True, name=f"monitor:{username}")
    WEB_DASHBOARD_MONITOR_THREADS[username] = t
    t.start()
    return True


# Stops monitoring for a specific target
def stop_monitoring_for_target(username):
    global WEB_DASHBOARD_STOP_EVENTS, WEB_DASHBOARD_MONITOR_THREADS

    if username in WEB_DASHBOARD_STOP_EVENTS:
        WEB_DASHBOARD_STOP_EVENTS[username].set()
        if username in WEB_DASHBOARD_MONITOR_THREADS:
            add_web_dashboard_activity(f"Stopping monitoring: {username}")
        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
            if username in WEB_DASHBOARD_DATA['targets']:
                WEB_DASHBOARD_DATA['targets'][username]['status'] = 'Stopped'

    # Clean up thread reference
    if username in WEB_DASHBOARD_MONITOR_THREADS:
        del WEB_DASHBOARD_MONITOR_THREADS[username]
    if username in WEB_DASHBOARD_STOP_EVENTS:
        del WEB_DASHBOARD_STOP_EVENTS[username]


# Starts the Flask web server in a background thread
def start_web_dashboard_server():
    global WEB_DASHBOARD_APP, WEB_DASHBOARD_THREAD

    if not FLASK_AVAILABLE:
        return False

    if not WEB_DASHBOARD_ENABLED:
        return False

    try:
        WEB_DASHBOARD_APP = create_web_dashboard_app()
        if WEB_DASHBOARD_APP is None:
            return False
    except Exception as e:
        # create_web_dashboard_app() already prints nice error messages, but catch any unexpected errors
        print(f"\n* Error: Failed to create web dashboard application: {e}\n")
        return False

    def run_server():
        assert WEB_DASHBOARD_APP is not None  # Type guard
        run_flask_quietly(WEB_DASHBOARD_APP, WEB_DASHBOARD_HOST, WEB_DASHBOARD_PORT, debug=False, use_reloader=False, threaded=True)

    WEB_DASHBOARD_THREAD = threading.Thread(target=run_server, daemon=True, name="web_ui_server")
    WEB_DASHBOARD_THREAD.start()

    print(f"\n* Web Dashboard available at:\t\thttp://{WEB_DASHBOARD_HOST}:{WEB_DASHBOARD_PORT}/")
    return True


# Updates the web dashboard data store
def update_web_dashboard_data(targets=None, config=None, check_count=None, last_check=None, next_check=None):
    with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
        if targets is not None:
            if 'targets' not in WEB_DASHBOARD_DATA:
                WEB_DASHBOARD_DATA['targets'] = {}
            for user, data in targets.items():
                if user not in WEB_DASHBOARD_DATA['targets']:
                    WEB_DASHBOARD_DATA['targets'][user] = {}
                # Deep merge the target data
                if isinstance(data, dict):
                    WEB_DASHBOARD_DATA['targets'][user].update(data)
                else:
                    WEB_DASHBOARD_DATA['targets'][user] = data
        if config is not None:
            if 'config' not in WEB_DASHBOARD_DATA:
                WEB_DASHBOARD_DATA['config'] = {}
            if isinstance(config, dict):
                WEB_DASHBOARD_DATA['config'].update(config)
            else:
                WEB_DASHBOARD_DATA['config'] = config
        if check_count is not None:
            WEB_DASHBOARD_DATA['check_count'] = check_count
        if last_check is not None:
            WEB_DASHBOARD_DATA['last_check'] = last_check
        if next_check is not None:
            WEB_DASHBOARD_DATA['next_check'] = next_check
        WEB_DASHBOARD_DATA['dashboard_mode'] = DASHBOARD_MODE


# Logs an activity to both Dashboard and Web Dashboard activity feeds
def log_activity(message, user=None):
    global DASHBOARD_DATA, WEB_DASHBOARD_DATA

    timestamp_full = datetime.now()
    timestamp_str = timestamp_full.strftime("%H:%M:%S")

    # Format message with user if provided
    display_message = f"[{user}] {message}" if user else message

    activity_item_rich = {'time': timestamp_str, 'message': display_message, 'dt': timestamp_full}
    activity_item_web = {'time': timestamp_str, 'message': display_message}

    # Update Dashboard data
    if 'activities' not in DASHBOARD_DATA:
        DASHBOARD_DATA['activities'] = []
    DASHBOARD_DATA['activities'].insert(0, activity_item_rich)
    DASHBOARD_DATA['activities'] = DASHBOARD_DATA['activities'][:50]  # Last 50 for Rich

    # Update Web Dashboard data (thread-safe)
    if WEB_DASHBOARD_DATA_LOCK:
        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore[union-attr]
            if 'activities' not in WEB_DASHBOARD_DATA:
                WEB_DASHBOARD_DATA['activities'] = []
            WEB_DASHBOARD_DATA['activities'].insert(0, activity_item_web)
            WEB_DASHBOARD_DATA['activities'] = WEB_DASHBOARD_DATA['activities'][:100]  # Last 100 for Web

    # If Dashboard is live, trigger an update
    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        update_dashboard()


# Legacy wrapper for add_web_dashboard_activity
def add_web_dashboard_activity(message):
    log_activity(message)


def _thread_key() -> int:
    return threading.get_ident()


# Resets the thread-specific output buffer for redirect/session detection
def reset_thread_output() -> None:
    with STDOUT_LOCK:
        LAST_OUTPUT_BY_THREAD[_thread_key()] = []


# Returns the thread-specific output buffer for redirect/session detection
def get_thread_output() -> list:
    with STDOUT_LOCK:
        return list(LAST_OUTPUT_BY_THREAD.get(_thread_key(), []))


# Returns a label for the current session (username or anonymous)
def session_label() -> str:
    # Session is shared across targets, include it in error notifications for clarity
    return SESSION_USERNAME if SESSION_USERNAME else "<anonymous>"


# Displays comparison between reported and actual follower/following counts
def show_follow_info(followers_reported: int, followers_actual: int, followings_reported: int, followings_actual: int) -> None:
    print(f"* Followers: reported ({followers_reported}) actual ({followers_actual}). Followings: reported ({followings_reported}) actual ({followings_actual})")


# Logger class to output messages to stdout and log file
class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.logfile = open(filename, "a", buffering=1, encoding="utf-8")

    def write(self, message):
        global last_output
        with STDOUT_LOCK:
            if message != '\n':
                last_output.append(message)
                tid = _thread_key()
                if tid not in LAST_OUTPUT_BY_THREAD:
                    LAST_OUTPUT_BY_THREAD[tid] = []
                LAST_OUTPUT_BY_THREAD[tid].append(message)
            if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                self.terminal.write(message)
                self.terminal.flush()
            self.logfile.write(message)
            self.logfile.flush()

    def flush(self):
        pass


# Signal handler when user presses Ctrl+C
def signal_handler(sig, frame):
    if getattr(_thread_local, 'pbar', None) is not None:
        close_pbar()

    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        stop_dashboard()

    sys.stdout = stdout_bck
    print('\n* You pressed Ctrl+C, tool is terminated.')
    os._exit(0)


# Checks internet connectivity
def check_internet(url=CHECK_INTERNET_URL, timeout=CHECK_INTERNET_TIMEOUT):
    try:
        _ = req.get(url, headers={'User-Agent': USER_AGENT}, timeout=timeout)
        return True
    except req.RequestException as e:
        print(f"* No connectivity, please check your network:\n\n{e}")
        return False


# Clears the terminal screen
def clear_screen(enabled=True):
    if not enabled:
        return
    try:
        if platform.system() == 'Windows':
            os.system('cls')
        else:
            os.system('clear')
    except Exception:
        print("* Cannot clear the screen contents")


# Converts absolute value of seconds to human readable format
def display_time(seconds, granularity=2):
    intervals = (
        ('years', 31556952),  # approximation
        ('months', 2629746),  # approximation
        ('weeks', 604800),    # 60 * 60 * 24 * 7
        ('days', 86400),      # 60 * 60 * 24
        ('hours', 3600),      # 60 * 60
        ('minutes', 60),
        ('seconds', 1),
    )
    result = []

    if seconds > 0:
        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append(f"{value} {name}")
        return ', '.join(result[:granularity])
    else:
        return '0 seconds'


# Calculates time span between two timestamps, accepts timestamp integers, floats and datetime objects
def calculate_timespan(timestamp1, timestamp2, show_weeks=True, show_hours=True, show_minutes=True, show_seconds=False, granularity=3):
    result = []
    intervals = ['years', 'months', 'weeks', 'days', 'hours', 'minutes', 'seconds']
    ts1 = timestamp1
    ts2 = timestamp2

    if isinstance(timestamp1, str):
        try:
            timestamp1 = isoparse(timestamp1)
        except Exception:
            return ""

    if isinstance(timestamp1, int):
        dt1 = datetime.fromtimestamp(int(ts1), tz=timezone.utc)
    elif isinstance(timestamp1, float):
        ts1 = int(round(ts1))
        dt1 = datetime.fromtimestamp(ts1, tz=timezone.utc)
    elif isinstance(timestamp1, datetime):
        dt1 = timestamp1
        if dt1.tzinfo is None:
            dt1 = pytz.utc.localize(dt1)
        else:
            dt1 = dt1.astimezone(pytz.utc)
        ts1 = int(round(dt1.timestamp()))
    else:
        return ""

    if isinstance(timestamp2, str):
        try:
            timestamp2 = isoparse(timestamp2)
        except Exception:
            return ""

    if isinstance(timestamp2, int):
        dt2 = datetime.fromtimestamp(int(ts2), tz=timezone.utc)
    elif isinstance(timestamp2, float):
        ts2 = int(round(ts2))
        dt2 = datetime.fromtimestamp(ts2, tz=timezone.utc)
    elif isinstance(timestamp2, datetime):
        dt2 = timestamp2
        if dt2.tzinfo is None:
            dt2 = pytz.utc.localize(dt2)
        else:
            dt2 = dt2.astimezone(pytz.utc)
        ts2 = int(round(dt2.timestamp()))
    else:
        return ""

    if ts1 >= ts2:
        ts_diff = ts1 - ts2
    else:
        ts_diff = ts2 - ts1
        dt1, dt2 = dt2, dt1

    if ts_diff > 0:
        date_diff = relativedelta.relativedelta(dt1, dt2)
        years = date_diff.years
        months = date_diff.months
        days_total = date_diff.days

        if show_weeks:
            weeks = days_total // 7
            days = days_total % 7
        else:
            weeks = 0
            days = days_total

        hours = date_diff.hours if show_hours or ts_diff <= 86400 else 0
        minutes = date_diff.minutes if show_minutes or ts_diff <= 3600 else 0
        seconds = date_diff.seconds if show_seconds or ts_diff <= 60 else 0

        date_list = [years, months, weeks, days, hours, minutes, seconds]

        for index, interval in enumerate(date_list):
            if interval > 0:
                name = intervals[index]
                if interval == 1:
                    name = name.rstrip('s')
                result.append(f"{interval} {name}")

        return ', '.join(result[:granularity])
    else:
        return '0 seconds'


# Sends email notification
def send_email(subject, body, body_html, use_ssl, image_file="", image_name="image1", smtp_timeout=15):
    fqdn_re = re.compile(r'(?=^.{4,253}$)(^((?!-)[a-zA-Z0-9-]{1,63}(?<!-)\.)+[a-zA-Z]{2,63}\.?$)')
    email_re = re.compile(r'[^@]+@[^@]+\.[^@]+')

    try:
        ipaddress.ip_address(str(SMTP_HOST))
    except ValueError:
        if not fqdn_re.search(str(SMTP_HOST)):
            print("Error sending email - SMTP settings are incorrect (invalid IP address/FQDN in SMTP_HOST)")
            return 1

    try:
        port = int(SMTP_PORT)
        if not (1 <= port <= 65535):
            raise ValueError
    except ValueError:
        print("Error sending email - SMTP settings are incorrect (invalid port number in SMTP_PORT)")
        return 1

    if not email_re.search(str(SENDER_EMAIL)) or not email_re.search(str(RECEIVER_EMAIL)):
        print("Error sending email - SMTP settings are incorrect (invalid email in SENDER_EMAIL or RECEIVER_EMAIL)")
        return 1

    if not SMTP_USER or not isinstance(SMTP_USER, str) or SMTP_USER == "your_smtp_user" or not SMTP_PASSWORD or not isinstance(SMTP_PASSWORD, str) or SMTP_PASSWORD == "your_smtp_password":
        print("Error sending email - SMTP settings are incorrect (check SMTP_USER & SMTP_PASSWORD variables)")
        return 1

    if not subject or not isinstance(subject, str):
        print("Error sending email - SMTP settings are incorrect (subject is not a string or is empty)")
        return 1

    if not body and not body_html:
        print("Error sending email - SMTP settings are incorrect (body and body_html cannot be empty at the same time)")
        return 1

    try:
        if use_ssl:
            ssl_context = ssl.create_default_context()
            smtpObj = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=smtp_timeout)
            smtpObj.starttls(context=ssl_context)
        else:
            smtpObj = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=smtp_timeout)
        smtpObj.login(SMTP_USER, SMTP_PASSWORD)
        email_msg = MIMEMultipart('alternative')
        email_msg["From"] = SENDER_EMAIL
        email_msg["To"] = RECEIVER_EMAIL
        email_msg["Subject"] = str(Header(subject, 'utf-8'))

        if body:
            part1 = MIMEText(body, 'plain')
            part1 = MIMEText(body.encode('utf-8'), 'plain', _charset='utf-8')
            email_msg.attach(part1)

        if body_html:
            part2 = MIMEText(body_html, 'html')
            part2 = MIMEText(body_html.encode('utf-8'), 'html', _charset='utf-8')
            email_msg.attach(part2)

        if image_file:
            with open(image_file, 'rb') as fp:
                img_part = MIMEImage(fp.read())
            img_part.add_header('Content-ID', f'<{image_name}>')
            email_msg.attach(img_part)

        smtpObj.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, email_msg.as_string())
        smtpObj.quit()
    except Exception as e:
        print(f"Error sending email: {e}")
        return 1
    return 0


# Validates webhook URL format
def validate_webhook_url(url):
    if not url:
        return False
    if not url.startswith('https://'):
        return False
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.netloc or not parsed.scheme == 'https':
            return False
        return True
    except Exception:
        return False


# Helper function to send follower/following change webhooks
def send_follower_change_webhook(user, change_type, old_count, new_count, added_list, removed_list):
    diff = new_count - old_count
    diff_str = f"+{diff}" if diff > 0 else str(diff)

    webhook_fields = [
        {"name": "Old Count", "value": str(old_count), "inline": True},
        {"name": "New Count", "value": str(new_count), "inline": True},
        {"name": "Change", "value": diff_str, "inline": True},
    ]

    if added_list:
        field_name = "New Followers" if change_type == "followers" else "Added"
        webhook_fields.append({
            "name": field_name,
            "value": added_list[:DISCORD_FIELD_VALUE_LIMIT]  # type: ignore
        })

    if removed_list:
        field_name = "Lost Followers" if change_type == "followers" else "Removed"
        webhook_fields.append({
            "name": field_name,
            "value": removed_list[:DISCORD_FIELD_VALUE_LIMIT]  # type: ignore
        })

    # Use different emojis/colors for followers vs followings
    if change_type == "followers":
        emoji = "📈" if diff > 0 else "📉"
        color = 0x2ecc71 if diff > 0 else 0xe74c3c  # Green if gained, red if lost
    else:  # followings
        emoji = "📊"
        color = 0x3498db  # Blue

    title = f"{emoji} {user} {change_type.capitalize()} Changed"
    description = f"User **{user}** {change_type} changed from {old_count} to {new_count}"
    notification_type = "followers" if change_type == "followers" else "status"

    return send_webhook(
        title,
        description,
        color=color,
        fields=webhook_fields,
        notification_type=notification_type
    )


# Sends webhook notification (Discord-compatible)
def send_webhook(title, description, color=0x7289DA, fields=None, image_url=None, notification_type="status"):
    if not WEBHOOK_ENABLED or not WEBHOOK_URL:
        return 1

    # Validate webhook URL
    if not validate_webhook_url(WEBHOOK_URL):
        if DEBUG_MODE:
            print(f"* Webhook error: Invalid webhook URL format")
        return 1

    # Check if this notification type is enabled
    if notification_type == "status" and not WEBHOOK_STATUS_NOTIFICATION:
        return 1
    elif notification_type == "followers" and not WEBHOOK_FOLLOWERS_NOTIFICATION:
        return 1
    elif notification_type == "error" and not WEBHOOK_ERROR_NOTIFICATION:
        return 1

    try:
        embed = {
            "title": title[:DISCORD_EMBED_TITLE_LIMIT] if title else "Instagram Monitor",  # type: ignore
            "description": description[:DISCORD_EMBED_DESCRIPTION_LIMIT] if description else "",  # type: ignore
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {
                "text": f"Instagram Monitor v{VERSION}"
            }
        }

        if fields:
            embed["fields"] = []
            for field in fields[:DISCORD_MAX_FIELDS]:  # type: ignore
                embed["fields"].append({
                    "name": str(field.get("name", ""))[:DISCORD_FIELD_NAME_LIMIT],  # type: ignore
                    "value": str(field.get("value", ""))[:DISCORD_FIELD_VALUE_LIMIT],  # type: ignore
                    "inline": field.get("inline", False)
                })

        if image_url:
            embed["image"] = {"url": image_url}

        payload: dict = {
            "embeds": [embed]
        }

        if WEBHOOK_USERNAME:
            payload["username"] = WEBHOOK_USERNAME

        if WEBHOOK_AVATAR_URL:
            payload["avatar_url"] = WEBHOOK_AVATAR_URL

        response = req.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code in (200, 204):
            if DEBUG_MODE:
                print(f"* Webhook notification sent successfully")
            return 0
        else:
            print(f"* Webhook error: HTTP {response.status_code} - {response.text[:200]}")
            return 1

    except Exception as e:
        print(f"* Error sending webhook: {e}")
        return 1


# Debug print helper - only prints if DEBUG_MODE is enabled
def debug_print(message):
    if DEBUG_MODE:
        timestamp = now_local_naive().strftime("%H:%M:%S.%f")[:-3]
        print(f"[DEBUG {timestamp}] {message}")


# Initializes the CSV file
def init_csv_file(csv_file_name):
    try:
        if not os.path.isfile(csv_file_name) or os.path.getsize(csv_file_name) == 0:
            with open(csv_file_name, 'a', newline='', buffering=1, encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=csvfieldnames, quoting=csv.QUOTE_NONNUMERIC)
                writer.writeheader()
    except Exception as e:
        raise RuntimeError(f"Could not initialize CSV file '{csv_file_name}': {e}")


# Writes CSV entry
def write_csv_entry(csv_file_name, timestamp, object_type, old, new):
    try:

        with open(csv_file_name, 'a', newline='', buffering=1, encoding="utf-8") as csv_file:
            csvwriter = csv.DictWriter(csv_file, fieldnames=csvfieldnames, quoting=csv.QUOTE_NONNUMERIC)
            csvwriter.writerow({'Date': timestamp, 'Type': object_type, 'Old': old, 'New': new})

    except Exception as e:
        raise RuntimeError(f"Failed to write to CSV file '{csv_file_name}': {e}")


# Randomizes how often to perform checks for user activity (INSTA_CHECK_INTERVAL)
def randomize_number(number, diff_low, diff_high):
    if number > diff_low:
        return (random.randint(number - diff_low, number + diff_high))
    else:
        return (random.randint(number, number + diff_high))


# Converts a datetime to local timezone and removes timezone info (naive)
def convert_to_local_naive(dt: Optional[datetime] = None):
    tz = pytz.timezone(LOCAL_TIMEZONE)

    if dt is not None:
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)

        dt_local = dt.astimezone(tz)

        return dt_local.replace(tzinfo=None)
    else:
        return None


# Returns current local time without timezone info (naive)
def now_local_naive():
    return datetime.now(pytz.timezone(LOCAL_TIMEZONE)).replace(microsecond=0, tzinfo=None)


# Returns current local time with timezone info (aware)
def now_local():
    return datetime.now(pytz.timezone(LOCAL_TIMEZONE))


# Converts UTC datetime object returned by Instagram API to datetime object in specified timezone
def convert_utc_datetime_to_tz_datetime(dt_utc):
    if not dt_utc:
        return None

    try:
        if dt_utc.tzinfo is None:
            dt_utc = pytz.utc.localize(dt_utc)
        return dt_utc.astimezone(pytz.timezone(LOCAL_TIMEZONE))
    except Exception:
        return None


# Converts UTC string returned by Instagram API to datetime object in specified timezone
def convert_utc_str_to_tz_datetime(dt_str):
    if not dt_str:
        return None

    try:
        dt = parse(dt_str)

        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)

        return dt.astimezone(pytz.timezone(LOCAL_TIMEZONE))

    except Exception:
        return None


# Returns the current date/time in human readable format; eg. Sun 21 Apr 2024, 15:08:45
def get_cur_ts(ts_str=""):
    return (f'{ts_str}{calendar.day_abbr[(now_local_naive()).weekday()]} {now_local_naive().strftime("%d %b %Y, %H:%M:%S")}')


# Prints the current date/time in human readable format with separator; eg. Sun 21 Apr 2024, 15:08:45
def print_cur_ts(ts_str=""):
    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        return
    print(get_cur_ts(str(ts_str)))
    print("─" * HORIZONTAL_LINE)


# Recomputes cycle-based liveness counter after INSTA_CHECK_INTERVAL changes
def recompute_liveness_check_counter() -> None:
    global LIVENESS_CHECK_COUNTER
    if LIVENESS_CHECK_INTERVAL and INSTA_CHECK_INTERVAL > 0:
        LIVENESS_CHECK_COUNTER = LIVENESS_CHECK_INTERVAL / INSTA_CHECK_INTERVAL
    else:
        LIVENESS_CHECK_COUNTER = 0


# Returns the timestamp/datetime object in human readable format (long version); eg. Sun 21 Apr 2024, 15:08:45
def get_date_from_ts(ts):
    tz = pytz.timezone(LOCAL_TIMEZONE)

    if isinstance(ts, str):
        try:
            ts = isoparse(ts)
        except Exception:
            return ""

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = pytz.utc.localize(ts)
        ts_new = ts.astimezone(tz)

    elif isinstance(ts, int):
        ts_new = datetime.fromtimestamp(ts, tz)

    elif isinstance(ts, float):
        ts_rounded = int(round(ts))
        ts_new = datetime.fromtimestamp(ts_rounded, tz)

    else:
        return ""

    return (f'{calendar.day_abbr[ts_new.weekday()]} {ts_new.strftime("%d %b %Y, %H:%M:%S")}')


# Returns the timestamp/datetime object in human readable format (short version); eg.
# Sun 21 Apr 15:08
# Sun 21 Apr 24, 15:08 (if show_year == True and current year is different)
# Sun 21 Apr 25, 15:08 (if always_show_year == True and current year can be the same)
# Sun 21 Apr (if show_hour == False)
# Sun 21 Apr 15:08:32 (if show_seconds == True)
# 21 Apr 15:08 (if show_weekday == False)
def get_short_date_from_ts(ts, show_year=False, show_hour=True, show_weekday=True, show_seconds=False, always_show_year=False):
    tz = pytz.timezone(LOCAL_TIMEZONE)
    if always_show_year:
        show_year = True

    if isinstance(ts, str):
        try:
            ts = isoparse(ts)
        except Exception:
            return ""

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = pytz.utc.localize(ts)
        ts_new = ts.astimezone(tz)

    elif isinstance(ts, int):
        ts_new = datetime.fromtimestamp(ts, tz)

    elif isinstance(ts, float):
        ts_rounded = int(round(ts))
        ts_new = datetime.fromtimestamp(ts_rounded, tz)

    else:
        return ""

    if show_hour:
        hour_strftime = " %H:%M:%S" if show_seconds else " %H:%M"
    else:
        hour_strftime = ""

    weekday_str = f"{calendar.day_abbr[ts_new.weekday()]} " if show_weekday else ""

    if (show_year and ts_new.year != datetime.now(tz).year) or always_show_year:
        hour_prefix = "," if show_hour else ""
        return f'{weekday_str}{ts_new.strftime(f"%d %b %y{hour_prefix}{hour_strftime}")}'
    else:
        return f'{weekday_str}{ts_new.strftime(f"%d %b{hour_strftime}")}'


# Returns the timestamp/datetime object in human readable format (only hour, minutes and optionally seconds): eg. 15:08:12
def get_hour_min_from_ts(ts, show_seconds=False):
    tz = pytz.timezone(LOCAL_TIMEZONE)

    if isinstance(ts, str):
        try:
            ts = isoparse(ts)
        except Exception:
            return ""

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = pytz.utc.localize(ts)
        ts_new = ts.astimezone(tz)

    elif isinstance(ts, int):
        ts_new = datetime.fromtimestamp(ts, tz)

    elif isinstance(ts, float):
        ts_rounded = int(round(ts))
        ts_new = datetime.fromtimestamp(ts_rounded, tz)

    else:
        return ""

    out_strf = "%H:%M:%S" if show_seconds else "%H:%M"
    return ts_new.strftime(out_strf)  # type: ignore[arg-type]


# Returns the range between two timestamps/datetime objects; eg. Sun 21 Apr 14:09 - 14:15
def get_range_of_dates_from_tss(ts1, ts2, between_sep=" - ", short=False):
    tz = pytz.timezone(LOCAL_TIMEZONE)

    if isinstance(ts1, datetime):
        ts1_new = int(round(ts1.timestamp()))
    elif isinstance(ts1, int):
        ts1_new = ts1
    elif isinstance(ts1, float):
        ts1_new = int(round(ts1))
    else:
        return ""

    if isinstance(ts2, datetime):
        ts2_new = int(round(ts2.timestamp()))
    elif isinstance(ts2, int):
        ts2_new = ts2
    elif isinstance(ts2, float):
        ts2_new = int(round(ts2))
    else:
        return ""

    ts1_strf = datetime.fromtimestamp(ts1_new, tz).strftime("%Y%m%d")
    ts2_strf = datetime.fromtimestamp(ts2_new, tz).strftime("%Y%m%d")

    if ts1_strf == ts2_strf:
        if short:
            out_str = f"{get_short_date_from_ts(ts1_new)}{between_sep}{get_hour_min_from_ts(ts2_new)}"
        else:
            out_str = f"{get_date_from_ts(ts1_new)}{between_sep}{get_hour_min_from_ts(ts2_new, show_seconds=True)}"
    else:
        if short:
            out_str = f"{get_short_date_from_ts(ts1_new)}{between_sep}{get_short_date_from_ts(ts2_new)}"
        else:
            out_str = f"{get_date_from_ts(ts1_new)}{between_sep}{get_date_from_ts(ts2_new)}"

    return str(out_str)


# Checks if the timezone name is correct
def is_valid_timezone(tz_name):
    return tz_name in pytz.all_timezones


# Signal handler for SIGUSR1 allowing to switch email notifications for new posts/reels/stories/followings/bio
def toggle_status_changes_notifications_signal_handler(sig, frame):
    global STATUS_NOTIFICATION
    STATUS_NOTIFICATION = not STATUS_NOTIFICATION
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Email notifications: [new posts/reels/stories/followings/bio/profile picture = {STATUS_NOTIFICATION}]")
    print_cur_ts("Timestamp:\t\t\t\t")


# Signal handler for SIGUSR2 allowing to switch email notifications for new followers
def toggle_followers_notifications_signal_handler(sig, frame):
    global FOLLOWERS_NOTIFICATION
    FOLLOWERS_NOTIFICATION = not FOLLOWERS_NOTIFICATION
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Email notifications: [followers = {FOLLOWERS_NOTIFICATION}]")
    print_cur_ts("Timestamp:\t\t\t\t")


# Signal handler for SIGTRAP allowing to increase check timer by INSTA_CHECK_SIGNAL_VALUE seconds
def increase_check_signal_handler(sig, frame):
    global INSTA_CHECK_INTERVAL
    INSTA_CHECK_INTERVAL = INSTA_CHECK_INTERVAL + INSTA_CHECK_SIGNAL_VALUE
    recompute_liveness_check_counter()
    if INSTA_CHECK_INTERVAL <= RANDOM_SLEEP_DIFF_LOW:
        check_interval_low = INSTA_CHECK_INTERVAL
    else:
        check_interval_low = INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Instagram timers: [check interval: {display_time(check_interval_low)} - {display_time(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH)}]")
    print_cur_ts("Timestamp:\t\t\t\t")


# Signal handler for SIGABRT allowing to decrease check timer by INSTA_CHECK_SIGNAL_VALUE seconds
def decrease_check_signal_handler(sig, frame):
    global INSTA_CHECK_INTERVAL
    if (INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW - INSTA_CHECK_SIGNAL_VALUE) > 0:
        INSTA_CHECK_INTERVAL = INSTA_CHECK_INTERVAL - INSTA_CHECK_SIGNAL_VALUE
    recompute_liveness_check_counter()
    if INSTA_CHECK_INTERVAL <= RANDOM_SLEEP_DIFF_LOW:
        check_interval_low = INSTA_CHECK_INTERVAL
    else:
        check_interval_low = INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Instagram timers: [check interval: {display_time(check_interval_low)} - {display_time(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH)}]")
    print_cur_ts("Timestamp:\t\t\t\t")


# Signal handler for SIGHUP allowing to reload secrets from .env
def reload_secrets_signal_handler(sig, frame):
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")

    # Disable autoscan if DOTENV_FILE set to none
    if DOTENV_FILE and DOTENV_FILE.lower() == 'none':
        env_path = None
    else:
        # Reload .env if python-dotenv is installed
        try:
            from dotenv import load_dotenv, find_dotenv
            if DOTENV_FILE:
                env_path = DOTENV_FILE
            else:
                env_path = find_dotenv()
            if env_path:
                load_dotenv(env_path, override=True)
            else:
                print("* No .env file found, skipping env-var reload")
        except ImportError:
            env_path = None
            print("* python-dotenv not installed, skipping env-var reload")

    if env_path:
        for secret in SECRET_KEYS:
            old_val = globals().get(secret)
            val = os.getenv(secret)
            if val is not None and val != old_val:
                globals()[secret] = val
                print(f"* Reloaded {secret} from {env_path}")

    print_cur_ts("Timestamp:\t\t\t\t")


# Saves user's image / video to selected file name
def save_pic_video(image_video_url, image_video_file_name, custom_mdate_ts=0):
    try:
        image_video_response = req.get(image_video_url, headers={'User-Agent': USER_AGENT}, timeout=FUNCTION_TIMEOUT, stream=True)
        image_video_response.raise_for_status()
        url_time = image_video_response.headers.get('last-modified')
        url_time_in_tz_ts = 0
        if url_time and not custom_mdate_ts:
            url_time_in_tz = convert_utc_str_to_tz_datetime(url_time)
            if url_time_in_tz:
                url_time_in_tz_ts = int(url_time_in_tz.timestamp())
            else:
                url_time_in_tz_ts = 0

        if image_video_response.status_code == 200:
            with open(image_video_file_name, 'wb') as f:
                image_video_response.raw.decode_content = True
                shutil.copyfileobj(image_video_response.raw, f)
            if url_time_in_tz_ts and not custom_mdate_ts:
                os.utime(image_video_file_name, (url_time_in_tz_ts, url_time_in_tz_ts))
            elif custom_mdate_ts:
                os.utime(image_video_file_name, (custom_mdate_ts, custom_mdate_ts))
        return True
    except Exception:
        return False


# Compares two image files
def compare_images(file1, file2):
    if not os.path.isfile(file1) or not os.path.isfile(file2):
        return False
    try:
        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            for line1, line2 in zip_longest(f1, f2, fillvalue=None):
                if line1 == line2:
                    continue
                else:
                    return False
            return True
    except Exception as e:
        print(f"* Error while comparing profile pictures: {e}")
        return False


# Detects changed Instagram profile pictures
def detect_changed_profile_picture(user, profile_image_url, profile_pic_file, profile_pic_file_tmp, profile_pic_file_old, profile_pic_file_empty, csv_file_name, r_sleep_time, send_email_notification, func_ver):

    is_empty_profile_pic = False
    is_empty_profile_pic_tmp = False

    if func_ver == 2:
        new_line = "\n"
    else:
        new_line = ""

    # Profile pic does not exist in the filesystem
    if not os.path.isfile(profile_pic_file):
        if save_pic_video(profile_image_url, profile_pic_file):
            profile_pic_mdate_dt = datetime.fromtimestamp(int(os.path.getmtime(profile_pic_file)), pytz.timezone(LOCAL_TIMEZONE))

            if profile_pic_file_empty and os.path.isfile(profile_pic_file_empty):
                is_empty_profile_pic = compare_images(profile_pic_file, profile_pic_file_empty)

            if is_empty_profile_pic:
                print(f"* User {user} does not have profile picture set, empty template saved to '{profile_pic_file}'{new_line}")
            else:
                print(f"* User {user} profile picture saved to '{profile_pic_file}'")
                log_activity("Profile picture saved", user=user)
                print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_mdate_dt, True)} ({calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False)} ago){new_line}")

            try:
                if imgcat_exe and not is_empty_profile_pic:
                    if func_ver == 1:
                        subprocess.run(f"{'echo.' if platform.system() == 'Windows' else 'echo'} {'&' if platform.system() == 'Windows' else ';'} {imgcat_exe} {profile_pic_file}", shell=True, check=True)
                    else:
                        subprocess.run(f"{imgcat_exe} {profile_pic_file} {'&' if platform.system() == 'Windows' else ';'} {'echo.' if platform.system() == 'Windows' else 'echo'}", shell=True, check=True)
                shutil.copy2(profile_pic_file, f'instagram_{user}_profile_pic_{profile_pic_mdate_dt.strftime("%Y%m%d_%H%M")}.jpeg')
            except Exception:
                pass
            try:
                if csv_file_name and not is_empty_profile_pic:
                    write_csv_entry(csv_file_name, now_local_naive(), "Profile Picture Created", "", convert_to_local_naive(profile_pic_mdate_dt))
            except Exception as e:
                print(f"* Error: {e}")
        else:
            print(f"* Error saving profile picture !{new_line}")

        if func_ver == 2:
            print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t\t\t")
        else:
            print_cur_ts("\nTimestamp:\t\t\t\t")

    # Profile pic exists in the filesystem, we check if it has not changed
    elif os.path.isfile(profile_pic_file):
        csv_text = ""
        m_subject = ""
        m_body = ""
        m_body_html = ""
        m_body_html_pic_saved_text = ""
        profile_pic_mdate_dt = datetime.fromtimestamp(int(os.path.getmtime(profile_pic_file)), pytz.timezone(LOCAL_TIMEZONE))
        profile_pic_mdate = get_short_date_from_ts(profile_pic_mdate_dt, True)
        if save_pic_video(profile_image_url, profile_pic_file_tmp):
            profile_pic_tmp_mdate_dt = datetime.fromtimestamp(int(os.path.getmtime(profile_pic_file_tmp)), pytz.timezone(LOCAL_TIMEZONE))
            if profile_pic_file_empty and os.path.isfile(profile_pic_file_empty):
                is_empty_profile_pic = compare_images(profile_pic_file, profile_pic_file_empty)

            if not compare_images(profile_pic_file, profile_pic_file_tmp) and profile_pic_mdate_dt != profile_pic_tmp_mdate_dt:
                if profile_pic_file_empty and os.path.isfile(profile_pic_file_empty):
                    is_empty_profile_pic_tmp = compare_images(profile_pic_file_tmp, profile_pic_file_empty)

                # User has removed profile picture
                if is_empty_profile_pic_tmp and not is_empty_profile_pic:
                    print(f"* User {user} has removed profile picture added on {profile_pic_mdate} ! (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)}){new_line}")
                    log_activity("Profile picture removed", user=user)
                    csv_text = "Profile Picture Removed"

                    if send_email_notification:
                        m_subject = f"Instagram user {user} has removed profile picture ! (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)})"

                        m_body = f"Instagram user {user} has removed profile picture added on {profile_pic_mdate} (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)})\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user {user} has removed profile picture added on <b>{profile_pic_mdate}</b> (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)})<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                # User has set profile picture
                elif is_empty_profile_pic and not is_empty_profile_pic_tmp:
                    print(f"* User {user} has set profile picture !")
                    log_activity("Profile picture set", user=user)
                    print(f"* User profile picture saved to '{profile_pic_file}'")
                    print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(now_local(), profile_pic_tmp_mdate_dt, show_seconds=False)} ago){new_line}")
                    csv_text = "Profile Picture Created"

                    if send_email_notification:
                        m_body_html_pic_saved_text = f'<br><br><img src="cid:profile_pic">'
                        m_subject = f"Instagram user {user} has set profile picture ! ({get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)})"

                        m_body = f"Instagram user {user} has set profile picture !\n\nProfile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(now_local(), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user <b>{user}</b> has set profile picture !{m_body_html_pic_saved_text}<br><br>Profile picture has been added on <b>{get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)}</b> ({calculate_timespan(now_local(), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                # User has changed profile picture
                elif not is_empty_profile_pic_tmp and not is_empty_profile_pic:
                    print(f"* User {user} has changed profile picture ! (previous one added on {profile_pic_mdate} - {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)} ago)")
                    log_activity("Profile picture changed", user=user)
                    print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(now_local(), profile_pic_tmp_mdate_dt, show_seconds=False)} ago){new_line}")
                    csv_text = "Profile Picture Changed"

                    if send_email_notification:
                        m_body_html_pic_saved_text = f'<br><br><img src="cid:profile_pic">'
                        m_subject = f"Instagram user {user} has changed profile picture ! (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)})"

                        m_body = f"Instagram user {user} has changed profile picture !\n\nPrevious one added on {profile_pic_mdate} ({calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)} ago)\n\nProfile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(now_local(), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user <b>{user}</b> has changed profile picture !{m_body_html_pic_saved_text}<br><br>Previous one added on <b>{profile_pic_mdate}</b> ({calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)} ago)<br><br>Profile picture has been added on <b>{get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)}</b> ({calculate_timespan(now_local(), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                try:
                    if csv_file_name:
                        if csv_text == "Profile Picture Removed":
                            write_csv_entry(csv_file_name, now_local_naive(), csv_text, convert_to_local_naive(profile_pic_mdate_dt), "")
                        elif csv_text == "Profile Picture Created":
                            write_csv_entry(csv_file_name, now_local_naive(), csv_text, "", convert_to_local_naive(profile_pic_tmp_mdate_dt))
                        else:
                            write_csv_entry(csv_file_name, now_local_naive(), csv_text, convert_to_local_naive(profile_pic_mdate_dt), convert_to_local_naive(profile_pic_tmp_mdate_dt))
                except Exception as e:
                    print(f"* Error: {e}")

                try:
                    if imgcat_exe and not is_empty_profile_pic_tmp:
                        if func_ver == 1:
                            subprocess.run(f"{'echo.' if platform.system() == 'Windows' else 'echo'} {'&' if platform.system() == 'Windows' else ';'} {imgcat_exe} {profile_pic_file_tmp}", shell=True, check=True)
                        else:
                            subprocess.run(f"{imgcat_exe} {profile_pic_file_tmp} {'&' if platform.system() == 'Windows' else ';'} {'echo.' if platform.system() == 'Windows' else 'echo'}", shell=True, check=True)
                    shutil.copy2(profile_pic_file_tmp, f'instagram_{user}_profile_pic_{profile_pic_tmp_mdate_dt.strftime("%Y%m%d_%H%M")}.jpeg')
                    if csv_text != "Profile Picture Created":
                        os.replace(profile_pic_file, profile_pic_file_old)
                    os.replace(profile_pic_file_tmp, profile_pic_file)
                except Exception as e:
                    print(f"* Error while replacing/copying files: {e}")

                if send_email_notification and m_subject and m_body:
                    print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                    if not m_body_html:
                        send_email(m_subject, m_body, "", SMTP_SSL)
                    else:
                        if m_body_html_pic_saved_text:
                            send_email(m_subject, m_body, m_body_html, SMTP_SSL, profile_pic_file, "profile_pic")
                        else:
                            send_email(m_subject, m_body, m_body_html, SMTP_SSL)

                if func_ver == 2:
                    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                        print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                        print_cur_ts("Timestamp:\t\t\t\t")

            else:
                if func_ver == 1:
                    if is_empty_profile_pic:
                        if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                            print(f"* User {user} does not have profile picture set")
                        else:
                            log_activity("No profile picture set", user=user)
                    else:
                        if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                            print(f"* Profile picture '{profile_pic_file}' already exists")
                            print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_mdate_dt, True)} ({calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False)} ago)")
                        else:
                            log_activity(f"Profile picture already exists (added {get_short_date_from_ts(profile_pic_mdate_dt, True)})", user=user)
                        try:
                            if imgcat_exe and not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                                subprocess.run(f"{'echo.' if platform.system() == 'Windows' else 'echo'} {'&' if platform.system() == 'Windows' else ';'} {imgcat_exe} {profile_pic_file}", shell=True, check=True)
                        except Exception:
                            pass
                    try:
                        os.remove(profile_pic_file_tmp)
                    except Exception:
                        pass
        else:
            print(f"* Error while checking if the profile picture has changed !")
            if func_ver == 2:
                if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                    print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                    print_cur_ts("Timestamp:\t\t\t\t")
        if func_ver == 1:
            if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                print_cur_ts("\nTimestamp:\t\t\t\t")


# Return the most recent post and/or reel for the user (GraphQL helper when logged in)
def latest_post_reel(user: str, bot: instaloader.Instaloader) -> Optional[Tuple[instaloader.Post, str]]:
    profile = instaloader.Profile.from_username(bot.context, user)

    # Max 3 pinned posts + the latest one
    posts = [(p, "post") for p in islice(profile.get_posts(), 4)]

    reels = [(r, "reel") for r in islice(profile.get_reels(), 4)]

    candidates = posts + reels

    if not candidates:
        return None

    latest, source = max(candidates, key=lambda pair: pair[0].date_utc)

    return latest, source


# Return the most recent post for the user (fallback to mobile helper when anonymous, reels cannot be fetched)
def latest_post_mobile(user: str, bot: instaloader.Instaloader):
    class P:
        date_utc: datetime
        likes: int
        comments: int
        caption: str
        pcaption: str
        tagged_users: List[Any]
        shortcode: str
        url: str
        video_url: Optional[str]
        mediaid: str

    data = bot.context.get_iphone_json(f"api/v1/users/web_profile_info/?username={user}", {})
    edges = data["data"]["user"].get("edge_owner_to_timeline_media", {}).get("edges", [])

    if not edges:
        return None

    best_node = None
    best_ts = -1

    # Iterate through the entire initial batch (usually 12 edges) and select the one with the latest timestamp
    for edge in edges:
        node = edge.get("node")
        if not node:
            continue
        ts = node.get("taken_at_timestamp", 0)
        if ts > best_ts:
            best_ts = ts
            best_node = node

    if not best_node:
        return None

    p = P()
    p.mediaid = best_node.get("id", "")
    p.date_utc = datetime.fromtimestamp(best_node["taken_at_timestamp"], timezone.utc)
    p.likes = best_node["edge_liked_by"]["count"]
    p.comments = best_node["edge_media_to_comment"]["count"]
    p.caption = best_node.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "")
    p.pcaption = ""
    p.tagged_users = []
    p.shortcode = best_node["shortcode"]
    p.url = best_node.get("display_url", "")
    p.video_url = best_node.get("video_url")

    return p, "post"


# Returns reels count by using Instaloader's iPhone API (requires session login)
def get_reels_count_mobile(user: str, bot: instaloader.Instaloader):
    profile = instaloader.Profile.from_username(bot.context, user)
    user_id = profile.userid

    # Fetch mobile JSON
    ctx: Any = bot.context  # type: ignore

    data = ctx.get_iphone_json(f"api/v1/users/{user_id}/info/", {})  # type: ignore

    u = data.get("user", {})

    # posts_count = u.get("media_count", 0)
    reels_count = (u.get("reel_count") or u.get("total_clips_count", 0))

    return reels_count


# Return the total number of reels (clips) for the user (two methods)
def get_total_reels_count(user: str, bot: instaloader.Instaloader, skip_session=False):

    # Try iPhone mobile API path if sessions are allowed
    if not skip_session:
        try:
            return get_reels_count_mobile(user, bot)
        except Exception:
            pass

    # Anonymous fallback: count every reel in the feed, might be API intensive
    try:
        profile = instaloader.Profile.from_username(bot.context, user)
        count = 0
        for _ in profile.get_reels():
            count += 1
        return count
    except PrivateProfileNotFollowedException:
        return 0


# Reports changed number of posts
def check_posts_counts(user, posts_count, posts_count_old, r_sleep_time):

    if posts_count != posts_count_old:
        print(f"* Posts number changed for user {user} from {posts_count_old} to {posts_count}\n")

        if STATUS_NOTIFICATION:
            m_subject = f"Instagram user {user} posts number has changed! ({posts_count_old} -> {posts_count})"

            m_body = f"Posts number changed for user {user} from {posts_count_old} to {posts_count}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
            print(f"Sending email notification to {RECEIVER_EMAIL}\n")
            send_email(m_subject, m_body, "", SMTP_SSL)

        print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
        print_cur_ts("Timestamp:\t\t\t\t")
        return 1
    else:
        return 0


# Reports changed number of reels
def check_reels_counts(user, reels_count, reels_count_old, r_sleep_time):

    if reels_count != reels_count_old:
        print(f"* Reels number changed for user {user} from {reels_count_old} to {reels_count}\n")

        if STATUS_NOTIFICATION:
            m_subject = f"Instagram user {user} reels number has changed! ({reels_count_old} -> {reels_count})"

            m_body = f"Reels number changed for user {user} from {reels_count_old} to {reels_count}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
            print(f"Sending email notification to {RECEIVER_EMAIL}\n")
            send_email(m_subject, m_body, "", SMTP_SSL)

        print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
        print_cur_ts("Timestamp:\t\t\t\t")
        return 1
    else:
        return 0


# Returns the tagged location name of the post, we use mobile API JSON call since last_post.location does not work anymore
def get_post_location_mobile(last_post: instaloader.Post, bot: instaloader.Instaloader) -> Optional[str]:

    if not bot.context.is_logged_in:
        return None

    media_id = getattr(last_post, "mediaid", None)
    if media_id is None:
        return None

    ctx: Any = bot.context  # type: ignore
    try:
        data = ctx.get_iphone_json(f"api/v1/media/{media_id}/info/", {})  # type: ignore
        items = data.get("items", [])
        if not items:
            return None
        media = items[0]
        loc_node = media.get("location")
        if isinstance(loc_node, dict):
            return loc_node.get("name")
    except Exception:
        return None

    return None


# Returns the true shortcode for the user's latest Reel via the mobile-web_profile_info endpoint
def get_real_reel_code(bot: instaloader.Instaloader, username: str) -> Optional[str]:
    try:
        ctx: Any = bot.context  # type: ignore

        data = ctx.get_iphone_json(f"api/v1/users/web_profile_info/?username={username}", {})
        user = data["data"]["user"]
        edges = user.get("edge_reels_media", {}).get("edges", [])
        if not edges:
            return None
        return edges[0]["node"].get("shortcode")
    except Exception:
        return None


# Finds (or prompts you to select) your Firefox cookies.sqlite file
def get_firefox_cookiefile():
    default_cookiefile = {
        "Windows": FIREFOX_WINDOWS_COOKIE,
        "Darwin": FIREFOX_MACOS_COOKIE,
    }.get(system(), FIREFOX_LINUX_COOKIE)

    cookiefiles = glob(expanduser(default_cookiefile))

    if not cookiefiles:
        raise SystemExit("No Firefox cookies.sqlite file found, use --cookie-file COOKIEFILE flag")

    if len(cookiefiles) == 1:
        return cookiefiles[0]

    print("Multiple Firefox profiles found:")

    for idx, path in enumerate(cookiefiles, start=1):
        profile = basename(dirname(path))
        print(f"  {idx}) {profile}  -  {path}")

    try:
        choice = int(input("Select profile number (0 to exit): "))
        if choice == 0:
            raise SystemExit("No profile selected, aborting ...")
        cookiefile = cookiefiles[choice - 1]
    except (ValueError, IndexError):
        raise SystemExit("Invalid profile selection !")
    return cookiefile


# Imports Instagram cookie into Instaloader, checks login and saves the session
def import_session(cookiefile, sessionfile):
    print(f"Using cookies from '{cookiefile}' file\n")

    try:
        with connect(f"file:{cookiefile}?immutable=1", uri=True) as conn:
            try:
                cookie_iter = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
                )
            except OperationalError:
                cookie_iter = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
                )

            cookie_dict = dict(cookie_iter)

    except sqlite3.DatabaseError:
        raise SystemExit(
            f"Error: '{cookiefile}' is not a valid Firefox cookies.sqlite file"
        )

    instaloader = Instaloader(max_connection_attempts=1)
    instaloader.context._session.cookies.update(cookie_dict)
    username = instaloader.test_login()

    if not username:
        raise SystemExit("Not logged in - are you logged in successfully in Firefox?")

    print(f"Imported session cookies for {username}")

    instaloader.context.username = username

    if sessionfile:
        instaloader.save_session_to_file(sessionfile)
    else:
        instaloader.save_session_to_file()


# Finds an optional config file
def find_config_file(cli_path=None):
    """
    Search for an optional config file in:
      1) CLI-provided path (must exist if given)
      2) ./{DEFAULT_CONFIG_FILENAME}
      3) ~/.{DEFAULT_CONFIG_FILENAME}
      4) script-directory/{DEFAULT_CONFIG_FILENAME}
    """

    if cli_path:
        p = Path(os.path.expanduser(cli_path))
        return str(p) if p.is_file() else None

    config_filename = f".{DEFAULT_CONFIG_FILENAME}"
    candidates = [
        Path.cwd() / DEFAULT_CONFIG_FILENAME,
        Path.home() / config_filename,
        Path(__file__).parent / DEFAULT_CONFIG_FILENAME,
    ]

    for p in candidates:
        if p.is_file():
            return str(p)
    return None


# Resolves an executable path by checking if it's a valid file or searching in $PATH
def resolve_executable(path):
    if os.path.isfile(path) and os.access(path, os.X_OK):
        return path

    found = shutil.which(path)
    if found:
        return found

    raise FileNotFoundError(f"Could not find executable '{path}'")


# Returns random web browser user agent string
def get_random_user_agent() -> str:
    browser = random.choice(['chrome', 'firefox', 'edge', 'safari'])

    if browser == 'chrome':
        os_choice = random.choice(['mac', 'windows'])
        if os_choice == 'mac':
            return (
                f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{random.randrange(11, 15)}_{random.randrange(4, 9)}) "
                f"AppleWebKit/{random.randrange(530, 537)}.{random.randrange(30, 37)} (KHTML, like Gecko) "
                f"Chrome/{random.randrange(80, 105)}.0.{random.randrange(3000, 4500)}.{random.randrange(60, 125)} "
                f"Safari/{random.randrange(530, 537)}.{random.randrange(30, 36)}"
            )
        else:
            chrome_version = random.randint(80, 105)
            build = random.randint(3000, 4500)
            patch = random.randint(60, 125)
            return (
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{chrome_version}.0.{build}.{patch} Safari/537.36"
            )

    elif browser == 'firefox':
        os_choice = random.choice(['windows', 'mac', 'linux'])
        version = random.randint(90, 110)
        if os_choice == 'windows':
            return (
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{version}.0) "
                f"Gecko/20100101 Firefox/{version}.0"
            )
        elif os_choice == 'mac':
            return (
                f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{random.randrange(11, 15)}_{random.randrange(0, 10)}; rv:{version}.0) "
                f"Gecko/20100101 Firefox/{version}.0"
            )
        else:
            return (
                f"Mozilla/5.0 (X11; Linux x86_64; rv:{version}.0) "
                f"Gecko/20100101 Firefox/{version}.0"
            )

    elif browser == 'edge':
        os_choice = random.choice(['windows', 'mac'])
        chrome_version = random.randint(80, 105)
        build = random.randint(3000, 4500)
        patch = random.randint(60, 125)
        version_str = f"{chrome_version}.0.{build}.{patch}"
        if os_choice == 'windows':
            return (
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{version_str} Safari/537.36 Edg/{version_str}"
            )
        else:
            return (
                f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{random.randrange(11, 15)}_{random.randrange(0, 10)}) "
                f"AppleWebKit/605.1.15 (KHTML, like Gecko) "
                f"Version/{random.randint(13, 16)}.0 Safari/605.1.15 Edg/{version_str}"
            )

    elif browser == 'safari':
        os_choice = 'mac'
        if os_choice == 'mac':
            mac_major = random.randrange(11, 16)
            mac_minor = random.randrange(0, 10)
            webkit_major = random.randint(600, 610)
            webkit_minor = random.randint(1, 20)
            webkit_patch = random.randint(1, 20)
            safari_version = random.randint(13, 16)
            return (
                f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{mac_major}_{mac_minor}) "
                f"AppleWebKit/{webkit_major}.{webkit_minor}.{webkit_patch} (KHTML, like Gecko) "
                f"Version/{safari_version}.0 Safari/{webkit_major}.{webkit_minor}.{webkit_patch}"
            )
        else:
            return ""
    else:
        return ""


# Returns random mobile user agent string (iPhone / iPad)
def get_random_mobile_user_agent() -> str:
    app_major = random.randint(240, 300)
    app_minor = random.randint(0, 9)
    app_patch = random.randint(0, 9)
    app_revision = random.randint(100, 999)

    if random.choice([True, False]):
        device = "iPhone"
        model, (width, height) = random.choice([
            ("10,3", (1125, 2436)),  # X
            ("11,2", (1125, 2436)),  # XS
            ("12,5", (1242, 2688)),  # 11 Pro Max
            ("13,4", (1284, 2778)),  # 12 Pro Max
            ("14,2", (1179, 2532)),  # 13 Pro
            ("14,4", (1080, 2340)),  # 13 mini
            ("15,2", (1170, 2532)),  # 15
            ("15,3", (1179, 2556)),  # 15 Pro
            ("16,1", (1290, 2796)),  # 15 Pro Max
        ])
    else:
        device = "iPad"
        model, (width, height) = random.choice([
            ("7,11", (1620, 2160)),  # 7th Gen
            ("13,4", (1668, 2388)),  # Pro 11"
            ("13,8", (2048, 2732)),  # Pro 12.9"
            ("14,5", (2360, 1640)),  # Air 5th Gen
            ("15,1", (2048, 2732)),  # Pro 12.9 Gen 6
            ("15,8", (1668, 2388)),  # Pro 11 3rd Gen
        ])

    os_major = random.randint(12, 17)
    os_minor = random.randint(0, 5)

    language = "en_US"
    locale = "en-US"

    scale = random.choice([2.00, 3.00])

    device_id = random.randint(10**14, 10**15 - 1)

    return (f"Instagram {app_major}.{app_minor}.{app_patch}.{app_revision} ({device}{model}; iOS {os_major}_{os_minor}; {language}; {locale}; scale={scale:.2f}; {width}x{height}; {device_id}) AppleWebKit/420+")


# Extracts usernames from a JSON response, automatically detecting if the data is for 'following' or 'followers'
def extract_usernames_safely(data_dict):
    usernames = []

    # Define the keys to look for in order of preference
    # The value is the path segment needed to reach the 'edges' list
    possible_keys = ['edge_followed_by', 'edge_follow']

    # 1. Safely access the 'user' dictionary
    try:
        user_data = data_dict['data']['user']
    except KeyError as e:
        # print(f"Format Check Failed: Missing essential key {e} in top level. Skipping.")
        return []

    # 2. Iterate through possible keys to find the correct list
    edges = None
    for key in possible_keys:
        if key in user_data:
            # We found the key (e.g., 'edge_followed_by')
            try:
                edges = user_data[key]['edges']
                break  # Exit the loop once the correct key is found
            except KeyError:
                # This handles the case where the key exists but 'edges' is missing
                # print(f"Warning: Found '{key}' but 'edges' list is missing inside it. Trying next key.")
                continue

    # 3. Check if any edges were found and if it's a list
    if edges is None:
        # print("Format Check Failed: Could not find 'edge_followed_by' or 'edge_follow' data.")
        return []

    if not isinstance(edges, list):
        # print("Format Check Failed: The 'edges' data is not a list.")
        return []

    # 4. Extract usernames from the list of edges
    for edge in edges:
        try:
            # The node structure is consistent: edge -> 'node' -> 'username'
            username = edge['node']['username']
            usernames.append(username)
        except KeyError:
            # Handle a malformed single entry by skipping it
            continue

    return usernames


# Extracts detailed user info from a JSON response for detailed follower logging
def extract_detailed_users_safely(data_dict):
    users = []

    possible_keys = ['edge_followed_by', 'edge_follow']

    try:
        user_data = data_dict['data']['user']
    except KeyError:
        return []

    edges = None
    for key in possible_keys:
        if key in user_data:
            try:
                edges = user_data[key]['edges']
                break
            except KeyError:
                continue

    if edges is None or not isinstance(edges, list):
        return []

    for edge in edges:
        try:
            node = edge['node']
            user_info = {
                'username': node.get('username', ''),
                'user_id': node.get('id', ''),
                'full_name': node.get('full_name', ''),
                'profile_pic_url': node.get('profile_pic_url', ''),
                'is_verified': node.get('is_verified', False),
                'is_private': node.get('is_private', False)
            }
            if user_info['username']:
                users.append(user_info)
        except (KeyError, TypeError):
            continue

    return users


# Save detailed followers/followings to JSON file
def save_detailed_followers(filename, count, users_list, detailed=False):
    if detailed and DETAILED_FOLLOWER_LOGGING:
        # Save detailed format: [count, [{username, user_id, full_name, ...}, ...]]
        data_to_save = [count, users_list]
    else:
        # Save simple format: [count, [username1, username2, ...]]
        if users_list and isinstance(users_list[0], dict):
            usernames = [u['username'] for u in users_list]
        else:
            usernames = users_list
        data_to_save = [count, usernames]

    try:
        with open(filename, 'w', encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"* Error saving to '{filename}': {e}")
        return False


# Load detailed followers/followings from JSON file
def load_detailed_followers(filename):
    try:
        with open(filename, 'r', encoding="utf-8") as f:
            data = json.load(f)

        if not data or len(data) < 2:
            return None, []

        count = data[0]
        users = data[1]

        # Check if it's detailed format (list of dicts) or simple (list of strings)
        if users and isinstance(users[0], dict):
            # Detailed format - extract usernames for comparison
            usernames = [u.get('username', '') for u in users]
            return count, usernames, users  # Return both usernames and full data
        else:
            # Simple format
            return count, users, None

    except Exception as e:
        debug_print(f"Error loading '{filename}': {e}")
        return None, [], None


# Dashboard input handler thread function - handles mode toggle and debug commands
def dashboard_input_handler():
    # This toggles the dashboard mode for both the Terminal Dashboard and the Web-based dashboard
    global MANUAL_CHECK_TRIGGERED, DASHBOARD_MODE

    import sys
    import tty
    import termios

    # Save terminal settings
    if sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin)
    else:
        old_settings = None

    try:
        # Set terminal to raw mode for single-character input (no echo, no Enter needed)
        if old_settings:
            tty.setcbreak(sys.stdin.fileno())

        while True:
            try:
                # Read single character without requiring Enter
                char = sys.stdin.read(1).lower()

                # Exit command: 'q' or 'Q'
                if char in ('q', 'Q'):
                    log_activity("User requested exit (pressed 'q')")
                    if DASHBOARD_ENABLED and RICH_AVAILABLE:
                        stop_dashboard()
                    # Use os._exit to immediately kill all threads
                    os._exit(0)

                # Mode toggle: just 'm' (no Enter needed)
                elif char == 'm':
                    DASHBOARD_MODE = 'config' if DASHBOARD_MODE == 'user' else 'user'
                    # Update DASHBOARD_DATA with new mode
                    global DASHBOARD_DATA
                    DASHBOARD_DATA['dashboard_mode'] = DASHBOARD_MODE
                    log_activity(f"Dashboard Mode changed to: {DASHBOARD_MODE.upper()}")
                    # Update web dashboard mode if enabled
                    if WEB_DASHBOARD_ENABLED:
                        WEB_DASHBOARD_DATA['dashboard_mode'] = DASHBOARD_MODE
                    # Update Dashboard if enabled
                    if DASHBOARD_ENABLED and RICH_AVAILABLE:
                        update_dashboard()
                    # Don't print in dashboard mode - the dashboard will update automatically
                    if not DASHBOARD_ENABLED or not RICH_AVAILABLE:
                        print(f"* dashboard mode: {DASHBOARD_MODE}")

                # Debug commands (only work in debug mode)
                elif char == 'c' and DEBUG_MODE:
                    MANUAL_CHECK_TRIGGERED.set()  # type: ignore
                    log_activity("Manual check triggered!")
                elif char == 's' and DEBUG_MODE:
                    print_status_summary()
                elif char == 'h':
                    if DASHBOARD_ENABLED and RICH_AVAILABLE:
                        log_activity("Commands: m=toggle mode | q=exit" + (" | c=check | s=status" if DEBUG_MODE else ""))
                    else:
                        print("\nCommands:")
                        print("  m  - Toggle dashboard view (user/config)")
                        print("  q  - Exit the tool")
                        if DEBUG_MODE:
                            print("  c  - Trigger immediate check")
                            print("  s  - Show status summary")
                        print("  h  - Show this help\n")
            except (EOFError, OSError):
                break
            except Exception:
                pass
    finally:
        # Restore terminal settings
        if old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


# Start Dashboard input handler thread
def start_dashboard_input_handler():
    global DEBUG_INPUT_THREAD

    # Start if Dashboard is enabled OR debug mode is on
    if DEBUG_INPUT_THREAD is None and (DASHBOARD_ENABLED or DEBUG_MODE):
        DEBUG_INPUT_THREAD = threading.Thread(target=dashboard_input_handler, daemon=True, name="dashboard_input_handler")
        DEBUG_INPUT_THREAD.start()
        if DEBUG_MODE:
            print("* Commands: 'm' toggle dashboard, 'check' manual check, 'status', 'help'")


# Print status summary (for debug mode)
def print_status_summary():
    print("─" * HORIZONTAL_LINE)
    print("Current Monitoring Status:")
    print(f"  Last check: {get_date_from_ts(LAST_CHECK_TIME) if LAST_CHECK_TIME else 'Not yet'}")
    print(f"  Next check: {get_date_from_ts(NEXT_CHECK_TIME) if NEXT_CHECK_TIME else 'Calculating...'}")
    print(f"  Total checks: {CHECK_COUNT}")
    print(f"  Debug mode: {DEBUG_MODE}")
    print("─" * HORIZONTAL_LINE)


# Update global tracking for last/next check times

def update_check_times(last_time=None, next_time=None, user=None):
    global LAST_CHECK_TIME, NEXT_CHECK_TIME, CHECK_COUNT, DASHBOARD_DATA
    if last_time:
        LAST_CHECK_TIME = last_time.timestamp()
    if next_time:
        NEXT_CHECK_TIME = next_time.timestamp()

    CHECK_COUNT += 1

    # Update dashboard data if dashboard is enabled
    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        DASHBOARD_DATA['config'] = get_dashboard_config_data() # Ensure timing is fresh
        update_dashboard()

    if WEB_DASHBOARD_ENABLED:
        last_str = get_short_date_from_ts(LAST_CHECK_TIME) if LAST_CHECK_TIME else None
        next_str = get_short_date_from_ts(NEXT_CHECK_TIME) if NEXT_CHECK_TIME else None

        update_web_dashboard_data(
            check_count=CHECK_COUNT,
            last_check=last_str,
            next_check=next_str,
            config=get_dashboard_config_data()
        )

        # Also update per-target check times if user is specified
        if user:
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                if user in WEB_DASHBOARD_DATA.get('targets', {}):
                    WEB_DASHBOARD_DATA['targets'][user]['last_checked'] = last_str
                    if next_str:
                        WEB_DASHBOARD_DATA['targets'][user]['next_check'] = next_str


# Generate shared Targets table for all dashboard modes
def generate_dashboard_targets_table(target_data):
    if not RICH_AVAILABLE:
        return None

    # Type guard: Rich components are available
    assert Table is not None
    assert box is not None
    assert Text is not None

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Target", style="green", width=18)
    table.add_column("Vis.", width=5) # Visibility: PUB/PRI
    table.add_column("Followers", justify="right", width=10)
    table.add_column("Following", justify="right", width=10)
    table.add_column("Posts", justify="right", width=7)
    table.add_column("Reels", justify="right", width=7)
    table.add_column("Story", width=6)
    table.add_column("Status", width=12)

    for target, data in target_data.items():
        status_style = "green" if data.get('status') == 'OK' else "yellow" if data.get('status') == 'Checking' else "blue"
        visibility = "PRI" if data.get('is_private') else "PUB"
        has_story = data.get('has_story')
        stories_count = data.get('stories_count', 0)

        story_str = "  -"
        if has_story:
            story_str = f"✨ {stories_count}" if stories_count > 0 else "✨ Yes"

        table.add_row(
            target,
            visibility,
            str(data.get('followers', '-')),
            str(data.get('following', '-')),
            str(data.get('posts', '-')),
            str(data.get('reels', '-')),
            story_str,
            Text(data.get('status', 'Unknown'), style=status_style)
        )
    return table


# Generate Dashboard layout for user mode (simple/minimal)
def generate_user_dashboard(target_data):
    if not RICH_AVAILABLE:
        return None

    # Type guard: Rich is available at this point
    assert Table is not None
    assert box is not None
    assert Text is not None
    assert Panel is not None
    assert Layout is not None

    # Header with Tool Name and Version
    header_text = Text.assemble(
        ("Instagram Monitor ", "bold magenta"),
        (f"v{VERSION}", "dim"),
        "  |  ",
        ("Status: ", "bold"),
        ("Active", "green"),
        "  |  ",
        ("Uptime: ", "bold"),
        (f"{calculate_timespan(datetime.now(), DASHBOARD_DATA.get('start_time', datetime.now()))}", "cyan")
    )
    header_panel = Panel(header_text, style="white on blue", box=box.SQUARE)

    table = generate_dashboard_targets_table(target_data)


    # Activity Log Panel (Latest at bottom)
    activities = DASHBOARD_DATA.get('activities', [])
    log_text = Text()
    if not activities:
        log_text.append("Waiting for activity...", style="dim italic")
    else:
        # Show last 10 activities, latest at bottom
        for act in reversed(activities[:10]):
            log_text.append(f"{act['time']} ", style="dim")
            log_text.append(f"{act['message']}\n")

    log_panel = Panel(log_text, title="Live Activity Log", box=box.ROUNDED, border_style="yellow")

    # Last Fetched Panel
    last_fetched_text = Text()
    # Find the most recently updated target with last_post/last_story
    latest_update = None
    latest_ts = 0

    for t_data in target_data.values():
        if t_data.get('last_post'):
            # Simple check, in reality would parse timestamp
             latest_update = t_data['last_post']
             break # Just take the first one found for now/single user
        if t_data.get('last_story'):
             latest_update = t_data['last_story']
             break

    if latest_update:
        last_fetched_text.append(f"Type: {latest_update.get('type', 'Unknown')}\n", style="bold cyan")
        last_fetched_text.append(f"Date: {latest_update.get('timestamp', '-')}\n", style="dim")
        caption = latest_update.get('caption', '')
        if caption:
            caption = caption.replace('\n', ' ')
            if len(caption) > 60: caption = caption[:57] + "..."
            last_fetched_text.append(f"Caption: {caption}\n")
        last_fetched_text.append(f"URL: {latest_update.get('url', '-')}", style="blue underline")
    else:
        last_fetched_text.append("No posts/stories fetched yet.", style="dim italic")

    last_fetched_panel = Panel(last_fetched_text, title="Last Fetched", box=box.ROUNDED, border_style="green")

    # Timing info panel
    timing_text = Text()
    if LAST_CHECK_TIME:
        timing_text.append(f"Last: {get_short_date_from_ts(LAST_CHECK_TIME)}\n", style="dim")
    if NEXT_CHECK_TIME:
        timing_text.append(f"Next: {get_short_date_from_ts(NEXT_CHECK_TIME)}\n", style="dim")
    timing_text.append(f"Checks: {CHECK_COUNT}", style="dim")

    timing_panel = Panel(timing_text, title="Timing", box=box.ROUNDED, border_style="blue")

    # Mode toggle button
    mode_btn_text = Text()
    mode_btn_text.append("USER", style="bold green reverse")
    mode_btn_text.append(" | CONFIG\n", style="dim")
    mode_btn_text.append("Press 'm' to toggle\n", style="dim italic")
    mode_btn_text.append("Press 'q' to exit", style="dim italic red")

    mode_panel = Panel(mode_btn_text, title="Mode", box=box.ROUNDED, border_style="cyan")

    layout = Layout()
    layout.split_column(
        Layout(header_panel, size=3),
        Layout(name="main", ratio=1),
        Layout(log_panel, size=12)
    )
    layout["main"].split_row(
        Layout(table, ratio=2),
        Layout(name="right", ratio=1)
    )
    layout["main"]["right"].split_column(
        Layout(timing_panel, size=6),
        Layout(last_fetched_panel),
        Layout(mode_panel, size=6)
    )

    return layout


# Generate Dashboard layout for config mode (detailed/complex)
def generate_config_dashboard(target_data, config_data):
    if not RICH_AVAILABLE:
        return None

    # Type guard: Rich is available at this point
    assert Table is not None
    assert box is not None
    assert Text is not None
    assert Panel is not None
    assert Layout is not None

    # Header
    header_text = Text.assemble(
        ("Instagram Monitor ", "bold magenta"),
        (f"v{VERSION}", "dim"),
        "  |  ",
        ("Settings Mode", "bold yellow")
    )
    header_panel = Panel(header_text, style="white on blue", box=box.SQUARE)

    # Main targets table - unified with user mode
    targets_table = generate_dashboard_targets_table(target_data)

    # Configuration tables (two columns for better space usage)
    config_table_left = Table(box=box.ROUNDED, show_header=False, header_style="bold magenta", border_style="magenta")
    config_table_left.add_column("Setting", style="cyan")
    config_table_left.add_column("Value")

    config_table_right = Table(box=box.ROUNDED, show_header=False, header_style="bold magenta", border_style="magenta")
    config_table_right.add_column("Setting", style="cyan")
    config_table_right.add_column("Value")

    # Left column items from unified config
    left_items = [
        ("Polling Interval", config_data.get('check_interval_str', '-')),
        ("Session User", config_data.get('session_user', '-')),
        ("Human Mode", str(config_data.get('human_mode', '-'))),
        ("Profile Pic Checks", str(config_data.get('profile_pic_changes', '-'))),
        ("Skip Session Login", str(config_data.get('skip_session', '-'))),
        ("Skip Followers", str(config_data.get('skip_followers', '-'))),
        ("Skip Followings", str(config_data.get('skip_followings', '-'))),
        ("Skip Stories Details", str(config_data.get('skip_story', '-'))),
        ("Skip Post Details", str(config_data.get('skip_posts', '-'))),
        ("Get More Post Details", str(config_data.get('get_more_details', '-'))),
        ("Detailed logging", str(config_data.get('detailed_log', '-'))),
        ("Liveness Check", str(config_data.get('liveness_check', '-'))),
    ]

    # Remove User Agent fields from main list (since we have a dedicated footer)
    # Right column items from unified config
    right_items = [
        ("Hours Range", config_data.get('hours_range', '-')),
        ("HTTP Jitter", str(config_data.get('enable_jitter', '-'))),
        ("CSV Logging", config_data.get('csv_logging', '-')),
        ("Imgcat Display", config_data.get('imgcat', '-')),
        ("Empty Pic Template", config_data.get('empty_profile_pic', '-')),
        ("Dashboard (Rich)", config_data.get('dashboard_status', '-')),
        ("Web Dashboard", config_data.get('web_dashboard_status', '-')),
        ("Output Logging", str(config_data.get('logging_enabled', '-'))),
        ("Output Dir", config_data.get('output_dir', '-')),
        ("Webhook Enabled", str(config_data.get('webhook_enabled', '-'))),
        ("Email Notifications", str(config_data.get('email_notifications', '-'))),
    ]

    for setting, value in left_items:
        config_table_left.add_row(setting, value)
    for setting, value in right_items:
        config_table_right.add_row(setting, value)

    # UA footer (mini panel)
    ua_text = Text()
    ua_text.append("Browser UA: ", style="cyan")
    ua_text.append(f"{USER_AGENT[:70]}..." if len(USER_AGENT) > 70 else (USER_AGENT or "Auto"), style="dim")
    ua_text.append("\nMobile UA:  ", style="cyan")
    ua_text.append(f"{USER_AGENT_MOBILE[:70]}..." if len(USER_AGENT_MOBILE) > 70 else (USER_AGENT_MOBILE or "Auto"), style="dim")
    ua_panel = Panel(ua_text, title="User Agents", box=box.ROUNDED, border_style="magenta", expand=True)

    # Activity Log Panel (Latest at bottom)
    activities = DASHBOARD_DATA.get('activities', [])
    log_text = Text()
    if not activities:
        log_text.append("Waiting for activity...", style="dim italic")
    else:
        for act in reversed(activities[:8]):
            log_text.append(f"{act['time']} ", style="dim")
            log_text.append(f"{act['message']}\n")
    log_panel = Panel(log_text, title="Live Activity Log", box=box.ROUNDED, border_style="yellow")

    # Timing info panel (Consistent with User mode)
    timing_text = Text()
    if LAST_CHECK_TIME:
        timing_text.append(f"Last: {get_short_date_from_ts(LAST_CHECK_TIME)}\n", style="dim")
    if NEXT_CHECK_TIME:
        timing_text.append(f"Next: {get_short_date_from_ts(NEXT_CHECK_TIME)}\n", style="dim")
    timing_text.append(f"Checks: {CHECK_COUNT}", style="dim")

    timing_panel = Panel(timing_text, title="Timing", box=box.ROUNDED, border_style="blue")

    # Mode toggle
    mode_btn_text = Text()
    mode_btn_text.append("USER | ", style="dim")
    mode_btn_text.append("CONFIG\n", style="bold magenta reverse")
    mode_btn_text.append("Press 'm' to toggle\n", style="dim italic")
    mode_btn_text.append("Press 'q' to exit", style="dim italic red")
    mode_panel = Panel(mode_btn_text, title="Mode", box=box.ROUNDED, border_style="cyan")

    # Dynamic height calculation to prevent cutoff
    # Base height + number of rows + padding
    config_height = max(len(left_items), len(right_items)) + 2

    # Build layout
    layout = Layout()
    layout.split_column(
        Layout(header_panel, size=3),
        Layout(targets_table, ratio=1),
        Layout(name="config_area", size=config_height),
        Layout(name="bottom", ratio=1)
    )

    layout["config_area"].split_row(
        Layout(config_table_left),
        Layout(config_table_right)
    )

    layout["bottom"].split_row(
        Layout(log_panel, ratio=2),
        Layout(name="right", ratio=1)
    )

    layout["bottom"]["right"].split_column(
        Layout(timing_panel, size=6),
        Layout(ua_panel, ratio=1),
        Layout(mode_panel, size=5)
    )

    return layout

# Update Dashboard display
def update_dashboard():
    global DASHBOARD_LIVE, DASHBOARD_CONSOLE, DASHBOARD_DATA, DASHBOARD_MODE

    if not RICH_AVAILABLE or not DASHBOARD_ENABLED or DASHBOARD_CONSOLE is None:
        return

    # Type guard: Rich is available at this point
    assert Layout is not None

    # Get current target data from DASHBOARD_DATA
    target_data = DASHBOARD_DATA.get('targets', {})
    config_data = DASHBOARD_DATA.get('config', {})

    # If no targets yet, show informative loading state
    if not target_data:
        # Create detailed loading screen
        assert Panel is not None
        assert Text is not None
        assert box is not None

        loading_text = Text()
        loading_text.append(f"Instagram Monitor v{VERSION} Dashboard\n\n", style="bold magenta")
        loading_text.append("⏳ Initializing and fetching profile data...\n\n", style="yellow")
        loading_text.append("This may take a moment while we:\n", style="dim")
        loading_text.append("  • Load Instagram session\n", style="dim")
        loading_text.append("  • Fetch profile information\n", style="dim")
        loading_text.append("  • Count posts, reels, and stories\n", style="dim")
        loading_text.append("  • Retrieve follower/following data\n\n", style="dim")

        # Show which users are being monitored
        targets_list = DASHBOARD_DATA.get('targets_list', [])
        if targets_list:
            loading_text.append("Monitored targets:\n", style="bold cyan")
            for target in targets_list:
                loading_text.append(f"  • {target}\n", style="cyan")

        loading_text.append("\n💡 Please wait patiently...\n\n", style="italic green")
        loading_text.append("Press ", style="dim")
        loading_text.append("q", style="bold red")
        loading_text.append(" to exit", style="dim")

        loading_panel = Panel(loading_text, title="Instagram Monitor", box=box.ROUNDED, border_style="magenta")
        loading_layout = Layout()
        loading_layout.split_column(Layout(loading_panel, name="content"))

        if DASHBOARD_LIVE is not None:
            DASHBOARD_LIVE.update(loading_layout)
        return

    # Generate appropriate Dashboard based on mode
    if DASHBOARD_MODE == 'config':
        layout = generate_config_dashboard(target_data, config_data)
    else:
        layout = generate_user_dashboard(target_data)

    if layout is not None and DASHBOARD_LIVE is not None:
        DASHBOARD_LIVE.update(layout)


# Initialize Dashboard Live display
def init_dashboard():
    global DASHBOARD_LIVE, DASHBOARD_CONSOLE

    if not RICH_AVAILABLE or not DASHBOARD_ENABLED or DASHBOARD_CONSOLE is None:
        return False

    # Type guard: Rich is available at this point
    assert Live is not None
    assert Layout is not None
    assert Panel is not None
    assert Text is not None

    # Prepare initial loading screen components
    loading_text = Text()
    loading_text.append("Instagram Monitor Dashboard\n\n", style="bold magenta")
    loading_text.append("⏳ Initializing and fetching profile data...\n\n", style="yellow")
    loading_text.append("This may take a moment while we:\n", style="dim")
    loading_text.append("  • Load Instagram session\n", style="dim")
    loading_text.append("  • Fetch profile information\n", style="dim")
    loading_text.append("  • Count posts, reels, and stories\n", style="dim")
    loading_text.append("  • Retrieve follower/following data\n\n", style="dim")

    # Show which users are being monitored
    targets_list = DASHBOARD_DATA.get('targets_list', [])
    if targets_list:
        loading_text.append("Monitored targets:\n", style="bold cyan")
        for target in targets_list:
            loading_text.append(f"  • {target}\n", style="cyan")

    loading_text.append("\n💡 Please wait patiently...", style="italic green")

    initial_layout = Layout()
    initial_layout.split_column(
        Layout(Panel(loading_text, title="Instagram Monitor", border_style="magenta"), name="content")
    )

    try:
        # Start Live display (fullscreen/screen=True for a true dashboard feel)
        DASHBOARD_LIVE = Live(initial_layout, console=DASHBOARD_CONSOLE, refresh_per_second=2, screen=True)
        DASHBOARD_LIVE.start()
        return True
    except Exception:
        # If screen=True fails, try screen=False
        try:
            DASHBOARD_LIVE = Live(initial_layout, console=DASHBOARD_CONSOLE, refresh_per_second=2, screen=False)
            DASHBOARD_LIVE.start()
            return True
        except Exception:
            # Dashboard failed completely
            return False


# Stop Dashboard Live display
def stop_dashboard():
    global DASHBOARD_LIVE

    if DASHBOARD_LIVE is not None:
        DASHBOARD_LIVE.stop()
        DASHBOARD_LIVE = None


# Prints remaining sleep time message
def print_check_timing(r_sleep_time, prefix=""):
    global NEXT_CHECK_TIME

    now = now_local_naive()
    next_check = now + timedelta(seconds=r_sleep_time)
    NEXT_CHECK_TIME = next_check

    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        return

    if DEBUG_MODE:
        print(f"{prefix}Last check:\t\t\t\t{get_date_from_ts(LAST_CHECK_TIME) if LAST_CHECK_TIME else 'N/A'}")
        print(f"{prefix}Next check:\t\t\t\t{get_date_from_ts(next_check)} (in {display_time(r_sleep_time)})")

    print(f"{prefix}Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")


# Initializes and sets up a progress bar for displaying download progress
def setup_pbar(total_expected, title):
    global START_TIME, NAME_COUNT, WRAPPER_COUNT, pbar

    # Use thread-local storage for multi-target safety
    if not hasattr(_thread_local, 'pbar'):
        _thread_local.pbar = None  # type: ignore[misc]
        _thread_local.START_TIME = 0  # type: ignore[misc]
        _thread_local.NAME_COUNT = 0  # type: ignore[misc]
        _thread_local.WRAPPER_COUNT = 0  # type: ignore[misc]

    _thread_local.START_TIME = datetime.now()  # type: ignore[misc]
    _thread_local.NAME_COUNT = 0  # type: ignore[misc]
    _thread_local.WRAPPER_COUNT = 0  # type: ignore[misc]

    # If a bar exists for this thread, close it first
    if _thread_local.pbar is not None:  # type: ignore[misc]
        close_pbar()

    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        return

    custom_bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{unit}]"
    # Write progress bar updates to terminal only (not log file) to avoid cluttering logs
    terminal_out = stdout_bck if stdout_bck is not None else sys.stdout
    # Use HORIZONTAL_LINE (default 113) as the fixed width for consistent behavior across environments
    _thread_local.pbar = tqdm(total=total_expected, bar_format=custom_bar_format, unit="Initializing...", desc=title, file=terminal_out, ncols=HORIZONTAL_LINE)  # type: ignore[misc]

    # Also set global for backward compatibility (single-threaded mode)
    pbar = _thread_local.pbar


# Closes progress bar and write final state to log file if logging is enabled
def close_pbar():
    global pbar
    # Use thread-local storage for multi-target safety
    thread_pbar = getattr(_thread_local, 'pbar', None)
    if thread_pbar is not None:
        # Get the final progress bar string before closing
        # Use format_dict to get current values and format the progress bar string
        d = thread_pbar.format_dict
        desc = thread_pbar.desc if thread_pbar.desc else ""
        unit = thread_pbar.unit if thread_pbar.unit else ""

        # Format the progress bar string to match the custom_bar_format: "{l_bar}{bar}| {n_fmt}/{total_fmt} [{unit}]"
        n = d.get('n', 0)
        total = d.get('total', 0)
        n_fmt = f"{n:,}" if n >= 1000 else str(n)
        total_fmt = f"{total:,}" if total >= 1000 else str(total)

        # Calculate bar visualization
        if total > 0:
            # Calculate available space for bar:
            # Total width (HORIZONTAL_LINE) - desc - stats - separators

            overhead = 0
            if desc:
                overhead += len(desc) + 2  # ": "

            overhead += 1  # "|"
            overhead += 1  # " "
            overhead += len(n_fmt)
            overhead += 1  # "/"
            overhead += len(total_fmt)
            overhead += 2  # " ["
            overhead += len(unit)
            overhead += 1  # "]"

            avail_for_bar = HORIZONTAL_LINE - overhead
            bar_length = max(10, avail_for_bar)  # Ensure at least 10 chars

            filled = int(bar_length * n / total)
            bar = '█' * filled + '░' * (bar_length - filled)
        else:
            bar = '░' * 40

        # Build final string matching the format: "{l_bar}{bar}| {n_fmt}/{total_fmt} [{unit}]"
        if desc:
            final_str = f"{desc}: {bar}| {n_fmt}/{total_fmt} [{unit}]"
        else:
            final_str = f"{bar}| {n_fmt}/{total_fmt} [{unit}]"

        # Close the progress bar (writes to terminal)
        thread_pbar.close()

        # Write final state to log file if logging is enabled
        if stdout_bck is not None and isinstance(sys.stdout, Logger):
            sys.stdout.logfile.write(final_str + "\n")
            sys.stdout.logfile.flush()

        _thread_local.pbar = None  # type: ignore[misc]
        # Also clear global for backward compatibility
        pbar = None


# Monkey-patches Instagram request to add human-like jitter and back-off
def instagram_wrap_request(orig_request):
    @wraps(orig_request)
    def wrapper(*args, **kwargs):
        global NAME_COUNT, START_TIME, WRAPPER_COUNT, pbar
        method = kwargs.get("method") or (args[1] if len(args) > 1 else None)
        url = kwargs.get("url") or (args[2] if len(args) > 2 else None)
        if JITTER_VERBOSE:
            print(f"[WRAP-REQ] {method} {url}")

        def _do_request():
            # If jitter is disabled, just perform the request (but still optionally serialized by the outer lock)
            if not ENABLE_JITTER:
                resp = orig_request(*args, **kwargs)
                # Still process progress bar even if jitter is disabled
                _update_progress_bar(resp)
                return resp

            # Human-like jitter + back-off on checkpoint/429
            time.sleep(random.uniform(0.8, 3.0))
            attempt = 0
            backoff = 60
            while True:
                resp = orig_request(*args, **kwargs)

                # Update progress bar for follower/following requests
                _update_progress_bar(resp)

                if resp.status_code in (429, 400) and "checkpoint" in resp.text:
                    attempt += 1
                    if attempt > 3:
                        thread_pbar = getattr(_thread_local, 'pbar', None)
                        if thread_pbar is not None:
                            close_pbar()
                        raise instaloader.exceptions.QueryReturnedNotFoundException(
                            "Giving up after multiple 429/checkpoint"
                        )
                    wait = backoff + random.uniform(0, 30)
                    if JITTER_VERBOSE:
                        thread_pbar = getattr(_thread_local, 'pbar', None)
                        if thread_pbar:
                            tqdm.write(f"* Back-off {wait:.0f}s after {resp.status_code}")
                        else:
                            print(f"* Back-off {wait:.0f}s after {resp.status_code}")
                    time.sleep(wait)
                    backoff *= 2
                    continue
                return resp

        def _update_progress_bar(resp):
            """Helper function to update progress bar based on response content."""
            # Use thread-local storage for multi-target safety
            thread_pbar = getattr(_thread_local, 'pbar', None)
            if thread_pbar is None:
                return

            thread_name_count = getattr(_thread_local, 'NAME_COUNT', 0)
            thread_wrapper_count = getattr(_thread_local, 'WRAPPER_COUNT', 0)

            # Only process and count requests that are likely follower/following related
            # Check if response is successful and JSON before processing
            user_list = []
            if resp.status_code == 200 and resp.headers.get('content-type', '').startswith('application/json'):
                try:
                    # Extract usernames from JSON response
                    user_list = extract_usernames_safely(resp.json())

                    # Only count requests that actually returned follower/following data
                    if user_list:
                        _thread_local.WRAPPER_COUNT = thread_wrapper_count + 1  # type: ignore[misc]
                        thread_wrapper_count = _thread_local.WRAPPER_COUNT  # type: ignore[misc]
                except (ValueError, KeyError) as e:
                    # JSON decode error or missing keys - not a follower/following request
                    # Silently skip, this is expected for non-follower/following requests
                    pass
                except Exception as e:
                    # Other exceptions - log but don't count
                    if thread_pbar:
                        tqdm.write(f"[WRAP-REQ] exception: {e}")
                    else:
                        print(f"[WRAP-REQ] exception: {e}")

            # Update progress bar only if we extracted usernames
            if user_list:
                increment = len(user_list)
                _thread_local.NAME_COUNT = thread_name_count + increment  # type: ignore[misc]
                thread_name_count = _thread_local.NAME_COUNT  # type: ignore[misc]
                if (thread_pbar.n + increment) > thread_pbar.total:
                    thread_pbar.total = thread_pbar.n + increment

                # Calculate Remaining Minutes
                d = thread_pbar.format_dict
                rate = d['rate'] if d['rate'] else 0
                remaining_items = d['total'] - d['n']

                # Calculate remaining seconds, then minutes
                rem_s = remaining_items / rate if rate > 0 else 0
                rem_m = rem_s / 60

                elapsed_m = d['elapsed'] / 60

                # Update Stats - use float division for precision
                names_per_req = d['n'] / thread_wrapper_count if thread_wrapper_count > 0 else 0
                stats_string = f"{names_per_req:.1f} names/req, reqs={thread_wrapper_count:d}, mins={elapsed_m:.1f}, remain={rem_m:.1f}"
                thread_pbar.unit = stats_string
                thread_pbar.update(increment)

        if MULTI_TARGET_SERIALIZE_HTTP:
            with HTTP_SERIAL_LOCK:
                return _do_request()
        return _do_request()
    return wrapper


# Monkey-patches Instagram prepared-request send to add human-like jitter
def instagram_wrap_send(orig_send):
    @wraps(orig_send)
    def wrapper(*args, **kwargs):
        req_obj = args[1] if len(args) > 1 else kwargs.get("request")
        method = getattr(req_obj, "method", None)
        url = getattr(req_obj, "url", None)
        if JITTER_VERBOSE:
            print(f"[WRAP-SEND] {method} {url}")

        def _do_send():
            if ENABLE_JITTER:
                time.sleep(random.uniform(0.8, 3.0))
            return orig_send(*args, **kwargs)

        if MULTI_TARGET_SERIALIZE_HTTP:
            with HTTP_SERIAL_LOCK:
                return _do_send()
        return _do_send()
    return wrapper


# Returns a dictionary containing all current configuration settings
def get_dashboard_config_data(final_log_path=None, imgcat_exe=None, profile_pic_file_exists=False, cfg_path=None, env_path=None, check_interval_low=None, mode_of_the_tool="Unknown", targets=None):
    # Prepare hours/ranges string
    hours_ranges_str = ""
    if CHECK_POSTS_IN_HOURS_RANGE:
        ranges = []
        if not (MIN_H1 == 0 and MAX_H1 == 0):
            ranges.append(f"{MIN_H1:02d}:00 - {MAX_H1:02d}:59")
        if not (MIN_H2 == 0 and MAX_H2 == 0):
            ranges.append(f"{MIN_H2:02d}:00 - {MAX_H2:02d}:59")

        if ranges:
            hours_ranges_str = ", ".join(ranges)
        else:
            hours_ranges_str = "None (both ranges disabled)"
    else:
        hours_ranges_str = "00:00 - 23:59"

    # Use arguments or fall back to defaults
    targets_list = targets if targets is not None else DASHBOARD_DATA.get('targets_list', [])
    mode_val = mode_of_the_tool
    if WEB_DASHBOARD_ENABLED:
         mode_val += " (Web UI)"

    # Determine status/reason for dashboards
    dashboard_status = DASHBOARD_ENABLED and RICH_AVAILABLE
    dashboard_reason = ""
    if not dashboard_status:
        if not RICH_AVAILABLE:
            dashboard_reason = " (missing rich)"
        elif not DASHBOARD_ENABLED:
            dashboard_reason = " (disabled)"

    web_dashboard_status = WEB_DASHBOARD_ENABLED and FLASK_AVAILABLE
    web_dashboard_reason = ""
    if not web_dashboard_status:
        if not WEB_DASHBOARD_ENABLED:
            web_dashboard_reason = " (disabled)"
        elif not FLASK_AVAILABLE:
             web_dashboard_reason = " (missing Flask)"

    csv_status = "False"
    if CSV_FILE:
         csv_status = f"True (Base: {CSV_FILE})" if len(targets_list) > 1 else f"True ({CSV_FILE})"

    # Calculate interval strings safely
    interval_str = ""
    try:
        if check_interval_low is None:
             check_interval_low = int(INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW)
        interval_str = f"[ {display_time(check_interval_low)} - {display_time(int(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH))} ]"
    except Exception:
        interval_str = f"[ {INSTA_CHECK_INTERVAL}s +/- ]"

    return {
        'check_interval': INSTA_CHECK_INTERVAL,
        'check_interval_low': int(INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW),
        'check_interval_high': int(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH),
        'check_interval_str': interval_str,
        'random_low': RANDOM_SLEEP_DIFF_LOW,
        'random_high': RANDOM_SLEEP_DIFF_HIGH,
        'session_user': SESSION_USERNAME or '<anonymous>',
        'human_mode': BE_HUMAN,
        'enable_jitter': ENABLE_JITTER,
        'mode': mode_val,
        'profile_pic_changes': DETECT_CHANGED_PROFILE_PIC,
        'skip_session_login': SKIP_SESSION,
        'skip_followers': SKIP_FOLLOWERS,
        'skip_followings': SKIP_FOLLOWINGS,
        'skip_stories': SKIP_GETTING_STORY_DETAILS,
        'skip_posts': SKIP_GETTING_POSTS_DETAILS,
        'get_more_post_details': GET_MORE_POST_DETAILS,
        'detailed_logging': DETAILED_FOLLOWER_LOGGING,
        'hours_range': hours_ranges_str,
        'user_agent': USER_AGENT,
        'user_agent_mobile': USER_AGENT_MOBILE,
        'liveness_check': f"{bool(LIVENESS_CHECK_INTERVAL)}" + (f" ({display_time(LIVENESS_CHECK_INTERVAL)})" if LIVENESS_CHECK_INTERVAL else ""),
        'csv_logging': csv_status,
        'imgcat': f"{bool(imgcat_exe)}" + (f" (via {imgcat_exe})" if imgcat_exe else ""),
        'empty_profile_pic': f"{bool(profile_pic_file_exists)}" + (f" ({PROFILE_PIC_FILE_EMPTY})" if PROFILE_PIC_FILE_EMPTY else ""),
        'dashboard_status': f"{dashboard_status}{dashboard_reason}",
        'web_dashboard_status': f"{web_dashboard_status}{web_dashboard_reason}",
        'logging_enabled': not DISABLE_LOGGING,
        'log_file': final_log_path if final_log_path and not DISABLE_LOGGING else "",
        'config_file': cfg_path or CLI_CONFIG_PATH or 'None',
        'dotenv_file': env_path or DOTENV_FILE or 'None',
        'output_dir': OUTPUT_DIR if OUTPUT_DIR else ".",
        'template_dir': WEB_DASHBOARD_TEMPLATE_DIR or "Auto",
        'local_timezone': LOCAL_TIMEZONE,
        'webhook_enabled': WEBHOOK_ENABLED,
        'webhook_url': WEBHOOK_URL,
        'webhook_status': WEBHOOK_STATUS_NOTIFICATION,
        'webhook_followers': WEBHOOK_FOLLOWERS_NOTIFICATION,
        'webhook_errors': WEBHOOK_ERROR_NOTIFICATION,
        'email_notifications': STATUS_NOTIFICATION,
        'follower_notifications': FOLLOWERS_NOTIFICATION,
        'error_notifications': ERROR_NOTIFICATION
    }


def sleep_message(sleeptime):
    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        return
    now = now_local_naive()
    next_check = now + timedelta(seconds=sleeptime)
    print(f"*** Sleeping for: {display_time(sleeptime)} (until ~{next_check.strftime('%H:%M:%S')}) @ {now.strftime('%H:%M:%S')}")
    print("─" * HORIZONTAL_LINE)


# Formats error messages to be more informative, especially for Instagram detection/challenge errors
def format_error_message(e: Exception) -> str:
    error_str = str(e)
    error_type = type(e).__name__

    # Check for KeyError related to 'data' key - indicates Instagram challenge/shadow ban
    if error_type == "KeyError" and ("'data'" in error_str or '"data"' in error_str or error_str == "data"):
        return "Instagram may have detected automated checks and requires a challenge or re-login (if session is used) or has temporarily shadow banned the IP. The API response is missing expected data."

    return f"{error_type}: {error_str}"


# Returns unique, validated hours (0-23) from the configured ranges
def hours_to_check():
    # Notes:
    # - Ranges can overlap; we de-duplicate
    # - Misconfigured ranges (e.g., MAX < MIN) will produce an empty list
    # - Invalid hours (outside 0-23) are ignored
    hours = set()

    # If MIN and MAX are both 0, we consider the range disabled
    if not (MIN_H1 == 0 and MAX_H1 == 0):
        hours.update(h for h in range(MIN_H1, MAX_H1 + 1) if 0 <= h <= 23)

    if not (MIN_H2 == 0 and MAX_H2 == 0):
        hours.update(h for h in range(MIN_H2, MAX_H2 + 1) if 0 <= h <= 23)

    return sorted(hours)


# Returns probability of executing one human action for cycle
def probability_for_cycle(sleep_seconds: int) -> float:
    if CHECK_POSTS_IN_HOURS_RANGE:
        allowed_hours = len(hours_to_check())
        if allowed_hours <= 0:
            return 0.0
        day_seconds = 3600 * allowed_hours
    else:
        day_seconds = 86400  # 1 day

    return min(1.0, DAILY_HUMAN_HITS * sleep_seconds / day_seconds)


# Performs random feed / profile / hashtag / followee actions to look more like a human being
def simulate_human_actions(bot: instaloader.Instaloader, sleep_seconds: int) -> None:
    ctx = bot.context
    prob = probability_for_cycle(sleep_seconds)

    if BE_HUMAN_VERBOSE:
        print("─" * HORIZONTAL_LINE)
        print("* BeHuman: simulation start")

    # Explore feed
    if ctx.is_logged_in and random.random() < prob:
        try:
            posts = bot.get_explore_posts()
            post = next(posts)
            if BE_HUMAN_VERBOSE:
                print("* BeHuman #1: explore feed peek OK")
            time.sleep(random.uniform(2, 6))
        except Exception as e:
            if BE_HUMAN_VERBOSE:
                print(f"* BeHuman #1 error: explore peek failed ({e})")

    # View your own profile
    if ctx.is_logged_in and random.random() < prob:
        try:
            _ = instaloader.Profile.own_profile(ctx)
            if BE_HUMAN_VERBOSE:
                print("* BeHuman #2: viewed own profile OK")
            time.sleep(random.uniform(1, 4))
        except Exception as e:
            if BE_HUMAN_VERBOSE:
                print(f"* BeHuman #2 error: cannot view own profile: {e}")

    # Browse a random hashtag
    if random.random() < prob / 2:
        tag = random.choice(MY_HASHTAGS)
        try:
            posts = bot.get_hashtag_posts(tag)
            post = next(posts)
            if BE_HUMAN_VERBOSE:
                print(f"* BeHuman #3: browsed one post from #{tag} OK")
            time.sleep(random.uniform(2, 5))
        except StopIteration:
            if BE_HUMAN_VERBOSE:
                print(f"* BeHuman #3 warning: no posts for #{tag}")
        except Exception as e:
            if BE_HUMAN_VERBOSE:
                print(f"* BeHuman #3 error: cannot browse #{tag}: {e}")

    # Visit a random followee profile
    if ctx.is_logged_in and random.random() < prob / 2:
        try:
            me = instaloader.Profile.own_profile(ctx)
            followees = list(me.get_followees())
            if not followees and BE_HUMAN_VERBOSE:
                print("* BeHuman #4 warning: you follow 0 accounts, skipping visit")
            else:
                someone = random.choice(followees)
                _ = instaloader.Profile.from_username(ctx, someone.username)
                if BE_HUMAN_VERBOSE:
                    print(f"* BeHuman #4: visited followee {someone.username} OK")
                time.sleep(random.uniform(2, 5))
        except Exception as e:
            if BE_HUMAN_VERBOSE:
                print(f"* BeHuman #4 error: cannot visit followee: {e}")

    if BE_HUMAN_VERBOSE:
        print("* BeHuman: simulation stop")
        print_cur_ts("\nTimestamp:\t\t\t\t")


# Monitors activity of the specified Instagram user
def instagram_monitor_user(user, csv_file_name, skip_session, skip_followers, skip_followings, skip_getting_story_details, skip_getting_posts_details, get_more_post_details, wait_for_prev_user=None, signal_loading_complete=None, stop_event=None, user_root_path=None):  # type: ignore[reportComplexity]
    global pbar, DASHBOARD_DATA

    # Wait for previous user's initial loading to complete (to avoid progress bar overlap)
    if wait_for_prev_user is not None:
        wait_for_prev_user.wait()

    # Only print if Dashboard is not enabled (Dashboard will show this information)
    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
        print(f"Target:\t\t\t\t\t{user}")
        print("─" * HORIZONTAL_LINE)

    # Resolve output directory for this user
    user_root_dir = ""
    json_dir = ""
    images_dir = ""
    videos_dir = ""

    if user_root_path:
        user_root_dir = user_root_path
        json_dir = os.path.join(user_root_dir, "json")
        images_dir = os.path.join(user_root_dir, "images")
        videos_dir = os.path.join(user_root_dir, "videos")
        for d in [user_root_dir, json_dir, images_dir, videos_dir]:
            os.makedirs(d, exist_ok=True)
    elif OUTPUT_DIR:
        user_root_dir = os.path.join(OUTPUT_DIR, user)
        json_dir = os.path.join(user_root_dir, "json")
        images_dir = os.path.join(user_root_dir, "images")
        videos_dir = os.path.join(user_root_dir, "videos")
        for d in [user_root_dir, json_dir, images_dir, videos_dir]:
            os.makedirs(d, exist_ok=True)

    try:
        if csv_file_name:
            init_csv_file(csv_file_name)
    except Exception as e:
        print(f"* Error: {e}")

    followers_count = 0
    followings_count = 0
    r_sleep_time = 0
    followers_followings_fetched = False
    stories_count = 0
    stories_old_count = 0
    reels_count = 0

    try:
        global REQUESTS_PATCHED
        # Monkey-patch requests only once (it is global), even if we run multi-target threads
        if (ENABLE_JITTER or MULTI_TARGET_SERIALIZE_HTTP) and not REQUESTS_PATCHED:
            req.Session.request = instagram_wrap_request(req.Session.request)
            req.Session.send = instagram_wrap_send(req.Session.send)
            REQUESTS_PATCHED = True

        bot = instaloader.Instaloader(user_agent=USER_AGENT, iphone_support=True, quiet=True)

        ctx = bot.context

        orig_request = ctx._session.request

        session = ctx._session

        if not skip_session and SESSION_USERNAME:
            # Session file is shared - avoid concurrent load/login/save in multi-target mode
            with SESSION_FILE_LOCK:
                if SESSION_PASSWORD:
                    try:
                        bot.load_session_from_file(SESSION_USERNAME)
                    except FileNotFoundError:
                        bot.login(SESSION_USERNAME, SESSION_PASSWORD)
                        bot.save_session_to_file()
                    except instaloader.exceptions.BadCredentialsException:
                        bot.login(SESSION_USERNAME, SESSION_PASSWORD)
                        bot.save_session_to_file()
                else:
                    try:
                        bot.load_session_from_file(SESSION_USERNAME)
                    except FileNotFoundError:
                        print("* Error: No Instagram session file found, please run 'instaloader -l SESSION_USERNAME' to create one")
                        if threading.current_thread() is threading.main_thread():
                            sys.exit(1)
                        else:
                            return

        patched = False

        # Mobile user agent patch for instaloader
        try:

            for attr in ("iphone_headers", "_iphone_headers"):
                if hasattr(ctx, attr):
                    getattr(ctx, attr)["User-Agent"] = USER_AGENT_MOBILE
                    patched = True
                    break

            if not patched:
                if hasattr(ctx, 'get_iphone_json'):
                    orig_get_iphone_json = ctx.get_iphone_json

                    def _get_iphone_json(path, params, **kwargs):
                        if '_extra_headers' in kwargs:
                            kwargs['_extra_headers']['User-Agent'] = USER_AGENT_MOBILE
                        else:
                            kwargs['_extra_headers'] = {'User-Agent': USER_AGENT_MOBILE}
                        return orig_get_iphone_json(path, params, **kwargs)

                    ctx.get_iphone_json = _get_iphone_json
                else:
                    print("* Warning: Could not apply custom mobile user-agent patch (missing header attributes or get_iphone_json method)!")
                    print("* Proceeding with the default Instaloader mobile user-agent")
        except Exception as e:
            print(f"* Warning: Could not apply custom mobile user-agent patch due to an unexpected error: {e}")
            print("* Proceeding with the default Instaloader mobile user-agent")

        if DASHBOARD_ENABLED:
            log_activity(f"Loading profile: {user}")
        else:
            print("- loading profile from username...", end=" ", flush=True)
            if WEB_DASHBOARD_ENABLED:
                log_activity(f"Loading profile: {user}", user=user)

        if WEB_DASHBOARD_ENABLED:
            update_web_dashboard_data(targets={user: {'status': 'Loading Profile'}})

        profile = instaloader.Profile.from_username(bot.context, user)

        time.sleep(NEXT_OPERATION_DELAY)
        insta_username = profile.username
        insta_userid = profile.userid

        if not DASHBOARD_ENABLED:
            print(f"     OK: {insta_username}")
            if WEB_DASHBOARD_ENABLED:
                log_activity(f"Profile loaded: {insta_username}", user=user)
        else:
            log_activity(f"Profile loaded: {insta_username}", user=user)

        followers_count = profile.followers
        followings_count = profile.followees
        bio = profile.biography
        is_private = profile.is_private
        followed_by_viewer = profile.followed_by_viewer
        can_view = (not is_private) or followed_by_viewer
        posts_count = profile.mediacount
        if not skip_session and can_view:
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Fetching Reels'}})
            if not DASHBOARD_ENABLED:
                print("- fetching reels count...", end=" ", flush=True)

            reels_count = get_total_reels_count(user, bot, skip_session)

            if not DASHBOARD_ENABLED:
                print("              OK")
                if WEB_DASHBOARD_ENABLED:
                    log_activity(f"Reels count fetched: {reels_count}", user=user)
            else:
                log_activity(f"Reels count fetched: {reels_count}", user=user)

        if not is_private:
            if bot.context.is_logged_in:
                has_story = profile.has_public_story
            else:
                has_story = False
        elif bot.context.is_logged_in and followed_by_viewer:
            if not DASHBOARD_ENABLED:
                print("- checking for stories...", end=" ", flush=True)

            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Checking Stories'}})

            story = next(bot.get_stories(userids=[insta_userid]), None)
            has_story = bool(story and story.itemcount)

            if not DASHBOARD_ENABLED:
                print("              OK")
                if WEB_DASHBOARD_ENABLED:
                    log_activity("Checked for stories", user=user)
            else:
                log_activity("Checked for stories", user=user)
        else:
            has_story = False

        profile_image_url = profile.profile_pic_url_no_iphone

        if bot.context.is_logged_in:
            if not DASHBOARD_ENABLED:
                print("- loading own profile...", end=" ", flush=True)

            me = instaloader.Profile.own_profile(bot.context)
            session_username = me.username

            if not DASHBOARD_ENABLED:
                print(f"               OK: {session_username}")
            else:
                log_activity(f"Session user loaded: {session_username}")

        if not DASHBOARD_ENABLED:
            print("─" * HORIZONTAL_LINE)

        if not bot.context.is_logged_in:
            session_username = None

    except Exception as e:
        error_msg = format_error_message(e)
        print(f"* Error: {error_msg}")
        if WEB_DASHBOARD_ENABLED:
            update_web_dashboard_data(targets={user: {'status': 'Error: ' + error_msg}})
        # traceback.print_exc()
        if threading.current_thread() is threading.main_thread():
            sys.exit(1)
        else:
            return

    story_flag = False
    last_post = None
    last_story = None

    followers_old_count = followers_count
    followings_old_count = followings_count
    bio_old = bio
    posts_count_old = posts_count
    reels_count_old = reels_count
    is_private_old = is_private
    followed_by_viewer_old = followed_by_viewer

    # Only print detailed profile info if Dashboard is not enabled
    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
        print(f"Session user:\t\t\t\t{session_username or '<anonymous>'}")

        print(f"\nUsername:\t\t\t\t{insta_username}")
        print(f"User ID:\t\t\t\t{insta_userid}")
        print(f"URL:\t\t\t\t\thttps://www.instagram.com/{insta_username}/")

        print(f"\nProfile:\t\t\t\t{'public' if not is_private else 'private'}")
        print(f"Can view all contents:\t\t\t{'Yes' if can_view else 'No'}")

        print(f"\nPosts:\t\t\t\t\t{posts_count}")
        if not skip_session and can_view:
            print(f"Reels:\t\t\t\t\t{reels_count}")

        print(f"\nFollowers:\t\t\t\t{followers_count}")
        print(f"Followings:\t\t\t\t{followings_count}")

        if bot.context.is_logged_in:
            print(f"\nStory available:\t\t\t{has_story}")

        print(f"\nBio:\n\n{bio}\n")
        print_cur_ts("Timestamp:\t\t\t\t")

    # Populate initial Dashboard data immediately after first fetch (regardless of print mode)
    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        if 'targets' not in DASHBOARD_DATA:
            DASHBOARD_DATA['targets'] = {}

        DASHBOARD_DATA['targets'][user] = {
            'followers': followers_count,
            'following': followings_count,
            'posts': posts_count,
            'reels': reels_count,
            'has_story': has_story,
            'stories_count': 0, # Initial count
            'status': 'OK',
            'bio_changed': False,
            'last_post': None,
            'last_story': None
        }

        # Use unified config data (reuse existing or fallback if not init)
        config_data = DASHBOARD_DATA.get('config', {})
        if not config_data:
            # Fallback (partial data is better than crash)
            config_data = get_dashboard_config_data()

        config_data['start_time'] = DASHBOARD_DATA.get('start_time', datetime.now())
        DASHBOARD_DATA['config'] = config_data

        update_dashboard()

    # Populate initial web dashboard data
    if WEB_DASHBOARD_ENABLED:
        target_data_initial = {
            user: {
                'followers': followers_count,
                'following': followings_count,
                'posts': posts_count,
                'reels': reels_count,
                'has_story': has_story,
                'stories_count': 0,
                'is_private': is_private,
                'status': 'OK',
                'bio_changed': False,
                'last_post': None,
                'last_story': None
            }
        }
        # Pass unified config data to web dashboard as well
        config_data_web = WEB_DASHBOARD_DATA.get('config', {})
        if not config_data_web:
             # Try to copy from main dashboard data or fallback
             config_data_web = DASHBOARD_DATA.get('config', get_dashboard_config_data())

        config_data_web['start_time'] = WEB_DASHBOARD_DATA.get('start_time', datetime.now())

        update_web_dashboard_data(targets=target_data_initial, config=config_data_web)

    if user_root_path or OUTPUT_DIR:
        insta_followers_file = os.path.join(json_dir, f"instagram_{user}_followers.json")
        insta_followings_file = os.path.join(json_dir, f"instagram_{user}_followings.json")
        profile_pic_file = os.path.join(images_dir, f"instagram_{user}_profile_pic.jpeg")
        profile_pic_file_old = os.path.join(images_dir, f"instagram_{user}_profile_pic_old.jpeg")
        profile_pic_file_tmp = os.path.join(images_dir, f"instagram_{user}_profile_pic_tmp.jpeg")
    else:
        insta_followers_file = f"instagram_{user}_followers.json"
        insta_followings_file = f"instagram_{user}_followings.json"
        profile_pic_file = f"instagram_{user}_profile_pic.jpeg"
        profile_pic_file_old = f"instagram_{user}_profile_pic_old.jpeg"
        profile_pic_file_tmp = f"instagram_{user}_profile_pic_tmp.jpeg"
    followers = []
    followings = []
    followers_old = followers
    followings_old = followings
    followers_read = []
    followings_read = []

    if os.path.isfile(insta_followers_file):
        try:
            with open(insta_followers_file, 'r', encoding="utf-8") as f:
                followers_read = json.load(f)
        except Exception as e:
            print(f"* Cannot load followers list from '{insta_followers_file}' file: {e}")
        if followers_read:
            followers_old_count = followers_read[0]
            followers_old = followers_read[1]
            if followers_count == followers_old_count:
                followers = followers_old
            followers_mdate = datetime.fromtimestamp(int(os.path.getmtime(insta_followers_file)), pytz.timezone(LOCAL_TIMEZONE))
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Loading Followers'}})

            if DASHBOARD_ENABLED:
                log_activity(f"Followers loaded from file: {len(followers_old)}", user=user)
            else:
                print(f"* Followers ({followers_old_count}) actual ({len(followers_old)}) loaded from file '{insta_followers_file}' ({get_short_date_from_ts(followers_mdate, show_weekday=False, always_show_year=True)})")
            followers_followings_fetched = True

    if followers_count != followers_old_count:
        followers_diff = followers_count - followers_old_count
        followers_diff_str = ""
        if followers_diff > 0:
            followers_diff_str = "+" + str(followers_diff)
        else:
            followers_diff_str = str(followers_diff)
        print(f"* Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})")
        followers_followings_fetched = True

        try:
            if csv_file_name:
                write_csv_entry(csv_file_name, now_local_naive(), "Followers Count", followers_old_count, followers_count)
        except Exception as e:
            print(f"* Error: {e}")

    if ((followers_count != followers_old_count) or (followers_count > 0 and not followers) or DETAILED_FOLLOWER_LOGGING) and not skip_session and not skip_followers and can_view:
        # Fetch followers if count changed, list is empty, or detailed logging is enabled
        if DETAILED_FOLLOWER_LOGGING:
            debug_print(f"Detailed follower logging: Fetching followers for {user}...")
        followers_followings_fetched = True

        try:
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Downloading Followers'}})
            setup_pbar(total_expected=followers_count, title="* Downloading Followers")
            followers = [follower.username for follower in profile.get_followers()]
            close_pbar()
            followers_count = profile.followers
        except Exception as e:
            close_pbar()
            error_msg = format_error_message(e)
            print(f"* Error while getting followers: {error_msg}")
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Error: ' + error_msg}})
            if threading.current_thread() is threading.main_thread():
                sys.exit(1)
            else:
                return

        if not followers and followers_count > 0:
            print("* Empty followers list returned, not saved to file")
        else:
            followers_to_save = []
            followers_to_save.append(followers_count)
            followers_to_save.append(followers)
            try:
                with open(insta_followers_file, 'w', encoding="utf-8") as f:
                    json.dump(followers_to_save, f, indent=2)
                    print(f"* Followers ({followers_count}) actual ({len(followers)}) saved to file '{insta_followers_file}'")
            except Exception as e:
                print(f"* Cannot save list of followers to '{insta_followers_file}' file: {e}")

    # Compare followers: either count changed OR detailed logging detected a difference
    should_compare_followers = ((followers_count != followers_old_count) or (DETAILED_FOLLOWER_LOGGING and followers != followers_old))
    if should_compare_followers and (followers != followers_old) and not skip_session and not skip_followers and can_view and ((followers and followers_count > 0) or (not followers and followers_count == 0)):
        a, b = set(followers_old), set(followers)
        removed_followers = list(a - b)
        added_followers = list(b - a)
        added_followers_list = ""
        removed_followers_list = ""

        print()

        if removed_followers:
            print("Removed followers:\n")
            for f_in_list in removed_followers:
                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                removed_followers_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Removed Followers", f_in_list, "")
                except Exception as e:
                    print(f"* Error: {e}")
            print()

        if added_followers:
            print("Added followers:\n")
            for f_in_list in added_followers:
                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                added_followers_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Added Followers", "", f_in_list)
                except Exception as e:
                    print(f"* Error: {e}")
            print()

    if os.path.isfile(insta_followings_file):
        try:
            with open(insta_followings_file, 'r', encoding="utf-8") as f:
                followings_read = json.load(f)
        except Exception as e:
            print(f"* Cannot load followings list from '{insta_followings_file}' file: {e}")
        if followings_read:
            followings_old_count = followings_read[0]
            followings_old = followings_read[1]
            if followings_count == followings_old_count:
                followings = followings_old
            following_mdate = datetime.fromtimestamp(int(os.path.getmtime(insta_followings_file)), pytz.timezone(LOCAL_TIMEZONE))
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Loading Followings'}})

            if DASHBOARD_ENABLED:
                log_activity(f"Followings loaded from file: {len(followings_old)}", user=user)
            else:
                print(f"\n* Followings ({followings_old_count}) actual ({len(followings_old)}) loaded from file '{insta_followings_file}' ({get_short_date_from_ts(following_mdate, show_weekday=False, always_show_year=True)})")
            followers_followings_fetched = True

    if followings_count != followings_old_count:
        followings_diff = followings_count - followings_old_count
        followings_diff_str = ""
        if followings_diff > 0:
            followings_diff_str = "+" + str(followings_diff)
        else:
            followings_diff_str = str(followings_diff)
        print(f"* Followings number changed by user {user} from {followings_old_count} to {followings_count} ({followings_diff_str})")
        followers_followings_fetched = True
        try:
            if csv_file_name:
                write_csv_entry(csv_file_name, now_local_naive(), "Followings Count", followings_old_count, followings_count)
        except Exception as e:
            print(f"* Error: {e}")

    if ((followings_count != followings_old_count) or (followings_count > 0 and not followings) or DETAILED_FOLLOWER_LOGGING) and not skip_session and not skip_followings and can_view:
        # Fetch followings if count changed, list is empty, or detailed logging is enabled
        if DETAILED_FOLLOWER_LOGGING:
            debug_print(f"Detailed follower logging: Fetching followings for {user}...")
        followers_followings_fetched = True

        try:
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Downloading Followings'}})
            setup_pbar(total_expected=followings_count, title="* Downloading Followings")
            followings = [followee.username for followee in profile.get_followees()]
            close_pbar()
            followings_count = profile.followees
        except Exception as e:
            close_pbar()
            error_msg = format_error_message(e)
            print(f"* Error while getting followings: {error_msg}")
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Error: ' + error_msg}})
            if threading.current_thread() is threading.main_thread():
                sys.exit(1)
            else:
                return

        if not followings and followings_count > 0:
            print("* Empty followings list returned, not saved to file")
        else:
            followings_to_save = []
            followings_to_save.append(followings_count)
            followings_to_save.append(followings)
            try:
                with open(insta_followings_file, 'w', encoding="utf-8") as f:
                    json.dump(followings_to_save, f, indent=2)
                    print(f"* Followings ({followings_count}) actual ({len(followings)}) saved to file '{insta_followings_file}'")
            except Exception as e:
                print(f"* Cannot save list of followings to '{insta_followings_file}' file: {e}")

    # Compare followings: either count changed OR detailed logging detected a difference
    should_compare_followings = ((followings_count != followings_old_count) or (DETAILED_FOLLOWER_LOGGING and followings != followings_old))
    if should_compare_followings and (followings != followings_old) and not skip_session and not skip_followings and can_view and ((followings and followings_count > 0) or (not followings and followings_count == 0)):
        a, b = set(followings_old), set(followings)
        removed_followings = list(a - b)
        added_followings = list(b - a)
        added_followings_list = ""
        removed_followings_list = ""

        print()

        if removed_followings:
            print("Removed followings:\n")
            for f_in_list in removed_followings:
                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                removed_followings_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Removed Followings", f_in_list, "")
                except Exception as e:
                    print(f"* Error: {e}")
            print()

        if added_followings:
            print("Added followings:\n")
            for f_in_list in added_followings:
                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                added_followings_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Added Followings", "", f_in_list)
                except Exception as e:
                    print(f"* Error: {e}")
            print()

    if not skip_session and not skip_followers and can_view:
        followers_old = followers
    else:
        followers = followers_old

    if not skip_session and not skip_followings and can_view:
        followings_old = followings
    else:
        followings = followings_old

    followers_old_count = followers_count
    followings_old_count = followings_count

    if followers_followings_fetched:
        print_cur_ts("\nTimestamp:\t\t\t\t")

    # Profile pic

    if DETECT_CHANGED_PROFILE_PIC:

        try:
            detect_changed_profile_picture(user, profile_image_url, profile_pic_file, profile_pic_file_tmp, profile_pic_file_old, PROFILE_PIC_FILE_EMPTY, csv_file_name, r_sleep_time, False, 1)
        except Exception as e:
            print(f"* Error while processing changed profile picture: {e}")

    # Stories

    processed_stories_list = []
    if has_story:
        story_flag = True
        stories_count = 1

        if not skip_session and can_view and not skip_getting_story_details:
            try:
                if WEB_DASHBOARD_ENABLED:
                    update_web_dashboard_data(targets={user: {'status': 'Loading Stories'}})
                stories = bot.get_stories(userids=[insta_userid])

                for story in stories:
                    stories_count = story.itemcount
                    if stories_count > 0:
                        print(f"* User {user} has {stories_count} story items:")
                        print("─" * HORIZONTAL_LINE)
                    i = 0
                    for story_item in story.get_items():
                        i += 1

                        utc_dt = story_item.date_utc
                        local_dt = convert_utc_datetime_to_tz_datetime(utc_dt)
                        if local_dt:
                            local_ts = int(local_dt.timestamp())
                        else:
                            local_ts = 0

                        processed_stories_list.append(local_ts)

                        expire_utc_dt = story_item.expiring_utc
                        expire_local_dt = convert_utc_datetime_to_tz_datetime(expire_utc_dt)
                        if expire_local_dt:
                            expire_ts = int(expire_local_dt.timestamp())
                        else:
                            expire_ts = 0

                        print(f"Date:\t\t\t\t\t{get_date_from_ts(local_dt)}")
                        print(f"Expiry:\t\t\t\t\t{get_date_from_ts(expire_local_dt)}")
                        if story_item.typename == "GraphStoryImage":
                            story_type = "Image"
                        else:
                            story_type = "Video"
                        print(f"Type:\t\t\t\t\t{story_type}")

                        story_mentions = story_item.caption_mentions
                        story_hashtags = story_item.caption_hashtags

                        if story_mentions:
                            print(f"Mentions:\t\t\t\t{story_mentions}")

                        if story_hashtags:
                            print(f"Hashtags:\t\t\t\t{story_hashtags}")

                        story_caption = story_item.caption
                        if story_caption:
                            print(f"Description:\n\n{story_caption}\n")
                        else:
                            print()

                        story_thumbnail_url = story_item.url
                        story_video_url = story_item.video_url

                        if story_video_url:
                            if local_dt:
                                story_video_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
                            else:
                                story_video_filename = f'instagram_{user}_story_{now_local().strftime("%Y%m%d_%H%M%S")}.mp4'

                            if user_root_path or OUTPUT_DIR:
                                story_video_filename = os.path.join(videos_dir, story_video_filename)
                            if not os.path.isfile(story_video_filename):
                                if save_pic_video(story_video_url, story_video_filename, local_ts):
                                    print(f"Story video saved for {user} to '{story_video_filename}'")

                        if story_thumbnail_url:
                            if local_dt:
                                story_image_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                            else:
                                story_image_filename = f'instagram_{user}_story_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'

                            if user_root_path or OUTPUT_DIR:
                                story_image_filename = os.path.join(images_dir, story_image_filename)
                            if not os.path.isfile(story_image_filename):
                                if save_pic_video(story_thumbnail_url, story_image_filename, local_ts):
                                    print(f"Story thumbnail image saved for {user} to '{story_image_filename}'")
                            if os.path.isfile(story_image_filename):
                                try:
                                    if imgcat_exe:
                                        subprocess.run(f"{'echo.' if platform.system() == 'Windows' else 'echo'} {'&' if platform.system() == 'Windows' else ';'} {imgcat_exe} {story_image_filename}", shell=True, check=True)
                                        if i < stories_count:
                                            print()
                                except Exception:
                                    pass

                        try:
                            if csv_file_name:
                                write_csv_entry(csv_file_name, convert_to_local_naive(local_dt), "New Story Item", "", story_type)
                        except Exception as e:
                            print(f"* Error: {e}")

                        # Update last_story for dashboard (this loop runs from oldest to newest usually, so we update on each)
                        last_story = {
                            'type': story_type,
                            'caption': story_caption[:50] + "..." if story_caption and len(story_caption) > 50 else (story_caption or ""),
                            'url': story_thumbnail_url,
                            'timestamp': get_short_date_from_ts(local_dt)
                        }

                        if i == stories_count:
                            print_cur_ts("\nTimestamp:\t\t\t\t")
                        else:
                            print("─" * HORIZONTAL_LINE)

                    break

                stories_old_count = stories_count

            except Exception as e:
                error_msg = format_error_message(e)
                print(f"* Error while processing story items: {error_msg}")
                if WEB_DASHBOARD_ENABLED:
                    update_web_dashboard_data(targets={user: {'status': 'Error: ' + error_msg}})
                if threading.current_thread() is threading.main_thread():
                    sys.exit(1)
                else:
                    return

    # Post details

    highestinsta_ts = 0
    highestinsta_dt = datetime.fromtimestamp(0)
    likes = 0
    comments = 0
    caption = ""
    pcaption = ""
    tagged_users = []
    shortcode = ""
    location = None
    likes_users_list = ""
    post_comments_list = ""
    last_post = None
    last_source = "post"
    thumbnail_url = ""
    video_url = ""

    if int(posts_count + reels_count) >= 1 and can_view and not skip_getting_posts_details:
        if bot.context.is_logged_in:
            print("Fetching user's latest post/reel ...\n")
        else:
            print("Fetching user's latest post ...\n")

        if WEB_DASHBOARD_ENABLED:
            update_web_dashboard_data(targets={user: {'status': 'Fetching Posts'}})
        try:

            time.sleep(NEXT_OPERATION_DELAY)
            if bot.context.is_logged_in:  # GraphQL helper when logged in
                last_post_reel = latest_post_reel(user, bot)
            else:  # fallback to mobile helper when anonymous
                last_post_reel = latest_post_mobile(user, bot)

            if last_post_reel:
                last_post, last_source = last_post_reel
                utc_dt = last_post.date_utc
                local_dt = convert_utc_datetime_to_tz_datetime(utc_dt)
                if local_dt:
                    local_ts = int(local_dt.timestamp())
                else:
                    local_ts = 0

                highestinsta_ts = local_ts
                highestinsta_dt = local_dt

            if last_post:
                likes = last_post.likes
                comments = last_post.comments
                caption = last_post.caption if last_post.caption is not None else "(empty)"
                pcaption = last_post.pcaption or ""
                tagged_users = last_post.tagged_users
                if last_source == "reel":
                    shortcode = get_real_reel_code(bot, user) or last_post.shortcode
                else:
                    shortcode = last_post.shortcode
                thumbnail_url = last_post.url
                video_url = last_post.video_url
                if last_source == "post":
                    location = get_post_location_mobile(last_post, bot)
            else:
                print(f"* Error: Failed to get last post/reel details")

        except Exception as e:
            error_msg = format_error_message(e)
            print(f"* Error while processing posts/reels: {error_msg}")
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Error: ' + error_msg}})
            if threading.current_thread() is threading.main_thread():
                sys.exit(1)
            else:
                return

        try:
            # Below won't work until Instaloader updates query hashes in new release
            if not skip_session and get_more_post_details and last_post:
                likes_list = last_post.get_likes()
                for like in likes_list:
                    likes_users_list += "- " + like.username + " [ " + "https://www.instagram.com/" + like.username + "/ ]\n"
                comments_list = last_post.get_comments()
                for comment in comments_list:
                    comment_created_at = convert_utc_datetime_to_tz_datetime(comment.created_at_utc)
                    if comment_created_at:
                        post_comments_list += "\n[ " + get_short_date_from_ts(comment_created_at) + " - " + "https://www.instagram.com/" + comment.owner.username + "/ ]\n" + comment.text + "\n"
        except Exception as e:
            error_msg = format_error_message(e)
            print(f"* Error while getting post's likes list / comments list: {error_msg}")

        post_url = f"https://www.instagram.com/{'reel' if last_source == 'reel' else 'p'}/{shortcode}/"
        print(f"* Newest {last_source.lower()} for user {user}:\n")
        print(f"Date:\t\t\t\t\t{get_date_from_ts(highestinsta_dt)} ({calculate_timespan(now_local(), highestinsta_dt)} ago)")
        print(f"{last_source.capitalize()} URL:\t\t\t\t{post_url}")
        print(f"Profile URL:\t\t\t\thttps://www.instagram.com/{insta_username}/")
        print(f"Likes:\t\t\t\t\t{likes}")
        print(f"Comments:\t\t\t\t{comments}")
        print(f"Tagged users:\t\t\t\t{tagged_users}")

        if location:
            print(f"Location:\t\t\t\t{location}")

        print(f"Description:\n\n{caption}\n")

        if likes_users_list:
            print(f"Likes list:\n{likes_users_list}")

        if post_comments_list:
            print(f"Comments list:{post_comments_list}")

        if video_url:
            if highestinsta_dt and highestinsta_dt.timestamp() > 0:
                video_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
            else:
                video_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.mp4'

            if (user_root_path or OUTPUT_DIR) and 'videos_dir' in locals():
                if not os.path.dirname(video_filename) == videos_dir:
                    video_filename = os.path.join(videos_dir, video_filename)

            if not os.path.isfile(video_filename):
                if save_pic_video(video_url, video_filename, highestinsta_ts):
                    print(f"{last_source.capitalize()} video saved for {user} to '{video_filename}'")
                else:
                    print(f"Error saving {last_source.lower()} video !")

        if thumbnail_url:
            if highestinsta_dt:
                image_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
            else:
                image_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'
            if not os.path.isfile(image_filename):
                if save_pic_video(thumbnail_url, image_filename, highestinsta_ts):
                    print(f"{last_source.capitalize()} thumbnail image saved for {user} to '{image_filename}'")
            if os.path.isfile(image_filename):
                try:
                    if imgcat_exe:
                        subprocess.run(f"{imgcat_exe} {image_filename}", shell=True, check=True)
                except Exception:
                    pass

        # Update last_post for dashboard
        last_post = {
            'type': last_source.capitalize(),
            'caption': caption[:50] + "..." if caption and len(caption) > 50 else (caption or ""),
            'url': thumbnail_url,
            'timestamp': get_short_date_from_ts(highestinsta_dt)
        }

        print_cur_ts("\nTimestamp:\t\t\t\t")

        highestinsta_ts_old = highestinsta_ts
        highestinsta_dt_old = highestinsta_dt

    else:
        highestinsta_ts_old = int(time.time())
        highestinsta_dt_old = now_local()

    # Initialize check timing and update last check time for dashboard
    # Combined call prevents double increment of CHECK_COUNT
    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
    update_check_times(
        last_time=now_local_naive(),
        next_time=now_local_naive() + timedelta(seconds=r_sleep_time),
        user=user
    )
    if DASHBOARD_ENABLED and RICH_AVAILABLE:
        if 'targets' not in DASHBOARD_DATA:
            DASHBOARD_DATA['targets'] = {}

        DASHBOARD_DATA['targets'][user].update({
            'followers': followers_count,
            'following': followings_count,
            'posts': posts_count,
            'reels': reels_count,
            'has_story': has_story,
            'stories_count': stories_count,
            'last_post': last_post,
            'last_story': last_story
        })

        DASHBOARD_DATA['config'] = get_dashboard_config_data()
        update_dashboard()

    if WEB_DASHBOARD_ENABLED:
        update_web_dashboard_data(targets={
            user: {
                'followers': followers_count,
                'following': followings_count,
                'posts': posts_count,
                'reels': reels_count,
                'has_story': has_story,
                'stories_count': stories_count,
                'last_post': last_post, # Will be merged
                'last_story': last_story, # Will be merged
                'status': 'Waiting'
            }
        }, config=get_dashboard_config_data())

    # Signal that full initial loading (followers, followings, profile pic, stories, latest post/reel) is complete
    # so the next user can start without interleaving output
    if signal_loading_complete is not None:
        signal_loading_complete.set()

    # Monitoring active message
    now = now_local_naive()
    next_check = now + timedelta(seconds=r_sleep_time)

    # Only print tracking message if Dashboard is not enabled
    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
        if threading.current_thread() is not threading.main_thread():
            print(f"* Tracking {user} (and others)... next check for {user} planned at ~{next_check.strftime('%H:%M:%S')} (in {display_time(r_sleep_time)})\n")
        else:
            print(f"* Tracking {user}... next check planned at ~{next_check.strftime('%H:%M:%S')} (in {display_time(r_sleep_time)})\n")

    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
        print_cur_ts("Timestamp:\t\t\t\t")

    if HOURS_VERBOSE or DEBUG_MODE:
        sleep_message(r_sleep_time)
        if DEBUG_MODE:
            print(f"[DEBUG] Next check scheduled: {get_date_from_ts(NEXT_CHECK_TIME)}")

    # Use interruptible sleep if stop_event is provided (allows immediate stop)
    if stop_event or DEBUG_MODE or WEB_DASHBOARD_ENABLED:
        # Sleep in smaller increments to allow stop event or manual check trigger
        sleep_remaining = r_sleep_time
        if WEB_DASHBOARD_ENABLED:
            update_web_dashboard_data(targets={user: {'status': 'Waiting'}})
        while sleep_remaining > 0:
            # Check for stop event
            if stop_event and stop_event.is_set():
                if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                    print(f"* Monitoring stopped for {user}\n")
                    print_cur_ts("Timestamp:\t\t\t\t")
                else:
                    log_activity("Monitoring stopped", user=user)
                return

            # Check for manual trigger (debug mode)
            if DEBUG_MODE and MANUAL_CHECK_TRIGGERED.is_set():  # type: ignore
                MANUAL_CHECK_TRIGGERED.clear()  # type: ignore
                if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                    print(f"* Manual check requested! Breaking sleep early...\n")
                    print_cur_ts("Timestamp:\t\t\t\t")
                else:
                    debug_print(f"Manual check triggered, {sleep_remaining}s remaining in sleep")
                break

            # Check for recheck trigger (Web Dashboard mode)
            recheck_triggered = False
            with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                if user in WEB_DASHBOARD_RECHECK_EVENTS and WEB_DASHBOARD_RECHECK_EVENTS[user].is_set():
                    WEB_DASHBOARD_RECHECK_EVENTS[user].clear()
                    recheck_triggered = True

            if recheck_triggered:
                if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                    print(f"* Recheck requested for {user}! Breaking sleep early...\n")
                    print_cur_ts("Timestamp:\t\t\t\t")
                break

            # Sleep in 1-second increments for responsiveness
            sleep_chunk = min(1, sleep_remaining)
            if stop_event:
                stop_event.wait(sleep_chunk)
            else:
                time.sleep(sleep_chunk)
            sleep_remaining -= sleep_chunk
    else:
        time.sleep(r_sleep_time)

    alive_counter = 0

    email_sent = False

    # Primary loop
    while True:
        # Check stop event at the start of each loop iteration
        if stop_event and stop_event.is_set():
            if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                print(f"* Monitoring stopped for {user}\n")
                print_cur_ts("Timestamp:\t\t\t\t")
            return

        reset_thread_output()
        if WEB_DASHBOARD_ENABLED:
            update_web_dashboard_data(targets={user: {'status': 'Checking'}})

        # Update last check time
        update_check_times(last_time=now_local_naive(), user=user)

        # Debug: show check start
        debug_print(f"Starting check #{CHECK_COUNT} for user {user}")

        cur_h = datetime.now().strftime("%H")

        in_allowed_hours = (CHECK_POSTS_IN_HOURS_RANGE and (int(cur_h) in hours_to_check())) or not CHECK_POSTS_IN_HOURS_RANGE

        if in_allowed_hours:
            if HOURS_VERBOSE:
                if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                    print(f"*** Fetching Updates. Current Hour: {int(cur_h)}. Allowed hours: {hours_to_check()}")
                    print("─" * HORIZONTAL_LINE)
                    if WEB_DASHBOARD_ENABLED:
                         log_activity(f"Fetching updates (Hour: {int(cur_h)})", user=user)
                else:
                    log_activity(f"Fetching updates (Hour: {int(cur_h)})", user=user)

            debug_print(f"Fetching profile data from Instagram API...")

            try:
                profile = instaloader.Profile.from_username(bot.context, user)
                time.sleep(NEXT_OPERATION_DELAY)
                new_post = False
                followers_count = profile.followers
                followings_count = profile.followees
                bio = profile.biography
                is_private = profile.is_private
                followed_by_viewer = profile.followed_by_viewer
                can_view = (not is_private) or followed_by_viewer
                posts_count = profile.mediacount

                debug_print(f"Profile loaded: followers={followers_count}, following={followings_count}, posts={posts_count}")

                if not skip_session and can_view:
                    reels_count = get_total_reels_count(user, bot, skip_session)
                    debug_print(f"Reels count: {reels_count}")

                if not is_private:
                    if bot.context.is_logged_in:
                        has_story = profile.has_public_story
                    else:
                        has_story = False
                elif bot.context.is_logged_in and followed_by_viewer:
                    story = next(bot.get_stories(userids=[insta_userid]), None)
                    has_story = bool(story and story.itemcount)
                else:
                    has_story = False

                debug_print(f"Story available: {has_story}")

                profile_image_url = profile.profile_pic_url_no_iphone
                email_sent = False

                # Prepare target data for both Dashboard and Web Dashboard
                target_data = {
                    user: {
                        'followers': followers_count,
                        'following': followings_count,
                        'posts': posts_count,
                        'reels': reels_count if 'reels_count' in dir() else 0,
                        'has_story': has_story,
                        'is_private': is_private,
                        'status': 'OK',
                        'bio_changed': False
                    }
                }
                config_data = {
                    'check_interval': INSTA_CHECK_INTERVAL,
                    'random_low': RANDOM_SLEEP_DIFF_LOW,
                    'random_high': RANDOM_SLEEP_DIFF_HIGH,
                    'session_user': SESSION_USERNAME or '<anonymous>',
                    'skip_session': SKIP_SESSION,
                    'skip_followers': SKIP_FOLLOWERS,
                    'skip_followings': SKIP_FOLLOWINGS,
                    'status_notif': STATUS_NOTIFICATION,
                    'follower_notif': FOLLOWERS_NOTIFICATION,
                    'error_notif': ERROR_NOTIFICATION,
                    'webhook_enabled': WEBHOOK_ENABLED,
                    'human_mode': BE_HUMAN,
                    'enable_jitter': ENABLE_JITTER,
                    'debug_mode': DEBUG_MODE,
                    'detailed_log': DETAILED_FOLLOWER_LOGGING,
                    'start_time': DASHBOARD_DATA.get('start_time', datetime.now())
                }

                # Update Dashboard with target data (merge with existing targets for multi-target mode)
                if DASHBOARD_ENABLED and RICH_AVAILABLE:
                    if 'targets' not in DASHBOARD_DATA:
                        DASHBOARD_DATA['targets'] = {}
                    DASHBOARD_DATA['targets'].update(target_data)  # Merge, don't overwrite
                    DASHBOARD_DATA['config'] = config_data
                    update_dashboard()

                # Update web dashboard with target data
                if WEB_DASHBOARD_ENABLED:
                    update_web_dashboard_data(targets=target_data, config=config_data)
            except Exception as e:
                r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
                error_msg = format_error_message(e)
                print(f"* Error, retrying in {display_time(r_sleep_time)}: {error_msg}")
                debug_print(f"Full exception: {type(e).__name__}: {e}")

                if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                    print("* Session might not be valid anymore!")
                    if ERROR_NOTIFICATION and not email_sent:
                        m_subject = f"instagram_monitor: session error! (session: {session_label()}, target: {user})"

                        m_body = f"Session might not be valid anymore.\n\nSession: {session_label()}\nTarget: {user}\n\nError: {e}{get_cur_ts(nl_ch + nl_ch + 'Timestamp: ')}"
                        print(f"Sending email notification to {RECEIVER_EMAIL}")
                        send_email(m_subject, m_body, "", SMTP_SSL)
                        email_sent = True

                print_cur_ts("Timestamp:\t\t\t\t")
                time.sleep(r_sleep_time)
                continue

            if (next((s for s in get_thread_output() if "HTTP redirect from" in s), None)):
                r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
                print("* Session might not be valid anymore!")
                print(f"Retrying in {display_time(r_sleep_time)}")
                if ERROR_NOTIFICATION and not email_sent:
                    m_subject = f"instagram_monitor: session error! (session: {session_label()}, target: {user})"

                    m_body = f"Session might not be valid anymore.\n\nSession: {session_label()}\nTarget: {user}\n\nOutput: {get_thread_output()}{get_cur_ts(nl_ch + nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}")
                    send_email(m_subject, m_body, "", SMTP_SSL)
                    email_sent = True
                print_cur_ts("Timestamp:\t\t\t\t")
                time.sleep(r_sleep_time)
                continue

            if followings_count != followings_old_count:
                followings_diff = followings_count - followings_old_count
                followings_diff_str = ""
                if followings_diff > 0:
                    followings_diff_str = "+" + str(followings_diff)
                else:
                    followings_diff_str = str(followings_diff)
                if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                    print(f"* Followings number changed by user {user} from {followings_old_count} to {followings_count} ({followings_diff_str})")
                log_activity(f"Followings changed: {followings_old_count} -> {followings_count}", user=user)
                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Followings Count", followings_old_count, followings_count)
                except Exception as e:
                    print(f"* Error: {e}")

                added_followings_list = ""
                removed_followings_list = ""
                added_followings_mbody = ""
                removed_followings_mbody = ""

                if not skip_session and not skip_followings and can_view:
                    try:
                        setup_pbar(total_expected=followings_count, title="* Downloading Followings")
                        followings = []
                        followings = [followee.username for followee in profile.get_followees()]
                        followings_to_save = []
                        close_pbar()
                        # Refresh profile to get current reported counts for comparison
                        profile = instaloader.Profile.from_username(bot.context, user)
                        followings_count = profile.followees
                        followers_count_reported = profile.followers
                        show_follow_info(followers_count_reported, len(followers), followings_count, len(followings))
                        if not followings and followings_count > 0:
                            print("* Empty followings list returned, not saved to file")
                        else:
                            followings_to_save.append(followings_count)
                            followings_to_save.append(followings)
                            with open(insta_followings_file, 'w', encoding="utf-8") as f:
                                json.dump(followings_to_save, f, indent=2)
                                print(f"* Followings ({followings_count}) actual ({len(followings)}) saved to file '{insta_followings_file}'")
                    except Exception as e:
                        close_pbar()
                        followings = followings_old
                        error_msg = format_error_message(e)
                        print(f"* Error while processing followings: {error_msg}")

                    if not followings and followings_count > 0:
                        followings = followings_old
                    else:
                        a, b = set(followings_old), set(followings)

                        removed_followings = list(a - b)
                        added_followings = list(b - a)

                        if followings != followings_old:
                            print()

                            if removed_followings:
                                print("Removed followings:\n")
                                removed_followings_mbody = "\nRemoved followings:\n\n"
                                for f_in_list in removed_followings:
                                    print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                                    removed_followings_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, now_local_naive(), "Removed Followings", f_in_list, "")
                                    except Exception as e:
                                        print(f"* Error: {e}")
                                print()

                            if added_followings:
                                print("Added followings:\n")
                                added_followings_mbody = "\nAdded followings:\n\n"
                                for f_in_list in added_followings:
                                    print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                                    log_activity(f"Added following: {f_in_list}", user=user)
                                    added_followings_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, now_local_naive(), "Added Followings", "", f_in_list)
                                    except Exception as e:
                                        print(f"* Error: {e}")
                                print()

                        followings_old = followings

                if STATUS_NOTIFICATION:
                    m_subject = f"Instagram user {user} followings number has changed! ({followings_diff_str}, {followings_old_count} -> {followings_count})"

                    if not skip_session and not skip_followings and can_view:

                        m_body = f"Followings number changed by user {user} from {followings_old_count} to {followings_count} ({followings_diff_str})\n{removed_followings_mbody}{removed_followings_list}{added_followings_mbody}{added_followings_list}\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    else:

                        m_body = f"Followings number changed by user {user} from {followings_old_count} to {followings_count} ({followings_diff_str})\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                    send_email(m_subject, m_body, "", SMTP_SSL)

                # Send webhook notification for followings change
                webhook_result = send_follower_change_webhook(
                    user, "followings", followings_old_count, followings_count,
                    added_followings_list, removed_followings_list
                )
                if webhook_result != 0 and DEBUG_MODE:
                    print(f"* Warning: Webhook notification for followings change failed")

                followings_old_count = followings_count

                print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t\t\t")

            if followers_count != followers_old_count:
                followers_diff = followers_count - followers_old_count
                followers_diff_str = ""
                if followers_diff > 0:
                    followers_diff_str = "+" + str(followers_diff)
                else:
                    followers_diff_str = str(followers_diff)
                print(f"* Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})")
                log_activity(f"Followers changed: {followers_old_count} -> {followers_count}", user=user)

                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Followers Count", followers_old_count, followers_count)
                except Exception as e:
                    print(f"* Error: {e}")

                added_followers_list = ""
                removed_followers_list = ""
                added_followers_mbody = ""
                removed_followers_mbody = ""

                if not skip_session and not skip_followers and can_view:
                    try:
                        setup_pbar(total_expected=followers_count, title="* Downloading Followers")
                        followers = []
                        followers = [follower.username for follower in profile.get_followers()]
                        followers_to_save = []
                        close_pbar()
                        # Refresh profile to get current reported counts for comparison
                        profile = instaloader.Profile.from_username(bot.context, user)
                        followers_count = profile.followers
                        followings_count_reported = profile.followees
                        show_follow_info(followers_count, len(followers), followings_count_reported, len(followings))
                        if not followers and followers_count > 0:
                            print("* Empty followers list returned, not saved to file")
                        else:
                            followers_to_save.append(followers_count)
                            followers_to_save.append(followers)
                            with open(insta_followers_file, 'w', encoding="utf-8") as f:
                                json.dump(followers_to_save, f, indent=2)
                                print(f"* Followers ({followers_count}) actual ({len(followers)}) saved to file '{insta_followers_file}'")
                    except Exception as e:
                        close_pbar()
                        followers = followers_old
                        error_msg = format_error_message(e)
                        print(f"* Error while processing followers: {error_msg}")

                    if not followers and followers_count > 0:
                        followers = followers_old
                    else:
                        a, b = set(followers_old), set(followers)
                        removed_followers = list(a - b)
                        added_followers = list(b - a)

                        if followers != followers_old:
                            print()

                            if removed_followers:
                                print("Removed followers:\n")
                                removed_followers_mbody = "\nRemoved followers:\n\n"
                                for f_in_list in removed_followers:
                                    print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                                    log_activity(f"Removed follower: {f_in_list}", user=user)
                                    removed_followers_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, now_local_naive(), "Removed Followers", f_in_list, "")
                                    except Exception as e:
                                        print(f"* Error: {e}")
                                print()

                            if added_followers:
                                print("Added followers:\n")
                                added_followers_mbody = "\nAdded followers:\n\n"
                                for f_in_list in added_followers:
                                    print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                                    log_activity(f"Added follower: {f_in_list}", user=user)
                                    added_followers_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, now_local_naive(), "Added Followers", "", f_in_list)
                                    except Exception as e:
                                        print(f"* Error: {e}")
                                print()

                        followers_old = followers

                if STATUS_NOTIFICATION and FOLLOWERS_NOTIFICATION:
                    m_subject = f"Instagram user {user} followers number has changed! ({followers_diff_str}, {followers_old_count} -> {followers_count})"

                    if not skip_session and not skip_followers and can_view:
                        m_body = f"Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})\n{removed_followers_mbody}{removed_followers_list}{added_followers_mbody}{added_followers_list}\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    else:
                        m_body = f"Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                    send_email(m_subject, m_body, "", SMTP_SSL)

                # Send webhook notification for followers change
                webhook_result = send_follower_change_webhook(
                    user, "followers", followers_old_count, followers_count,
                    added_followers_list, removed_followers_list
                )
                if webhook_result != 0 and DEBUG_MODE:
                    print(f"* Warning: Webhook notification for followers change failed")

                followers_old_count = followers_count

                print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t\t\t")

            # Profile pic

            if DETECT_CHANGED_PROFILE_PIC:

                try:
                    detect_changed_profile_picture(user, profile_image_url, profile_pic_file, profile_pic_file_tmp, profile_pic_file_old, PROFILE_PIC_FILE_EMPTY, csv_file_name, r_sleep_time, STATUS_NOTIFICATION, 2)
                except Exception as e:
                    print(f"* Error while processing changed profile picture: {e}")

            if bio != bio_old:
                print(f"* Bio changed for user {user} !\n")
                log_activity("Bio changed", user=user)
                print(f"Old bio:\n\n{bio_old}\n")
                print(f"New bio:\n\n{bio}\n")

                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Bio Changed", bio_old, bio)
                except Exception as e:
                    print(f"* Error: {e}")

                if STATUS_NOTIFICATION:
                    m_subject = f"Instagram user {user} bio has changed!"

                    m_body = f"Instagram user {user} bio has changed\n\nOld bio:\n\n{bio_old}\n\nNew bio:\n\n{bio}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                    send_email(m_subject, m_body, "", SMTP_SSL)

                # Send webhook notification for bio change
                webhook_result = send_webhook(
                    f"📝 {user} Bio Changed",
                    f"User **{user}** has updated their bio",
                    color=0x9b59b6,  # Purple
                    fields=[
                        {"name": "Old Bio", "value": (bio_old[:DISCORD_FIELD_VALUE_LIMIT-4] + "...") if len(bio_old) > DISCORD_FIELD_VALUE_LIMIT else bio_old or "(empty)"},
                        {"name": "New Bio", "value": (bio[:DISCORD_FIELD_VALUE_LIMIT-4] + "...") if len(bio) > DISCORD_FIELD_VALUE_LIMIT else bio or "(empty)"},
                    ],
                    notification_type="status"
                )
                if webhook_result != 0 and DEBUG_MODE:
                    print(f"* Warning: Webhook notification for bio change failed")

                bio_old = bio
                print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t\t\t")

            if is_private != is_private_old:

                if is_private:
                    profile_visibility = "private"
                    profile_visibility_old = "public"
                else:
                    profile_visibility = "public"
                    profile_visibility_old = "private"

                print(f"* Profile visibility changed for user {user} to {profile_visibility} !\n")
                log_activity(f"Visibility changed: {profile_visibility}", user=user)

                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Profile Visibility", profile_visibility_old, profile_visibility)
                except Exception as e:
                    print(f"* Error: {e}")

                if STATUS_NOTIFICATION:
                    m_subject = f"Instagram user {user} profile visibility has changed to {profile_visibility} !"

                    m_body = f"Instagram user {user} profile visibility has changed to {profile_visibility}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                    send_email(m_subject, m_body, "", SMTP_SSL)

                # Send webhook notification for visibility change
                emoji = "🔒" if is_private else "🔓"
                webhook_result = send_webhook(
                    f"{emoji} {user} Profile Visibility Changed",
                    f"User **{user}** profile is now **{profile_visibility}**",
                    color=0xe67e22,  # Orange
                    fields=[
                        {"name": "Old", "value": profile_visibility_old, "inline": True},
                        {"name": "New", "value": profile_visibility, "inline": True},
                    ],
                    notification_type="status"
                )
                if webhook_result != 0 and DEBUG_MODE:
                    print(f"* Warning: Webhook notification for visibility change failed")

                is_private_old = is_private
                print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t\t\t")

            if followed_by_viewer != followed_by_viewer_old:

                print(f"* Your account {'started following' if followed_by_viewer else 'stopped following'} the user {user} !")

                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "Followed By Viewer", followed_by_viewer_old, followed_by_viewer)
                except Exception as e:
                    print(f"* Error: {e}")

                if STATUS_NOTIFICATION:
                    m_subject = f"Your account {'started following' if followed_by_viewer else 'stopped following'} the user {user} !"

                    m_body = f"Your account {'started following' if followed_by_viewer else 'stopped following'} the user {user}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                    send_email(m_subject, m_body, "", SMTP_SSL)

                followed_by_viewer_old = followed_by_viewer
                print(f"Check interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t\t\t")

            if has_story and not story_flag:
                print(f"* New story for user {user} !\n")
                log_activity("New story detected", user=user)
                story_flag = True
                stories_count = 1

                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, now_local_naive(), "New Story", "", "")
                except Exception as e:
                    print(f"* Error: {e}")

                if STATUS_NOTIFICATION:
                    m_subject = f"Instagram user {user} has a new story!"

                    m_body = f"Instagram user {user} has a new story\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}")
                    send_email(m_subject, m_body, "", SMTP_SSL)

                # Send webhook notification for new story
                webhook_result = send_webhook(
                    f"📖 {user} New Story",
                    f"User **{user}** has posted a new story!",
                    color=0xe91e63,  # Pink
                    fields=[
                        {"name": "Profile", "value": f"https://www.instagram.com/{user}/", "inline": True},
                    ],
                    notification_type="status"
                )
                if webhook_result != 0 and DEBUG_MODE:
                    print(f"* Warning: Webhook notification for new story failed")

                print(f"\nCheck interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t\t\t")

            if not has_story and story_flag:
                processed_stories_list = []
                stories_count = 0
                print(f"* Story for user {user} disappeared !")
                log_activity("Story disappeared", user=user)
                print(f"\nCheck interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t\t\t")
                story_flag = False

            if has_story and not skip_session and can_view and not skip_getting_story_details:
                try:
                    stories = bot.get_stories(userids=[insta_userid])

                    for story in stories:
                        stories_count = story.itemcount
                        if stories_count == stories_old_count or stories_count <= 0:
                            break

                        i = 0
                        for story_item in story.get_items():
                            i += 1

                            utc_dt = story_item.date_utc
                            local_dt = convert_utc_datetime_to_tz_datetime(utc_dt)
                            if local_dt:
                                local_ts = int(local_dt.timestamp())
                            else:
                                local_ts = 0

                            if local_ts in processed_stories_list:
                                continue
                            processed_stories_list.append(local_ts)

                            expire_utc_dt = story_item.expiring_utc
                            expire_local_dt = convert_utc_datetime_to_tz_datetime(expire_utc_dt)
                            if expire_local_dt:
                                expire_ts = int(expire_local_dt.timestamp())
                            else:
                                expire_ts = 0

                            print(f"* User {user} has new story item:\n")
                            log_activity(f"New story item: {story_type}", user=user)
                            print(f"Date:\t\t\t{get_date_from_ts(local_dt)}")
                            print(f"Expiry:\t\t\t{get_date_from_ts(expire_local_dt)}")
                            if story_item.typename == "GraphStoryImage":
                                story_type = "Image"
                            else:
                                story_type = "Video"
                            print(f"Type:\t\t\t{story_type}")

                            story_mentions = story_item.caption_mentions
                            story_hashtags = story_item.caption_hashtags

                            story_mentions_m_body = ""
                            story_mentions_m_body_html = ""
                            if story_mentions:
                                story_mentions_m_body = f"\nMentions: {story_mentions}"
                                story_mentions_m_body_html = f"<br>Mentions: {story_mentions}"
                                print(f"Mentions:\t\t\t\t{story_mentions}")

                            story_hashtags_m_body = ""
                            story_hashtags_m_body_html = ""
                            if story_hashtags:
                                story_hashtags_m_body = f"\nHashtags: {story_hashtags}"
                                story_hashtags_m_body_html = f"<br>Hashtags: {story_hashtags}"
                                print(f"Hashtags:\t\t\t\t{story_hashtags}")

                            story_caption_m_body = ""
                            story_caption_m_body_html = ""
                            story_caption = story_item.caption
                            if story_caption:
                                story_caption_m_body = f"\nDescription:\n\n{story_caption}"
                                story_caption_m_body_html = f"<br>Description:<br><br>{story_caption}"
                                print(f"Description:\n\n{story_caption}\n")
                            else:
                                print()

                            story_thumbnail_url = story_item.url
                            story_video_url = story_item.video_url

                            if story_video_url:
                                if local_dt:
                                    story_video_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
                                else:
                                    story_video_filename = f'instagram_{user}_story_{now_local().strftime("%Y%m%d_%H%M%S")}.mp4'

                                if user_root_path or OUTPUT_DIR:
                                    story_video_filename = os.path.join(videos_dir, story_video_filename)
                                if not os.path.isfile(story_video_filename):
                                    if save_pic_video(story_video_url, story_video_filename, local_ts):
                                        print(f"Story video saved for {user} to '{story_video_filename}'")

                            m_body_html_pic_saved_text = ""
                            if local_dt:
                                story_image_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                            else:
                                story_image_filename = f'instagram_{user}_story_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'

                            if user_root_path or OUTPUT_DIR:
                                story_image_filename = os.path.join(images_dir, story_image_filename)
                            if story_thumbnail_url:
                                if not os.path.isfile(story_image_filename):
                                    if save_pic_video(story_thumbnail_url, story_image_filename, local_ts):
                                        m_body_html_pic_saved_text = f'<br><br><img src="cid:story_pic" width="50%">'
                                        print(f"Story thumbnail image saved for {user} to '{story_image_filename}'")
                                        try:
                                            if imgcat_exe:
                                                subprocess.run(f"{'echo.' if platform.system() == 'Windows' else 'echo'} {'&' if platform.system() == 'Windows' else ';'} {imgcat_exe} {story_image_filename}", shell=True, check=True)
                                                if i < stories_count:
                                                    print()
                                        except Exception:
                                            pass

                            try:
                                if csv_file_name:
                                    write_csv_entry(csv_file_name, convert_to_local_naive(local_dt), "New Story Item", "", story_type)
                            except Exception as e:
                                print(f"* Error: {e}")

                            if STATUS_NOTIFICATION:
                                m_subject = f"Instagram user {user} has a new story item ({get_short_date_from_ts(int(local_ts))})"

                                m_body = f"Instagram user {user} has a new story item\n\nDate: {get_date_from_ts(int(local_ts))}\nExpiry: {get_date_from_ts(int(expire_ts))}\nType: {story_type}{story_mentions_m_body}{story_hashtags_m_body}{story_caption_m_body}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                                m_body_html = f"Instagram user <b>{user}</b> has a new story item{m_body_html_pic_saved_text}<br><br>Date: <b>{get_date_from_ts(int(local_ts))}</b><br>Expiry: {get_date_from_ts(int(expire_ts))}<br>Type: {story_type}{story_mentions_m_body_html}{story_hashtags_m_body_html}{story_caption_m_body_html}<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                                print(f"Sending email notification to {RECEIVER_EMAIL}")
                                if m_body_html_pic_saved_text:
                                    send_email(m_subject, m_body, m_body_html, SMTP_SSL, story_image_filename, "story_pic")
                                else:
                                    send_email(m_subject, m_body, m_body_html, SMTP_SSL)

                            print(f"\nCheck interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                            print_cur_ts("Timestamp:\t\t\t\t")

                        break

                    stories_old_count = stories_count

                except Exception as e:
                    error_msg = format_error_message(e)
                    print(f"* Error while processing story items: {error_msg}")
                    print_cur_ts("\nTimestamp:\t\t\t\t")

            new_post = False

            if (posts_count != posts_count_old or reels_count != reels_count_old) and can_view and not skip_getting_posts_details:
                likes = 0
                comments = 0
                caption = ""
                pcaption = ""
                tagged_users = []
                shortcode = ""
                location = None
                likes_users_list = ""
                post_comments_list = ""
                last_post = None
                last_source = "post"
                thumbnail_url = ""
                video_url = ""

                try:
                    if bot.context.is_logged_in:  # GraphQL helper when logged in
                        last_post_reel = latest_post_reel(user, bot)
                    else:  # fallback to mobile helper when anonymous
                        last_post_reel = latest_post_mobile(user, bot)

                    if last_post_reel:
                        last_post, last_source = last_post_reel
                        utc_dt = last_post.date_utc
                        local_dt = convert_utc_datetime_to_tz_datetime(utc_dt)
                        if local_dt:
                            local_ts = int(local_dt.timestamp())
                        else:
                            local_ts = 0

                        if local_ts > highestinsta_ts_old:
                            highestinsta_ts = local_ts
                            highestinsta_dt = local_dt
                            new_post = True

                    if csv_file_name:

                        csv_dt = convert_to_local_naive(highestinsta_dt) if highestinsta_dt else now_local_naive()

                        metrics = [("Posts Count", posts_count, posts_count_old), ("Reels Count", reels_count, reels_count_old)]

                        for label, new, old in metrics:
                            if new != old:
                                # Use csv_dt when it is an increase, now_local_naive() when it is a decrease
                                dt = csv_dt if new > old else now_local_naive()
                                write_csv_entry(csv_file_name, dt, label, old, new)

                    if new_post:

                        if last_post:
                            likes = last_post.likes
                            comments = last_post.comments
                            caption = last_post.caption if last_post.caption is not None else "(empty)"
                            pcaption = last_post.pcaption or ""
                            tagged_users = last_post.tagged_users
                            if last_source == "reel":
                                shortcode = get_real_reel_code(bot, user) or last_post.shortcode
                            else:
                                shortcode = last_post.shortcode
                            thumbnail_url = last_post.url
                            video_url = last_post.video_url
                            if last_source == "post":
                                location = get_post_location_mobile(last_post, bot)
                        else:
                            raise Exception("Failed to get last post/reel details")

                    # Prepare next check timing
                    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
                    next_check = now_local_naive() + timedelta(seconds=r_sleep_time)
                    update_check_times(next_time=next_check, user=user)

                    if stop_event or DEBUG_MODE or WEB_DASHBOARD_ENABLED:
                        if WEB_DASHBOARD_ENABLED:
                            update_web_dashboard_data(targets={user: {'status': 'Waiting'}})
                        sleep_remaining = r_sleep_time
                        while sleep_remaining > 0:
                            if stop_event and stop_event.is_set():
                                break
                            if DEBUG_MODE and check_manual_trigger():
                                reset_thread_output()
                                break
                            time.sleep(min(1, sleep_remaining))
                            sleep_remaining -= min(1, sleep_remaining)
                    else:
                        time.sleep(r_sleep_time)

                except Exception as e:
                    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
                    error_msg = format_error_message(e)
                    print(f"* Error, retrying in {display_time(r_sleep_time)}: {error_msg}")
                    if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                        print("* Session might not be valid anymore!")
                        if ERROR_NOTIFICATION and not email_sent:
                            m_subject = f"instagram_monitor: session error! (session: {session_label()}, target: {user})"

                            m_body = f"Session might not be valid anymore.\n\nSession: {session_label()}\nTarget: {user}\n\nError: {e}{get_cur_ts(nl_ch + nl_ch + 'Timestamp: ')}"
                            print(f"Sending email notification to {RECEIVER_EMAIL}")
                            send_email(m_subject, m_body, "", SMTP_SSL)
                            email_sent = True

                    print_cur_ts("Timestamp:\t\t\t\t")

                    time.sleep(r_sleep_time)
                    continue

                try:
                    if new_post and not skip_session and get_more_post_details and last_post:
                        likes_list = last_post.get_likes()
                        for like in likes_list:
                            likes_users_list += "- " + like.username + " [ " + "https://www.instagram.com/" + like.username + "/ ]\n"
                        comments_list = last_post.get_comments()
                        for comment in comments_list:
                            comment_created_at = convert_utc_datetime_to_tz_datetime(comment.created_at_utc)
                            if comment_created_at:
                                post_comments_list += "\n[ " + get_short_date_from_ts(comment_created_at) + " - " + "https://www.instagram.com/" + comment.owner.username + "/ ]\n" + comment.text + "\n"
                except Exception as e:
                    error_msg = format_error_message(e)
                    print(f"* Error while getting post's likes list / comments list: {error_msg}")

                if new_post:

                    post_url = f"https://www.instagram.com/{'reel' if last_source == 'reel' else 'p'}/{shortcode}/"

                    print(f"* New {last_source.lower()} for user {user} after {calculate_timespan(highestinsta_dt, highestinsta_dt_old)} ({get_date_from_ts(highestinsta_dt_old)})\n")
                    log_activity(f"New {last_source.lower()} detected", user=user)
                    print(f"Date:\t\t\t\t\t{get_date_from_ts(highestinsta_dt)}")
                    print(f"{last_source.capitalize()} URL:\t\t\t\t{post_url}")
                    print(f"Profile URL:\t\t\t\thttps://www.instagram.com/{insta_username}/")
                    print(f"Likes:\t\t\t\t\t{likes}")
                    print(f"Comments:\t\t\t\t{comments}")
                    print(f"Tagged users:\t\t\t\t{tagged_users}")

                    location_mbody = ""
                    location_mbody_str = ""
                    if location:
                        location_mbody = "\nLocation: "
                        location_mbody_str = location
                        print(f"Location:\t\t\t\t{location}")

                    print(f"Description:\n\n{caption}\n")

                    likes_users_list_mbody = ""
                    post_comments_list_mbody = ""

                    if likes_users_list:
                        likes_users_list_mbody = "\nLikes list:\n\n"
                        print(f"Likes list:\n{likes_users_list}")

                    if post_comments_list:
                        post_comments_list_mbody = "\nComments list:\n"
                        print(f"Comments list:{post_comments_list}")

                    if video_url:
                        if highestinsta_dt and highestinsta_dt.timestamp() > 0:
                            video_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
                        else:
                            video_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.mp4'

                        if (user_root_path or OUTPUT_DIR) and 'videos_dir' in locals():
                            if not os.path.dirname(video_filename) == videos_dir:
                                video_filename = os.path.join(videos_dir, video_filename)

                        if not os.path.isfile(video_filename):
                            if save_pic_video(video_url, video_filename, highestinsta_ts):
                                print(f"{last_source.capitalize()} video saved for {user} to '{video_filename}'")
                            else:
                                print(f"Error saving {last_source.lower()} video !")

                    m_body_html_pic_saved_text = ""
                    if highestinsta_dt:
                        image_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                    else:
                        image_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'
                    if thumbnail_url:
                        if not os.path.isfile(image_filename):
                            if save_pic_video(thumbnail_url, image_filename, highestinsta_ts):
                                m_body_html_pic_saved_text = f'<br><br><img src="cid:{last_source.lower()}_pic" width="50%">'
                                print(f"{last_source.capitalize()} thumbnail image saved for {user} to '{image_filename}'")
                                try:
                                    if imgcat_exe:
                                        subprocess.run(f"{imgcat_exe} {image_filename}", shell=True, check=True)
                                except Exception:
                                    pass

                    try:
                        if csv_file_name:
                            write_csv_entry(csv_file_name, convert_to_local_naive(highestinsta_dt), f"New {last_source.capitalize()}", "", pcaption)
                    except Exception as e:
                        print(f"* Error: {e}")

                    if STATUS_NOTIFICATION:
                        m_subject = f"Instagram user {user} has a new {last_source.lower()} - {get_short_date_from_ts(highestinsta_dt)} (after {calculate_timespan(highestinsta_dt, highestinsta_dt_old, show_seconds=False)} - {get_short_date_from_ts(highestinsta_dt_old)})"

                        m_body = f"Instagram user {user} has a new {last_source.lower()} after {calculate_timespan(highestinsta_dt, highestinsta_dt_old)} ({get_date_from_ts(highestinsta_dt_old)})\n\nDate: {get_date_from_ts(highestinsta_dt)}\n{last_source.capitalize()} URL: {post_url}\nProfile URL: https://www.instagram.com/{insta_username}/\nLikes: {likes}\nComments: {comments}\nTagged: {tagged_users}{location_mbody}{location_mbody_str}\nDescription:\n\n{caption}\n{likes_users_list_mbody}{likes_users_list}{post_comments_list_mbody}{post_comments_list}\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user <b>{user}</b> has a new {last_source.lower()} after <b>{calculate_timespan(highestinsta_dt, highestinsta_dt_old)}</b> ({get_date_from_ts(highestinsta_dt_old)}){m_body_html_pic_saved_text}<br><br>Date: <b>{get_date_from_ts(highestinsta_dt)}</b><br>{last_source.capitalize()} URL: <a href=\"{post_url}\">{post_url}</a><br>Profile URL: <a href=\"https://www.instagram.com/{insta_username}/\">https://www.instagram.com/{insta_username}/</a><br>Likes: {likes}<br>Comments: {comments}<br>Tagged: {tagged_users}{location_mbody}{location_mbody_str}<br>Description:<br><br>{escape(str(caption))}<br>{likes_users_list_mbody}{likes_users_list}{post_comments_list_mbody}{escape(post_comments_list)}<br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                        print(f"\nSending email notification to {RECEIVER_EMAIL}")
                        if m_body_html_pic_saved_text:
                            send_email(m_subject, m_body, m_body_html, SMTP_SSL, image_filename, f"{last_source.lower()}_pic")
                        else:
                            send_email(m_subject, m_body, m_body_html, SMTP_SSL)

                    # Send webhook notification for new post/reel
                    emoji = "🎬" if last_source == "reel" else "📸"
                    webhook_fields = [
                        {"name": "Date", "value": get_date_from_ts(highestinsta_dt), "inline": True},
                        {"name": "Likes", "value": str(likes), "inline": True},
                        {"name": "Comments", "value": str(comments), "inline": True},
                        {"name": f"{last_source.capitalize()} URL", "value": post_url},
                    ]
                    if location:
                        webhook_fields.append({"name": "Location", "value": location, "inline": True})
                    if caption:
                        webhook_fields.append({"name": "Description", "value": (caption[:DISCORD_FIELD_VALUE_LIMIT-4] + "...") if len(caption) > DISCORD_FIELD_VALUE_LIMIT else caption})

                    webhook_result = send_webhook(
                        f"{emoji} {user} New {last_source.capitalize()}",
                        f"User **{user}** posted a new {last_source.lower()}!",
                        color=0x1da1f2 if last_source == "post" else 0xff6b6b,  # Blue for post, coral for reel
                        fields=webhook_fields,
                        image_url=thumbnail_url if thumbnail_url else None,
                        notification_type="status"
                    )
                    if webhook_result != 0 and DEBUG_MODE:
                        print(f"* Warning: Webhook notification for new {last_source} failed")

                    posts_count_old = posts_count
                    reels_count_old = reels_count

                    highestinsta_ts_old = highestinsta_ts
                    highestinsta_dt_old = highestinsta_dt

                    print(f"\nCheck interval:\t\t\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                    print_cur_ts("Timestamp:\t\t\t\t")

                elif not new_post and (posts_count != posts_count_old or reels_count != reels_count_old):

                    if check_posts_counts(user, posts_count, posts_count_old, r_sleep_time):
                        posts_count_old = posts_count

                    if check_reels_counts(user, reels_count, reels_count_old, r_sleep_time):
                        reels_count_old = reels_count

            elif (posts_count != posts_count_old or reels_count != reels_count_old) and (not can_view or skip_getting_posts_details):

                if check_posts_counts(user, posts_count, posts_count_old, r_sleep_time):
                    posts_count_old = posts_count

                if check_reels_counts(user, reels_count, reels_count_old, r_sleep_time):
                    reels_count_old = reels_count

        else:
            if HOURS_VERBOSE:
                print(f"*** Skipping Updates. Current Hour: {int(cur_h)}. Allowed hours: {hours_to_check()}")
                print("─" * HORIZONTAL_LINE)

        alive_counter += 1

        if LIVENESS_CHECK_COUNTER and alive_counter >= LIVENESS_CHECK_COUNTER:
            print_cur_ts("Liveness check, timestamp:\t")
            alive_counter = 0

        r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)

        # Update next check time tracking
        update_check_times(next_time=now_local_naive() + timedelta(seconds=r_sleep_time), user=user)

        # Print timing information (includes last check and next check in debug mode)
        if DEBUG_MODE:
            print_check_timing(r_sleep_time)
            debug_print(f"Check #{CHECK_COUNT} completed for user {user}")

        # Be human please
        try:
            if BE_HUMAN and in_allowed_hours:
                simulate_human_actions(bot, r_sleep_time)
        except Exception as e:
            print(f"* Warning: It is not easy to be a human, our simulation failed: {e}")
            print_cur_ts("\nTimestamp:\t\t\t\t")

        if HOURS_VERBOSE:
            sleep_message(r_sleep_time)

        # Sleep with manual check support in debug mode (or stop event support in Web Dashboard mode)
        if DEBUG_MODE or stop_event or WEB_DASHBOARD_ENABLED:
            if WEB_DASHBOARD_ENABLED:
                update_web_dashboard_data(targets={user: {'status': 'Waiting'}})
            # Sleep in smaller increments to allow manual check trigger or stop event
            sleep_remaining = r_sleep_time
            while sleep_remaining > 0:
                # Check for stop event (Web Dashboard mode)
                if stop_event and stop_event.is_set():
                    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                        print(f"* Monitoring stopped for {user}\n")
                        print_cur_ts("Timestamp:\t\t\t\t")
                    return

                # Check for manual trigger
                if MANUAL_CHECK_TRIGGERED.is_set():  # type: ignore
                    MANUAL_CHECK_TRIGGERED.clear()  # type: ignore
                    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                        print(f"* Manual check requested! Breaking sleep early...\n")
                        print_cur_ts("Timestamp:\t\t\t\t")
                    else:
                        debug_print(f"Manual check triggered, {sleep_remaining}s remaining in sleep")
                    break

                # Check for recheck trigger (Web Dashboard mode)
                recheck_triggered = False
                with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
                    if user in WEB_DASHBOARD_RECHECK_EVENTS and WEB_DASHBOARD_RECHECK_EVENTS[user].is_set():
                        WEB_DASHBOARD_RECHECK_EVENTS[user].clear()
                        recheck_triggered = True

                if recheck_triggered:
                    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
                        print(f"* Recheck requested for {user}! Breaking sleep early...\n")
                        print_cur_ts("Timestamp:\t\t\t\t")
                    break

                # Sleep in 1-second increments for responsiveness
                sleep_chunk = min(1, sleep_remaining)
                time.sleep(sleep_chunk)
                sleep_remaining -= sleep_chunk
        else:
            time.sleep(r_sleep_time)


def main():
    global CLI_CONFIG_PATH, DOTENV_FILE, LOCAL_TIMEZONE, LIVENESS_CHECK_COUNTER, SESSION_USERNAME, SESSION_PASSWORD, CSV_FILE, DISABLE_LOGGING, INSTA_LOGFILE, OUTPUT_DIR, STATUS_NOTIFICATION, FOLLOWERS_NOTIFICATION, ERROR_NOTIFICATION, INSTA_CHECK_INTERVAL, DETECT_CHANGED_PROFILE_PIC, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH, imgcat_exe, SKIP_SESSION, SKIP_FOLLOWERS, SKIP_FOLLOWINGS, SKIP_GETTING_STORY_DETAILS, SKIP_GETTING_POSTS_DETAILS, GET_MORE_POST_DETAILS, SMTP_PASSWORD, stdout_bck, PROFILE_PIC_FILE_EMPTY, USER_AGENT, USER_AGENT_MOBILE, BE_HUMAN, ENABLE_JITTER
    global DEBUG_MODE, DASHBOARD_MODE, DASHBOARD_ENABLED, WEB_DASHBOARD_ENABLED, DETAILED_FOLLOWER_LOGGING, WEBHOOK_ENABLED, WEBHOOK_URL, WEBHOOK_STATUS_NOTIFICATION, WEBHOOK_FOLLOWERS_NOTIFICATION, WEBHOOK_ERROR_NOTIFICATION, DASHBOARD_CONSOLE, DASHBOARD_DATA
    global WEB_DASHBOARD_HOST, WEB_DASHBOARD_PORT, WEB_DASHBOARD_TEMPLATE_DIR

    if "--generate-config" in sys.argv:
        print(CONFIG_BLOCK.strip("\n"))
        sys.exit(0)

    if "--version" in sys.argv:
        print(f"{os.path.basename(sys.argv[0])} v{VERSION}")
        sys.exit(0)

    stdout_bck = sys.stdout

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    clear_screen(CLEAR_SCREEN)

    parser = argparse.ArgumentParser(
        prog="instagram_monitor",
        description=("Monitor an Instagram user's activity and send customizable email alerts [ https://github.com/misiektoja/instagram_monitor/ ]"), formatter_class=argparse.RawTextHelpFormatter
    )

    # Positional targets (one or more)
    parser.add_argument(
        "usernames",
        nargs="*",
        metavar="TARGET_USERNAME",
        help="Instagram username(s) to monitor (one or more)",
        type=str
    )

    # Version, just to list in help, it is handled earlier
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s v{VERSION}"
    )

    # Configuration & dotenv files
    conf = parser.add_argument_group("Configuration & dotenv files")
    conf.add_argument(
        "--config-file",
        dest="config_file",
        metavar="PATH",
        help="Location of the optional config file",
    )
    conf.add_argument(
        "--generate-config",
        action="store_true",
        help="Print default config template and exit",
    )
    conf.add_argument(
        "--env-file",
        dest="env_file",
        metavar="PATH",
        help="Path to optional dotenv file (auto-search if not set, disable with 'none')",
    )

    # Session login credentials
    creds = parser.add_argument_group("Session login credentials")
    creds.add_argument(
        "-u", "--session-username",
        dest="session_username",
        metavar="SESSION_USERNAME",
        type=str,
        help="Instagram username for session login (to fetch followers/followings, stories/posts/reels details)"
    )
    creds.add_argument(
        "-p", "--session-password",
        dest="session_password",
        metavar="SESSION_PASSWORD",
        type=str,
        help="Instagram password for session login (recommended to use saved session)"
    )

    # Notifications
    notify = parser.add_argument_group("Notifications")
    notify.add_argument(
        "-s", "--notify-status",
        dest="status_notification",
        action="store_true",
        default=None,
        help="Email on new post/reel/story, bio change, new follow, profile pic or visibility change"
    )
    notify.add_argument(
        "-m", "--notify-followers",
        dest="followers_notification",
        action="store_true",
        default=None,
        help="Email on new followers (disabled by default)"
    )
    notify.add_argument(
        "-e", "--no-error-notify",
        dest="error_notification",
        action="store_false",
        default=None,
        help="Disable email on errors (e.g. invalid session)"
    )
    notify.add_argument(
        "--send-test-email",
        dest="send_test_email",
        action="store_true",
        help="Send test email to verify SMTP settings"
    )

    # Intervals & timers
    times = parser.add_argument_group("Intervals & timers")
    times.add_argument(
        "-c", "--check-interval",
        dest="check_interval",
        metavar="SECONDS",
        type=int,
        help="Time between monitoring checks, in seconds"
    )
    times.add_argument(
        "-i", "--random-diff-low",
        dest="check_interval_random_diff_low",
        metavar="SECONDS",
        type=int,
        help="Subtract up to this value from check-interval"
    )
    times.add_argument(
        "-j", "--random-diff-high",
        dest="check_interval_random_diff_high",
        metavar="SECONDS",
        type=int,
        help="Add up to this value to check-interval"
    )

    # Multi-target monitoring
    multi = parser.add_argument_group("Multi-target monitoring")
    multi.add_argument(
        "--targets",
        dest="targets",
        metavar="USER[,USER...]",
        type=str,
        help="Comma-separated list of target usernames to monitor (alternative to passing multiple positional usernames)"
    )
    multi.add_argument(
        "--targets-stagger",
        dest="targets_stagger",
        metavar="SECONDS",
        type=int,
        default=None,
        help="Seconds to wait between starting each target monitor loop (0 = auto-spread across check-interval)"
    )
    multi.add_argument(
        "--targets-stagger-jitter",
        dest="targets_stagger_jitter",
        metavar="SECONDS",
        type=int,
        default=None,
        help="Random jitter (seconds) added to each target start time"
    )

    # Session‐related options
    session_opts = parser.add_argument_group("Session‐related options")
    session_opts.add_argument(
        "-l", "--skip-session",
        dest="skip_session",
        action="store_true",
        default=None,
        help="Skip session login (no followers/followings or detailed info)"
    )
    session_opts.add_argument(
        "-f", "--skip-followers",
        dest="skip_followers",
        action="store_true",
        default=None,
        help="Do not fetch followers list"
    )
    session_opts.add_argument(
        "-g", "--skip-followings",
        dest="skip_followings",
        action="store_true",
        default=None,
        help="Do not fetch followings list"
    )
    session_opts.add_argument(
        "-r", "--skip-story-details",
        dest="skip_getting_story_details",
        action="store_true",
        default=None,
        help="Do not fetch detailed story info"
    )
    session_opts.add_argument(
        "-w", "--skip-post-details",
        dest="skip_getting_posts_details",
        action="store_true",
        default=None,
        help="Do not fetch detailed post info"
    )
    session_opts.add_argument(
        "-t", "--more-post-details",
        dest="get_more_post_details",
        action="store_true",
        default=None,
        help="Fetch extra post details (list of comments and likes)"
    )
    session_opts.add_argument(
        "--user-agent",
        dest="user_agent",
        metavar="USER_AGENT",
        type=str,
        help="Specify a custom web browser user agent for Instagram API requests; leave empty to auto-generate it"
    )
    session_opts.add_argument(
        "--user-agent-mobile",
        dest="user_agent_mobile",
        metavar="USER_AGENT_MOBILE",
        type=str,
        help="Specify a custom mobile user agent for Instagram API requests; leave empty to auto-generate it"
    )
    session_opts.add_argument(
        "--be-human",
        dest="be_human",
        action="store_true",
        default=None,
        help="Make the tool behave more like a human by performing random feed / profile / hashtag / followee actions"
    )
    session_opts.add_argument(
        "--enable-jitter",
        dest="enable_jitter",
        action="store_true",
        default=None,
        help="Enable human-like HTTP jitter and back-off wrapper"
    )

    # Features & output
    opts = parser.add_argument_group("Features & output")
    opts.add_argument(
        "-k", "--no-profile-pic-detect",
        dest="do_not_detect_changed_profile_pic",
        action="store_false",
        default=None,
        help="Disable detection of changed profile picture"
    )
    opts.add_argument(
        "--detailed-followers",
        dest="detailed_follower_logging",
        action="store_true",
        default=None,
        help="Store detailed follower info (user_id, full_name, profile_pic_url) in JSON files"
    )
    opts.add_argument(
        "-b", "--csv-file",
        dest="csv_file",
        metavar="CSV_FILENAME",
        type=str,
        help="Write all activities and profile changes to CSV file"
    )
    opts.add_argument(
        "-o", "--output-dir",
        dest="output_dir",
        metavar="PATH",
        help="Root directory for saving all generated files (logs, images, videos, json)",
    )
    opts.add_argument(
        "-d", "--disable-logging",
        dest="disable_logging",
        action="store_true",
        default=None,
        help="Disable logging to instagram_monitor_<username>.log"
    )
    opts.add_argument(
        "--debug",
        dest="debug_mode",
        action="store_true",
        default=None,
        help="Enable debug mode (verbose output, manual 'check' command support)"
    )

    # Terminal dashboard options
    term_opts = parser.add_argument_group("Terminal dashboard")
    term_opts.add_argument(
        "--dashboard",
        dest="dashboard",
        action="store_true",
        default=None,
        help="Enable terminal dashboard (live view). Default: traditional text output"
    )
    term_opts.add_argument(
        "--no-dashboard",
        dest="disable_dashboard",
        action="store_true",
        default=None,
        help="Disable terminal dashboard (use traditional text output)"
    )

    # Web dashboard options
    web_opts = parser.add_argument_group("Web dashboard")
    web_opts.add_argument(
        "--web-dashboard",
        dest="web_dashboard",
        action="store_true",
        default=None,
        help="Enable web-based dashboard on localhost (default: disabled)"
    )
    web_opts.add_argument(
        "--no-web-dashboard",
        dest="no_web_dashboard",
        action="store_true",
        default=None,
        help="Disable web-based dashboard"
    )
    web_opts.add_argument(
        "--web-dashboard-port",
        dest="web_dashboard_port",
        metavar="PORT",
        type=int,
        help="Port for web dashboard server (default: 8000)"
    )
    web_opts.add_argument(
        "--web-dashboard-template-dir",
        dest="web_dashboard_template_dir",
        metavar="DIR",
        type=str,
        help="Directory containing web dashboard templates (default: auto-detect)"
    )

    # Webhook options
    webhook_grp = parser.add_argument_group("Webhook notifications")
    webhook_grp.add_argument(
        "--webhook-url",
        dest="webhook_url",
        metavar="URL",
        type=str,
        help="Discord-compatible webhook URL for notifications"
    )
    webhook_grp.add_argument(
        "--webhook-status",
        dest="webhook_status",
        action="store_true",
        default=None,
        help="Send webhook on status changes (posts/reels/stories/bio/profile pic)"
    )
    webhook_grp.add_argument(
        "--webhook-followers",
        dest="webhook_followers",
        action="store_true",
        default=None,
        help="Send webhook on follower changes"
    )
    webhook_grp.add_argument(
        "--webhook-errors",
        dest="webhook_errors",
        action="store_true",
        default=None,
        help="Send webhook on errors"
    )

    # Firefox session import options
    import_grp = parser.add_argument_group("Firefox session import")
    import_grp.add_argument(
        "--import-firefox-session",
        action="store_true",
        help="Import Firefox session cookies into Instaloader"
    )
    import_grp.add_argument(
        "--cookie-file",
        dest="cookie_file",
        metavar="COOKIEFILE",
        help="Path to Firefox cookies.sqlite; if omitted, it will list all available"
    )
    import_grp.add_argument(
        "--session-file",
        dest="session_file",
        metavar="SESSIONFILE",
        help="Path to save Instaloader session; if omitted, it will save to the default one"
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.config_file:
        CLI_CONFIG_PATH = os.path.expanduser(args.config_file)

    cfg_path = find_config_file(CLI_CONFIG_PATH)

    if cfg_path:
        CLI_CONFIG_PATH = cfg_path # Update global for dashboard display

    if not cfg_path and CLI_CONFIG_PATH:
        print(f"* Error: Config file '{CLI_CONFIG_PATH}' does not exist")
        sys.exit(1)

    if cfg_path:
        try:
            with open(cfg_path, "r") as cf:
                exec(cf.read(), globals())
        except Exception as e:
            print(f"* Error loading config file '{cfg_path}': {e}")
            sys.exit(1)

    if args.output_dir:
        OUTPUT_DIR = os.path.expanduser(args.output_dir)

    if args.env_file:
        DOTENV_FILE = os.path.expanduser(args.env_file)
    else:
        if DOTENV_FILE:
            DOTENV_FILE = os.path.expanduser(DOTENV_FILE)

    if DOTENV_FILE and DOTENV_FILE.lower() == 'none':
        env_path = None
    else:
        try:
            from dotenv import load_dotenv, find_dotenv

            if DOTENV_FILE:
                env_path = DOTENV_FILE
                if not os.path.isfile(env_path):
                    print(f"* Warning: dotenv file '{env_path}' does not exist\n")
                else:
                    load_dotenv(env_path, override=True)
            else:
                env_path = find_dotenv() or None
                if env_path:
                    load_dotenv(env_path, override=True)
        except ImportError:
            env_path = DOTENV_FILE if DOTENV_FILE else None
            if env_path:
                print(f"* Warning: Cannot load dotenv file '{env_path}' because 'python-dotenv' is not installed\n\nTo install it, run:\n    pip3 install python-dotenv\n\nOnce installed, re-run this tool\n")

    if env_path:
        for secret in SECRET_KEYS:
            val = os.getenv(secret)
            if val is not None:
                globals()[secret] = val

    if args.import_firefox_session:

        session_path = None
        if args.session_file:
            session_path = os.path.expanduser(args.session_file)
            session_dir = os.path.dirname(session_path) or "."
            if not os.path.isdir(session_dir):
                raise SystemExit(f"Error: Session directory '{session_dir}' not found !")

        cookie_path = args.cookie_file or get_firefox_cookiefile()
        cookie_path = os.path.expanduser(cookie_path)
        if not os.path.isfile(cookie_path):
            raise SystemExit(f"Error: Cookie file '{cookie_path}' not found !")

        import_session(cookie_path, session_path)
        sys.exit(0)

    local_tz = None
    if LOCAL_TIMEZONE == "Auto":
        # Ensure we update the global variable so API sees it
        if get_localzone is not None:
            try:
                local_tz = get_localzone()
            except Exception:
                pass
        if local_tz:
            LOCAL_TIMEZONE = str(local_tz)
        else:
            print("* Error: Cannot detect local timezone, consider setting LOCAL_TIMEZONE to your local timezone manually !")
            sys.exit(1)
    else:
        if not is_valid_timezone(LOCAL_TIMEZONE):
            print(f"* Error: Configured LOCAL_TIMEZONE '{LOCAL_TIMEZONE}' is not valid. Please use a valid pytz timezone name.")
            sys.exit(1)

    if args.user_agent:
        USER_AGENT = args.user_agent

    if not USER_AGENT:
        USER_AGENT = get_random_user_agent()

    if args.user_agent_mobile:
        USER_AGENT_MOBILE = args.user_agent_mobile

    if not USER_AGENT_MOBILE:
        USER_AGENT_MOBILE = get_random_mobile_user_agent()

    if not check_internet():
        sys.exit(1)

    if args.send_test_email:
        print("* Sending test email notification ...\n")
        if send_email("instagram_monitor: test email", "This is test email - your SMTP settings seems to be correct !", "", SMTP_SSL, smtp_timeout=5) == 0:
            print("* Email sent successfully !")
        else:
            sys.exit(1)
        sys.exit(0)

    # Resolve targets: CLI (positional + --targets) > config TARGET_USERNAMES
    targets: List[str] = []
    if getattr(args, "targets", None):
        # Allow commas and whitespace
        for part in re.split(r"[,\s]+", args.targets.strip()):
            if part:
                targets.append(part)
    if getattr(args, "usernames", None):
        targets.extend([u for u in args.usernames if u])

    if not targets and TARGET_USERNAMES:
        targets = list(TARGET_USERNAMES)

    # Normalize + de-duplicate while preserving order
    seen = set()
    normalized: List[str] = []
    for u in targets:
        u = u.strip()
        if not u:
            continue
        if u not in seen:
            seen.add(u)
            normalized.append(u)
    targets = normalized
    DASHBOARD_DATA['targets_list'] = targets


    # Terminal Dashboard handling
    if getattr(args, 'dashboard', None) is True:
        DASHBOARD_ENABLED = True

    if args.disable_dashboard is True:
        DASHBOARD_ENABLED = False

    # Web Dashboard handling
    if args.web_dashboard is True:
        WEB_DASHBOARD_ENABLED = True

    if args.no_web_dashboard is True:
        WEB_DASHBOARD_ENABLED = False

    if args.web_dashboard_port:
        WEB_DASHBOARD_PORT = args.web_dashboard_port

    if args.web_dashboard_template_dir:
        # Resolve to absolute path immediately
        WEB_DASHBOARD_TEMPLATE_DIR = os.path.abspath(os.path.expanduser(args.web_dashboard_template_dir))

    # Allow empty targets if web dashboard is enabled
    if not targets and not WEB_DASHBOARD_ENABLED:
        print("* Error: At least one TARGET_USERNAME argument is required !")
        parser.print_help()
        sys.exit(1)

    if args.skip_session is True:
        SKIP_SESSION = True

    if args.skip_followers is True:
        SKIP_FOLLOWERS = True

    if args.skip_followings is True:
        SKIP_FOLLOWINGS = True

    if args.skip_getting_story_details is True:
        SKIP_GETTING_STORY_DETAILS = True

    if args.skip_getting_posts_details is True:
        SKIP_GETTING_POSTS_DETAILS = True

    if args.get_more_post_details is True:
        GET_MORE_POST_DETAILS = True

    if args.be_human is True:
        BE_HUMAN = True

    if args.enable_jitter is True:
        ENABLE_JITTER = True

    # Handle new debug, dashboard, and webhook arguments
    if args.debug_mode is True:
        DEBUG_MODE = True



    if args.detailed_follower_logging is True:
        DETAILED_FOLLOWER_LOGGING = True

    # Webhook configuration
    if args.webhook_url:
        if not validate_webhook_url(args.webhook_url):
            print(f"* Error: Invalid webhook URL format. Must be HTTPS URL.")
            sys.exit(1)
        WEBHOOK_URL = args.webhook_url
        WEBHOOK_ENABLED = True

    if args.webhook_status is True:
        WEBHOOK_STATUS_NOTIFICATION = True

    if args.webhook_followers is True:
        WEBHOOK_FOLLOWERS_NOTIFICATION = True

    if args.webhook_errors is True:
        WEBHOOK_ERROR_NOTIFICATION = True

    if args.check_interval:
        if args.check_interval <= 0:
            print("* Error: Check interval must be greater than 0")
            sys.exit(1)
        INSTA_CHECK_INTERVAL = args.check_interval

    if args.check_interval_random_diff_low:
        RANDOM_SLEEP_DIFF_LOW = args.check_interval_random_diff_low

    if args.check_interval_random_diff_high:
        RANDOM_SLEEP_DIFF_HIGH = args.check_interval_random_diff_high

    if args.session_username:
        SESSION_USERNAME = args.session_username

    if args.session_password:
        SESSION_PASSWORD = args.session_password

    if not SESSION_USERNAME:
        SKIP_SESSION = True

    # Validate INSTA_CHECK_INTERVAL to prevent division by zero
    if INSTA_CHECK_INTERVAL <= 0:
        print("* Error: INSTA_CHECK_INTERVAL must be greater than 0. Please set it in config file or via -c flag")
        sys.exit(1)

    # Finalize liveness cadence after config/env/CLI have been applied
    recompute_liveness_check_counter()

    if SKIP_SESSION is True:
        SKIP_FOLLOWERS = True
        SKIP_FOLLOWINGS = True
        GET_MORE_POST_DETAILS = False
        SKIP_GETTING_STORY_DETAILS = True
        BE_HUMAN = False
        mode_of_the_tool = "1 (no session login - anonymous)"
    else:
        mode_of_the_tool = "2 (session login)"

    if INSTA_CHECK_INTERVAL <= RANDOM_SLEEP_DIFF_LOW:
        check_interval_low = INSTA_CHECK_INTERVAL
    else:
        check_interval_low = INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW

    if args.do_not_detect_changed_profile_pic is False:
        DETECT_CHANGED_PROFILE_PIC = False

    if PROFILE_PIC_FILE_EMPTY:
        PROFILE_PIC_FILE_EMPTY = os.path.expanduser(PROFILE_PIC_FILE_EMPTY)

    profile_pic_file_exists = os.path.exists(PROFILE_PIC_FILE_EMPTY) if PROFILE_PIC_FILE_EMPTY else False

    if IMGCAT_PATH:
        try:
            imgcat_exe = resolve_executable(IMGCAT_PATH)
        except Exception:
            pass

    # Print version header after arguments are parsed and DASHBOARD_ENABLED is set
    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
        print(f"Instagram Monitoring Tool v{VERSION}\n")

    if args.csv_file:
        CSV_FILE = os.path.expanduser(args.csv_file)
    else:
        if CSV_FILE:
            CSV_FILE = os.path.expanduser(CSV_FILE)

    # CSV per-user handling:
    # - single target: keep existing behavior (use CSV_FILE as-is)
    # - multi target: create one CSV per user based on CSV_FILE prefix, e.g. instagram_data.csv -> instagram_data_user.csv
    csv_files_by_user: dict = {}
    if CSV_FILE and len(targets) == 1:
        try:
            with open(CSV_FILE, 'a', newline='', buffering=1, encoding="utf-8") as _:
                pass
        except Exception as e:
            print(f"* Error, CSV file cannot be opened for writing: {e}")
            sys.exit(1)
        csv_files_by_user[targets[0]] = CSV_FILE
    elif CSV_FILE and len(targets) > 1:
        base_path = Path(CSV_FILE)
        base_suffix = base_path.suffix if base_path.suffix else ".csv"
        for u in targets:
            per_user = str(base_path.with_name(f"{base_path.stem}_{u}{base_suffix}"))
            try:
                with open(per_user, 'a', newline='', buffering=1, encoding="utf-8") as _:
                    pass
            except Exception as e:
                print(f"* Error, CSV file cannot be opened for writing ({u}): {e}")
                sys.exit(1)
            csv_files_by_user[u] = per_user

    if args.disable_logging is True:
        DISABLE_LOGGING = True

    # Decide output log suffix
    if len(targets) == 1:
        log_suffix = targets[0]
    else:
        # Join sorted usernames (human readable, deterministic)
        joined = "_".join(sorted(targets))
        joined = joined.replace(os.sep, "_").replace(" ", "_")
        # Keep filenames at a reasonable length, add a short hash only if we had to truncate
        if len(joined) > 140:
            h = hashlib.md5(joined.encode("utf-8")).hexdigest()[:8]
            joined = joined[:140] + "_" + h
        log_suffix = joined

    if not DISABLE_LOGGING:
        log_path = Path(os.path.expanduser(INSTA_LOGFILE))

        if OUTPUT_DIR:
            out_path = Path(os.path.expanduser(OUTPUT_DIR))
            logs_dir = out_path / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Construct log filename
            if log_path.name:
                log_filename = log_path.name
            else:
                log_filename = "instagram_monitor"

            if not log_filename.endswith(".log"):
                log_filename += ".log"

            # Append suffix if needed
            if log_path.suffix == "":
                log_path = logs_dir / f"{Path(log_filename).stem}_{log_suffix}.log"
            else:
                log_path = logs_dir / f"{Path(log_filename).stem}_{log_suffix}{log_path.suffix}"

        else:
            # Default behavior
            if log_path.parent != Path('.'):
                if log_path.suffix == "":
                    log_path = log_path.parent / f"{log_path.name}_{log_suffix}.log"
            else:
                if log_path.suffix == "":
                    log_path = Path(f"{log_path.name}_{log_suffix}.log")

        log_path.parent.mkdir(parents=True, exist_ok=True)
        FINAL_LOG_PATH = str(log_path)
        sys.stdout = Logger(FINAL_LOG_PATH)
    else:
        FINAL_LOG_PATH = None

    if args.status_notification is True:
        STATUS_NOTIFICATION = True

    if args.followers_notification is True:
        FOLLOWERS_NOTIFICATION = True

    if args.error_notification is False:
        ERROR_NOTIFICATION = False

    if STATUS_NOTIFICATION is False:
        FOLLOWERS_NOTIFICATION = False

    if SMTP_HOST.startswith("your_smtp_server_"):
        STATUS_NOTIFICATION = False
        FOLLOWERS_NOTIFICATION = False
        ERROR_NOTIFICATION = False

    # Only print summary screen if Dashboard is not enabled
    if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
        print(f"* Instagram polling interval:\t\t[ {display_time(check_interval_low)} - {display_time(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH)} ]")
        print(f"* Email notifications:\t\t\t[new posts/reels/stories/followings/bio/profile picture/visibility = {STATUS_NOTIFICATION}]\n*\t\t\t\t\t[followers = {FOLLOWERS_NOTIFICATION}] [errors = {ERROR_NOTIFICATION}]")
        print(f"* Mode of the tool:\t\t\t{mode_of_the_tool}")
        print(f"* Human mode:\t\t\t\t{BE_HUMAN}")
        print(f"* Profile pic changes:\t\t\t{DETECT_CHANGED_PROFILE_PIC}")
        print(f"* Skip session login:\t\t\t{SKIP_SESSION}")
        print(f"* Skip fetching followers:\t\t{SKIP_FOLLOWERS}")
        print(f"* Skip fetching followings:\t\t{SKIP_FOLLOWINGS}")
        print(f"* Skip stories details:\t\t\t{SKIP_GETTING_STORY_DETAILS}")
        print(f"* Skip posts details:\t\t\t{SKIP_GETTING_POSTS_DETAILS}")
        print(f"* Get more posts details:\t\t{GET_MORE_POST_DETAILS}")
        print(f"* Detailed follower logging:\t\t{DETAILED_FOLLOWER_LOGGING}")
        hours_ranges_str = ""
        if CHECK_POSTS_IN_HOURS_RANGE:
            ranges = []
            if not (MIN_H1 == 0 and MAX_H1 == 0):
                ranges.append(f"{MIN_H1:02d}:00 - {MAX_H1:02d}:59")
            if not (MIN_H2 == 0 and MAX_H2 == 0):
                ranges.append(f"{MIN_H2:02d}:00 - {MAX_H2:02d}:59")

            if ranges:
                hours_ranges_str = ", ".join(ranges)
            else:
                hours_ranges_str = "None (both ranges disabled)"
        else:
            hours_ranges_str = "00:00 - 23:59"
        print("* Hours for fetching updates:\t\t" + hours_ranges_str)
        print(f"* Browser user agent:\t\t\t{USER_AGENT}")
        print(f"* Mobile user agent:\t\t\t{USER_AGENT_MOBILE}")
        print(f"* HTTP jitter/back-off:\t\t\t{ENABLE_JITTER}")
        print(f"* Liveness check:\t\t\t{bool(LIVENESS_CHECK_INTERVAL)}" + (f" ({display_time(LIVENESS_CHECK_INTERVAL)})" if LIVENESS_CHECK_INTERVAL else ""))
        if len(targets) == 1:
            print(f"* CSV logging enabled:\t\t\t{bool(CSV_FILE)}" + (f" ({CSV_FILE})" if CSV_FILE else ""))
        else:
            if CSV_FILE:
                print(f"* CSV logging enabled:\t\t\tTrue (per-user files, base: {CSV_FILE})")
            else:
                print(f"* CSV logging enabled:\t\t\tFalse")
        print(f"* Display profile pics:\t\t\t{bool(imgcat_exe)}" + (f" (via {imgcat_exe})" if imgcat_exe else ""))
        print(f"* Empty profile pic template:\t\t{profile_pic_file_exists}" + (f" ({PROFILE_PIC_FILE_EMPTY})" if profile_pic_file_exists else ""))
        # Dashboard status
        dashboard_status = DASHBOARD_ENABLED and RICH_AVAILABLE
        dashboard_reason = ""
        if not dashboard_status:
            if not RICH_AVAILABLE:
                dashboard_reason = " (missing rich)"
            elif not DASHBOARD_ENABLED:
                dashboard_reason = " (disabled)"
        print(f"* Dashboard:\t\t\t\t{dashboard_status}{dashboard_reason}")
        # Web Dashboard status
        web_dashboard_status = WEB_DASHBOARD_ENABLED and FLASK_AVAILABLE
        web_dashboard_reason = ""
        if not web_dashboard_status:
            if not WEB_DASHBOARD_ENABLED:
                web_dashboard_reason = " (disabled)"
            elif not FLASK_AVAILABLE:
                web_dashboard_reason = " (missing Flask)"
        print(f"* Web Dashboard:\t\t\t{web_dashboard_status}{web_dashboard_reason}")
        print(f"* Output logging enabled:\t\t{not DISABLE_LOGGING}" + (f" ({FINAL_LOG_PATH})" if not DISABLE_LOGGING else ""))
        print(f"* Configuration file:\t\t\t{cfg_path}")
        print(f"* Dotenv file:\t\t\t\t{env_path or 'None'}")
        if WEB_DASHBOARD_ENABLED:
            print(f"* Web Dashboard templates:\t\t{WEB_DASHBOARD_TEMPLATE_DIR or 'Auto-detect'}")
        if OUTPUT_DIR:
            output_dir_desc = "(root for user data & logs)" if len(targets) == 1 else "(container for per-user subdirectories & logs)"
            print(f"* Output directory:\t\t\t{OUTPUT_DIR} {output_dir_desc}")
        print(f"* Webhook notifications:\t\t{WEBHOOK_ENABLED}" + (f" ({WEBHOOK_URL[:50]}...)" if WEBHOOK_ENABLED and WEBHOOK_URL and len(WEBHOOK_URL) > 50 else (f" ({WEBHOOK_URL})" if WEBHOOK_ENABLED and WEBHOOK_URL else "")))
        if WEBHOOK_ENABLED:
            print(f"*   Webhook status:\t\t\t{WEBHOOK_STATUS_NOTIFICATION}")
            print(f"*   Webhook followers:\t\t\t{WEBHOOK_FOLLOWERS_NOTIFICATION}")
            print(f"*   Webhook errors:\t\t\t{WEBHOOK_ERROR_NOTIFICATION}")
        print(f"* Debug mode:\t\t\t\t{DEBUG_MODE}")

        print(f"* Local timezone:\t\t\t{LOCAL_TIMEZONE}")

        # More visible warnings if requested features are missing
        if DASHBOARD_ENABLED and not RICH_AVAILABLE:
            print("\n" + "*" * HORIZONTAL_LINE)
            print("* WARNING: Terminal Dashboard is enabled, but 'rich' library is missing!")
            print("* To fix this, please run: pip install rich")
            print("* Reverting to original text console...")
            print("*" * HORIZONTAL_LINE)
            DASHBOARD_ENABLED = False

        if WEB_DASHBOARD_ENABLED and not FLASK_AVAILABLE:
            print("\n" + "*" * HORIZONTAL_LINE)
            print("* WARNING: Web Dashboard is enabled, but 'Flask' library is missing!")
            print("* To fix this, please run: pip install flask")
            print("* Web Dashboard will NOT be available!")
            print("*" * HORIZONTAL_LINE)

    # Initialize Rich console if available and enabled (can work alongside web dashboard)
    if (RICH_AVAILABLE and DASHBOARD_ENABLED) or WEB_DASHBOARD_ENABLED:
        if DEBUG_MODE:
            print("\n* Initializing dashboard data...")

        # Initial config data population for dashboard
        DASHBOARD_DATA['config'] = get_dashboard_config_data(
            final_log_path=FINAL_LOG_PATH,
            imgcat_exe=imgcat_exe,
            profile_pic_file_exists=profile_pic_file_exists,
            cfg_path=cfg_path,
            env_path=env_path,
            check_interval_low=check_interval_low,
            mode_of_the_tool=mode_of_the_tool,
            targets=targets
        )
        DASHBOARD_DATA['targets_list'] = targets

    if RICH_AVAILABLE and DASHBOARD_ENABLED:  # type: ignore[name-defined]
        assert Console is not None
        DASHBOARD_CONSOLE = Console(file=stdout_bck)
        DASHBOARD_DATA['start_time'] = datetime.now()
        DASHBOARD_DATA['dashboard_mode'] = DASHBOARD_MODE

    # Start web dashboard server if enabled (before monitoring starts to avoid message interleaving)
    if WEB_DASHBOARD_ENABLED:  # type: ignore[name-defined]
        WEB_DASHBOARD_DATA['start_time'] = datetime.now()
        WEB_DASHBOARD_DATA['dashboard_mode'] = DASHBOARD_MODE

        # Pre-populate web dashboard targets from CLI targets
        with WEB_DASHBOARD_DATA_LOCK:  # type: ignore
            for u in targets:
                if u not in WEB_DASHBOARD_DATA['targets']:
                    WEB_DASHBOARD_DATA['targets'][u] = {
                        'followers': None,
                        'following': None,
                        'posts': None,
                        'status': 'Starting',
                        'added': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'last_checked': None
                    }

        start_web_dashboard_server()

    # Start Dashboard input handler for mode toggle (and debug commands if debug mode)
    # Works for both Dashboard and Web Dashboard
    start_dashboard_input_handler()

    # Initialize Dashboard Live display if enabled
    if RICH_AVAILABLE and DASHBOARD_ENABLED and DASHBOARD_CONSOLE is not None:
        init_dashboard()
        # Show initial Dashboard immediately
        update_dashboard()

    # We define signal handlers only for Linux, Unix & MacOS since Windows has limited number of signals supported
    if platform.system() != 'Windows':
        signal.signal(signal.SIGUSR1, toggle_status_changes_notifications_signal_handler)
        signal.signal(signal.SIGUSR2, toggle_followers_notifications_signal_handler)
        signal.signal(signal.SIGTRAP, increase_check_signal_handler)
        signal.signal(signal.SIGABRT, decrease_check_signal_handler)
        signal.signal(signal.SIGHUP, reload_secrets_signal_handler)

    # Print monitoring message after all setup is complete
    # Note: If Dashboard is enabled, this will be shown in the dashboard instead
    if not (RICH_AVAILABLE and DASHBOARD_ENABLED) and targets:
        if len(targets) == 1:
            out = f"\nMonitoring Instagram user {targets[0]}"
        else:
            out = f"\nMonitoring Instagram users ({len(targets)}): {', '.join(targets)}"
        print(out)
        print("─" * len(out))

    # Multi-target mode: run multiple monitors in one process, with configurable staggering
    if len(targets) == 0:
        print("\n" + "═" * 80)
        print("     INSTAGRAM MONITOR - WEB DASHBOARD MODE")
        print("═" * 80)
        print(f"\n* Status: Waiting for targets...")
        print(f"* Web UI: http://{WEB_DASHBOARD_HOST}:{WEB_DASHBOARD_PORT}/")
        print("\n* Info: No initial targets specified on command line.")
        print("  Please open the Web UI above to manually add Instagram users for monitoring.")
        print("  You can also configure sessions and settings directly from the dashboard.")
        print("\n" + "─" * 80)
        print("Press Ctrl+C to exit\n")

        # We need to keep the main thread alive.
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # Cleanly stop any monitors started via Web UI
            for u in list(WEB_DASHBOARD_STOP_EVENTS.keys()):
                stop_monitoring_for_target(u)
            sys.exit(0)
    elif len(targets) == 1:
        # Integrated Mode Stop Event registration
        stop_event = threading.Event()
        if WEB_DASHBOARD_ENABLED:
            WEB_DASHBOARD_STOP_EVENTS[targets[0]] = stop_event

        instagram_monitor_user(targets[0], csv_files_by_user.get(targets[0], CSV_FILE), SKIP_SESSION, SKIP_FOLLOWERS, SKIP_FOLLOWINGS, SKIP_GETTING_STORY_DETAILS, SKIP_GETTING_POSTS_DETAILS, GET_MORE_POST_DETAILS, user_root_path=OUTPUT_DIR, stop_event=stop_event)
    else:
        stagger = args.targets_stagger if args.targets_stagger is not None else MULTI_TARGET_STAGGER
        jitter = args.targets_stagger_jitter if args.targets_stagger_jitter is not None else MULTI_TARGET_STAGGER_JITTER

        if stagger is None:
            stagger = 0
        if jitter is None:
            jitter = 0

        if stagger < 0 or jitter < 0:
            print("* Error: --targets-stagger and --targets-stagger-jitter must be >= 0")
            sys.exit(1)

        # Auto-spread across the base interval
        if stagger == 0:
            stagger = max(1, int(INSTA_CHECK_INTERVAL / max(1, len(targets))))

        now = now_local_naive()
        if not (DASHBOARD_ENABLED and RICH_AVAILABLE):
            print(f"* Multi-target staggering:\t\t{display_time(stagger)} between targets (jitter: {display_time(jitter)})")
            print("* Planned first poll times:")
            for idx, u in enumerate(targets):
                base_delay = idx * stagger
                add_jitter = int(random.uniform(0, jitter)) if jitter else 0
                delay = base_delay + add_jitter
                planned = now + timedelta(seconds=delay)
                print(f"  - {u} @ ~{planned.strftime('%H:%M:%S')} (in {display_time(delay)})")

            print("─" * HORIZONTAL_LINE)

        # Create events to coordinate initial loading between users.
        # We create N+1 events: event[i] means "user i finished initial load".
        # User i waits on event[i] and signals event[i+1].
        loading_events = [threading.Event() for _ in range(len(targets) + 1)]
        loading_events[0].set()  # allow the first user to start immediately

        def _runner(u: str, delay_s: int, idx: int, stop_event: Optional[threading.Event] = None):
            try:
                if delay_s > 0:
                    time.sleep(delay_s)
                # Wait for previous user's loading to complete
                wait_event = loading_events[idx]
                # Signal when this user's loading is complete
                signal_event = loading_events[idx + 1]

                user_root = None
                if OUTPUT_DIR:
                    if len(targets) == 1:
                        user_root = OUTPUT_DIR
                    else:
                        user_root = os.path.join(OUTPUT_DIR, u)

                instagram_monitor_user(
                    u,
                    csv_files_by_user.get(u, ""),
                    SKIP_SESSION,
                    SKIP_FOLLOWERS,
                    SKIP_FOLLOWINGS,
                    SKIP_GETTING_STORY_DETAILS,
                    SKIP_GETTING_POSTS_DETAILS,
                    GET_MORE_POST_DETAILS,
                    wait_for_prev_user=wait_event,
                    signal_loading_complete=signal_event,
                    user_root_path=user_root,
                    stop_event=stop_event
                )
            except Exception as e:
                # Surface thread exceptions so the user sees them
                error_msg = format_error_message(e)
                print(f"* Error in target '{u}': {error_msg}")
                traceback.print_exc()
                # Still signal completion even on error, so next user can proceed
                loading_events[idx + 1].set()

        threads = []
        for idx, u in enumerate(targets):
            base_delay = idx * stagger
            add_jitter = int(random.uniform(0, jitter)) if jitter else 0
            delay = base_delay + add_jitter
            stop_event = threading.Event()
            if WEB_DASHBOARD_ENABLED:
                WEB_DASHBOARD_STOP_EVENTS[u] = stop_event

            t = threading.Thread(target=_runner, args=(u, delay, idx, stop_event), name=f"instagram_monitor:{u}", daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    if WEB_DASHBOARD_ENABLED:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # Cleanly stop any monitors started via Web UI
            for u in list(WEB_DASHBOARD_STOP_EVENTS.keys()):
                stop_monitoring_for_target(u)
            sys.exit(0)

    sys.stdout = stdout_bck
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C (though main() handles this mostly)
        if DASHBOARD_LIVE:
            DASHBOARD_LIVE.stop()
        sys.exit(0)
    except Exception as e:
        # Critical error handling
        error_trace = traceback.format_exc()

        # Stop Terminal Dashboard so we can see the error
        if DASHBOARD_LIVE:
            DASHBOARD_LIVE.stop()

        # Force restore stdout/stderr to ensure visibility (bypassing Logger suppression)
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        # Print error to console
        print("\n" + "*" * 80)
        print("CRITICAL ERROR ENCOUNTERED")
        print("*" * 80)
        print(f"\n{error_trace}")
        print("*" * 80 + "\n")

        # Propagate to Web Dashboard if enabled
        if WEB_DASHBOARD_ENABLED:
            with WEB_DASHBOARD_DATA_LOCK: # type: ignore
                WEB_DASHBOARD_DATA['error'] = {
                    'message': str(e),
                    'traceback': error_trace,
                    'timestamp': time.time()
                }

            print("The Web Dashboard may have disconnected due to this error.")

        sys.exit(1)
