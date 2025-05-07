#!/usr/bin/env python3
"""
Author: Michal Szymanski <misiektoja-github@rm-rf.ninja>
v1.6

OSINT tool implementing real-time tracking of Instagram users activities and profile changes:
https://github.com/misiektoja/instagram_monitor/

Python pip3 requirements:

instaloader
pytz
tzlocal
python-dateutil
requests
"""

VERSION = 1.6

# ---------------------------
# CONFIGURATION SECTION START
# ---------------------------

# Session login is needed for some functionalities like getting list of followings & followers
# In such case we need Instagram username & password for session login in order to monitor other users
# You can type the username & password below, however it is recommended to not specify the password here and log in via:
# <instaloader_location>/bin/instaloader -l <insta_username_for_session_login>
# Then only put the username below (or use -u parameter) to specify the user you used while doing session login via instaloader
INSTA_USERNAME_FOR_SESSION_LOGIN = ''
INSTA_PASSWORD_FOR_SESSION_LOGIN = ''

# SMTP settings for sending email notifications, you can leave it as it is below and no notifications will be sent
SMTP_HOST = "your_smtp_server_ssl"
SMTP_PORT = 587
SMTP_USER = "your_smtp_user"
SMTP_PASSWORD = "your_smtp_password"
SMTP_SSL = True
SENDER_EMAIL = "your_sender_email"
# SMTP_HOST = "your_smtp_server_plaintext"
# SMTP_PORT = 25
# SMTP_USER = "your_smtp_user"
# SMTP_PASSWORD = "your_smtp_password"
# SMTP_SSL = False
# SENDER_EMAIL = "your_sender_email"
RECEIVER_EMAIL = "your_receiver_email"

# How often do we perform checks for user activity, you can also use -c parameter; in seconds
INSTA_CHECK_INTERVAL = 5400  # 1,5 hours

# Specify your local time zone so we convert Instagram API timestamps to your time (for example: 'Europe/Warsaw')
# If you leave it as 'Auto' we will try to automatically detect the local timezone
LOCAL_TIMEZONE = 'Auto'

# Do you want to be informed about changed user's profile pic ? (via console & email notifications when -s is enabled)
# If so, the tool will save the pic to the file named 'instagram_username_profile_pic.jpeg' after tool is started
# And also to files named 'instagram_username_profile_pic_YYmmdd_HHMM.jpeg' when changes are detected
# We need to save the binary form of the image as the pic URL can change, so we need to actually do bin comparison of jpeg files
# It is enabled by default, you can change it below or disable by using -k parameter
DETECT_CHANGED_PROFILE_PIC = True

# If you have 'imgcat' installed, you can configure its path below, so new profile, posts and stories pictures will be displayed right in your terminal
# Leave it empty to disable this feature
# IMGCAT_PATH = "/usr/local/bin/imgcat"
IMGCAT_PATH = ""

# How often do we perform alive check by printing "alive check" message in the output; in seconds
TOOL_ALIVE_INTERVAL = 21600  # 6 hours

# URL we check in the beginning to make sure we have internet connectivity
CHECK_INTERNET_URL = 'http://www.google.com/'

# Default value for initial checking of internet connectivity; in seconds
CHECK_INTERNET_TIMEOUT = 5

# To avoid captcha checks and detection of automated tools we randomize INSTA_CHECK_INTERVAL via randomize_number function
# We pick number from range: INSTA_CHECK_INTERVAL-RANDOM_SLEEP_DIFF_LOW <-> INSTA_CHECK_INTERVAL+RANDOM_SLEEP_DIFF_HIGH
RANDOM_SLEEP_DIFF_LOW = 900  # -15 min, you can also use -i parameter
RANDOM_SLEEP_DIFF_HIGH = 180  # +3 min, you can also use -j parameter

# Do we want to check for new posts only in specified hours ?
CHECK_POSTS_IN_HOURS_RANGE = False

# If CHECK_POSTS_IN_HOURS_RANGE==True, here comes the first hours range to check
# In the example below we check between 00:00-04:59
MIN_H1 = 0
MAX_H1 = 4

# If CHECK_POSTS_IN_HOURS_RANGE==True, here comes the second hours range to check
# In the example below we check between 11:00-23:59
MIN_H2 = 11
MAX_H2 = 23

# The name of the .log file; the tool by default will output its messages to instagram_monitor_username.log file
INSTA_LOGFILE = "instagram_monitor"

# Value used by signal handlers increasing/decreasing the user activity check (INSTA_CHECK_INTERVAL); in seconds
INSTA_CHECK_SIGNAL_VALUE = 300  # 5 min

# -------------------------
# CONFIGURATION SECTION END
# -------------------------

# Default value for network-related timeouts in functions
FUNCTION_TIMEOUT = 15

TOOL_ALIVE_COUNTER = TOOL_ALIVE_INTERVAL / INSTA_CHECK_INTERVAL

# Delay for fetching consecutive posts to avoid captcha checks and detection of automated tools
POST_FETCH_DELAY = 0.2

# Delay for fetching other data to avoid captcha checks and detection of automated tools
NEXT_OPERATION_DELAY = 0.7

stdout_bck = None
last_output = []
csvfieldnames = ['Date', 'Type', 'Old', 'New']

status_notification = False
followers_notification = False

# to solve the issue: 'SyntaxError: f-string expression part cannot include a backslash'
nl_ch = "\n"


import sys

if sys.version_info < (3, 9):
    print("* Error: Python version 3.9 or higher required !")
    sys.exit(1)

import time
import string
import json
import os
from datetime import datetime
from dateutil import relativedelta
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
import pytz
try:
    from tzlocal import get_localzone
except ImportError:
    pass
import platform
import re
import ipaddress
from itertools import zip_longest
import subprocess
import instaloader
from html import escape


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


# Function to check internet connectivity
def check_internet():
    url = CHECK_INTERNET_URL
    try:
        _ = req.get(url, timeout=CHECK_INTERNET_TIMEOUT)
        print("OK")
        return True
    except Exception as e:
        print(f"No connectivity, please check your network - {e}")
        sys.exit(1)
    return False


# Function to convert absolute value of seconds to human readable format
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


# Function to calculate time span between two timestamps in seconds
def calculate_timespan(timestamp1, timestamp2, show_weeks=True, show_hours=True, show_minutes=True, show_seconds=False, granularity=3):
    result = []
    intervals = ['years', 'months', 'weeks', 'days', 'hours', 'minutes', 'seconds']
    ts1 = timestamp1
    ts2 = timestamp2

    if type(timestamp1) is int:
        dt1 = datetime.fromtimestamp(int(ts1))
    elif type(timestamp1) is float:
        ts1 = int(round(ts1))
        dt1 = datetime.fromtimestamp(ts1)
    elif type(timestamp1) is datetime:
        dt1 = timestamp1
        ts1 = int(round(dt1.timestamp()))
    else:
        return ""

    if type(timestamp2) is int:
        dt2 = datetime.fromtimestamp(int(ts2))
    elif type(timestamp2) is float:
        ts2 = int(round(ts2))
        dt2 = datetime.fromtimestamp(ts2)
    elif type(timestamp2) is datetime:
        dt2 = timestamp2
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
        weeks = date_diff.weeks
        if not show_weeks:
            weeks = 0
        days = date_diff.days
        if weeks > 0:
            days = days - (weeks * 7)
        hours = date_diff.hours
        if (not show_hours and ts_diff > 86400):
            hours = 0
        minutes = date_diff.minutes
        if (not show_minutes and ts_diff > 3600):
            minutes = 0
        seconds = date_diff.seconds
        if (not show_seconds and ts_diff > 60):
            seconds = 0
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


