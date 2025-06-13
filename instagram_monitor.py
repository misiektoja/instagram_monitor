#!/usr/bin/env python3
"""
Author: Michal Szymanski <misiektoja-github@rm-rf.ninja>
v1.7

OSINT tool implementing real-time tracking of Instagram users activities and profile changes:
https://github.com/misiektoja/instagram_monitor/

Python pip3 requirements:

instaloader
requests
python-dateutil
pytz
tzlocal (optional)
python-dotenv (optional)
"""

VERSION = "1.7"

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

# Limit checking for new posts/reels to specific hours of the day?
# If True, the tool will only check within the defined hour ranges below
CHECK_POSTS_IN_HOURS_RANGE = False

# First range of hours to check (if CHECK_POSTS_IN_HOURS_RANGE is True)
# Example: check from 00:00 to 04:59
MIN_H1 = 0
MAX_H1 = 4

# Second range of hours to check
# Example: check from 11:00 to 23:59
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

# Whether to disable logging to instagram_monitor_<username>.log
# Can also be disabled via the -d flag
DISABLE_LOGGING = False

# Width of horizontal line
HORIZONTAL_LINE = 113

# Whether to clear the terminal screen after starting the tool
CLEAR_SCREEN = True

# Value used by signal handlers to increase/decrease user activity check interval (INSTA_CHECK_INTERVAL); in seconds
INSTA_CHECK_SIGNAL_VALUE = 300  # 5 min
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
DISABLE_LOGGING = False
HORIZONTAL_LINE = 0
CLEAR_SCREEN = False
INSTA_CHECK_SIGNAL_VALUE = 0

exec(CONFIG_BLOCK, globals())

# Default name for the optional config file
DEFAULT_CONFIG_FILENAME = "instagram_monitor.conf"

# List of secret keys to load from env/config
SECRET_KEYS = ("SESSION_PASSWORD", "SMTP_PASSWORD")

# Default value for network-related timeouts in functions
FUNCTION_TIMEOUT = 15

LIVENESS_CHECK_COUNTER = LIVENESS_CHECK_INTERVAL / INSTA_CHECK_INTERVAL

stdout_bck = None
last_output = []
csvfieldnames = ['Date', 'Type', 'Old', 'New']

imgcat_exe = ""

CLI_CONFIG_PATH = None

# To solve the issue: 'SyntaxError: f-string expression part cannot include a backslash'
nl_ch = "\n"


import sys

if sys.version_info < (3, 9):
    print("* Error: Python version 3.9 or higher required !")
    sys.exit(1)

import time
import string
import json
import os
from os.path import expanduser, dirname, basename
from datetime import datetime, timezone
from dateutil import relativedelta
from dateutil.parser import isoparse, parse
import calendar
import requests as req
import shutil
import signal
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

try:
    import instaloader
    from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
    raise SystemExit("Error: Couldn't find the instaloader library !\n\nTo install it, run:\n    pip3 install instaloader\n\nOnce installed, re-run this tool. For more help, visit:\nhttps://instaloader.github.io/")

from instaloader.exceptions import PrivateProfileNotFollowedException
from html import escape
from itertools import islice
from typing import Optional, Tuple, Any, Callable
from glob import glob
import sqlite3
from sqlite3 import OperationalError, connect
from pathlib import Path
from functools import wraps


# Logger class to output messages to stdout and log file
class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.logfile = open(filename, "a", buffering=1, encoding="utf-8")

    def write(self, message):
        global last_output
        if message != '\n':
            last_output.append(message)
        self.terminal.write(message)
        self.logfile.write(message)
        self.terminal.flush()
        self.logfile.flush()

    def flush(self):
        pass


# Signal handler when user presses Ctrl+C
def signal_handler(sig, frame):
    sys.stdout = stdout_bck
    print('\n* You pressed Ctrl+C, tool is terminated.')
    sys.exit(0)


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
def convert_to_local_naive(dt: datetime | None = None):
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
    return (f'{ts_str}{calendar.day_abbr[(now_local_naive()).weekday()]}, {now_local_naive().strftime("%d %b %Y, %H:%M:%S")}')


# Prints the current date/time in human readable format with separator; eg. Sun 21 Apr 2024, 15:08:45
def print_cur_ts(ts_str=""):
    print(get_cur_ts(str(ts_str)))
    print("─" * HORIZONTAL_LINE)


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
    return ts_new.strftime(out_strf)


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
    print_cur_ts("Timestamp:\t\t")


