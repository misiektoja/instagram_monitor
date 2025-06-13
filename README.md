# instagram_monitor

instagram_monitor is an OSINT tool for real-time monitoring of Instagram users' activities and profile changes.

<a id="features"></a>
## Features

- Real-time tracking of Instagram users' activities and profile changes:
  - new posts, reels and stories
  - changes in followings, followers and bio
  - changes in profile pictures
  - changes in profile visibility (from private to public and vice versa)
- Anonymous download of users' story images and videos; the user won't know you watched their stories 😉
- Download of users' post images and post / reel videos
- Email notifications for different events (new posts, reels, stories, changes in followings, followers, bio, profile pictures, visibility and errors)
- Attachment of changed profile pictures and stories/posts/reels images directly in email notifications
- Displaying of profile pictures and stories/posts/reels images right in your terminal (if you have `imgcat` installed)
- Saving all user activities and profile changes with timestamps to a CSV file
- Support for both public and private profiles
- Two modes of operation: with or without a logged-in Instagram account
- Various mechanisms to prevent captcha and detection of automated tools
- Possibility to control the running copy of the script via signals

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor.png" alt="instagram_monitor_screenshot" width="90%"/>
</p>

<a id="table-of-contents"></a>
## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
   * [Install from PyPI](#install-from-pypi)
   * [Manual Installation](#manual-installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
   * [Configuration File](#configuration-file)
   * [Mode 1: Without Logged-In Instagram Account (No Session Login)](#mode-1-without-logged-in-instagram-account-no-session-login)
   * [Mode 2: With Logged-In Instagram Account (Session Login)](#mode-2-with-logged-in-instagram-account-session-login)
   * [Time Zone](#time-zone)
   * [SMTP Settings](#smtp-settings)
   * [Storing Secrets](#storing-secrets)
5. [Usage](#usage)
   * [Monitoring Mode](#monitoring-mode)
   * [Email Notifications](#email-notifications)
   * [CSV Export](#csv-export)
   * [Detection of Changed Profile Pictures](#detection-of-changed-profile-pictures)
   * [Displaying Images in Your Terminal](#displaying-images-in-your-terminal)
   * [Check Intervals](#check-intervals)
   * [Signal Controls (macOS/Linux/Unix)](#signal-controls-macoslinuxunix)
   * [Coloring Log Output with GRC](#coloring-log-output-with-grc)
6. [How to Prevent Getting Challenged and Account Suspension](#how-to-prevent-getting-challenged-and-account-suspension)
7. [Change Log](#change-log)
8. [License](#license)

<a id="requirements"></a>
## Requirements

* Python 3.9 or higher
* Libraries: [instaloader](https://github.com/instaloader/instaloader), `requests`, `python-dateutil`, `pytz`, `tzlocal`, `python-dotenv`

Tested on:

* **macOS**: Ventura, Sonoma, Sequoia
* **Linux**: Raspberry Pi OS (Bullseye, Bookworm), Ubuntu 24, Rocky Linux 8.x/9.x, Kali Linux 2024/2025
* **Windows**: 10, 11

It should work on other versions of macOS, Linux, Unix and Windows as well.

<a id="installation"></a>
## Installation

<a id="install-from-pypi"></a>
### Install from PyPI

```sh
pip install instagram_monitor
```

<a id="manual-installation"></a>
### Manual Installation

Download the *[instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py)* file to the desired location.

Install dependencies via pip:

```sh
pip install instaloader requests python-dateutil pytz tzlocal python-dotenv
```

Alternatively, from the downloaded *[requirements.txt](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt)*:

```sh
pip install -r requirements.txt
```

<a id="quick-start"></a>
## Quick Start

- Track the `target_insta_user` in [mode 1](#mode-1-without-logged-in-instagram-account-no-session-login) (no session login):

```sh
instagram_monitor <target_insta_user>
```

Or if you installed [manually](#manual-installation):

```sh
python3 instagram_monitor.py <target_insta_user>
```

- Track the `target_insta_user` in [mode 2](#option-3-session-login-using-firefox-cookies-recommended) (with session login via Firefox web browser):

```sh
# log in to the Instagram account (your_insta_user) via Firefox web browser
instagram_monitor --import-firefox-session
instagram_monitor -u <your_insta_user> <target_insta_user>
```

To get the list of all supported command-line arguments / flags:

```sh
instagram_monitor --help
```

<a id="configuration"></a>
## Configuration

<a id="configuration-file"></a>
### Configuration File

Most settings can be configured via command-line arguments.

If you want to have it stored persistently, generate a default config template and save it to a file named `instagram_monitor.conf`:

```sh
instagram_monitor --generate-config > instagram_monitor.conf

```

Edit the `instagram_monitor.conf` file and change any desired configuration options (detailed comments are provided for each).

<a id="mode-1-without-logged-in-instagram-account-no-session-login"></a>
### Mode 1: Without Logged-In Instagram Account (No Session Login)

In this mode, the tool operates without logging in to an Instagram account. 

You can still monitor basic user activity such as post, reel and story counts (without details due to Instagram API limits), bio changes and changes in follower/following counts. However, you won't see which specific followers/followings were added or removed and you won't get any details about posts, reels and stories.

This mode requires no setup, is easy to use and is resistant to Instagram's anti-bot mechanisms and CAPTCHA challenges.

<a id="mode-2-with-logged-in-instagram-account-session-login"></a>
### Mode 2: With Logged-In Instagram Account (Session Login)

In this mode, the tool uses an Instagram session login to access additional data. This includes detailed insights into new posts, reels and stories, also about added or removed followers/followings.

**Important**: It is highly recommended to use a dedicated Instagram account when using this tool in session login mode. While the risk of account suspension is generally low (in practice, accounts often stay active long-term), Instagram may still flag it as an automated tool. This can lead to challenges presented by Instagram that must be dismissed manually. To minimize any chance of detection, make sure to follow the best practices outlined [here](#how-to-prevent-getting-challenged-and-account-suspension). 

<a id="option-1-basic-session-login-not-recommended"></a>
#### Option 1: Basic Session Login (not recommended)

You can provide your Instagram username (`your_insta_user`) and password directly in the `instagram_monitor.conf` configuration file, [environment variable](#storing-secrets) or via the `-u` and `-p` flags. 

However, this triggers a full login every time the tool runs, increasing the chance of detection and account lockouts.

If you store the `SESSION_PASSWORD` in a dotenv file you can update its value and send a `SIGHUP` signal to the process to reload the file with the new password without restarting the tool. More info in [Storing Secrets](#storing-secrets) and [Signal Controls (macOS/Linux/Unix)](#signal-controls-macoslinuxunix).

<a id="option-2-session-login-via-instaloader-better-but-can-be-detected"></a>
#### Option 2: Session Login via Instaloader (better, but can be detected)

A better approach is to use `Instaloader` to perform a one-time login and save the session:

```sh
instaloader -l <your_insta_user>
```

This saves the session locally. However, frequent follower/following/stories changes can still lead to detection, as Instagram may flag this as automated behavior.

<a id="option-3-session-login-using-firefox-cookies-recommended"></a>
#### Option 3: Session Login Using Firefox Cookies (recommended)

The most reliable method is to reuse an existing Instagram session from your Firefox web browser, along with manually specifying the user agent.

Log in to your account (`your_insta_user`) in Firefox, then run:

```sh
instagram_monitor --import-firefox-session
```

The tool will detect available Firefox profiles with a `cookies.sqlite` file. If multiple profiles are found, it will prompt you to select one, then import the session and save it via Instaloader.

To use a specific Firefox profile path:

```sh
instagram_monitor --import-firefox-session --cookie-file "/path/cookies.sqlite"
```

You can adjust the default Firefox cookie directory permanently via `FIREFOX_*_COOKIE` configuration options.

The session login method using Firefox cookies has the added benefit of blending tool activity with regular user behavior. Interacting with Instagram via Firefox every few days (scrolling, liking posts etc.) helps maintain session trust. However, avoid overlapping browser activity with tool activity, as simultaneous actions can trigger suspicious behavior flags.

<a id="user-agent"></a>
##### User Agent

It is also recommended to use the exact user agent string from your Firefox web browser:
- open Firefox and type `about:support` in the address bar
- find the `User Agent` value under the `Application Basics` section and copy it
- set this value via the `USER_AGENT` configuration option or by using the `--user-agent` flag

<a id="time-zone"></a>
### Time Zone

By default, time zone is auto-detected using `tzlocal`. You can set it manually in `instagram_monitor.conf`:

```ini
LOCAL_TIMEZONE='Europe/Warsaw'
```

You can get the list of all time zones supported by pytz like this:

```sh
python3 -c "import pytz; print('\n'.join(pytz.all_timezones))"
```

<a id="smtp-settings"></a>
### SMTP Settings

If you want to use email notifications functionality, configure SMTP settings in the `instagram_monitor.conf` file. 

Verify your SMTP settings by using `--send-test-email` flag (the tool will try to send a test email notification):

```sh
instagram_monitor --send-test-email
```

<a id="storing-secrets"></a>
### Storing Secrets

It is recommended to store secrets like `SESSION_PASSWORD` or `SMTP_PASSWORD` as either an environment variable or in a dotenv file.

Set environment variables using `export` on **Linux/Unix/macOS/WSL** systems:

```sh
export SESSION_PASSWORD="your_instagram_session_password"
export SMTP_PASSWORD="your_smtp_password"
```

On **Windows Command Prompt** use `set` instead of `export` and on **Windows PowerShell** use `$env`.

Alternatively store them persistently in a dotenv file (recommended):

```ini
SESSION_PASSWORD="your_instagram_session_password"
SMTP_PASSWORD="your_smtp_password"
```

By default the tool will auto-search for dotenv file named `.env` in current directory and then upward from it. 

You can specify a custom file with `DOTENV_FILE` or `--env-file` flag:

```sh
instagram_monitor <target_insta_user> --env-file /path/.env-instagram_monitor
```

 You can also disable `.env` auto-search with `DOTENV_FILE = "none"` or `--env-file none`:

```sh
instagram_monitor <target_insta_user> --env-file none
```

As a fallback, you can also store secrets in the configuration file or source code.

<a id="usage"></a>
## Usage

<a id="monitoring-mode"></a>
### Monitoring Mode

To monitor specific user activity in [mode 1](#mode-1-without-logged-in-instagram-account-no-session-login) (no session login), just type Instagram username as a command-line argument (`target_insta_user` in the example below):

```sh
instagram_monitor <target_insta_user>
```

To monitor specific user activity in [mode 2](#mode-2-with-logged-in-instagram-account-session-login) (with session login), you also need to specify your Instagram account name (`your_insta_user` in the example below) via `SESSION_USERNAME` configuration option or `-u` flag:

```sh
instagram_monitor -u <your_insta_user> <target_insta_user>
```

By default, the tool looks for a configuration file named `instagram_monitor.conf` in:
 - current directory 
 - home directory (`~`)
 - script directory 

 If you generated a configuration file as described in [Configuration](#configuration), but saved it under a different name or in a different directory, you can specify its location using the `--config-file` flag:

```sh
instagram_monitor <target_insta_user> --config-file /path/instagram_monitor_new.conf
```

The tool runs until interrupted (`Ctrl+C`). Use `tmux` or `screen` for persistence.

You can monitor multiple Instagram users by launching multiple instances of the script.

The tool automatically saves its output to `instagram_monitor_<username>.log` file. It can be changed in the settings via `INSTA_LOGFILE` configuration option or disabled completely via `DISABLE_LOGGING` / `-d` flag.

The tool in mode 2 (session login) also saves the list of followings & followers to these files:
- `instagram_<username>_followings.json`
- `instagram_<username>_followers.json`

Thanks to this we do not need to re-fetch it every time the tool is restarted and we can also detect changes since the last usage of the tool.

The tool also saves the user profile picture to `instagram_<username>_profile_pic*.jpeg` files.

It also saves downloaded posts/reels images & videos to:
- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.jpeg`
- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.mp4`

And downloaded stories images & videos to:
- `instagram_<username>_story_YYYYmmdd_HHMMSS.jpeg`
- `instagram_<username>_story_YYYYmmdd_HHMMSS.mp4`

<a id="email-notifications"></a>
### Email Notifications

To enable email notifications for various events (such as new posts, reels and stories, changes in followings, bio updates, changes in profile picture and visibility):
- set `STATUS_NOTIFICATION` to `True`
- or use the `-s` flag

```sh
instagram_monitor <target_insta_user> -s
```

To also get email notifications about changed followers:
- set `FOLLOWERS_NOTIFICATION` to `True`
- or use the `-m` flag

```sh
instagram_monitor <target_insta_user> -m
```

To disable sending an email on errors (enabled by default):
- set `ERROR_NOTIFICATION` to `False`
- or use the `-e` flag

```sh
instagram_monitor <target_insta_user> -e
```

Make sure you defined your SMTP settings earlier (see [SMTP settings](#smtp-settings)).

Example email:

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_email_notifications.png" alt="instagram_monitor_email_notifications" width="80%"/>
</p>

<a id="csv-export"></a>
### CSV Export

If you want to save all Instagram user's activities and profile changes to a CSV file, set `CSV_FILE` or use `-b` flag:

```sh
instagram_monitor <target_insta_user> -b instagram_username.csv
```

The file will be automatically created if it does not exist.

<a id="detection-of-changed-profile-pictures"></a>
### Detection of Changed Profile Pictures

The tool can detect when a monitored user changes their profile picture. Notifications appear in the console and (if the `-s` flag is enabled) via email.

This feature is enabled by default. To disable it, either:

- set the `DETECT_CHANGED_PROFILE_PIC` to `False`
- or use the `-k` flag

<a id="how-it-works"></a>
#### How It Works

Since Instagram periodically changes the profile picture URL even when the image is the same, the tool performs a binary comparison of JPEG files to detect actual changes.

On the first run, it saves the current profile picture to `instagram_<username>_profile_pic.jpeg`

On each subsequent check a new image is fetched and it is compared byte-for-byte with the saved image.

If a change is detected, the old picture is moved to `instagram_<username>_profile_pic_old.jpeg` and the new one is saved to:
- `instagram_<username>_profile_pic.jpeg` (current)
- `instagram_<username>_profile_pic_YYmmdd_HHMM.jpeg` (for history)

<a id="empty-profile-picture-detection"></a>
#### Empty Profile Picture Detection

The tool also has built-in detection of empty profile pictures. Instagram does not indicate an empty user's profile image in their API; that's why the tool detects it by using an empty profile image template (which appears to be identical on a binary level for all users).

To enable this:
- download the [instagram_profile_pic_empty.jpeg](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_profile_pic_empty.jpeg) file
- place it in the directory where you run the tool (or change the path via `PROFILE_PIC_FILE_EMPTY` configuration option)

Without this file, the tool will treat an empty profile picture as a regular image. For example, if a user removes their profile picture, it would be treated as a change rather than a removal.

<a id="displaying-images-in-your-terminal"></a>
### Displaying Images in Your Terminal

If you have `imgcat` installed, you can use the feature of displaying profile pictures and stories/reels/posts images right in your terminal. 

To do this, set the path to your `imgcat` binary in the `IMGCAT_PATH` configuration option. 

If you specify only the binary name, it will be auto-searched in your PATH.

Set it to empty to disable this feature.

<a id="check-intervals"></a>
### Check Intervals

If you want to customize polling interval, use `-c` flag (or `INSTA_CHECK_INTERVAL` configuration option):

```sh
instagram_monitor <target_insta_user> -c 3600
```

It is generally not recommended to use values lower than 1 hour as it will be quickly picked up by Instagram automated tool detection mechanisms.

In order to make the tool's behavior less suspicious for Instagram, by default the polling interval is randomly picked from the range: 

```
[ INSTA_CHECK_INTERVAL (-c) - RANDOM_SLEEP_DIFF_LOW (-i) ]  
                         ⇄  
[ INSTA_CHECK_INTERVAL (-c) + RANDOM_SLEEP_DIFF_HIGH (-j) ]  
```

This means each check will happen after a random delay centered around `INSTA_CHECK_INTERVAL` with some variation defined by `RANDOM_SLEEP_DIFF_LOW` and `RANDOM_SLEEP_DIFF_HIGH`.

So having the check interval set to 1 hour (-c 3600), `RANDOM_SLEEP_DIFF_LOW` set to default 15 mins (-i 900) and `RANDOM_SLEEP_DIFF_HIGH` set to default 3 mins (-j 180) means that the check interval will be with every iteration picked from the range of 45 mins to 1 hour and 3 mins.

That's why the check interval information is printed in the console and email notifications as it is essentially a random number.

On top of that you can also define that checks for new posts / reels should be done only in specific hour ranges by setting `CHECK_POSTS_IN_HOURS_RANGE` to `True` and then defining proper values for `MIN/MAX_H1/H2` configuration options (see the comments in the configuration file for more information).

<a id="signal-controls-macoslinuxunix"></a>
### Signal Controls (macOS/Linux/Unix)

The tool has several signal handlers implemented which allow to change behavior of the tool without a need to restart it with new configuration options / flags.

List of supported signals:

| Signal | Description |
| ----------- | ----------- |
| USR1 | Toggle email notifications for new posts, reels & stories, changed followings, bio, profile picture, visibility (-s) |
| USR2 | Toggle email notifications for new followers (-m) |
| TRAP | Increase the user activity check interval (by 5 mins) |
| ABRT | Decrease the user activity check interval (by 5 mins) |
| HUP | Reload secrets from .env file |

Send signals with `kill` or `pkill`, e.g.:

```sh
pkill -USR1 -f "instagram_monitor <target_insta_user>"
```

As Windows supports limited number of signals, this functionality is available only on Linux/Unix/macOS.

<a id="coloring-log-output-with-grc"></a>
### Coloring Log Output with GRC

You can use [GRC](https://github.com/garabik/grc) to color logs.

Add to your GRC config (`~/.grc/grc.conf`):

```
# monitoring log file
.*_monitor_.*\.log
conf.monitor_logs
```

Now copy the [conf.monitor_logs](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/grc/conf.monitor_logs) to your `~/.grc/` and log files should be nicely colored when using `grc` tool.

Example:

```sh
grc tail -F -n 100 instagram_monitor_<username>.log
```

<a id="how-to-prevent-getting-challenged-and-account-suspension"></a>
## How to Prevent Getting Challenged and Account Suspension

As mentioned earlier it is highly recommended to use a dedicated Instagram account when using this tool in session login mode. While the risk of account suspension is generally low (in practice, accounts often stay active long-term), Instagram may still flag it as an automated tool. This can lead to challenges presented by Instagram that must be dismissed manually.

To minimize any chance of detection, make sure to follow the best practices outlined below. 

<a id="sign-in-using-session-mode-with-firefox-cookies"></a>
### Sign In Using Session Mode with Firefox Cookies

Use your Firefox web browser to log in, ensuring the session looks natural and consistent to Instagram. Follow instructions described [here](#option-3-session-login-using-firefox-cookies-recommended)

<a id="set-the-correct-user-agent"></a>
### Set the Correct User-Agent

Always pass the exact web browser user agent string from your Firefox web browser by using `USER_AGENT` configuration option or the `--user-agent` flag. This helps maintain device consistency during automated actions. Follow instructions described [here](#user-agent)

<a id="use-the-human-mode"></a>
### Use the Human Mode

Since v1.7, the tool includes a new experimental **Be Human** mode that makes it behave more like a real user to reduce bot detection. 

It is disabled by default, but you can enable it via `BE_HUMAN` configuration option or `--be-human` flag.

It is used only with session login (mode 2).

After each check cycle, the tool will randomly do one or more of these harmless actions:
- View your explore feed: pulls a single post from Instagram's explore feed
- Open your own profile, as if tapping your avatar
- Browse a hashtag: fetches one post from a random tag listed in `MY_HASHTAGS` configuration option
- Look at a profile of someone you follow

By default it does around 5 of these actions spread over 24 hours, but you can adjust it via `DAILY_HUMAN_HITS` option. 

If you are interested in your human actions set `BE_HUMAN_VERBOSE` option to `True`.

<a id="use-the-jitter-mode"></a>
### Use the Jitter Mode

Since v.1.7, the tools allows to force every HTTP call made by Instaloader to go through a built-in jitter/back-off layer to look more human. 

This adds random delay (0.8-3 s) before each request and automatically retries on Instagram's 429 "too many requests" or checkpoint challenges, with exponential back-off (60 s → 120 s → 240 s) and a little extra jitter. 

This significantly reduces detection risk, but also makes the tool slower. 

You can enable this feature via `ENABLE_JITTER` configuration option or `--enable-jitter` flag.

If you want to see verbose output for HTTP jitter/back-off wrappers set `JITTER_VERBOSE` option to `True`.

<a id="keep-the-polling-interval-reasonable"></a>
### Keep the Polling Interval Reasonable

Avoid setting the polling interval (`INSTA_CHECK_INTERVAL` option or `-c` flag) too aggressively. Use a minimum of 1 hour - longer is better. For example, I set it to 12 hours on test accounts, resulting in only 2 checks per day.

Also consider to randomize the check interval, as explained [here](#check-intervals).

<a id="do-not-monitor-too-many-users"></a>
### Do Not Monitor Too Many Users

It is recommended to limit the number of users monitored by a single account, especially if they post frequent updates. In some cases, it may be best to create a separate account for additional users and even run it from a different IP address to reduce the risk of detection.

<a id="use-only-needed-functionality"></a>
### Use Only Needed Functionality

Frequent updates to certain data types, such as new stories or changes in followers/followings, are more likely to flag the account as an automated tool. If certain data isn't essential for your use case, consider disabling its retrieval. The tool provides fine-grained control, for example you can skip fetching the list of followings (`-g` flag), followers (`-f`), stories details (`-r`) or posts/reels details (`-w`). 

<a id="use-two-factor-authentication-2fa"></a>
### Use Two-Factor Authentication (2FA)

Activate 2FA on the account used for monitoring. It adds credibility to your account and reduces the likelihood of security flags.

<a id="avoid-using-vpns"></a>
### Avoid Using VPNs

Refrain from logging in via VPNs, especially with IPs in different regions. Sudden location changes can trigger Instagram's security systems.

<a id="use-the-account-for-normal-activities"></a>
### Use the Account for Normal Activities

If you have created a new account for monitoring and you are using [Session Login Using Firefox](#option-3-session-login-using-firefox-cookies-recommended), make sure to behave like a regular user for several days. New accounts are more closely monitored by Instagram's bot detection systems. Watch content, post stories or reels and leave comments - this helps establish a natural activity pattern.

Once you start using the tool, try to blend its actions with normal usage. However, avoid overlapping browser activity with tool activity, as simultaneous actions can trigger suspicious behavior flags.

<a id="change-log"></a>
## Change Log

See [RELEASE_NOTES.md](https://github.com/misiektoja/instagram_monitor/blob/main/RELEASE_NOTES.md) for details.

<a id="license"></a>
## License

Licensed under GPLv3. See [LICENSE](https://github.com/misiektoja/instagram_monitor/blob/main/LICENSE).