# Function to send email notification
def send_email(subject, body, body_html, use_ssl, image_file="", image_name="image1", smtp_timeout=15):
    fqdn_re = re.compile(r'(?=^.{4,253}$)(^((?!-)[a-zA-Z0-9-]{1,63}(?<!-)\.)+[a-zA-Z]{2,63}\.?$)')
    email_re = re.compile(r'[^@]+@[^@]+\.[^@]+')

    try:
        is_ip = ipaddress.ip_address(str(SMTP_HOST))
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
        email_msg["Subject"] = Header(subject, 'utf-8')

        if image_file:
            fp = open(image_file, 'rb')
            img_part = MIMEImage(fp.read())
            fp.close()

        if body:
            part1 = MIMEText(body, 'plain')
            part1 = MIMEText(body.encode('utf-8'), 'plain', _charset='utf-8')
            email_msg.attach(part1)

        if body_html:
            part2 = MIMEText(body_html, 'html')
            part2 = MIMEText(body_html.encode('utf-8'), 'html', _charset='utf-8')
            email_msg.attach(part2)

        if image_file:
            img_part.add_header('Content-ID', f'<{image_name}>')
            email_msg.attach(img_part)

        smtpObj.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, email_msg.as_string())
        smtpObj.quit()
    except Exception as e:
        print(f"Error sending email - {e}")
        return 1
    return 0


# Function to write CSV entry
def write_csv_entry(csv_file_name, timestamp, object_type, old, new):
    try:
        csv_file = open(csv_file_name, 'a', newline='', buffering=1, encoding="utf-8")
        csvwriter = csv.DictWriter(csv_file, fieldnames=csvfieldnames, quoting=csv.QUOTE_NONNUMERIC)
        csvwriter.writerow({'Date': timestamp, 'Type': object_type, 'Old': old, 'New': new})
        csv_file.close()
    except Exception as e:
        raise


# Function to randomize how often we perform checks for user activity (INSTA_CHECK_INTERVAL)
def randomize_number(number, diff_low, diff_high):
    if number > diff_low:
        return (random.randint(number - diff_low, number + diff_high))
    else:
        return (random.randint(number, number + diff_high))


# Function to return the timestamp in human readable format; eg. Sun, 21 Apr 2024, 15:08:45
def get_cur_ts(ts_str=""):
    return (f'{ts_str}{calendar.day_abbr[(datetime.fromtimestamp(int(time.time()))).weekday()]}, {datetime.fromtimestamp(int(time.time())).strftime("%d %b %Y, %H:%M:%S")}')


# Function to print the current timestamp in human readable format; eg. Sun, 21 Apr 2024, 15:08:45
def print_cur_ts(ts_str=""):
    print(get_cur_ts(str(ts_str)))
    print("-----------------------------------------------------------------------------------------------------------------")


# Function to return the timestamp/datetime object in human readable format (long version); eg. Sun, 21 Apr 2024, 15:08:45
def get_date_from_ts(ts):
    if type(ts) is datetime:
        ts_new = int(round(ts.timestamp()))
    elif type(ts) is int:
        ts_new = ts
    elif type(ts) is float:
        ts_new = int(round(ts))
    else:
        return ""

    return (f'{calendar.day_abbr[(datetime.fromtimestamp(ts_new)).weekday()]} {datetime.fromtimestamp(ts_new).strftime("%d %b %Y, %H:%M:%S")}')


# Function to return the timestamp/datetime object in human readable format (short version); eg.
# Sun 21 Apr 15:08
# Sun 21 Apr 24, 15:08 (if show_year == True and current year is different)
# Sun 21 Apr (if show_hour == False)
def get_short_date_from_ts(ts, show_year=False, show_hour=True):
    if type(ts) is datetime:
        ts_new = int(round(ts.timestamp()))
    elif type(ts) is int:
        ts_new = ts
    elif type(ts) is float:
        ts_new = int(round(ts))
    else:
        return ""

    if show_hour:
        hour_strftime = " %H:%M"
    else:
        hour_strftime = ""

    if show_year and int(datetime.fromtimestamp(ts_new).strftime("%Y")) != int(datetime.now().strftime("%Y")):
        if show_hour:
            hour_prefix = ","
        else:
            hour_prefix = ""
        return (f'{calendar.day_abbr[(datetime.fromtimestamp(ts_new)).weekday()]} {datetime.fromtimestamp(ts_new).strftime(f"%d %b %y{hour_prefix}{hour_strftime}")}')
    else:
        return (f'{calendar.day_abbr[(datetime.fromtimestamp(ts_new)).weekday()]} {datetime.fromtimestamp(ts_new).strftime(f"%d %b{hour_strftime}")}')


# Function to return the timestamp/datetime object in human readable format (only hour, minutes and optionally seconds): eg. 15:08:12
def get_hour_min_from_ts(ts, show_seconds=False):
    if type(ts) is datetime:
        ts_new = int(round(ts.timestamp()))
    elif type(ts) is int:
        ts_new = ts
    elif type(ts) is float:
        ts_new = int(round(ts))
    else:
        return ""

    if show_seconds:
        out_strf = "%H:%M:%S"
    else:
        out_strf = "%H:%M"
    return (str(datetime.fromtimestamp(ts_new).strftime(out_strf)))


# Function to return the range between two timestamps/datetime objects; eg. Sun 21 Apr 14:09 - 14:15
def get_range_of_dates_from_tss(ts1, ts2, between_sep=" - ", short=False):
    if type(ts1) is datetime:
        ts1_new = int(round(ts1.timestamp()))
    elif type(ts1) is int:
        ts1_new = ts1
    elif type(ts1) is float:
        ts1_new = int(round(ts1))
    else:
        return ""

    if type(ts2) is datetime:
        ts2_new = int(round(ts2.timestamp()))
    elif type(ts2) is int:
        ts2_new = ts2
    elif type(ts2) is float:
        ts2_new = int(round(ts2))
    else:
        return ""

    ts1_strf = datetime.fromtimestamp(ts1_new).strftime("%Y%m%d")
    ts2_strf = datetime.fromtimestamp(ts2_new).strftime("%Y%m%d")

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
    return (str(out_str))


# Function to convert UTC datetime object returned by Instagram API to datetime object in specified timezone
def convert_utc_datetime_to_tz_datetime(dt_utc, timezone):
    try:
        old_tz = pytz.timezone("UTC")
        new_tz = pytz.timezone(timezone)
        dt_new_tz = old_tz.localize(dt_utc).astimezone(new_tz)
        return dt_new_tz
    except Exception as e:
        return datetime.fromtimestamp(0)


# Function to convert UTC string returned by Instagram API to datetime object in specified timezone
def convert_utc_str_to_tz_datetime(utc_string, timezone):
    try:
        utc_string_sanitize = utc_string.split(' GMT', 1)[0]
        dt_utc = datetime.strptime(utc_string_sanitize, '%a, %d %b %Y %H:%M:%S')

        old_tz = pytz.timezone("UTC")
        new_tz = pytz.timezone(timezone)
        dt_new_tz = old_tz.localize(dt_utc).astimezone(new_tz)
        return dt_new_tz
    except Exception as e:
        return datetime.fromtimestamp(0)


# Signal handler for SIGUSR1 allowing to switch email notifications for new posts/stories/followings/bio
def toggle_status_changes_notifications_signal_handler(sig, frame):
    global status_notification
    status_notification = not status_notification
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Email notifications: [new posts/stories/followings/bio/profile picture = {status_notification}]")
    print_cur_ts("Timestamp:\t\t")


# Signal handler for SIGUSR2 allowing to switch email notifications for new followers
def toggle_followers_notifications_signal_handler(sig, frame):
    global followers_notification
    followers_notification = not followers_notification
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Email notifications: [followers = {followers_notification}]")
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


