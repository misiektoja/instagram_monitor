#!/usr/bin/env python3
"""
Author: Michal Szymanski <misiektoja-github@rm-rf.ninja>
v1.1

Script implementing real-time monitoring of Instagram users activity:
https://github.com/misiektoja/instagram_monitor/

Python pip3 requirements:

instaloader
pytz
python-dateutil
requests
"""

VERSION = 1.1

# ---------------------------
# CONFIGURATION SECTION START
# ---------------------------

# Session login is needed for some functionalities like getting list of followings & followers
# In such case we need Instagram username & password to monitor other user
# Instead of typing the username & password below it is recommended to keep it empty here and log in via:
# <instaloader_location>/bin/instaloader -l username
INSTA_USERNAME = ''
INSTA_PASSWORD = ''

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

# How often do we perform checks for user activity; in seconds
INSTA_CHECK_INTERVAL = 5400  # 1,5 hours

# Specify your local time zone so we convert Instagram API timestamps to your time (for example: 'Europe/Warsaw')
LOCAL_TIMEZONE = 'Europe/Warsaw'

# How often do we perform alive check by printing "alive check" message in the output; in seconds
TOOL_ALIVE_INTERVAL = 21600  # 6 hours

# URL we check in the beginning to make sure we have internet connectivity
CHECK_INTERNET_URL = 'http://www.google.com/'

# Default value for initial checking of internet connectivity; in seconds
CHECK_INTERNET_TIMEOUT = 5

# To avoid captcha checks and detection of automated tools we randomize INSTA_CHECK_INTERVAL via randomize_number function
# We pick number from range: INSTA_CHECK_INTERVAL-RANDOM_SLEEP_DIFF_LOW <-> INSTA_CHECK_INTERVAL+RANDOM_SLEEP_DIFF_HIGH
RANDOM_SLEEP_DIFF_LOW = 900  # -15 min
RANDOM_SLEEP_DIFF_HIGH = 180  # +3 min

# Do we want to check for new posts only in specified hours ?
CHECK_POSTS_IN_HOURS_RANGE = False

# If CHECK_POSTS_IN_HOURS_RANGE==True, here comes the first hours range to check
# In the example below we check between 00:00-04:00
MIN_H1 = 0
MAX_H1 = 4

# If CHECK_POSTS_IN_HOURS_RANGE==True, here comes the second hours range to check
# In the example below we check between 11:00-23:00
MIN_H2 = 11
MAX_H2 = 23

# The name of the .log file; the tool by default will output its messages to instagram_monitor_username.log file
INSTA_LOGFILE = "instagram_monitor"

# Value used by signal handlers increasing/decreasing the user activity check (INSTA_CHECK_INTERVAL); in seconds
INSTA_CHECK_SIGNAL_VALUE = 300  # 5 min

# -------------------------
# CONFIGURATION SECTION END
# -------------------------

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

import sys
import time
import string
import json
import os
from datetime import datetime
from dateutil import relativedelta
import calendar
import requests as req
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
import re
import ipaddress
import instaloader


# Logger class to output messages to stdout and log file
class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.logfile = open(filename, "a", buffering=1)

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
        print("No connectivity, please check your network -", e)
        sys.exit(1)
    return False