# Signal handler for SIGUSR2 allowing to switch email notifications for new followers
def toggle_followers_notifications_signal_handler(sig, frame):
    global FOLLOWERS_NOTIFICATION
    FOLLOWERS_NOTIFICATION = not FOLLOWERS_NOTIFICATION
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Email notifications: [followers = {FOLLOWERS_NOTIFICATION}]")
    print_cur_ts("Timestamp:\t\t")


# Signal handler for SIGTRAP allowing to increase check timer by INSTA_CHECK_SIGNAL_VALUE seconds
def increase_check_signal_handler(sig, frame):
    global INSTA_CHECK_INTERVAL
    INSTA_CHECK_INTERVAL = INSTA_CHECK_INTERVAL + INSTA_CHECK_SIGNAL_VALUE
    if INSTA_CHECK_INTERVAL <= RANDOM_SLEEP_DIFF_LOW:
        check_interval_low = INSTA_CHECK_INTERVAL
    else:
        check_interval_low = INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Instagram timers: [check interval: {display_time(check_interval_low)} - {display_time(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH)}]")
    print_cur_ts("Timestamp:\t\t")


# Signal handler for SIGABRT allowing to decrease check timer by INSTA_CHECK_SIGNAL_VALUE seconds
def decrease_check_signal_handler(sig, frame):
    global INSTA_CHECK_INTERVAL
    if (INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW - INSTA_CHECK_SIGNAL_VALUE) > 0:
        INSTA_CHECK_INTERVAL = INSTA_CHECK_INTERVAL - INSTA_CHECK_SIGNAL_VALUE
    if INSTA_CHECK_INTERVAL <= RANDOM_SLEEP_DIFF_LOW:
        check_interval_low = INSTA_CHECK_INTERVAL
    else:
        check_interval_low = INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Instagram timers: [check interval: {display_time(check_interval_low)} - {display_time(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH)}]")
    print_cur_ts("Timestamp:\t\t")


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

    print_cur_ts("Timestamp:\t\t")


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
    if not os.path.isfile(file1) or not os.path.isfile(file1):
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
            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")
        else:
            print_cur_ts("\nTimestamp:\t\t")

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
                    csv_text = "Profile Picture Removed"

                    if send_email_notification:
                        m_subject = f"Instagram user {user} has removed profile picture ! (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)})"

                        m_body = f"Instagram user {user} has removed profile picture added on {profile_pic_mdate} (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)})\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user {user} has removed profile picture added on <b>{profile_pic_mdate}</b> (after {calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False, granularity=2)})<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                # User has set profile picture
                elif is_empty_profile_pic and not is_empty_profile_pic_tmp:
                    print(f"* User {user} has set profile picture !")
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
                    print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                    print_cur_ts("Timestamp:\t\t")

            else:
                if func_ver == 1:
                    if is_empty_profile_pic:
                        print(f"* User {user} does not have profile picture set")
                    else:
                        print(f"* Profile picture '{profile_pic_file}' already exists")
                        print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_mdate_dt, True)} ({calculate_timespan(now_local(), profile_pic_mdate_dt, show_seconds=False)} ago)")
                        try:
                            if imgcat_exe:
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
                print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t")
        if func_ver == 1:
            print_cur_ts("\nTimestamp:\t\t")


# Return the most recent post and/or reel for the user
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

        print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
        print_cur_ts("Timestamp:\t\t")
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

        print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
        print_cur_ts("Timestamp:\t\t")
        return 1
    else:
        return 0