# Function saving user's image / video to selected file name
def save_pic_video(image_video_url, image_video_file_name, custom_mdate_ts=0):
    try:
        image_video_response = req.get(image_video_url, timeout=FUNCTION_TIMEOUT, stream=True)
        image_video_response.raise_for_status()
        url_time = image_video_response.headers.get('last-modified')
        url_time_in_tz_ts = 0
        if url_time and not custom_mdate_ts:
            url_time_in_tz = convert_utc_str_to_tz_datetime(url_time, LOCAL_TIMEZONE)
            url_time_in_tz_ts = int(url_time_in_tz.timestamp())

        if image_video_response.status_code == 200:
            with open(image_video_file_name, 'wb') as f:
                image_video_response.raw.decode_content = True
                shutil.copyfileobj(image_video_response.raw, f)
            if url_time_in_tz_ts and not custom_mdate_ts:
                os.utime(image_video_file_name, (url_time_in_tz_ts, url_time_in_tz_ts))
            elif custom_mdate_ts:
                os.utime(image_video_file_name, (custom_mdate_ts, custom_mdate_ts))
        return True
    except Exception as e:
        return False


# Function comparing two image files
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
        print(f"Error while comparing profile pictures - {e}")
        return False


# Function detecting changed Instagram profile pictures
def detect_changed_profile_picture(user, profile_image_url, profile_pic_file, profile_pic_file_tmp, profile_pic_file_old, profile_pic_file_empty, csv_file_name, r_sleep_time, send_email_notification, func_ver):

    is_empty_profile_pic = False
    is_empty_profile_pic_tmp = False

    if func_ver == 2:
        new_line = "\n"
    else:
        new_line = ""

    # profile pic does not exist in the filesystem
    if not os.path.isfile(profile_pic_file):
        if save_pic_video(profile_image_url, profile_pic_file):
            profile_pic_mdate_dt = datetime.fromtimestamp(int(os.path.getmtime(profile_pic_file)))

            if os.path.isfile(profile_pic_file_empty):
                is_empty_profile_pic = compare_images(profile_pic_file, profile_pic_file_empty)

            if is_empty_profile_pic:
                print(f"* User {user} does not have profile picture set, empty template saved to '{profile_pic_file}'{new_line}")
            else:
                print(f"* User {user} profile picture saved to '{profile_pic_file}'")
                print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_mdate_dt, True)} ({calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False)} ago){new_line}")

            try:
                if IMGCAT_PATH and os.path.isfile(IMGCAT_PATH) and not is_empty_profile_pic:
                    if func_ver == 1:
                        subprocess.call((f'echo;{IMGCAT_PATH} {profile_pic_file}'), shell=True)
                    else:
                        subprocess.call((f'{IMGCAT_PATH} {profile_pic_file};echo'), shell=True)
                shutil.copy2(profile_pic_file, f'instagram_{user}_profile_pic_{profile_pic_mdate_dt.strftime("%Y%m%d_%H%M")}.jpeg')
            except:
                pass
            try:
                if csv_file_name and not is_empty_profile_pic:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Profile Picture Created", "", profile_pic_mdate_dt)
            except Exception as e:
                print(f"* Cannot write CSV entry - {e}")
        else:
            print(f"Error saving profile picture !{new_line}")

        if func_ver == 2:
            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")
        else:
            print_cur_ts("\nTimestamp:\t\t")

    # profile pic exists in the filesystem, we check if it has not changed
    elif os.path.isfile(profile_pic_file):
        csv_text = ""
        m_subject = ""
        m_body = ""
        m_body_html = ""
        m_body_html_pic_saved_text = ""
        profile_pic_mdate_dt = datetime.fromtimestamp(int(os.path.getmtime(profile_pic_file)))
        profile_pic_mdate = get_short_date_from_ts(profile_pic_mdate_dt, True)
        if save_pic_video(profile_image_url, profile_pic_file_tmp):
            profile_pic_tmp_mdate_dt = datetime.fromtimestamp(int(os.path.getmtime(profile_pic_file_tmp)))
            if os.path.isfile(profile_pic_file_empty):
                is_empty_profile_pic = compare_images(profile_pic_file, profile_pic_file_empty)

            if not compare_images(profile_pic_file, profile_pic_file_tmp) and profile_pic_mdate_dt != profile_pic_tmp_mdate_dt:
                if os.path.isfile(profile_pic_file_empty):
                    is_empty_profile_pic_tmp = compare_images(profile_pic_file_tmp, profile_pic_file_empty)

                # User has removed profile picture
                if is_empty_profile_pic_tmp and not is_empty_profile_pic:
                    print(f"* User {user} has removed profile picture added on {profile_pic_mdate} ! (after {calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)}){new_line}")
                    csv_text = "Profile Picture Removed"

                    if send_email_notification:
                        m_subject = f"Instagram user {user} has removed profile picture ! (after {calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)})"

                        m_body = f"Instagram user {user} has removed profile picture added on {profile_pic_mdate} (after {calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)})\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user {user} has removed profile picture added on <b>{profile_pic_mdate}</b> (after {calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)})<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                # User has set profile picture
                elif is_empty_profile_pic and not is_empty_profile_pic_tmp:
                    print(f"* User {user} has set profile picture !")
                    print(f"* User profile picture saved to '{profile_pic_file}'")
                    print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(int(time.time()), profile_pic_tmp_mdate_dt, show_seconds=False)} ago){new_line}")
                    csv_text = "Profile Picture Created"

                    if send_email_notification:
                        m_body_html_pic_saved_text = f'<br><br><img src="cid:profile_pic">'
                        m_subject = f"Instagram user {user} has set profile picture ! ({get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)})"

                        m_body = f"Instagram user {user} has set profile picture !\n\nProfile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(int(time.time()), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user <b>{user}</b> has set profile picture !{m_body_html_pic_saved_text}<br><br>Profile picture has been added on <b>{get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)}</b> ({calculate_timespan(int(time.time()), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                # User has changed profile picture
                elif not is_empty_profile_pic_tmp and not is_empty_profile_pic:
                    print(f"* User {user} has changed profile picture ! (previous one added on {profile_pic_mdate} - {calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)} ago)")
                    print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(int(time.time()), profile_pic_tmp_mdate_dt, show_seconds=False)} ago){new_line}")
                    csv_text = "Profile Picture Changed"

                    if send_email_notification:
                        m_body_html_pic_saved_text = f'<br><br><img src="cid:profile_pic">'
                        m_subject = f"Instagram user {user} has changed profile picture ! (after {calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)})"

                        m_body = f"Instagram user {user} has changed profile picture !\n\nPrevious one added on {profile_pic_mdate} ({calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)} ago)\n\nProfile picture has been added on {get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)} ({calculate_timespan(int(time.time()), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user <b>{user}</b> has changed profile picture !{m_body_html_pic_saved_text}<br><br>Previous one added on <b>{profile_pic_mdate}</b> ({calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False, granularity=2)} ago)<br><br>Profile picture has been added on <b>{get_short_date_from_ts(profile_pic_tmp_mdate_dt, True)}</b> ({calculate_timespan(int(time.time()), profile_pic_tmp_mdate_dt, show_seconds=False)} ago)<br><br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                try:
                    if csv_file_name:
                        if csv_text == "Profile Picture Removed":
                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), csv_text, profile_pic_mdate_dt, "")
                        elif csv_text == "Profile Picture Created":
                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), csv_text, "", profile_pic_tmp_mdate_dt)
                        else:
                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), csv_text, profile_pic_mdate_dt, profile_pic_tmp_mdate_dt)
                except Exception as e:
                    print(f"* Cannot write CSV entry - {e}")

                try:
                    if IMGCAT_PATH and os.path.isfile(IMGCAT_PATH) and not is_empty_profile_pic_tmp:
                        if func_ver == 1:
                            subprocess.call((f'echo;{IMGCAT_PATH} {profile_pic_file_tmp}'), shell=True)
                        else:
                            subprocess.call((f'{IMGCAT_PATH} {profile_pic_file_tmp};echo'), shell=True)
                    shutil.copy2(profile_pic_file_tmp, f'instagram_{user}_profile_pic_{profile_pic_tmp_mdate_dt.strftime("%Y%m%d_%H%M")}.jpeg')
                    if csv_text != "Profile Picture Created":
                        os.replace(profile_pic_file, profile_pic_file_old)
                    os.replace(profile_pic_file_tmp, profile_pic_file)
                except Exception as e:
                    print(f"Error while replacing/copying files - {e}")

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
                        print(f"* Profile picture has been added on {get_short_date_from_ts(profile_pic_mdate_dt, True)} ({calculate_timespan(int(time.time()), profile_pic_mdate_dt, show_seconds=False)} ago)")
                        try:
                            if IMGCAT_PATH and os.path.isfile(IMGCAT_PATH):
                                subprocess.call((f'echo;{IMGCAT_PATH} {profile_pic_file}'), shell=True)
                        except:
                            pass
                    try:
                        os.remove(profile_pic_file_tmp)
                    except:
                        pass
        else:
            print(f"Error while checking if the profile picture has changed !")
            if func_ver == 2:
                print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t")
        if func_ver == 1:
            print_cur_ts("\nTimestamp:\t\t")