# Function to convert absolute value of seconds to human readable format
def display_time(seconds, granularity=2):
    intervals = (
        ('years', 31556952),  # approximation
        ('months', 2629746),  # approximation
        ('weeks', 604800),  # 60 * 60 * 24 * 7
        ('days', 86400),    # 60 * 60 * 24
        ('hours', 3600),    # 60 * 60
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
                result.append("{} {}".format(value, name))
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
    elif type(timestamp1) is datetime:
        dt1 = timestamp1
        ts1 = int(round(dt1.timestamp()))
    else:
        return ""

    if type(timestamp2) is int:
        dt2 = datetime.fromtimestamp(int(ts2))
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
                result.append("{} {}".format(interval, name))
        return ', '.join(result[:granularity])
    else:
        return '0 seconds'


# Function to send email notification
def send_email(subject, body, body_html, use_ssl, image_file="", image_name="image1"):
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
            smtpObj = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            smtpObj.starttls(context=ssl_context)
        else:
            smtpObj = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
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
        csv_file = open(csv_file_name, 'a', newline='', buffering=1)
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
    return (str(ts_str) + str(calendar.day_abbr[(datetime.fromtimestamp(int(time.time()))).weekday()]) + ", " + str(datetime.fromtimestamp(int(time.time())).strftime("%d %b %Y, %H:%M:%S")))


# Function to print the current timestamp in human readable format; eg. Sun, 21 Apr 2024, 15:08:45
def print_cur_ts(ts_str=""):
    print(get_cur_ts(str(ts_str)))
    print("-----------------------------------------------------------------------------------")


# Function to return the timestamp in human readable format (long version); eg. Sun, 21 Apr 2024, 15:08:45
def get_date_from_ts(ts):
    return (str(calendar.day_abbr[(datetime.fromtimestamp(ts)).weekday()]) + " " + str(datetime.fromtimestamp(ts).strftime("%d %b %Y, %H:%M:%S")))


# Function to return the timestamp in human readable format (short version); eg. Sun 21 Apr 15:08
def get_short_date_from_ts(ts):
    return (str(calendar.day_abbr[(datetime.fromtimestamp(ts)).weekday()]) + " " + str(datetime.fromtimestamp(ts).strftime("%d %b %H:%M")))


# Function to return the timestamp in human readable format (only hour, minutes and optionally seconds): eg. 15:08:12
def get_hour_min_from_ts(ts, show_seconds=False):
    if show_seconds:
        out_strf = "%H:%M:%S"
    else:
        out_strf = "%H:%M"
    return (str(datetime.fromtimestamp(ts).strftime(out_strf)))


# Function to return the range between two timestamps; eg. Sun 21 Apr 14:09 - 14:15
def get_range_of_dates_from_tss(ts1, ts2, between_sep=" - ", short=False):
    ts1_strf = datetime.fromtimestamp(ts1).strftime("%Y%m%d")
    ts2_strf = datetime.fromtimestamp(ts2).strftime("%Y%m%d")

    if ts1_strf == ts2_strf:
        if short:
            out_str = get_short_date_from_ts(ts1) + between_sep + get_hour_min_from_ts(ts2)
        else:
            out_str = get_date_from_ts(ts1) + between_sep + get_hour_min_from_ts(ts2, show_seconds=True)
    else:
        if short:
            out_str = get_short_date_from_ts(ts1) + between_sep + get_short_date_from_ts(ts2)
        else:
            out_str = get_date_from_ts(ts1) + between_sep + get_date_from_ts(ts2)
    return (str(out_str))


# Function to convert UTC string returned by Instagram API to datetime object in specified timezone
def convert_utc_datetime_to_tz_datetime(dt_utc, timezone):
    old_tz = pytz.timezone("UTC")
    new_tz = pytz.timezone(timezone)
    dt_new_tz = old_tz.localize(dt_utc).astimezone(new_tz)
    return dt_new_tz


# Signal handler for SIGUSR1 allowing to switch email notifications for new posts/stories/followings/bio
def toggle_status_changes_notifications_signal_handler(sig, frame):
    global status_notification
    status_notification = not status_notification
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Email notifications: [new posts/stories/followings/bio = " + str(status_notification) + "]")
    print_cur_ts("Timestamp:\t\t")


# Signal handler for SIGUSR2 allowing to switch email notifications for new followers
def toggle_followers_notifications_signal_handler(sig, frame):
    global followers_notification
    followers_notification = not followers_notification
    sig_name = signal.Signals(sig).name
    print(f"* Signal {sig_name} received")
    print(f"* Email notifications: [followers = " + str(followers_notification) + "]")
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
    print("* Instagram timers: [check interval: " + display_time(check_interval_low) + " - " + display_time(INSTA_CHECK_INTERVAL+RANDOM_SLEEP_DIFF_HIGH) + "]")
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
    print("* Instagram timers: [check interval: " + display_time(check_interval_low) + " - " + display_time(INSTA_CHECK_INTERVAL+RANDOM_SLEEP_DIFF_HIGH) + "]")
    print_cur_ts("Timestamp:\t\t")


# Main function monitoring activity of the specified Instagram user
def instagram_monitor_user(user, error_notification, csv_file_name, csv_exists, skip_session, skip_followers, skip_followings):

    try:
        if csv_file_name:
            csv_file = open(csv_file_name, 'a', newline='', buffering=1)
            csvwriter = csv.DictWriter(csv_file, fieldnames=csvfieldnames, quoting=csv.QUOTE_NONNUMERIC)
            if not csv_exists:
                csvwriter.writeheader()
            csv_file.close()
    except Exception as e:
        print("* Error -", e)

    followers_count = 0
    followings_count = 0
    r_sleep_time = 0
    followers_followings_fetched = False

    try:
        bot = instaloader.Instaloader()
        if (INSTA_USERNAME and INSTA_PASSWORD) and not skip_session:
            bot.login(user=INSTA_USERNAME, passwd=INSTA_PASSWORD)
        elif INSTA_USERNAME and not INSTA_PASSWORD and not skip_session:
            # log in via: <instaloader_location>/bin/instaloader -l username
            bot.load_session_from_file(INSTA_USERNAME)
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
    except Exception as e:
        print("Error -", e)
        sys.exit(1)

    story = False

    followers_old_count = followers_count
    followings_old_count = followings_count
    bio_old = bio
    posts_count_old = posts_count

    print("\nUsername:\t\t" + str(insta_username))
    print("User ID:\t\t" + str(insta_userid))
    print("URL:\t\t\t" + "https://www.instagram.com/" + insta_username + "/")
    print("Posts number:\t\t" + str(posts_count))
    print("Followers Count:\t" + str(followers_count))
    print("Followings Count:\t" + str(followings_count))
    print("Story available:\t" + str(has_story))
    print("Public profile:\t\t" + str(not is_private))
    print("Bio:\n\n" + str(bio) + "\n")
    print_cur_ts("Timestamp:\t\t")

    if has_story:
        story = True

    insta_followers_file = "instagram_" + str(user) + "_followers.json"
    insta_followings_file = "instagram_" + str(user) + "_followings.json"
    followers = []
    followings = []
    followers_old = followers
    followings_old = followings
    followers_read = []
    followings_read = []

    try:

        if os.path.isfile(insta_followers_file):
            with open(insta_followers_file, 'r') as f:
                followers_read = json.load(f)
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
            print("* Followers number changed for user " + user + " from " + str(followers_old_count) + " to " + str(followers_count) + " (" + followers_diff_str + ")")
            followers_followings_fetched = True

            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followers Count", followers_old_count, followers_count)
            except Exception as e:
                print("* Cannot write CSV entry -", e)

        if ((followers_count != followers_old_count) or (followers_count > 0 and not followers)) and not skip_session and not skip_followers and not is_private:
            print("\n* Getting followers ...")
            followers_followings_fetched = True

            followers = [follower.username for follower in profile.get_followers()]
            followers_to_save = []
            followers_count = profile.followers
            followers_to_save.append(followers_count)
            followers_to_save.append(followers)
            with open(insta_followers_file, 'w') as f:
                json.dump(followers_to_save, f, indent=2)
                print(f"* Followers saved to file '{insta_followers_file}'")

        if ((followers_count != followers_old_count) and (followers != followers_old)) and not skip_session and not skip_followers and not is_private:
            a, b = set(followers_old), set(followers)
            removed_followers = list(a - b)
            added_followers = list(b - a)
            added_followers_list = ""
            removed_followers_list = ""

            print()

            if removed_followers:
                print("Removed followers:\n")
                for f_in_list in removed_followers:
                        print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                        removed_followers_list = removed_followers_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                        try:
                            if csv_file_name:
                                write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followers", "", f_in_list)
                        except Exception as e:
                            print("* Cannot write CSV entry -", e)
                print()

            if added_followers:
                print("Added followers:\n")
                for f_in_list in added_followers:
                        print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                        added_followers_list = added_followers_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                        try:
                            if csv_file_name:
                                write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followers", "", f_in_list)
                        except Exception as e:
                            print("* Cannot write CSV entry -", e)
                print()

        if os.path.isfile(insta_followings_file):
            with open(insta_followings_file, 'r') as f:
                followings_read = json.load(f)
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
            print("* Followings number changed by user " + user + " from " + str(followings_old_count) + " to " + str(followings_count) + " (" + followings_diff_str + ")")
            followers_followings_fetched = True
            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followings Count", followings_old_count, followings_count)
            except Exception as e:
                print("* Cannot write CSV entry -", e)

        if ((followings_count != followings_old_count) or (followings_count > 0 and not followings)) and not skip_session and not skip_followings and not is_private:
            print("\n* Getting followings ...")
            followers_followings_fetched = True

            followings = [followee.username for followee in profile.get_followees()]
            followings_to_save = []
            followings_count = profile.followees
            followings_to_save.append(followings_count)
            followings_to_save.append(followings)
            with open(insta_followings_file, 'w') as f:
                json.dump(followings_to_save, f, indent=2)
                print(f"* Followings saved to file '{insta_followings_file}'")

        if ((followings_count != followings_old_count) and (followings != followings_old)) and not skip_session and not skip_followings and not is_private:
            a, b = set(followings_old), set(followings)
            removed_followings = list(a - b)
            added_followings = list(b - a)
            added_followings_list = ""
            removed_followings_list = ""

            print()

            if removed_followings:
                print("Removed followings:\n")
                for f_in_list in removed_followings:
                        print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                        removed_followings_list = removed_followings_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                        try:
                            if csv_file_name:
                                write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followings", "", f_in_list)
                        except Exception as e:
                            print("* Cannot write CSV entry -", e)
                print()

            if added_followings:
                print("Added followings:\n")
                for f_in_list in added_followings:
                        print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                        added_followings_list = added_followings_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                        try:
                            if csv_file_name:
                                write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followings", "", f_in_list)
                        except Exception as e:
                            print("* Cannot write CSV entry -", e)
                print()

    except Exception as e:
        print("Error -", e)

    if not skip_session and not skip_followers and not is_private:
        followers_old = followers
    else:
        followers = followers_old

    if not skip_session and not skip_followings and not is_private:
        followings_old = followings
    else:
        followings = followings_old

    followers_old_count = followers_count
    followings_old_count = followings_count

    if followers_followings_fetched:
        print_cur_ts("\nTimestamp:\t\t")

    highestinsta_ts = 0
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

    if int(posts_count) >= 1 and not is_private:
        try:
            time.sleep(NEXT_OPERATION_DELAY)
            posts = instaloader.Profile.from_username(bot.context, user).get_posts()

            for post in posts:
                time.sleep(POST_FETCH_DELAY)
                local_ts = int(post.date_local.timestamp())

                if local_ts > highestinsta_ts:
                    highestinsta_ts = local_ts
                    last_post = post

            likes = last_post.likes
            comments = last_post.comments
            caption = last_post.caption
            pcaption = last_post.pcaption
            tagged_users = last_post.tagged_users
            shortcode = last_post.shortcode

            # We disable fetching location, likes and comments due to errors after recent Instagram changes (HTTP Error 400)
            """
            if not skip_session:
                if last_post.location:
                    location=last_post.location.name
                likes_list=last_post.get_likes()
                for like in likes_list:
                    likes_users_list=likes_users_list + "- " + like.username + " [ " + "https://www.instagram.com/" + like.username + "/ ]\n"
                comments_list=last_post.get_comments()
                for comment in comments_list:
                    comment_created_at=convert_utc_datetime_to_tz_datetime(comment.created_at_utc,LOCAL_TIMEZONE)
                    post_comments_list=post_comments_list + "\n[ " + get_short_date_from_ts(comment_created_at.timestamp()) + " - " + "https://www.instagram.com/" + comment.owner.username + "/ ]\n" + comment.text + "\n"
            """
        except Exception as e:
            print("Error -", e)
            sys.exit(1)

        post_url = "https://instagram.com/p/" + str(shortcode) + "/"

        print("* Newest post for user " + str(user) + ":\n")
        print("Date:\t\t\t" + get_date_from_ts(int(highestinsta_ts)) + " (" + str(calculate_timespan(int(time.time()), int(highestinsta_ts))) + " ago)")
        print("Post URL:\t\t" + str(post_url))
        print("Profile URL:\t\t" + "https://www.instagram.com/" + insta_username + "/")
        print("Likes:\t\t\t" + str(likes))
        print("Comments:\t\t" + str(comments))
        print("Tagged users:\t\t" + str(tagged_users))

        if location:
            print("Location:\t\t" + str(location))

        print("Caption:\n\n" + str(caption) + "\n")

        if likes_users_list:
            print("Likes list:\n")
            print(likes_users_list)

        if post_comments_list:
            print("Comments list:")
            print(post_comments_list)

        print_cur_ts("Timestamp:\t\t")

        highestinsta_ts_old = highestinsta_ts

    else:
        highestinsta_ts_old = int(time.time())

    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
    time.sleep(r_sleep_time)

    alive_counter = 0

    while True:
        last_output = []
        try:
            profile = instaloader.Profile.from_username(bot.context, user)
            time.sleep(NEXT_OPERATION_DELAY)
            email_sent = False
            new_post = False
            followers_count = profile.followers
            followings_count = profile.followees
            bio = profile.biography
            posts_count = profile.mediacount
            has_story = profile.has_public_story
            is_private = profile.is_private
        except Exception as e:
            r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
            print("Retrying in", display_time(r_sleep_time), ", error -", e)
            if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                print("* Session might not be valid anymore!")
                if error_notification and not email_sent:
                    m_subject = "instagram_monitor: session error! (user: " + str(user) + ")"
                    m_body = "Session might not be valid anymore: " + str(e) + get_cur_ts("\n\nTimestamp: ")
                    print("Sending email notification to", RECEIVER_EMAIL)
                    send_email(m_subject, m_body, "", SMTP_SSL)
                    email_sent = True

            print_cur_ts("Timestamp:\t\t")
            time.sleep(r_sleep_time)
            continue

        if (next((s for s in last_output if "HTTP redirect from" in s), None)):
            r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
            print("* Session might not be valid anymore!")
            print("Retrying in", display_time(r_sleep_time))
            if error_notification and not email_sent:
                m_subject = "instagram_monitor: session error! (user: " + str(user) + ")"
                m_body = "Session might not be valid anymore: " + str(last_output) + get_cur_ts("\n\nTimestamp: ")
                print("Sending email notification to", RECEIVER_EMAIL)
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
            print("* Followings number changed by user " + user + " from " + str(followings_old_count) + " to " + str(followings_count) + " (" + followings_diff_str + ")")
            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followings Count", followings_old_count, followings_count)
            except Exception as e:
                print("* Cannot write CSV entry -", e)

            added_followings_list = ""
            removed_followings_list = ""
            added_followings_mbody = ""
            removed_followings_mbody = ""

            if not skip_session and not skip_followings and not is_private:
                try:
                    followings = []
                    followings = [followee.username for followee in profile.get_followees()]
                    followings_to_save = []
                    followings_count = profile.followees
                    if not followings and followings_count > 0:
                        print("* Empty followings list returned")
                    else:
                        followings_to_save.append(followings_count)
                        followings_to_save.append(followings)
                        with open(insta_followings_file, 'w') as f:
                            json.dump(followings_to_save, f, indent=2)
                except Exception as e:
                    followings = followings_old
                    print("Error -", e)

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
                                    print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                                    removed_followings_list = removed_followings_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followings", "", f_in_list)
                                    except Exception as e:
                                        print("* Cannot write CSV entry -", e)
                            print()

                        if added_followings:
                            print("Added followings:\n")
                            added_followings_mbody = "\nAdded followings:\n\n"
                            for f_in_list in added_followings:
                                    print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                                    added_followings_list = added_followings_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followings", "", f_in_list)
                                    except Exception as e:
                                        print("* Cannot write CSV entry -", e)
                            print()

                    followings_old = followings

            m_subject = f"Instagram user {user} followings number has changed! ({followings_diff_str}, {followings_old_count} -> {followings_count})"

            if not skip_session and not skip_followings and not is_private:
                m_body = f"Followings number changed by user {user} from {followings_old_count} to {followings_count} ({followings_diff_str})\n{removed_followings_mbody}{removed_followings_list}{added_followings_mbody}{added_followings_list}\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")
            else:
                m_body = f"Followings number changed by user {user} from {followings_old_count} to {followings_count} ({followings_diff_str})\n\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")

            if status_notification:
                print("Sending email notification to", RECEIVER_EMAIL)
                send_email(m_subject, m_body, "", SMTP_SSL)
                email_sent = True

            followings_old_count = followings_count

            print("Check interval:\t\t" + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time())-r_sleep_time, int(time.time()), short=True) + ")")
            print_cur_ts("Timestamp:\t\t")

        if followers_count != followers_old_count:
            followers_diff = followers_count - followers_old_count
            followers_diff_str = ""
            if followers_diff > 0:
                followers_diff_str = "+" + str(followers_diff)
            else:
                followers_diff_str = str(followers_diff)
            print("* Followers number changed for user " + user + " from " + str(followers_old_count) + " to " + str(followers_count) + " (" + followers_diff_str + ")")

            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Followers Count", followers_old_count, followers_count)
            except Exception as e:
                print("* Cannot write CSV entry -", e)

            added_followers_list = ""
            removed_followers_list = ""
            added_followers_mbody = ""
            removed_followers_mbody = ""

            if not skip_session and not skip_followers and not is_private:
                try:
                    followers = []
                    followers = [follower.username for follower in profile.get_followers()]
                    followers_to_save = []
                    followers_count = profile.followers
                    if not followers and followers_count > 0:
                        print("* Empty followers list returned")
                    else:
                        followers_to_save.append(followers_count)
                        followers_to_save.append(followers)
                        with open(insta_followers_file, 'w') as f:
                            json.dump(followers_to_save, f, indent=2)
                except Exception as e:
                    followers = followers_old
                    print("Error -", e)

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
                                    print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                                    removed_followers_list = removed_followers_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Removed Followers", "", f_in_list)
                                    except Exception as e:
                                        print("* Cannot write CSV entry -", e)
                            print()

                        if added_followers:
                            print("Added followers:\n")
                            added_followers_mbody = "\nAdded followers:\n\n"
                            for f_in_list in added_followers:
                                    print("- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]")
                                    added_followers_list = added_followers_list + "- " + f_in_list + " [ " + "https://www.instagram.com/" + f_in_list + "/ ]\n"
                                    try:
                                        if csv_file_name:
                                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Added Followers", "", f_in_list)
                                    except Exception as e:
                                        print("* Cannot write CSV entry -", e)
                            print()

                    followers_old = followers

            m_subject = f"Instagram user {user} followers number has changed! ({followers_diff_str}, {followers_old_count} -> {followers_count})"

            if not skip_session and not skip_followers and not is_private:
                m_body = f"Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})\n{removed_followers_mbody}{removed_followers_list}{added_followers_mbody}{added_followers_list}\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")
            else:
                m_body = f"Followers number changed for user {user} from {followers_old_count} to {followers_count} ({followers_diff_str})\n\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")

            if status_notification and followers_notification:
                print("Sending email notification to", RECEIVER_EMAIL)
                send_email(m_subject, m_body, "", SMTP_SSL)
                email_sent = True

            followers_old_count = followers_count

            print("Check interval:\t\t" + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")")
            print_cur_ts("Timestamp:\t\t")

        if bio != bio_old:
            print("* Bio changed for user " + str(user) + " !")
            print("Old bio:\n\n" + str(bio_old) + "\n")
            print("New bio:\n\n" + str(bio) + "\n")

            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "Bio Changed", bio_old, bio)
            except Exception as e:
                print("* Cannot write CSV entry -", e)

            m_subject = "Instagram user " + user + " bio has changed!"
            m_body = "Instagram user " + user + " bio has changed" + "\n\nOld bio:\n\n" + str(bio_old) + "\n\nNew bio:\n\n" + str(bio) + "\n\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")

            if status_notification:
                print("Sending email notification to", RECEIVER_EMAIL)
                send_email(m_subject, m_body, "", SMTP_SSL)
                email_sent = True

            bio_old = bio
            print("Check interval:\t\t" + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")")
            print_cur_ts("Timestamp:\t\t")

        if has_story and not story:
            print("* New story for user " + str(user) + " !")
            story = True

            try:
                if csv_file_name:
                    write_csv_entry(csv_file_name, datetime.fromtimestamp(int(time.time())), "New Story", "", "")
            except Exception as e:
                print("* Cannot write CSV entry -", e)

            m_subject = "Instagram user " + user + " has a new story!"
            m_body = "Instagram user " + user + " has a new story" + "\n\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")

            if status_notification:
                print("Sending email notification to", RECEIVER_EMAIL)
                send_email(m_subject, m_body, "", SMTP_SSL)
                email_sent = True

            print("Check interval:\t\t" + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")")
            print_cur_ts("Timestamp:\t\t")

        if not has_story and story:
            print("* Story for user " + str(user) + " disappeared !")
            print("Check interval:\t\t" + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")")
            print_cur_ts("Timestamp:\t\t")
            story = False

        new_post = False

        cur_h = datetime.now().strftime("%H")
        hours_to_check = list(range(MIN_H1, MAX_H1 + 1)) + list(range(MIN_H2, MAX_H2 + 1))

        if (CHECK_POSTS_IN_HOURS_RANGE and (int(cur_h) in hours_to_check)) or not CHECK_POSTS_IN_HOURS_RANGE:
            if posts_count != posts_count_old and not is_private:
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
                try:
                    posts = instaloader.Profile.from_username(bot.context, user).get_posts()
                    for post in posts:
                        time.sleep(POST_FETCH_DELAY)
                        local_ts = int(post.date_local.timestamp())

                        if local_ts > highestinsta_ts_old:
                            highestinsta_ts = local_ts
                            new_post = True
                            last_post = post
                            break
                    if csv_file_name:
                        write_csv_entry(csv_file_name, datetime.fromtimestamp(int(highestinsta_ts)), "Posts Count", posts_count_old, posts_count)
                    posts_count_old = posts_count

                    if new_post:

                        likes = last_post.likes
                        comments = last_post.comments
                        caption = last_post.caption
                        pcaption = last_post.pcaption
                        tagged_users = last_post.tagged_users
                        shortcode = last_post.shortcode

                        # We disable fetching location, likes and comments due to errors after recent Instagram changes (HTTP Error 400)
                        """
                        if not skip_session:
                            if last_post.location:
                                location=last_post.location.name
                            likes_list=last_post.get_likes()
                            for like in likes_list:
                                likes_users_list=likes_users_list + "- " + like.username + " [ " + "https://www.instagram.com/" + like.username + "/ ]\n"
                            comments_list=last_post.get_comments()
                            for comment in comments_list:
                                comment_created_at=convert_utc_datetime_to_tz_datetime(comment.created_at_utc,LOCAL_TIMEZONE)
                                post_comments_list=post_comments_list + "\n[ " + get_short_date_from_ts(comment_created_at.timestamp()) + " - " + "https://www.instagram.com/" + comment.owner.username + "/ ]\n" + comment.text + "\n"
                        """

                except Exception as e:
                    r_sleep_time = randomize_number(INSTA_CHECK_INTERVAL, RANDOM_SLEEP_DIFF_LOW, RANDOM_SLEEP_DIFF_HIGH)
                    print("Retrying in", display_time(r_sleep_time), ", error -", e)
                    if 'Redirected' in str(e) or 'login' in str(e) or 'Forbidden' in str(e) or 'Wrong' in str(e) or 'Bad Request' in str(e):
                        print("* Session might not be valid anymore!")
                        if error_notification and not email_sent:
                            m_subject = "instagram_monitor: session error! (user: " + str(user) + ")"
                            m_body = "Session might not be valid anymore: " + str(e) + get_cur_ts("\n\nTimestamp: ")
                            print("Sending email notification to", RECEIVER_EMAIL)
                            send_email(m_subject, m_body, "", SMTP_SSL)
                            email_sent = True

                    print_cur_ts("Timestamp:\t\t")

                    time.sleep(r_sleep_time)
                    continue

                if new_post:

                    post_url = "https://instagram.com/p/" + str(shortcode) + "/"

                    print("* New post for user " + str(user) + " after " + calculate_timespan(int(highestinsta_ts), int(highestinsta_ts_old)) + " (" + get_date_from_ts(int(highestinsta_ts_old)) + ")\n")
                    print("Date:\t\t\t" + get_date_from_ts(int(highestinsta_ts)))
                    print("Post URL:\t\t" + str(post_url))
                    print("Profile URL:\t\t" + "https://www.instagram.com/" + insta_username + "/")
                    print("Likes:\t\t\t" + str(likes))
                    print("Comments:\t\t" + str(comments))
                    print("Tagged users:\t\t" + str(tagged_users))

                    location_mbody = ""
                    if location:
                        location_mbody = "\nLocation: "
                        print("Location:\t\t" + str(location))

                    print("Caption:\n\n" + str(caption) + "\n")

                    likes_users_list_mbody = ""
                    post_comments_list_mbody = ""

                    if likes_users_list:
                        likes_users_list_mbody = "\nLikes list:\n\n"
                        print("Likes list:\n")
                        print(likes_users_list)

                    if post_comments_list:
                        post_comments_list_mbody = "\nComments list:\n"
                        print("Comments list:")
                        print(post_comments_list)

                    try:
                        if csv_file_name:
                            write_csv_entry(csv_file_name, datetime.fromtimestamp(int(highestinsta_ts)), "New Post", "", pcaption)
                    except Exception as e:
                        print("* Cannot write CSV entry -", e)

                    m_subject = "Instagram user " + user + " has a new post - " + get_short_date_from_ts(int(highestinsta_ts)) + " (after " + calculate_timespan(int(highestinsta_ts), int(highestinsta_ts_old), show_seconds=False) + " - " + get_short_date_from_ts(highestinsta_ts_old) + ")"
                    m_body = "Instagram user " + user + " has a new post after " + calculate_timespan(int(highestinsta_ts), int(highestinsta_ts_old)) + " (" + get_date_from_ts(int(highestinsta_ts_old)) + ")\n\nDate: " + get_date_from_ts(int(highestinsta_ts)) + "\nPost URL: " + str(post_url) + "\nProfile URL: " + "https://www.instagram.com/" + insta_username + "/" + "\nLikes: " + str(likes) + "\nComments: " + str(comments) + "\nTagged: " + str(tagged_users) + location_mbody + str(location) + "\nCaption:\n\n" + str(caption) + "\n" + likes_users_list_mbody + likes_users_list + post_comments_list_mbody + post_comments_list + "\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")

                    if status_notification:
                        print("Sending email notification to", RECEIVER_EMAIL)
                        send_email(m_subject, m_body, "", SMTP_SSL)
                        email_sent = True

                    highestinsta_ts_old = highestinsta_ts

                    print("Check interval:\t\t" + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")")
                    print_cur_ts("Timestamp:\t\t")

            elif posts_count != posts_count_old and is_private:
                print("* Posts number changed for user " + user + " from " + str(posts_count_old) + " to " + str(posts_count))

                m_subject = f"Instagram user {user} posts number has changed! ({posts_count_old} -> {posts_count})"

                m_body = f"Posts number changed for user {user} from {posts_count_old} to {posts_count}\n\nCheck interval: " + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")" + get_cur_ts("\nTimestamp: ")

                if status_notification:
                    print("Sending email notification to", RECEIVER_EMAIL)
                    send_email(m_subject, m_body, "", SMTP_SSL)
                    email_sent = True

                posts_count_old = posts_count

                print("Check interval:\t\t" + str(display_time(r_sleep_time)) + " (" + get_range_of_dates_from_tss(int(time.time()) - r_sleep_time, int(time.time()), short=True) + ")")
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
        os.system('clear')
    except:
        print("* Cannot clear the screen contents")

    print("Instagram Monitoring Tool", VERSION, "\n")

    parser = argparse.ArgumentParser("instagram_monitor")
    parser.add_argument("user", nargs="?", help="Instagram username", type=str)
    parser.add_argument("-b", "--csv_file", help="Write info about new posts & stories to CSV file", type=str, metavar="CSV_FILENAME")
    parser.add_argument("-u", "--instagram_user", help="Instagram user to use to fetch followers/followings", type=str, metavar="INSTAGRAM_USER")
    parser.add_argument("-p", "--instagram_password", help="Instagram user's password to use to fetch followers/followings, however it is recommended to save the session via 'instaloader -l username'", type=str, metavar="INSTAGRAM_PASSWORD")
    parser.add_argument("-s", "--status_notification", help="Send email notification once user puts new post/story, changes bio or follows new users", action='store_true')
    parser.add_argument("-m", "--followers_notification", help="Send email notification once user gets new followers, by default it is disabled", action='store_true')
    parser.add_argument("-e", "--error_notification", help="Disable sending email notifications in case of errors like invalid password", action='store_false')
    parser.add_argument("-l", "--skip_session", help="Skip session login and do not fetch followers/followings", action='store_true')
    parser.add_argument("-f", "--skip_followers", help="Do not fetch followers", action='store_true')
    parser.add_argument("-g", "--skip_followings", help="Do not fetch followings", action='store_true')
    parser.add_argument("-c", "--check_interval", help="Time between monitoring checks, in seconds", type=int)
    parser.add_argument("-i", "--check_interval_random_diff_low", help="Value substracted from check interval to randomize, in seconds", type=int)
    parser.add_argument("-j", "--check_interval_random_diff_high", help="Value added to check interval to randomize, in seconds", type=int)
    parser.add_argument("-d", "--disable_logging", help="Disable logging to file 'instagram_monitor_user.log' file", action='store_true')
    args = parser.parse_args()

    if not args.user:
        print("* user argument is required\n")
        parser.print_help()
        sys.exit(1)

    sys.stdout.write("* Checking internet connectivity ... ")
    sys.stdout.flush()
    check_internet()
    print("")

    skip_session = args.skip_session

    if args.check_interval:
        INSTA_CHECK_INTERVAL = args.check_interval
        TOOL_ALIVE_COUNTER = TOOL_ALIVE_INTERVAL / INSTA_CHECK_INTERVAL

    if args.check_interval_random_diff_low:
        RANDOM_SLEEP_DIFF_LOW = args.check_interval_random_diff_low

    if args.check_interval_random_diff_high:
        RANDOM_SLEEP_DIFF_HIGH = args.check_interval_random_diff_high

    if args.instagram_user:
        INSTA_USERNAME = args.instagram_user

    if args.instagram_password:
        INSTA_PASSWORD = args.instagram_password

    if not INSTA_USERNAME:
        skip_session = True

    if args.csv_file:
        csv_enabled = True
        csv_exists = os.path.isfile(args.csv_file)
        try:
            csv_file = open(args.csv_file, 'a', newline='', buffering=1)
        except Exception as e:
            print("\n* Error, CSV file cannot be opened for writing -", e)
            sys.exit(1)
        csv_file.close()
    else:
        csv_enabled = False
        csv_file = None
        csv_exists = False

    if not args.disable_logging:
        INSTA_LOGFILE = INSTA_LOGFILE + "_" + str(args.user) + ".log"
        sys.stdout = Logger(INSTA_LOGFILE)

    if INSTA_CHECK_INTERVAL <= RANDOM_SLEEP_DIFF_LOW:
        check_interval_low = INSTA_CHECK_INTERVAL
    else:
        check_interval_low = INSTA_CHECK_INTERVAL - RANDOM_SLEEP_DIFF_LOW

    status_notification = args.status_notification
    followers_notification = args.followers_notification

    print("* Instagram timers: [check interval: " + display_time(check_interval_low) + " - " + display_time(INSTA_CHECK_INTERVAL + RANDOM_SLEEP_DIFF_HIGH) + "]")
    print("* Email notifications: [new posts/stories/followings/bio = " + str(status_notification) + "] [followers = " + str(followers_notification) + "] [errors = " + str(args.error_notification) + "]")
    print("* Output logging disabled:", str(args.disable_logging))
    print("* Skip session login and fetching followers/followings:", str(skip_session))
    print("* Skip fetching followers:", str(args.skip_followers))
    print("* Skip fetching followings:", str(args.skip_followings))
    print("* CSV logging enabled:", str(csv_enabled))

    out = "\nMonitoring Instagram user %s" % args.user
    print(out)
    print("-" * len(out))

    signal.signal(signal.SIGUSR1, toggle_status_changes_notifications_signal_handler)
    signal.signal(signal.SIGUSR2, toggle_followers_notifications_signal_handler)
    signal.signal(signal.SIGTRAP, increase_check_signal_handler)
    signal.signal(signal.SIGABRT, decrease_check_signal_handler)

    instagram_monitor_user(args.user, args.error_notification, args.csv_file, csv_exists, skip_session, args.skip_followers, args.skip_followings)

    sys.stdout = stdout_bck
    sys.exit(0)