# Returns the tagged location name of the post, we use mobile API JSON call since last_post.location does not work anymore
def get_post_location_mobile(last_post: instaloader.Post, bot: instaloader.Instaloader) -> Optional[str]:

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
        raise SystemExit("No Firefox cookies.sqlite file found, use -c COOKIEFILE flag")

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
        conn = connect(f"file:{cookiefile}?immutable=1", uri=True)

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

    candidates = [
        Path.cwd() / DEFAULT_CONFIG_FILENAME,
        Path.home() / f".{DEFAULT_CONFIG_FILENAME}",
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


# Monkey-patches Instagram request to add human-like jitter and back-off
def instagram_wrap_request(orig_request):
    @wraps(orig_request)
    def wrapper(*args, **kwargs):
        method = kwargs.get("method") or (args[1] if len(args) > 1 else None)
        url = kwargs.get("url") or (args[2] if len(args) > 2 else None)
        if JITTER_VERBOSE:
            print(f"[WRAP-REQ] {method} {url}")
        time.sleep(random.uniform(0.8, 3.0))

        attempt = 0
        backoff = 60
        while True:
            resp = orig_request(*args, **kwargs)
            if resp.status_code in (429, 400) and "checkpoint" in resp.text:
                attempt += 1
                if attempt > 3:
                    raise instaloader.exceptions.QueryReturnedNotFoundException(
                        "Giving up after multiple 429/checkpoint"
                    )
                wait = backoff + random.uniform(0, 30)
                if JITTER_VERBOSE:
                    print(f"* Back-off {wait:.0f}s after {resp.status_code}")
                time.sleep(wait)
                backoff *= 2
                continue
            return resp
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
        time.sleep(random.uniform(0.8, 3.0))
        return orig_send(*args, **kwargs)
    return wrapper


# Returns probability of executing one human action for cycle
def probability_for_cycle(sleep_seconds: int) -> float:
    return min(1.0, DAILY_HUMAN_HITS * sleep_seconds / 86_400)  # 86400 s = 1 day


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
        print_cur_ts("\nTimestamp:\t\t")


# Monitors activity of the specified Instagram user
def instagram_monitor_user(user, csv_file_name, skip_session, skip_followers, skip_followings, skip_getting_story_details, skip_getting_posts_details, get_more_post_details):

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
        if ENABLE_JITTER:
            req.Session.request = instagram_wrap_request(req.Session.request)
            req.Session.send = instagram_wrap_send(req.Session.send)

        bot = instaloader.Instaloader(user_agent=USER_AGENT, iphone_support=True, quiet=True)

        ctx = bot.context

        orig_request = ctx._session.request

        session = ctx._session

        if not skip_session and SESSION_USERNAME:
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
                    sys.exit(1)

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

        print("Sneaking into Instagram like a ninja ... (be patient, secrets take time)")

        profile = instaloader.Profile.from_username(bot.context, user)
        time.sleep(NEXT_OPERATION_DELAY)
        insta_username = profile.username
        insta_userid = profile.userid
        followers_count = profile.followers
        followings_count = profile.followees
        bio = profile.biography
        is_private = profile.is_private
        followed_by_viewer = profile.followed_by_viewer
        can_view = (not is_private) or followed_by_viewer
        posts_count = profile.mediacount
        if not skip_session and can_view:
            reels_count = get_total_reels_count(user, bot, skip_session)

        if not is_private:
            has_story = profile.has_public_story
        elif bot.context.is_logged_in and followed_by_viewer:
            story = next(bot.get_stories(userids=[insta_userid]), None)
            has_story = bool(story and story.itemcount)
        else:
            has_story = False

        profile_image_url = profile.profile_pic_url_no_iphone

        if bot.context.is_logged_in:
            me = instaloader.Profile.own_profile(bot.context)
            session_username = me.username
        else:
            session_username = None

    except Exception as e:
        print(f"* Error: {type(e).__name__}: {e}")
        sys.exit(1)

    story_flag = False

    followers_old_count = followers_count
    followings_old_count = followings_count
    bio_old = bio
    posts_count_old = posts_count
    reels_count_old = reels_count
    is_private_old = is_private
    followed_by_viewer_old = followed_by_viewer

    print(f"\nSession user:\t\t{session_username or '<anonymous>'}")

    print(f"\nUsername:\t\t{insta_username}")
    print(f"User ID:\t\t{insta_userid}")
    print(f"URL:\t\t\thttps://www.instagram.com/{insta_username}/")

    print(f"\nProfile:\t\t{'public' if not is_private else 'private'}")
    print(f"Can view all contents:\t{'Yes' if can_view else 'No'}")

    print(f"\nPosts:\t\t\t{posts_count}")
    if not skip_session and can_view:
        print(f"Reels:\t\t\t{reels_count}")

    print(f"\nFollowers:\t\t{followers_count}")
    print(f"Followings:\t\t{followings_count}")

    print(f"\nStory available:\t{has_story}")

    print(f"\nBio:\n\n{bio}\n")
    print_cur_ts("Timestamp:\t\t")

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
            print(f"* Followers ({followers_old_count}) loaded from file '{insta_followers_file}' ({get_short_date_from_ts(followers_mdate, show_weekday=False, always_show_year=True)})")
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

    if ((followers_count != followers_old_count) or (followers_count > 0 and not followers)) and not skip_session and not skip_followers and can_view:
        print("\n* Getting followers ...")
        followers_followings_fetched = True

        followers = [follower.username for follower in profile.get_followers()]
        followers_count = profile.followers

        if not followers and followers_count > 0:
            print("* Empty followers list returned, not saved to file")
        else:
            followers_to_save = []
            followers_to_save.append(followers_count)
            followers_to_save.append(followers)
            try:
                with open(insta_followers_file, 'w', encoding="utf-8") as f:
                    json.dump(followers_to_save, f, indent=2)
                    print(f"* Followers saved to file '{insta_followers_file}'")
            except Exception as e:
                print(f"* Cannot save list of followers to '{insta_followers_file}' file: {e}")

    if ((followers_count != followers_old_count) and (followers != followers_old)) and not skip_session and not skip_followers and can_view and ((followers and followers_count > 0) or (not followers and followers_count == 0)):
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
            print(f"\n* Followings ({followings_old_count}) loaded from file '{insta_followings_file}' ({get_short_date_from_ts(following_mdate, show_weekday=False, always_show_year=True)})")
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

    if ((followings_count != followings_old_count) or (followings_count > 0 and not followings)) and not skip_session and not skip_followings and can_view:
        print("\n* Getting followings ...")
        followers_followings_fetched = True

        followings = [followee.username for followee in profile.get_followees()]
        followings_count = profile.followees

        if not followings and followings_count > 0:
            print("* Empty followings list returned, not saved to file")
        else:
            followings_to_save = []
            followings_to_save.append(followings_count)
            followings_to_save.append(followings)
            try:
                with open(insta_followings_file, 'w', encoding="utf-8") as f:
                    json.dump(followings_to_save, f, indent=2)
                    print(f"* Followings saved to file '{insta_followings_file}'")
            except Exception as e:
                print(f"* Cannot save list of followings to '{insta_followings_file}' file: {e}")

    if ((followings_count != followings_old_count) and (followings != followings_old)) and not skip_session and not skip_followings and can_view and ((followings and followings_count > 0) or (not followings and followings_count == 0)):
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
        print_cur_ts("\nTimestamp:\t\t")

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

                        print(f"Date:\t\t\t{get_date_from_ts(local_dt)}")
                        print(f"Expiry:\t\t\t{get_date_from_ts(expire_local_dt)}")
                        if story_item.typename == "GraphStoryImage":
                            story_type = "Image"
                        else:
                            story_type = "Video"
                        print(f"Type:\t\t\t{story_type}")

                        story_mentions = story_item.caption_mentions
                        story_hashtags = story_item.caption_hashtags

                        if story_mentions:
                            print(f"Mentions:\t\t{story_mentions}")

                        if story_hashtags:
                            print(f"Hashtags:\t\t{story_hashtags}")

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
                            if not os.path.isfile(story_video_filename):
                                if save_pic_video(story_video_url, story_video_filename, local_ts):
                                    print(f"Story video saved to '{story_video_filename}'")

                        if story_thumbnail_url:
                            if local_dt:
                                story_image_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                            else:
                                story_image_filename = f'instagram_{user}_story_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'
                            if not os.path.isfile(story_image_filename):
                                if save_pic_video(story_thumbnail_url, story_image_filename, local_ts):
                                    print(f"Story thumbnail image saved to '{story_image_filename}'")
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

                        if i == stories_count:
                            print_cur_ts("\nTimestamp:\t\t")
                        else:
                            print("─" * HORIZONTAL_LINE)

                    break

                stories_old_count = stories_count

            except Exception as e:
                print(f"* Error: {e}")
                sys.exit(1)

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
        print("Fetching user's latest post/reel ...\n")
        try:

            time.sleep(NEXT_OPERATION_DELAY)
            last_post_reel = latest_post_reel(user, bot)

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
            print(f"* Error: {e}")
            sys.exit(1)

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
            print(f"* Error: Failed to get post's likes list / comments list: {e}")

        post_url = f"https://www.instagram.com/{'reel' if last_source == 'reel' else 'p'}/{shortcode}/"
        print(f"* Newest {last_source.lower()} for user {user}:\n")
        print(f"Date:\t\t\t{get_date_from_ts(highestinsta_dt)} ({calculate_timespan(now_local(), highestinsta_dt)} ago)")
        print(f"{last_source.capitalize()} URL:\t\t{post_url}")
        print(f"Profile URL:\t\thttps://www.instagram.com/{insta_username}/")
        print(f"Likes:\t\t\t{likes}")
        print(f"Comments:\t\t{comments}")
        print(f"Tagged users:\t\t{tagged_users}")

        if location:
            print(f"Location:\t\t{location}")

        print(f"Description:\n\n{caption}\n")

        if likes_users_list:
            print(f"Likes list:\n{likes_users_list}")

        if post_comments_list:
            print(f"Comments list:{post_comments_list}")

        if video_url:
            if highestinsta_dt:
                video_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
            else:
                video_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.mp4'
            if not os.path.isfile(video_filename):
                if save_pic_video(video_url, video_filename, highestinsta_ts):
                    print(f"{last_source.capitalize()} video saved to '{video_filename}'")

        if thumbnail_url:
            if highestinsta_dt:
                image_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
            else:
                image_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'
            if not os.path.isfile(image_filename):
                if save_pic_video(thumbnail_url, image_filename, highestinsta_ts):
                    print(f"{last_source.capitalize()} thumbnail image saved to '{image_filename}'")
            if os.path.isfile(image_filename):
                try:
                    if imgcat_exe:
                        subprocess.run(f"{imgcat_exe} {image_filename}", shell=True, check=True)
                except Exception:
                    pass

        print_cur_ts("\nTimestamp:\t\t")

        highestinsta_ts_old = highestinsta_ts
        highestinsta_dt_old = highestinsta_dt

    else:
        highestinsta_ts_old = int(time.time())
        highestinsta_dt_old = now_local()

    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
    time.sleep(r_sleep_time)

    alive_counter = 0

    email_sent = False

    # Primary loop
    while True:
        last_output = []
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
            if not skip_session and can_view:
                reels_count = get_total_reels_count(user, bot, skip_session)

            if not is_private:
                has_story = profile.has_public_story
            elif bot.context.is_logged_in and followed_by_viewer:
                story = next(bot.get_stories(userids=[insta_userid]), None)
                has_story = bool(story and story.itemcount)
            else:
                has_story = False

            profile_image_url = profile.profile_pic_url_no_iphone
            email_sent = False
        except Exception as e:
            r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
            print(f"* Error, retrying in {display_time(r_sleep_time)}: {e}")
            if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                print("* Session might not be valid anymore!")
                if ERROR_NOTIFICATION and not email_sent:
                    m_subject = f"instagram_monitor: session error! (user: {user})"

                    m_body = f"Session might not be valid anymore: {e}{get_cur_ts(nl_ch + nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}")
                    send_email(m_subject, m_body, "", SMTP_SSL)
                    email_sent = True

            print_cur_ts("Timestamp:\t\t")
            time.sleep(r_sleep_time)
            continue

        if (next((s for s in last_output if "HTTP redirect from" in s), None)):
            r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
            print("* Session might not be valid anymore!")
            print(f"Retrying in {display_time(r_sleep_time)}")
            if ERROR_NOTIFICATION and not email_sent:
                m_subject = f"instagram_monitor: session error! (user: {user})"

                m_body = f"Session might not be valid anymore: {last_output}{get_cur_ts(nl_ch + nl_ch + 'Timestamp: ')}"
                print(f"Sending email notification to {RECEIVER_EMAIL}")
                send_email(m_subject, m_body, "", SMTP_SSL)
                email_sent = True
            print_cur_ts("Timestamp:\t\t")
            time.sleep(r_sleep_time)
            continue

        if followings_count != followings_old_count:
            followings_diff = followings_count - followings_old_count
            followings_diff_str = ""
            if followings_diff > 0:
                followings_diff_str = "+" + str(followings_diff)
            else:
                followings_diff_str = str(followings_diff)
            print(f"* Followings number changed by user {user} from {followings_old_count} to {followings_count} ({followings_diff_str})")
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
                    followings = []
                    followings = [followee.username for followee in profile.get_followees()]
                    followings_to_save = []
                    followings_count = profile.followees
                    if not followings and followings_count > 0:
                        print("* Empty followings list returned, not saved to file")
                    else:
                        followings_to_save.append(followings_count)
                        followings_to_save.append(followings)
                        with open(insta_followings_file, 'w', encoding="utf-8") as f:
                            json.dump(followings_to_save, f, indent=2)
                except Exception as e:
                    followings = followings_old
                    print(f"* Error while processing followings list: {e}")

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

            followings_old_count = followings_count

            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

        if followers_count != followers_old_count:
            followers_diff = followers_count - followers_old_count
            followers_diff_str = ""
            if followers_diff > 0:
                followers_diff_str = "+" + str(followers_diff)
            else:
                followers_diff_str = str(followers_diff)
            print(f"* Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})")

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
                    followers = []
                    followers = [follower.username for follower in profile.get_followers()]
                    followers_to_save = []
                    followers_count = profile.followers
                    if not followers and followers_count > 0:
                        print("* Empty followers list returned, not saved to file")
                    else:
                        followers_to_save.append(followers_count)
                        followers_to_save.append(followers)
                        with open(insta_followers_file, 'w', encoding="utf-8") as f:
                            json.dump(followers_to_save, f, indent=2)
                except Exception as e:
                    followers = followers_old
                    print(f"* Error while processing followers list: {e}")

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

            followers_old_count = followers_count

            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

        # Profile pic

        if DETECT_CHANGED_PROFILE_PIC:

            try:
                detect_changed_profile_picture(user, profile_image_url, profile_pic_file, profile_pic_file_tmp, profile_pic_file_old, PROFILE_PIC_FILE_EMPTY, csv_file_name, r_sleep_time, STATUS_NOTIFICATION, 2)
            except Exception as e:
                print(f"* Error while processing changed profile picture: {e}")

        if bio != bio_old:
            print(f"* Bio changed for user {user} !\n")
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

            bio_old = bio
            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

        if is_private != is_private_old:

            if is_private:
                profile_visibility = "private"
                profile_visibility_old = "public"
            else:
                profile_visibility = "public"
                profile_visibility_old = "private"

            print(f"* Profile visibility changed for user {user} to {profile_visibility} !\n")

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

            is_private_old = is_private
            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

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
            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

        if has_story and not story_flag:
            print(f"* New story for user {user} !\n")
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

            print(f"\nCheck interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

        if not has_story and story_flag:
            processed_stories_list = []
            stories_count = 0
            print(f"* Story for user {user} disappeared !")
            print(f"\nCheck interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")
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
                            print(f"Mentions:\t\t{story_mentions}")

                        story_hashtags_m_body = ""
                        story_hashtags_m_body_html = ""
                        if story_hashtags:
                            story_hashtags_m_body = f"\nHashtags: {story_hashtags}"
                            story_hashtags_m_body_html = f"<br>Hashtags: {story_hashtags}"
                            print(f"Hashtags:\t\t{story_hashtags}")

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
                            if not os.path.isfile(story_video_filename):
                                if save_pic_video(story_video_url, story_video_filename, local_ts):
                                    print(f"Story video saved to '{story_video_filename}'")

                        m_body_html_pic_saved_text = ""
                        if local_dt:
                            story_image_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                        else:
                            story_image_filename = f'instagram_{user}_story_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'
                        if story_thumbnail_url:
                            if not os.path.isfile(story_image_filename):
                                if save_pic_video(story_thumbnail_url, story_image_filename, local_ts):
                                    m_body_html_pic_saved_text = f'<br><br><img src="cid:story_pic" width="50%">'
                                    print(f"Story thumbnail image saved to '{story_image_filename}'")
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

                        print(f"\nCheck interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                        print_cur_ts("Timestamp:\t\t")

                    break

                stories_old_count = stories_count

            except Exception as e:
                print(f"* Error while processing story items: {e}")
                print_cur_ts("\nTimestamp:\t\t")

        new_post = False

        cur_h = datetime.now().strftime("%H")
        hours_to_check = list(range(MIN_H1, MAX_H1 + 1)) + list(range(MIN_H2, MAX_H2 + 1))

        if (CHECK_POSTS_IN_HOURS_RANGE and (int(cur_h) in hours_to_check)) or not CHECK_POSTS_IN_HOURS_RANGE:
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
                    last_post_reel = latest_post_reel(user, bot)

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

                except Exception as e:
                    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
                    print(f"* Error, retrying in {display_time(r_sleep_time)}: {e}")
                    if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                        print("* Session might not be valid anymore!")
                        if ERROR_NOTIFICATION and not email_sent:
                            m_subject = f"instagram_monitor: session error! (user: {user})"

                            m_body = f"Session might not be valid anymore: {e}{get_cur_ts(nl_ch + nl_ch + 'Timestamp: ')}"
                            print(f"Sending email notification to {RECEIVER_EMAIL}")
                            send_email(m_subject, m_body, "", SMTP_SSL)
                            email_sent = True

                    print_cur_ts("Timestamp:\t\t")

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
                    print(f"* Error while getting post's likes list / comments list: {e}")

                if new_post:

                    post_url = f"https://www.instagram.com/{'reel' if last_source == 'reel' else 'p'}/{shortcode}/"

                    print(f"* New {last_source.lower()} for user {user} after {calculate_timespan(highestinsta_dt, highestinsta_dt_old)} ({get_date_from_ts(highestinsta_dt_old)})\n")
                    print(f"Date:\t\t\t{get_date_from_ts(highestinsta_dt)}")
                    print(f"{last_source.capitalize()} URL:\t\t{post_url}")
                    print(f"Profile URL:\t\thttps://www.instagram.com/{insta_username}/")
                    print(f"Likes:\t\t\t{likes}")
                    print(f"Comments:\t\t{comments}")
                    print(f"Tagged users:\t\t{tagged_users}")

                    location_mbody = ""
                    location_mbody_str = ""
                    if location:
                        location_mbody = "\nLocation: "
                        location_mbody_str = location
                        print(f"Location:\t\t{location}")

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
                        if highestinsta_dt:
                            video_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
                        else:
                            video_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.mp4'
                        if not os.path.isfile(video_filename):
                            if save_pic_video(video_url, video_filename, highestinsta_ts):
                                print(f"{last_source.capitalize()} video saved to '{video_filename}'")

                    m_body_html_pic_saved_text = ""
                    if highestinsta_dt:
                        image_filename = f'instagram_{user}_{last_source.lower()}_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                    else:
                        image_filename = f'instagram_{user}_{last_source.lower()}_{now_local().strftime("%Y%m%d_%H%M%S")}.jpeg'
                    if thumbnail_url:
                        if not os.path.isfile(image_filename):
                            if save_pic_video(thumbnail_url, image_filename, highestinsta_ts):
                                m_body_html_pic_saved_text = f'<br><br><img src="cid:{last_source.lower()}_pic" width="50%">'
                                print(f"{last_source.capitalize()} thumbnail image saved to '{image_filename}'")
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

                    posts_count_old = posts_count
                    reels_count_old = reels_count

                    highestinsta_ts_old = highestinsta_ts
                    highestinsta_dt_old = highestinsta_dt

                    print(f"\nCheck interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                    print_cur_ts("Timestamp:\t\t")

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

        alive_counter += 1

        if LIVENESS_CHECK_COUNTER and alive_counter >= LIVENESS_CHECK_COUNTER:
            print_cur_ts("Liveness check, timestamp:\t")
            alive_counter = 0

        r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)

        # Be human please
        try:
            if BE_HUMAN:
                simulate_human_actions(bot, r_sleep_time)
        except Exception as e:
            print(f"* Warning: It is not easy to be a human, our simulation failed: {e}")
            print_cur_ts("\nTimestamp:\t\t")

        time.sleep(r_sleep_time)


def main():
    global CLI_CONFIG_PATH, DOTENV_FILE, LOCAL_TIMEZONE, LIVENESS_CHECK_COUNTER, SESSION_USERNAME, SESSION_PASSWORD, CSV_FILE, DISABLE_LOGGING, INSTA_LOGFILE, STATUS_NOTIFICATION, FOLLOWERS_NOTIFICATION, ERROR_NOTIFICATION, INSTA_CHECK_INTERVAL, DETECT_CHANGED_PROFILE_PIC, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH, imgcat_exe, SKIP_SESSION, SKIP_FOLLOWERS, SKIP_FOLLOWINGS, SKIP_GETTING_STORY_DETAILS, SKIP_GETTING_POSTS_DETAILS, GET_MORE_POST_DETAILS, SMTP_PASSWORD, stdout_bck, PROFILE_PIC_FILE_EMPTY, USER_AGENT, USER_AGENT_MOBILE, BE_HUMAN, ENABLE_JITTER

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

    print(f"Instagram Monitoring Tool v{VERSION}\n")

    parser = argparse.ArgumentParser(
        prog="instagram_monitor",
        description=("Monitor an Instagram user's activity and send customizable email alerts [ https://github.com/misiektoja/instagram_monitor/ ]"), formatter_class=argparse.RawTextHelpFormatter
    )

    # Positional
    parser.add_argument(
        "username",
        nargs="?",
        metavar="TARGET_USERNAME",
        help="Instagram username to monitor",
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
        "-b", "--csv-file",
        dest="csv_file",
        metavar="CSV_FILENAME",
        type=str,
        help="Write all activities and profile changes to CSV file"
    )
    opts.add_argument(
        "-d", "--disable-logging",
        dest="disable_logging",
        action="store_true",
        default=None,
        help="Disable logging to instagram_monitor_<username>.log"
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

        if args.session_file:
            session_path = os.path.expanduser(args.session_file)
            session_dir = os.path.dirname(session_path) or "."
            if not os.path.isdir(session_dir):
                raise SystemExit(f"Error: Session directory '{session_dir}' not found !")

        cookie_path = args.cookie_file or get_firefox_cookiefile()
        cookie_path = os.path.expanduser(cookie_path)
        if not os.path.isfile(cookie_path):
            raise SystemExit(f"Error: Cookie file '{cookie_path}' not found !")

        import_session(cookie_path, args.session_file)
        sys.exit(0)

    local_tz = None
    if LOCAL_TIMEZONE == "Auto":
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

    if not args.username:
        print("* Error: TARGET_USERNAME argument is required !")
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

    if args.check_interval:
        INSTA_CHECK_INTERVAL = args.check_interval
        LIVENESS_CHECK_COUNTER = LIVENESS_CHECK_INTERVAL / INSTA_CHECK_INTERVAL

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

    if SKIP_SESSION is True:
        SKIP_FOLLOWERS = True
        SKIP_FOLLOWINGS = True
        GET_MORE_POST_DETAILS = False
        SKIP_GETTING_STORY_DETAILS = True
        BE_HUMAN = False
        mode_of_the_tool = "1 (no session login)"
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

    if args.csv_file:
        CSV_FILE = os.path.expanduser(args.csv_file)
    else:
        if CSV_FILE:
            CSV_FILE = os.path.expanduser(CSV_FILE)

    if CSV_FILE:
        try:
            with open(CSV_FILE, 'a', newline='', buffering=1, encoding="utf-8") as _:
                pass
        except Exception as e:
            print(f"* Error, CSV file cannot be opened for writing: {e}")
            sys.exit(1)

    if args.disable_logging is True:
        DISABLE_LOGGING = True

    if not DISABLE_LOGGING:
        log_path = Path(os.path.expanduser(INSTA_LOGFILE))
        if log_path.parent != Path('.'):
            if log_path.suffix == "":
                log_path = log_path.parent / f"{log_path.name}_{args.username}.log"
        else:
            if log_path.suffix == "":
                log_path = Path(f"{log_path.name}_{args.username}.log")
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
    print("* Hours for checking posts/reels:\t" + (f"{MIN_H1:02d}:00 - {MAX_H1:02d}:59, {MIN_H2:02d}:00 - {MAX_H2:02d}:59" if CHECK_POSTS_IN_HOURS_RANGE else "00:00 - 23:59"))
    print(f"* Browser user agent:\t\t\t{USER_AGENT}")
    print(f"* Mobile user agent:\t\t\t{USER_AGENT_MOBILE}")
    print(f"* HTTP jitter/back-off:\t\t\t{ENABLE_JITTER}")
    print(f"* Liveness check:\t\t\t{bool(LIVENESS_CHECK_INTERVAL)}" + (f" ({display_time(LIVENESS_CHECK_INTERVAL)})" if LIVENESS_CHECK_INTERVAL else ""))
    print(f"* CSV logging enabled:\t\t\t{bool(CSV_FILE)}" + (f" ({CSV_FILE})" if CSV_FILE else ""))
    print(f"* Display profile pics:\t\t\t{bool(imgcat_exe)}" + (f" (via {imgcat_exe})" if imgcat_exe else ""))
    print(f"* Empty profile pic template:\t\t{profile_pic_file_exists}" + (f" ({PROFILE_PIC_FILE_EMPTY})" if profile_pic_file_exists else ""))
    print(f"* Output logging enabled:\t\t{not DISABLE_LOGGING}" + (f" ({FINAL_LOG_PATH})" if not DISABLE_LOGGING else ""))
    print(f"* Configuration file:\t\t\t{cfg_path}")
    print(f"* Dotenv file:\t\t\t\t{env_path or 'None'}")
    print(f"* Local timezone:\t\t\t{LOCAL_TIMEZONE}")

    out = f"\nMonitoring Instagram user {args.username}"
    print(out)
    print("-" * len(out))

    # We define signal handlers only for Linux, Unix & MacOS since Windows has limited number of signals supported
    if platform.system() != 'Windows':
        signal.signal(signal.SIGUSR1, toggle_status_changes_notifications_signal_handler)
        signal.signal(signal.SIGUSR2, toggle_followers_notifications_signal_handler)
        signal.signal(signal.SIGTRAP, increase_check_signal_handler)
        signal.signal(signal.SIGABRT, decrease_check_signal_handler)
        signal.signal(signal.SIGHUP, reload_secrets_signal_handler)

    instagram_monitor_user(args.username, CSV_FILE, SKIP_SESSION, SKIP_FOLLOWERS, SKIP_FOLLOWINGS, SKIP_GETTING_STORY_DETAILS, SKIP_GETTING_POSTS_DETAILS, GET_MORE_POST_DETAILS)

    sys.stdout = stdout_bck
    sys.exit(0)


if __name__ == "__main__":
    main()