# Main function monitoring activity of the specified Instagram user
def instagram_monitor_user(user, error_notification, csv_file_name, csv_exists, skip_session, skip_followers, skip_followings, skip_getting_story_details, skip_getting_posts_details, get_more_post_details):

    try:
        if csv_file_name:
            csv_file = open(csv_file_name, 'a', newline='', buffering=1, encoding="utf-8")
            csvwriter = csv.DictWriter(csv_file, fieldnames=csvfieldnames, quoting=csv.QUOTE_NONNUMERIC)
            if not csv_exists:
                csvwriter.writeheader()
            csv_file.close()
    except Exception as e:
        print(f"Error - {e}")

    followers_count = 0
    followings_count = 0
    r_sleep_time = 0
    followers_followings_fetched = False
    stories_count = 0
    stories_old_count = 0

    try:
        bot = instaloader.Instaloader()
        if (INSTA_USERNAME_FOR_SESSION_LOGIN and INSTA_PASSWORD_FOR_SESSION_LOGIN) and not skip_session:
            bot.login(user=INSTA_USERNAME_FOR_SESSION_LOGIN, passwd=INSTA_PASSWORD_FOR_SESSION_LOGIN)
        elif INSTA_USERNAME_FOR_SESSION_LOGIN and not INSTA_PASSWORD_FOR_SESSION_LOGIN and not skip_session:
            # log in via: <instaloader_location>/bin/instaloader -l username
            bot.load_session_from_file(INSTA_USERNAME_FOR_SESSION_LOGIN)
        profile = instaloader.Profile.from_username(bot.context, user)
        time.sleep(NEXT_OPERATION_DELAY)
        insta_username = profile.username
        insta_userid = profile.userid
        followers_count = profile.followers
        followings_count = profile.followees
        bio = profile.biography
        posts_count = profile.mediacount
        has_story = profile.has_public_story
        is_private = profile.is_private
        profile_image_url = profile.profile_pic_url_no_iphone
    except Exception as e:
        print(f"Error - {e}")
        sys.exit(1)

    story_flag = False

    followers_old_count = followers_count
    followings_old_count = followings_count
    bio_old = bio
    posts_count_old = posts_count
    is_private_old = is_private

    print(f"\nUsername:\t\t{insta_username}")
    print(f"User ID:\t\t{insta_userid}")
    print(f"URL:\t\t\thttps://www.instagram.com/{insta_username}/")
    print(f"Posts number:\t\t{posts_count}")
    print(f"Followers Count:\t{followers_count}")
    print(f"Followings Count:\t{followings_count}")
    print(f"Story available:\t{has_story}")
    print(f"Public profile:\t\t{not is_private}")
    print(f"Bio:\n\n{bio}\n")
    print_cur_ts("Timestamp:\t\t")

    processed_stories_list = []
    if has_story:
        story_flag = True
        stories_count = 1

        if not skip_session and not skip_getting_story_details:
            try:
                stories = bot.get_stories(userids=[profile.userid])

                for story in stories:
                    stories_count = story.itemcount
                    if stories_count > 0:
                        print(f"* User {user} has {stories_count} story items:")
                        print("-----------------------------------------------------------------------------------------------------------------")
                    i = 0
                    for story_item in story.get_items():
                        i += 1
                        local_dt = story_item.date_local
                        local_ts = int(local_dt.timestamp())
                        processed_stories_list.append(local_ts)
                        expire_dt = story_item.expiring_local
                        expire_ts = int(expire_dt.timestamp())
                        print(f"Date:\t\t\t{get_date_from_ts(int(local_ts))}")
                        print(f"Expiry:\t\t\t{get_date_from_ts(int(expire_ts))}")
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
                            print(f"Caption:\n\n{story_caption}\n")
                        else:
                            print()

                        story_thumbnail_url = story_item.url
                        story_video_url = story_item.video_url

                        if story_video_url:
                            story_video_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
                            if not os.path.isfile(story_video_filename):
                                if save_pic_video(story_video_url, story_video_filename, local_ts):
                                    print(f"Story video saved to '{story_video_filename}'")

                        if story_thumbnail_url:
                            story_image_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                            if not os.path.isfile(story_image_filename):
                                if save_pic_video(story_thumbnail_url, story_image_filename, local_ts):
                                    print(f"Story thumbnail image saved to '{story_image_filename}'")
                            if os.path.isfile(story_image_filename):
                                try:
                                    if IMGCAT_PATH and os.path.isfile(IMGCAT_PATH):
                                        subprocess.call((f'echo;{IMGCAT_PATH} {story_image_filename}'), shell=True)
                                        if i < stories_count:
                                            print()
                                except:
                                    pass

                        try:
                            if csv_file_name:
                                write_csv_entry(csv_file_name, local_dt, "New Story Item", "", story_type)
                        except Exception as e:
                            print(f"Error: cannot write CSV entry - {e}")

                        if i == stories_count:
                            print_cur_ts("\nTimestamp:\t\t")
                        else:
                            print("-----------------------------------------------------------------------------------------------------------------")

                    break

                stories_old_count = stories_count

            except Exception as e:
                print(f"Error - {e}")
                sys.exit(1)

    insta_followers_file = f"instagram_{user}_followers.json"
    insta_followings_file = f"instagram_{user}_followings.json"
    profile_pic_file = f"instagram_{user}_profile_pic.jpeg"
    profile_pic_file_old = f"instagram_{user}_profile_pic_old.jpeg"
    profile_pic_file_tmp = f"instagram_{user}_profile_pic_tmp.jpeg"
    profile_pic_file_empty = f"instagram_profile_pic_empty.jpeg"
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
            print(f"* Cannot load followers list from '{insta_followers_file}' file - {e}")
        if followers_read:
            followers_old_count = followers_read[0]
            followers_old = followers_read[1]
            if followers_count == followers_old_count:
                followers = followers_old
            followers_mdate = datetime.fromtimestamp(int(os.path.getmtime(insta_followers_file))).strftime("%d %b %Y, %H:%M:%S")
            print(f"* Followers ({followers_old_count}) loaded from file '{insta_followers_file}' ({followers_mdate})")
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
                write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followers Count", followers_old_count, followers_count)
        except Exception as e:
            print(f"Error: cannot write CSV entry - {e}")

    if ((followers_count != followers_old_count) or (followers_count > 0 and not followers)) and not skip_session and not skip_followers:
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
                print(f"* Cannot save list of followers to '{insta_followers_file}' file - {e}")

    if ((followers_count != followers_old_count) and (followers != followers_old)) and not skip_session and not skip_followers and ((followers and followers_count > 0) or (not followers and followers_count == 0)):
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
                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followers", f_in_list, "")
                except Exception as e:
                    print(f"Error: cannot write CSV entry - {e}")
            print()

        if added_followers:
            print("Added followers:\n")
            for f_in_list in added_followers:
                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                added_followers_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followers", "", f_in_list)
                except Exception as e:
                    print(f"Error: cannot write CSV entry - {e}")
            print()

    if os.path.isfile(insta_followings_file):
        try:
            with open(insta_followings_file, 'r', encoding="utf-8") as f:
                followings_read = json.load(f)
        except Exception as e:
            print(f"* Cannot load followings list from '{insta_followings_file}' file - {e}")
        if followings_read:
            followings_old_count = followings_read[0]
            followings_old = followings_read[1]
            if followings_count == followings_old_count:
                followings = followings_old
            following_mdate = datetime.fromtimestamp(int(os.path.getmtime(insta_followings_file))).strftime("%d %b %Y, %H:%M:%S")
            print(f"\n* Followings ({followings_old_count}) loaded from file '{insta_followings_file}' ({following_mdate})")
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
                write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followings Count", followings_old_count, followings_count)
        except Exception as e:
            print(f"Error: cannot write CSV entry - {e}")

    if ((followings_count != followings_old_count) or (followings_count > 0 and not followings)) and not skip_session and not skip_followings:
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
                print(f"* Cannot save list of followings to '{insta_followings_file}' file - {e}")

    if ((followings_count != followings_old_count) and (followings != followings_old)) and not skip_session and not skip_followings and ((followings and followings_count > 0) or (not followings and followings_count == 0)):
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
                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followings", f_in_list, "")
                except Exception as e:
                    print(f"Error: cannot write CSV entry - {e}")
            print()

        if added_followings:
            print("Added followings:\n")
            for f_in_list in added_followings:
                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                added_followings_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                try:
                    if csv_file_name:
                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followings", "", f_in_list)
                except Exception as e:
                    print(f"Error: cannot write CSV entry - {e}")
            print()

    if not skip_session and not skip_followers:
        followers_old = followers
    else:
        followers = followers_old

    if not skip_session and not skip_followings:
        followings_old = followings
    else:
        followings = followings_old

    followers_old_count = followers_count
    followings_old_count = followings_count

    if followers_followings_fetched:
        print_cur_ts("\nTimestamp:\t\t")

    # profile pic

    if DETECT_CHANGED_PROFILE_PIC:

        try:
            detect_changed_profile_picture(user, profile_image_url, profile_pic_file, profile_pic_file_tmp, profile_pic_file_old, profile_pic_file_empty, csv_file_name, r_sleep_time, False, 1)
        except Exception as e:
            print(f"Error while processing changed profile picture - {e}")

    highestinsta_ts = 0
    highestinsta_dt = datetime.fromtimestamp(0)
    likes = 0
    comments = 0
    caption = ""
    pcaption = ""
    tagged_users = []
    shortcode = ""
    location = ""
    likes_users_list = ""
    post_comments_list = ""
    last_post = None
    thumbnail_url = ""
    video_url = ""

    if int(posts_count) >= 1 and not skip_getting_posts_details:
        print("Fetching user's latest post/reel (be patient, it might take a while depending on the number of posts) ...\n")
        try:

            time.sleep(NEXT_OPERATION_DELAY)
            posts = instaloader.Profile.from_username(bot.context, user).get_posts()

            for post in posts:
                time.sleep(POST_FETCH_DELAY)
                local_dt = post.date_local
                local_ts = int(local_dt.timestamp())

                if local_ts > highestinsta_ts:
                    highestinsta_ts = local_ts
                    highestinsta_dt = local_dt
                    last_post = post

            likes = last_post.likes
            comments = last_post.comments
            caption = last_post.caption
            pcaption = last_post.pcaption
            tagged_users = last_post.tagged_users
            shortcode = last_post.shortcode
            thumbnail_url = last_post.url
            video_url = last_post.video_url

        except Exception as e:
            print(f"Error - {e}")
            sys.exit(1)

        try:
            if not skip_session and get_more_post_details:
                # if last_post.location:
                #    location = last_post.location.name
                likes_list = last_post.get_likes()
                for like in likes_list:
                    likes_users_list += "- " + like.username + " [ " + "https://www.instagram.com/" + like.username + "/ ]\n"
                comments_list = last_post.get_comments()
                for comment in comments_list:
                    comment_created_at = convert_utc_datetime_to_tz_datetime(comment.created_at_utc, LOCAL_TIMEZONE)
                    post_comments_list += "\n[ " + get_short_date_from_ts(comment_created_at.timestamp()) + " - " + "https://www.instagram.com/" + comment.owner.username + "/ ]\n" + comment.text + "\n"
        except Exception as e:
            print(f"Error while getting post location / likes list / comments list - {e}")

        post_url = f"https://instagram.com/p/{shortcode}/"

        print(f"* Newest post for user {user}:\n")
        print(f"Date:\t\t\t{get_date_from_ts(int(highestinsta_ts))} ({calculate_timespan(int(time.time()), int(highestinsta_ts))} ago)")
        print(f"Post URL:\t\t{post_url}")
        print(f"Profile URL:\t\thttps://www.instagram.com/{insta_username}/")
        print(f"Likes:\t\t\t{likes}")
        print(f"Comments:\t\t{comments}")
        print(f"Tagged users:\t\t{tagged_users}")

        if location:
            print(f"Location:\t\t{location}")

        print(f"Caption:\n\n{caption}\n")

        if likes_users_list:
            print(f"Likes list:\n{likes_users_list}")

        if post_comments_list:
            print(f"Comments list:{post_comments_list}")

        if video_url:
            video_filename = f'instagram_{user}_post_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
            if not os.path.isfile(video_filename):
                if save_pic_video(video_url, video_filename, highestinsta_ts):
                    print(f"Post video saved to '{video_filename}'")

        if thumbnail_url:
            image_filename = f'instagram_{user}_post_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
            if not os.path.isfile(image_filename):
                if save_pic_video(thumbnail_url, image_filename, highestinsta_ts):
                    print(f"Post thumbnail image saved to '{image_filename}'")
            if os.path.isfile(image_filename):
                try:
                    if IMGCAT_PATH and os.path.isfile(IMGCAT_PATH):
                        subprocess.call((f'{IMGCAT_PATH} {image_filename}'), shell=True)
                except:
                    pass

        print_cur_ts("\nTimestamp:\t\t")

        highestinsta_ts_old = highestinsta_ts

    else:
        highestinsta_ts_old = int(time.time())

    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
    time.sleep(r_sleep_time)

    alive_counter = 0

    email_sent = False

    # main loop
    while True:
        last_output = []
        try:
            profile = instaloader.Profile.from_username(bot.context, user)
            time.sleep(NEXT_OPERATION_DELAY)
            new_post = False
            followers_count = profile.followers
            followings_count = profile.followees
            bio = profile.biography
            posts_count = profile.mediacount
            has_story = profile.has_public_story
            is_private = profile.is_private
            profile_image_url = profile.profile_pic_url_no_iphone
            email_sent = False
        except Exception as e:
            r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
            print(f"Error, retrying in {display_time(r_sleep_time)} - {e}")
            if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                print("* Session might not be valid anymore!")
                if error_notification and not email_sent:
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
            if error_notification and not email_sent:
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
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followings Count", followings_old_count, followings_count)
            except Exception as e:
                print(f"Error: cannot write CSV entry - {e}")

            added_followings_list = ""
            removed_followings_list = ""
            added_followings_mbody = ""
            removed_followings_mbody = ""

            if not skip_session and not skip_followings:
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
                    print(f"Error while processing followings list - {e}")

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
                                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followings", f_in_list, "")
                                except Exception as e:
                                    print(f"Error: cannot write CSV entry - {e}")
                            print()

                        if added_followings:
                            print("Added followings:\n")
                            added_followings_mbody = "\nAdded followings:\n\n"
                            for f_in_list in added_followings:
                                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                                added_followings_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                                try:
                                    if csv_file_name:
                                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followings", "", f_in_list)
                                except Exception as e:
                                    print(f"Error: cannot write CSV entry - {e}")
                            print()

                    followings_old = followings

            if status_notification:
                m_subject = f"Instagram user {user} followings number has changed! ({followings_diff_str}, {followings_old_count} -> {followings_count})"

                if not skip_session and not skip_followings:

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
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followers Count", followers_old_count, followers_count)
            except Exception as e:
                print(f"Error: cannot write CSV entry - {e}")

            added_followers_list = ""
            removed_followers_list = ""
            added_followers_mbody = ""
            removed_followers_mbody = ""

            if not skip_session and not skip_followers:
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
                    print(f"Error while processing followers list - {e}")

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
                                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followers", f_in_list, "")
                                except Exception as e:
                                    print(f"Error: cannot write CSV entry - {e}")
                            print()

                        if added_followers:
                            print("Added followers:\n")
                            added_followers_mbody = "\nAdded followers:\n\n"
                            for f_in_list in added_followers:
                                print(f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]")
                                added_followers_list += f"- {f_in_list} [ https://www.instagram.com/{f_in_list}/ ]\n"
                                try:
                                    if csv_file_name:
                                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followers", "", f_in_list)
                                except Exception as e:
                                    print(f"Error: cannot write CSV entry - {e}")
                            print()

                    followers_old = followers

            if status_notification and followers_notification:
                m_subject = f"Instagram user {user} followers number has changed! ({followers_diff_str}, {followers_old_count} -> {followers_count})"

                if not skip_session and not skip_followers:
                    m_body = f"Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})\n{removed_followers_mbody}{removed_followers_list}{added_followers_mbody}{added_followers_list}\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                else:
                    m_body = f"Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                send_email(m_subject, m_body, "", SMTP_SSL)

            followers_old_count = followers_count

            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

        # profile pic

        if DETECT_CHANGED_PROFILE_PIC:

            try:
                detect_changed_profile_picture(user, profile_image_url, profile_pic_file, profile_pic_file_tmp, profile_pic_file_old, profile_pic_file_empty, csv_file_name, r_sleep_time, status_notification, 2)
            except Exception as e:
                print(f"Error while processing changed profile picture - {e}")

        if bio != bio_old:
            print(f"* Bio changed for user {user} !\n")
            print(f"Old bio:\n\n{bio_old}\n")
            print(f"New bio:\n\n{bio}\n")

            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Bio Changed", bio_old, bio)
            except Exception as e:
                print(f"Error: cannot write CSV entry - {e}")

            if status_notification:
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
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Profile Visibility", profile_visibility_old, profile_visibility)
            except Exception as e:
                print(f"Error: cannot write CSV entry - {e}")

            if status_notification:
                m_subject = f"Instagram user {user} profile visibility has changed to {profile_visibility} !"

                m_body = f"Instagram user {user} profile visibility has changed to {profile_visibility}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                send_email(m_subject, m_body, "", SMTP_SSL)

            is_private_old = is_private
            print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
            print_cur_ts("Timestamp:\t\t")

        if has_story and not story_flag:
            print(f"* New story for user {user} !\n")
            story_flag = True
            stories_count = 1

            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "New Story", "", "")
            except Exception as e:
                print(f"Error: cannot write CSV entry - {e}")

            if status_notification:
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

        if has_story and not skip_session and not skip_getting_story_details:
            try:
                stories = bot.get_stories(userids=[profile.userid])

                for story in stories:
                    stories_count = story.itemcount
                    if stories_count == stories_old_count or stories_count <= 0:
                        break

                    i = 0
                    for story_item in story.get_items():
                        i += 1
                        local_dt = story_item.date_local
                        local_ts = int(local_dt.timestamp())
                        if local_ts in processed_stories_list:
                            continue
                        processed_stories_list.append(local_ts)
                        expire_dt = story_item.expiring_local
                        expire_ts = int(expire_dt.timestamp())
                        print(f"* User {user} has new story item:\n")
                        print(f"Date:\t\t\t{get_date_from_ts(int(local_ts))}")
                        print(f"Expiry:\t\t\t{get_date_from_ts(int(expire_ts))}")
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
                            story_caption_m_body = f"\nCaption:\n\n{story_caption}"
                            story_caption_m_body_html = f"<br>Caption:<br><br>{story_caption}"
                            print(f"Caption:\n\n{story_caption}\n")
                        else:
                            print()

                        story_thumbnail_url = story_item.url
                        story_video_url = story_item.video_url

                        if story_video_url:
                            story_video_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
                            if not os.path.isfile(story_video_filename):
                                if save_pic_video(story_video_url, story_video_filename, local_ts):
                                    print(f"Story video saved to '{story_video_filename}'")

                        m_body_html_pic_saved_text = ""
                        story_image_filename = f'instagram_{user}_story_{local_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                        if story_thumbnail_url:
                            if not os.path.isfile(story_image_filename):
                                if save_pic_video(story_thumbnail_url, story_image_filename, local_ts):
                                    m_body_html_pic_saved_text = f'<br><br><img src="cid:story_pic" width="50%">'
                                    print(f"Story thumbnail image saved to '{story_image_filename}'")
                                    try:
                                        if IMGCAT_PATH and os.path.isfile(IMGCAT_PATH):
                                            subprocess.call((f'echo;{IMGCAT_PATH} {story_image_filename}'), shell=True)
                                            if i < stories_count:
                                                print()
                                    except:
                                        pass

                        try:
                            if csv_file_name:
                                write_csv_entry(csv_file_name, local_dt, "New Story Item", "", story_type)
                        except Exception as e:
                            print(f"Error: cannot write CSV entry - {e}")

                        if status_notification:
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
                print(f"Error while processing story items - {e}")
                print_cur_ts("\nTimestamp:\t\t")

        new_post = False

        cur_h = datetime.now().strftime("%H")
        hours_to_check = list(range(MIN_H1, MAX_H1 + 1)) + list(range(MIN_H2, MAX_H2 + 1))

        if (CHECK_POSTS_IN_HOURS_RANGE and (int(cur_h) in hours_to_check)) or not CHECK_POSTS_IN_HOURS_RANGE:
            if posts_count != posts_count_old and not skip_getting_posts_details:
                likes = 0
                comments = 0
                caption = ""
                pcaption = ""
                tagged_users = []
                shortcode = ""
                location = ""
                likes_users_list = ""
                post_comments_list = ""
                last_post = None
                thumbnail_url = ""
                video_url = ""

                try:
                    posts = instaloader.Profile.from_username(bot.context, user).get_posts()
                    for post in posts:
                        time.sleep(POST_FETCH_DELAY)
                        local_dt = post.date_local
                        local_ts = int(local_dt.timestamp())

                        if local_ts > highestinsta_ts_old:
                            highestinsta_ts = local_ts
                            highestinsta_dt = local_dt
                            new_post = True
                            last_post = post
                            break

                    if csv_file_name:
                        if posts_count > posts_count_old:
                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(highestinsta_ts)), "Posts Count", posts_count_old, posts_count)
                        else:
                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Posts Count", posts_count_old, posts_count)

                    posts_count_old = posts_count

                    if new_post:

                        likes = last_post.likes
                        comments = last_post.comments
                        caption = last_post.caption
                        pcaption = last_post.pcaption
                        tagged_users = last_post.tagged_users
                        shortcode = last_post.shortcode
                        thumbnail_url = last_post.url
                        video_url = last_post.video_url

                except Exception as e:
                    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
                    print(f"Error, retrying in {display_time(r_sleep_time)} - {e}")
                    if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                        print("* Session might not be valid anymore!")
                        if error_notification and not email_sent:
                            m_subject = f"instagram_monitor: session error! (user: {user})"

                            m_body = f"Session might not be valid anymore: {e}{get_cur_ts(nl_ch + nl_ch + 'Timestamp: ')}"
                            print(f"Sending email notification to {RECEIVER_EMAIL}")
                            send_email(m_subject, m_body, "", SMTP_SSL)
                            email_sent = True

                    print_cur_ts("Timestamp:\t\t")

                    time.sleep(r_sleep_time)
                    continue

                try:
                    if new_post and not skip_session and get_more_post_details:
                        if last_post.location:
                            location = last_post.location.name
                        likes_list = last_post.get_likes()
                        for like in likes_list:
                            likes_users_list += "- " + like.username + " [ " + "https://www.instagram.com/" + like.username + "/ ]\n"
                        comments_list = last_post.get_comments()
                        for comment in comments_list:
                            comment_created_at = convert_utc_datetime_to_tz_datetime(comment.created_at_utc, LOCAL_TIMEZONE)
                            post_comments_list += "\n[ " + get_short_date_from_ts(comment_created_at.timestamp()) + " - " + "https://www.instagram.com/" + comment.owner.username + "/ ]\n" + comment.text + "\n"
                except Exception as e:
                    print(f"Error while getting post location / likes list / comments list - {e}")

                if new_post:

                    post_url = f"https://instagram.com/p/{shortcode}/"

                    print(f"* New post for user {user} after {calculate_timespan(int(highestinsta_ts), int(highestinsta_ts_old))} ({get_date_from_ts(int(highestinsta_ts_old))})\n")
                    print(f"Date:\t\t\t{get_date_from_ts(int(highestinsta_ts))}")
                    print(f"Post URL:\t\t{post_url}")
                    print(f"Profile URL:\t\thttps://www.instagram.com/{insta_username}/")
                    print(f"Likes:\t\t\t{likes}")
                    print(f"Comments:\t\t{comments}")
                    print(f"Tagged users:\t\t{tagged_users}")

                    location_mbody = ""
                    if location:
                        location_mbody = "\nLocation: "
                        print(f"Location:\t\t{location}")

                    print(f"Caption:\n\n{caption}\n")

                    likes_users_list_mbody = ""
                    post_comments_list_mbody = ""

                    if likes_users_list:
                        likes_users_list_mbody = "\nLikes list:\n\n"
                        print(f"Likes list:\n{likes_users_list}")

                    if post_comments_list:
                        post_comments_list_mbody = "\nComments list:\n"
                        print(f"Comments list:{post_comments_list}")

                    if video_url:
                        video_filename = f'instagram_{user}_post_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.mp4'
                        if not os.path.isfile(video_filename):
                            if save_pic_video(video_url, video_filename, highestinsta_ts):
                                print(f"Post video saved to '{video_filename}'")

                    m_body_html_pic_saved_text = ""
                    image_filename = f'instagram_{user}_post_{highestinsta_dt.strftime("%Y%m%d_%H%M%S")}.jpeg'
                    if thumbnail_url:
                        if not os.path.isfile(image_filename):
                            if save_pic_video(thumbnail_url, image_filename, highestinsta_ts):
                                m_body_html_pic_saved_text = f'<br><br><img src="cid:post_pic" width="50%">'
                                print(f"Post thumbnail image saved to '{image_filename}'")
                                try:
                                    if IMGCAT_PATH and os.path.isfile(IMGCAT_PATH):
                                        subprocess.call((f'{IMGCAT_PATH} {image_filename}'), shell=True)
                                except:
                                    pass

                    try:
                        if csv_file_name:
                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(highestinsta_ts)), "New Post", "", pcaption)
                    except Exception as e:
                        print(f"Error: cannot write CSV entry - {e}")

                    if status_notification:
                        m_subject = f"Instagram user {user} has a new post - {get_short_date_from_ts(int(highestinsta_ts))} (after {calculate_timespan(int(highestinsta_ts), int(highestinsta_ts_old), show_seconds=False)} - {get_short_date_from_ts(highestinsta_ts_old)})"

                        m_body = f"Instagram user {user} has a new post after {calculate_timespan(int(highestinsta_ts), int(highestinsta_ts_old))} ({get_date_from_ts(int(highestinsta_ts_old))})\n\nDate: {get_date_from_ts(int(highestinsta_ts))}\nPost URL: {post_url}\nProfile URL: https://www.instagram.com/{insta_username}/\nLikes: {likes}\nComments: {comments}\nTagged: {tagged_users}{location_mbody}{location}\nCaption:\n\n{caption}\n{likes_users_list_mbody}{likes_users_list}{post_comments_list_mbody}{post_comments_list}\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                        m_body_html = f"Instagram user <b>{user}</b> has a new post after <b>{calculate_timespan(int(highestinsta_ts), int(highestinsta_ts_old))}</b> ({get_date_from_ts(int(highestinsta_ts_old))}){m_body_html_pic_saved_text}<br><br>Date: <b>{get_date_from_ts(int(highestinsta_ts))}</b><br>Post URL: <a href=\"{post_url}\">{post_url}</a><br>Profile URL: <a href=\"https://www.instagram.com/{insta_username}/\">https://www.instagram.com/{insta_username}/</a><br>Likes: {likes}<br>Comments: {comments}<br>Tagged: {tagged_users}{location_mbody}{location}<br>Caption:<br><br>{escape(str(caption))}<br>{likes_users_list_mbody}{likes_users_list}{post_comments_list_mbody}{escape(post_comments_list)}<br>Check interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts('<br>Timestamp: ')}"

                        print(f"\nSending email notification to {RECEIVER_EMAIL}")
                        if m_body_html_pic_saved_text:
                            send_email(m_subject, m_body, m_body_html, SMTP_SSL, image_filename, "post_pic")
                        else:
                            send_email(m_subject, m_body, m_body_html, SMTP_SSL)

                    highestinsta_ts_old = highestinsta_ts

                    print(f"\nCheck interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                    print_cur_ts("Timestamp:\t\t")

            elif posts_count != posts_count_old and (is_private or skip_getting_posts_details):
                print(f"* Posts number changed for user {user} from {posts_count_old} to {posts_count}\n")

                if status_notification:
                    m_subject = f"Instagram user {user} posts number has changed! ({posts_count_old} -> {posts_count})"

                    m_body = f"Posts number changed for user {user} from {posts_count_old} to {posts_count}\n\nCheck interval: {display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)}){get_cur_ts(nl_ch + 'Timestamp: ')}"
                    print(f"Sending email notification to {RECEIVER_EMAIL}\n")
                    send_email(m_subject, m_body, "", SMTP_SSL)

                posts_count_old = posts_count

                print(f"Check interval:\t\t{display_time(r_sleep_time)} ({get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True)})")
                print_cur_ts("Timestamp:\t\t")

        alive_counter += 1

        if alive_counter >= TOOL_ALIVE_COUNTER:
            print_cur_ts("Alive check, timestamp: ")
            alive_counter = 0

        r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
        time.sleep(r_sleep_time)


if __name__ == "__main__":

    stdout_bck = sys.stdout

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if platform.system() == 'Windows':
            os.system('cls')
        else:
            os.system('clear')
    except:
        print("* Cannot clear the screen contents")

    print(f"Instagram Monitoring Tool v{VERSION}\n")

    parser = argparse.ArgumentParser("instagram_monitor")
    parser.add_argument("INSTAGRAM_USERNAME", nargs="?", help="Instagram username to monitor", type=str)
    parser.add_argument("-u", "--instagram_user_for_session_login", help="Instagram username for session login to fetch list of followers/followings and detailed info about new stories/posts/reels", type=str, metavar="INSTAGRAM_USER")
    parser.add_argument("-p", "--instagram_password_for_session_login", help="Instagram user's password for session login to fetch list of followers/followings and detailed info about new stories/posts/reels, however it is recommended to save the session via 'instaloader -l <instagram_user_for_session_login>'", type=str, metavar="INSTAGRAM_PASSWORD")
    parser.add_argument("-s", "--status_notification", help="Send email notification once user puts new post/reel/story, changes bio, follows new users, changes profile picture or visibility", action='store_true')
    parser.add_argument("-m", "--followers_notification", help="Send email notification once user gets new followers, by default it is disabled", action='store_true')
    parser.add_argument("-e", "--error_notification", help="Disable sending email notifications in case of errors like invalid session", action='store_false')
    parser.add_argument("-c", "--check_interval", help="Time between monitoring checks, in seconds", type=int)
    parser.add_argument("-i", "--check_interval_random_diff_low", help="Value subtracted from check interval to randomize, in seconds", type=int)
    parser.add_argument("-j", "--check_interval_random_diff_high", help="Value added to check interval to randomize, in seconds", type=int)
    parser.add_argument("-b", "--csv_file", help="Write all user activities and profile changes to CSV file", type=str, metavar="CSV_FILENAME")
    parser.add_argument("-k", "--do_not_detect_changed_profile_pic", help="Disable detection of changed user's profile picture", action='store_false')
    parser.add_argument("-l", "--skip_session", help="Skip session login and do not fetch list of followers/followings and more detailed info about new stories/posts/reels", action='store_true')
    parser.add_argument("-f", "--skip_followers", help="Do not fetch list of followers, even if session login is used", action='store_true')
    parser.add_argument("-g", "--skip_followings", help="Do not fetch list of followings, even if session login is used", action='store_true')
    parser.add_argument("-r", "--skip_getting_story_details", help="Do not get detailed info about new stories and its images/videos, even if session login is used; you will still get generic information about new stories", action='store_true')
    parser.add_argument("-w", "--skip_getting_posts_details", help="Do not get detailed info about new posts like its date, caption, URL, tagged users, number of likes and comments, even if session login is used; you will still get information about changed number of posts for the user", action='store_true')
    parser.add_argument("-t", "--get_more_post_details", help="Get more detailed info about new posts like its location and list of comments and likes, only possible if session login is used; if not enabled you will still get generic information about new posts (unless account is private or -w / --skip_getting_posts_details is used)", action='store_true')
    parser.add_argument("-d", "--disable_logging", help="Disable output logging to file 'instagram_monitor_username.log' file", action='store_true')
    parser.add_argument("-z", "--send_test_email_notification", help="Send test email notification to verify SMTP settings defined in the script", action='store_true')
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    local_tz = None
    if LOCAL_TIMEZONE == "Auto":
        try:
            local_tz = get_localzone()
        except NameError:
            pass
        if local_tz:
            LOCAL_TIMEZONE = str(local_tz)
        else:
            print("* Error: Cannot detect local timezone, consider setting LOCAL_TIMEZONE manually !")
            sys.exit(1)

    sys.stdout.write("* Checking internet connectivity ... ")
    sys.stdout.flush()
    check_internet()
    print("")

    if args.send_test_email_notification:
        print("* Sending test email notification ...\n")
        if send_email("instagram_monitor: test email", "This is test email - your SMTP settings seems to be correct !", "", SMTP_SSL, smtp_timeout=5) == 0:
            print("* Email sent successfully !")
        else:
            sys.exit(1)
        sys.exit(0)

    if not args.INSTAGRAM_USERNAME:
        print("* Error: INSTAGRAM_USERNAME argument is required !")
        parser.print_help()
        sys.exit(1)

    skip_session = args.skip_session
    skip_followers = args.skip_followers
    skip_followings = args.skip_followings
    skip_getting_story_details = args.skip_getting_story_details
    skip_getting_posts_details = args.skip_getting_posts_details
    get_more_post_details = args.get_more_post_details

    if args.check_interval:
        INSTA_CHECK_INTERVAL = args.check_interval
        TOOL_ALIVE_COUNTER = TOOL_ALIVE_INTERVAL / INSTA_CHECK_INTERVAL

    if args.check_interval_random_diff_low:
        RANDOM_SLEEP_DIFF_LOW = args.check_interval_random_diff_low

    if args.check_interval_random_diff_high:
        RANDOM_SLEEP_DIFF_HIGH = args.check_interval_random_diff_high

    if args.instagram_user_for_session_login:
        INSTA_USERNAME_FOR_SESSION_LOGIN = args.instagram_user_for_session_login

    if args.instagram_password_for_session_login:
        INSTA_PASSWORD_FOR_SESSION_LOGIN = args.instagram_password_for_session_login

    if not INSTA_USERNAME_FOR_SESSION_LOGIN:
        skip_session = True

    if skip_session:
        skip_followers = True
        skip_followings = True
        get_more_post_details = False
        skip_getting_story_details = True
        mode_of_the_tool = "1 (without session login)"
    else:
        mode_of_the_tool = "2 (with session login)"

    if INSTA_CHECK_INTERVAL <= RANDOM_SLEEP_DIFF_LOW:
        check_interval_low = INSTA_CHECK_INTERVAL
    else:
        check_interval_low = INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW

    if args.do_not_detect_changed_profile_pic is False:
        DETECT_CHANGED_PROFILE_PIC = False

    if args.csv_file:
        csv_enabled = True
        csv_exists = os.path.isfile(args.csv_file)
        try:
            csv_file = open(args.csv_file, 'a', newline='', buffering=1, encoding="utf-8")
        except Exception as e:
            print(f"Error: CSV file cannot be opened for writing - {e}")
            sys.exit(1)
        csv_file.close()
    else:
        csv_enabled = False
        csv_file = None
        csv_exists = False

    if not args.disable_logging:
        INSTA_LOGFILE = f"{INSTA_LOGFILE}_{args.INSTAGRAM_USERNAME}.log"
        sys.stdout = Logger(INSTA_LOGFILE)

    status_notification = args.status_notification
    followers_notification = args.followers_notification

    print(f"* Instagram timers:\t\t\t[check interval: {display_time(check_interval_low)} - {display_time(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH)}]")
    print(f"* Email notifications:\t\t\t[new posts/reels/stories/followings/bio/profile picture/visibility = {status_notification}]\n*\t\t\t\t\t[followers = {followers_notification}] [errors = {args.error_notification}]")
    print(f"* Detect changed profile pic:\t\t{DETECT_CHANGED_PROFILE_PIC}")
    print(f"* Mode of the tool:\t\t\t{mode_of_the_tool}")
    print(f"* Skip session login:\t\t\t{skip_session}")
    print(f"* Skip fetching followers:\t\t{skip_followers}")
    print(f"* Skip fetching followings:\t\t{skip_followings}")
    print(f"* Skip stories details:\t\t\t{skip_getting_story_details}")
    print(f"* Skip posts details:\t\t\t{skip_getting_posts_details}")
    print(f"* Get more posts details:\t\t{get_more_post_details}")
    if CHECK_POSTS_IN_HOURS_RANGE:
        print(f"* Hours for checking new posts:\t\t{MIN_H1:02d}:00 - {MAX_H1:02d}:59, {MIN_H2:02d}:00 - {MAX_H2:02d}:59")
    else:
        print(f"* Hours for checking new posts:\t\t00:00 - 23:59")
    if not args.disable_logging:
        print(f"* Output logging enabled:\t\t{not args.disable_logging} ({INSTA_LOGFILE})")
    else:
        print(f"* Output logging enabled:\t\t{not args.disable_logging}")
    if csv_enabled:
        print(f"* CSV logging enabled:\t\t\t{csv_enabled} ({args.csv_file})")
    else:
        print(f"* CSV logging enabled:\t\t\t{csv_enabled}")
    print(f"* Local timezone:\t\t\t{LOCAL_TIMEZONE}")

    out = f"\nMonitoring Instagram user {args.INSTAGRAM_USERNAME}"
    print(out)
    print("-" * len(out))

    # We define signal handlers only for Linux, Unix & MacOS since Windows has limited number of signals supported
    if platform.system() != 'Windows':
        signal.signal(signal.SIGUSR1, toggle_status_changes_notifications_signal_handler)
        signal.signal(signal.SIGUSR2, toggle_followers_notifications_signal_handler)
        signal.signal(signal.SIGTRAP, increase_check_signal_handler)
        signal.signal(signal.SIGABRT, decrease_check_signal_handler)

    instagram_monitor_user(args.INSTAGRAM_USERNAME, args.error_notification, args.csv_file, csv_exists, skip_session, skip_followers, skip_followings, skip_getting_story_details, skip_getting_posts_details, get_more_post_details)

    sys.stdout = stdout_bck
    sys.exit(0)
