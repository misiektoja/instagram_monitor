# instagram_monitor

instagram_monitor is an OSINT tool for real-time monitoring of **Instagram users' activities and profile changes**.

<a id="features"></a>
## Features

- **Real-time tracking** of Instagram users' activities and profile changes:
  - **new posts, reels** and **stories**
  - changes in **followings, followers** and **bio**
  - changes in **profile pictures**
  - changes in **profile visibility** (public to private and vice versa)
- **Anonymous download** of users' **story images and videos** without leaving view traces
- **Download** of users' **post images and post / reel videos**
- **Email and webhook notifications** for different events (new posts, reels, stories, changes in followings, followers, bio, profile pictures, visibility and errors)
- **Terminal Dashboard** - beautiful, live-updating terminal dashboard with real-time stats and interactive controls
- **Web Dashboard** - modern, real-time UI on localhost with stats, interactive controls and activity feed
- **Attaching changed profile pictures** and **stories/posts/reels images** directly in notifications
- **Displaying the profile picture** and **stories/posts/reels images** right in your terminal (if you have `imgcat` installed)
- **Saving all user activities and profile changes** with timestamps to a **CSV file**
- Support for both **public and private profiles**
- **Two session modes**: with or without a logged-in Instagram account
- **Monitor multiple users** in a single process with automatic request staggering to avoid detection
- Various mechanisms to **prevent captcha and detection of automated tools**, including **Be Human mode** (simulates random user actions), **Jitter mode** (adds human-like delays and back-off to HTTP requests) and **hour-range checking** (limits fetching updates to specific hours of the day)
- **Flexible configuration** - support for config files, dotenv files, environment variables and command-line arguments
- Possibility to **control the running copy** of the script via signals
- **Functional, procedural Python** (minimal OOP)

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor.png" alt="instagram_monitor_screenshot" width="90%"/>
</p>

<a id="table-of-contents"></a>
## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
   * [Install from PyPI](#install-from-pypi)
   * [Manual Installation](#manual-installation)
   * [Upgrading](#upgrading)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
   * [Configuration File](#configuration-file)
   * [Session Mode 1: Without Logged-In Instagram Account (No Session Login)](#session-mode-1-without-logged-in-instagram-account-no-session-login)
   * [Session Mode 2: With Logged-In Instagram Account (Session Login)](#session-mode-2-with-logged-in-instagram-account-session-login)
   * [Time Zone](#time-zone)
   * [SMTP Settings](#smtp-settings)
   * [Storing Secrets](#storing-secrets)
5. [View Modes](#view-modes)
   * [Traditional Text Mode](#traditional-text-mode)
   * [Terminal Dashboard](#terminal-dashboard-mode)
   * [Web Dashboard](#web-dashboard-mode)
   * [Dashboard View Modes](#dashboard-view-modes)
6. [Usage](#usage)
   * [Monitoring Mode](#monitoring-mode)
   * [Email Notifications](#email-notifications)
   * [Webhook Notifications](#webhook-notifications)
   * [Detailed Follower Logging](#detailed-follower-logging)
   * [CSV Export](#csv-export)
   * [Output Directory](#output-directory)
   * [Detection of Changed Profile Pictures](#detection-of-changed-profile-pictures)
   * [Displaying Images in Your Terminal](#displaying-images-in-your-terminal)
   * [Check Intervals](#check-intervals)
   * [Signal Controls (macOS/Linux/Unix)](#signal-controls-macoslinuxunix)
   * [Coloring Log Output with GRC](#coloring-log-output-with-grc)
6. [How to Prevent Getting Challenged and Account Suspension](#how-to-prevent-getting-challenged-and-account-suspension)
7. [Troubleshooting](#troubleshooting)
8. [Change Log](#change-log)
9. [License](#license)

<a id="requirements"></a>
## Requirements

* Python 3.9 or higher
* Libraries: [instaloader](https://github.com/instaloader/instaloader), `requests`, `python-dateutil`, `pytz`, `tzlocal`, `python-dotenv`, `tqdm`, `rich` (for Terminal Dashboard), `flask` (for Web Dashboard)

Tested on:

* **macOS**: Ventura, Sonoma, Sequoia, Tahoe
* **Linux**: Raspberry Pi OS (Bullseye, Bookworm, Trixie), Ubuntu 24/25, Rocky Linux 8.x/9.x, Kali Linux 2024/2025
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
pip install instaloader requests python-dateutil pytz tzlocal python-dotenv tqdm rich flask
```

**Note:** `rich` is required for the Terminal Dashboard, `flask` is required for the Web Dashboard. If Rich or Flask is not installed, the corresponding dashboard is disabled automatically.

Alternatively, from the downloaded *[requirements.txt](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt)*:

```sh
pip install -r requirements.txt
```

<a id="upgrading"></a>
### Upgrading

To upgrade to the latest version when installed from PyPI:

```sh
pip install instagram_monitor -U
```

If you installed manually, download the newest *[instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py)* file to replace your existing installation.

<a id="quick-start"></a>
## Quick Start

- Track the `target_insta_user` in [session mode 1](#session-mode-1-without-logged-in-instagram-account-no-session-login) (no session login - anonymous):

```sh
instagram_monitor <target_insta_user>
```

Or if you installed [manually](#manual-installation):

```sh
python3 instagram_monitor.py <target_insta_user>
```

- Track the `target_insta_user` in [session mode 2](#option-3-session-login-using-firefox-cookies-recommended) (with session login via Firefox web browser):

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

<a id="session-mode-1-without-logged-in-instagram-account-no-session-login"></a>
### Session Mode 1: Without Logged-In Instagram Account (No Session Login)

In this mode, the tool operates without logging in to an Instagram account (anonymous).

You can still monitor basic user activity such as new or deleted posts (excluding reels and stories due to Instagram API limitations), bio changes and changes in follower/following counts. However, you won't see which specific followers/followings were added or removed.

This mode requires no setup, is easy to use and is resistant to Instagram's anti-bot mechanisms and CAPTCHA challenges.

<a id="session-mode-2-with-logged-in-instagram-account-session-login"></a>
### Session Mode 2: With Logged-In Instagram Account (Session Login)

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

Set the needed environment variables using `export` on **Linux/Unix/macOS/WSL** systems:

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


<a id="view-modes"></a>
## View Modes

The tool provides three distinct ways to visualize monitoring activity:

1. **Traditional Text Mode**: Standard CLI output, best for logging and background processes.
2. **Terminal Dashboard**: A rich, interactive terminal interface with real-time stats.
3. **Web Dashboard**: A modern web interface accessible via your browser.

---

<a id="traditional-text-mode"></a>
### Traditional Text Mode

This is the classic command-line output. It is characterized by:
- **Clean, sequential logging**: Every event is printed as it happens with a timestamp.
- **Persistence**: Ideal for running in the background (e.g., via `nohup` or `tmux`) where you want a full history of events in your terminal scrollback or log files.
- **Low Overhead**: Minimal resource usage and compatible with any terminal.

It is the default mode of operation.

---

<a id="terminal-dashboard-mode"></a>
### Terminal Dashboard

The Terminal Dashboard provides a beautiful, live-updating interface directly in your terminal. It requires the `rich` library.

To enable the terminal dashboard, use the `--dashboard` flag (or set `DASHBOARD_ENABLED = True` in your config).

**Key Features:**
- **Visual Analytics**: Real-time display of tracked targets with number of followers, followings, posts, visibility and story status.
- **Live Activity Log**: A scrolling view of the last few events.
- **Interactive Toggles**: Press **'m'** to switch between 'User' and 'Config' views instantly.
- **Remote Control**: Start, stop or recheck monitoring for all targets directly from the terminal.
- **Uptime & Status**: Clean header showing tool version, status and total runtime.

**Keyboard Shortcuts:**
- **'m'**: Toggle dashboard view (User/Config)
- **'s'**: **Start All** monitoring
- **'x'**: **Stop All** monitoring
- **'r'**: **Recheck All** targets
- **'q'**: **Exit** the tool
- **'h'**: Show help (lists commands in the activity log)

```sh
instagram_monitor target1 target2 --dashboard
```

---

<a id="web-dashboard-mode"></a>
### Web Dashboard

A modern, real-time web interface running on your local machine (default: `http://127.0.0.1:8000/`).

**Key Features:**
- **Full Control Panel**: Add or remove monitoring targets directly from the browser.
- **Visual Analytics**: Real-time display of tracked targets with number of followers, followings, posts, visibility and story status.
- **Live Activity Log**: A scrolling view of the last few events.
- **Manual Trigger**: A "Recheck" button to force an immediate update for specific or all users.
- **Remote Management**: Start or stop monitoring for specific or all targets with a single click.
- **Synchronization**: Changes made in the web dashboard (like mode toggles) are reflected in the terminal instantly.
- **Dynamic Configuration**: Configure sessions and settings without touching the terminal or config files.

To enable the web dashboard, use the `--web-dashboard` flag (or set `WEB_DASHBOARD_ENABLED = True` in your config).

**Flexible Usage:**
- **Standard Monitoring**: Provide targets on the CLI, and the dashboard acts as a live mirror and remote management interface.
- **Control Panel Mode**: Start the tool with **only** the `--web-dashboard` flag (no initial targets). The script will wait for you to add users through the browser.

```sh
# Starting with initial targets
instagram_monitor target1 target2 --web-dashboard

# Starting as a pure control panel
instagram_monitor --web-dashboard
```

The web dashboard requires `flask`. If flask is missing, it will be disabled while the console output remains active.

---

<a id="dashboard-view-modes"></a>
### Dashboard View Modes

Both the Terminal and Web dashboards support two levels of information density:

1. **User Mode** (`user`):
   - Simple, minimal interface.
   - Focuses on core stats and latest activity.
   - Ideal for "always-on" monitoring.

2. **Config Mode** (`config`):
   - Detailed view showing all internal settings.
   - Displays User Agent strings, Hour Ranges, Jitter status and more.
   - Useful for auditing your setup and verifying configuration.

Toggle seamlessly between modes using the **'m'** key or the web dashboard toggle button.

<a id="usage"></a>
## Usage

<a id="monitoring-mode"></a>
### Monitoring Mode

To monitor specific user activity in [session mode 1](#session-mode-1-without-logged-in-instagram-account-no-session-login) (no session login - anonymous), just type Instagram username as a command-line argument (`target_insta_user` in the example below):

```sh
instagram_monitor <target_insta_user>
```

To monitor specific user activity in [session mode 2](#session-mode-2-with-logged-in-instagram-account-session-login) (with session login), you also need to specify your Instagram account name (`your_insta_user` in the example below) via `SESSION_USERNAME` configuration option or `-u` flag:

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

You can monitor multiple Instagram users in **one process** by passing multiple target usernames:

```sh
instagram_monitor target_user_1 target_user_2 target_user_3
```

To reduce the chance of triggering Instagram anti-bot mechanisms, the tool will **stagger** the start of each target's monitoring loop (auto-spread across your `INSTA_CHECK_INTERVAL` by default). You can override it with:

```sh
instagram_monitor target_user_1 target_user_2 --targets-stagger 300
```

The tool automatically saves its output to an `instagram_monitor_<suffix>.log` file. It can be changed in the settings via `INSTA_LOGFILE` configuration option or disabled completely via `DISABLE_LOGGING` / `-d` flag.

- In single-target mode, `<suffix>` is the username.
- In multi-target mode, `<suffix>` is the sorted list of target usernames joined with underscores.

The tool in mode 2 (session login) also saves the list of followings & followers to these files:
- `instagram_<username>_followings.json`
- `instagram_<username>_followers.json`

Thanks to this we do not need to re-fetch it every time the tool is restarted and we can also detect changes since the last usage of the tool.

When downloading lists of followers or followings, a **progress bar** is displayed showing real-time download progress, including statistics such as names per request, total requests, elapsed time and estimated remaining time. Progress updates are shown in the terminal only (to avoid cluttering log files), with the final completion state written to the log file for reference.

The tool also saves the user profile picture to `instagram_<username>_profile_pic*.jpg` files.

It also saves downloaded posts/reels images & videos to:
- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.jpg`
- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.mp4`

And downloaded stories images & videos to:
- `instagram_<username>_story_YYYYmmdd_HHMMSS.jpg`
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

<a id="webhook-notifications"></a>
### Webhook Notifications

The tool supports webhook notifications (compatible with Discord and other webhook services) for all monitored events (posts, reels, stories, followings, followers, bio, profile visibility, profile picture changes and errors).

#### 1. Configure Discord Webhook
If you are new to Discord, follow these steps to get your **Webhook URL**:

1.  **Create a Server**: Click the **+** (Plus) icon on the left sidebar ("Add a Server") -> **Create My Own** -> **For me and my friends**.
2.  **Create/Edit a Channel**: In your new server, find the **#general** channel (or create a new one). Click the **Edit Channel** icon (⚙️ gear) next to the channel name.
3.  **Create Webhook**: Go to **Integrations** in the left menu -> **Webhooks** -> **New Webhook**.
4.  **Copy URL**: Click on the new webhook (often named "Spidey Bot", you can rename it) and click **Copy Webhook URL**.

#### 2. Enable in the Tool
To enable webhook notifications:
- set `WEBHOOK_ENABLED` to `True` and `WEBHOOK_URL` to your copied URL in `instagram_monitor.conf`
- or use the `--webhook-url` flag (alternatively use the `--webhook` flag if URL is already in config)

```sh
# Enable with URL
instagram_monitor <target_insta_user> --webhook-url "https://discord.com/api/webhooks/..."

# Explicitly enable/disable if URL is in config
instagram_monitor <target_insta_user> --webhook
instagram_monitor <target_insta_user> --no-webhook
```

#### 3. Test your settings
You can verify your configuration by sending a test notification:

```sh
# Verify settings from configuration file
instagram_monitor --send-test-webhook

# Verify a specific URL from command line
instagram_monitor --webhook-url "https://discord.com/api/webhooks/..." --send-test-webhook
```

#### 4. Advanced Configuration
By default, all webhook notification types (status, followers, errors) are **disabled**. You must explicitly enable what you want the tool to send:

- Use `--webhook-status` to toggle status notifications (new posts, reels, stories, bio, visibility, profile pic)
- Use `--webhook-followers` to toggle follower/following change notifications
- Use `--webhook-errors` to toggle error notifications

Example with explicit control:
```sh
# Enable webhooks and specifically choose what to send
instagram_monitor <target_insta_user> --webhook-url "..." --webhook-status --webhook-followers --webhook-errors
```

Configuration file options (all disabled by default):
```ini
WEBHOOK_ENABLED = False
WEBHOOK_URL = "https://discord.com/api/webhooks/..."
WEBHOOK_USERNAME = "Instagram Monitor"
WEBHOOK_AVATAR_URL = ""
WEBHOOK_STATUS_NOTIFICATION = False
WEBHOOK_FOLLOWERS_NOTIFICATION = False
WEBHOOK_ERROR_NOTIFICATION = False
```

<a id="detailed-follower-logging"></a>
### Detailed Follower Logging

When enabled, the tool fetches the full list of followers and followings on **every check** (not just when counts change) and compares usernames to detect changes. This is useful for scenarios where:

- Someone unfollows and someone else follows at the same time (count stays the same)
- You want to track exactly who followed/unfollowed even without count changes
- You need comprehensive logging of all follower/following activity

To enable detailed follower logging:
- set `DETAILED_FOLLOWER_LOGGING` to `True`
- or use the `--detailed-followers` flag

```sh
instagram_monitor <target_insta_user> --detailed-followers
```

**Note**: This feature requires [Session Mode 2](#session-mode-2-with-logged-in-instagram-account-session-login) (session login) to access the Instagram API. It will increase API calls since it fetches the full follower/following lists every check interval.

<a id="csv-export"></a>
### CSV Export

If you want to save all Instagram user's activities and profile changes to a CSV file, set `CSV_FILE` or use `-b` flag:

```sh
instagram_monitor <target_insta_user> -b instagram_username.csv
```

The file will be automatically created if it does not exist.

The tool uses the following logic for CSV path resolution:

1.  **Absolute Path**:
    *   **Single-target mode**: The file is saved exactly where specified.
    *   **Multi-target mode**: The absolute path is used as a base; separate files are created for each user (e.g., `/path/file_user1.csv`). Isolation is preserved.
2.  **Relative Path + `OUTPUT_DIR`**: If you provide a relative path and have `OUTPUT_DIR` configured, the file is saved in the `csvs/` subdirectory:
    *   **Single-target mode**: `OUTPUT_DIR/csvs/<filename>` (uses basename of your input)
    *   **Multi-target mode**: `OUTPUT_DIR/<username>/csvs/<filename>` (uses basename of your input)
3.  **Relative Path + no `OUTPUT_DIR`**:
    *   **Single-target mode**: Saved as specified in the current working directory.
    *   **Multi-target mode**: One file per user is created in the current working directory using a suffix: `<CSV_FILE_basename>_<username>.csv`.

<a id="output-directory"></a>
### Output Directory

By default, the tool saves all generated files (JSON, images, videos, logs) in the current working directory.

You can specify a custom root directory for all output files using the `-o` / `--output-dir` flag or `OUTPUT_DIR` configuration option:

```sh
instagram_monitor <target_insta_user> -o /path/to/downloads
```

The tool will organize files into subdirectories:

- **Output structure**: The layout depends on whether you monitor one or multiple users:

  - **Single-target mode**: All files are organized into subdirectories directly under `OUTPUT_DIR`:
    - `OUTPUT_DIR/images/`
    - `OUTPUT_DIR/videos/`
    - `OUTPUT_DIR/json/`
    - `OUTPUT_DIR/logs/`
    - `OUTPUT_DIR/csvs/`

  - **Multi-target mode**: Each user gets their own isolated subdirectory:
    - `OUTPUT_DIR/<username>/images/`
    - `OUTPUT_DIR/<username>/videos/`
    - `OUTPUT_DIR/<username>/json/`
    - `OUTPUT_DIR/<username>/logs/`
    - `OUTPUT_DIR/<username>/csvs/`

Common messages (like the summary screen or global errors) are automatically broadcasted to all active log files.

This helps keep your files organized, especially when monitoring multiple users.

<a id="detection-of-changed-profile-pictures"></a>
### Detection of Changed Profile Pictures

The tool can detect when a monitored user changes their profile picture. Notifications appear in the console and (if the `-s` flag is enabled) via email.

This feature is enabled by default. To disable it, either:

- set the `DETECT_CHANGED_PROFILE_PIC` to `False`
- or use the `-k` flag

<a id="how-it-works"></a>
#### How It Works

Since Instagram periodically changes the profile picture URL even when the image is the same, the tool performs a binary comparison of JPEG files to detect actual changes.

On the first run, it saves the current profile picture to `instagram_<username>_profile_pic.jpg`

On each subsequent check a new image is fetched and it is compared byte-for-byte with the saved image.

If a change is detected, the old picture is moved to `instagram_<username>_profile_pic_old.jpg` and the new one is saved to:
- `instagram_<username>_profile_pic.jpg` (current)
- `instagram_<username>_profile_pic_YYmmdd_HHMM.jpg` (for history)

<a id="empty-profile-picture-detection"></a>
#### Empty Profile Picture Detection

The tool also has built-in detection of empty profile pictures. Instagram does not indicate an empty user's profile image in their API; that's why the tool detects it by using an empty profile image template (which appears to be identical on a binary level for all users).

To enable this:
- download the [instagram_profile_pic_empty.jpg](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_profile_pic_empty.jpg) file
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

On top of that you can also define that fetching updates should be done only in specific hour ranges by setting `CHECK_POSTS_IN_HOURS_RANGE` to `True` and then defining proper values for `MIN/MAX_H1/H2` configuration options (see [Use Hour-Range Checking](#use-hour-range-checking) for more information).

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

It is used only with session login (session mode 2).

After each check cycle, the tool will randomly do one or more of these harmless actions:
- View your explore feed: pulls a single post from Instagram's explore feed
- Open your own profile, as if tapping your avatar
- Browse a hashtag: fetches one post from a random tag listed in `MY_HASHTAGS` configuration option
- Look at a profile of someone you follow

By default it does around 5 of these actions spread over 24 hours, but you can adjust it via `DAILY_HUMAN_HITS` option.

If you are interested in your human actions set `BE_HUMAN_VERBOSE` option to `True`.

<a id="use-the-jitter-mode"></a>
### Use the Jitter Mode

Since v1.7, the tool allows to force every HTTP call made by Instaloader to go through a built-in jitter/back-off layer to look more human.

This adds random delay (0.8-3 s) before each request and automatically retries on Instagram's 429 "too many requests" or checkpoint challenges, with exponential back-off (60 s → 120 s → 240 s) and a little extra jitter.

This significantly reduces detection risk, but also makes the tool slower.

You can enable this feature via `ENABLE_JITTER` configuration option or `--enable-jitter` flag.

If you want to see verbose output for HTTP jitter/back-off wrappers set `JITTER_VERBOSE` option to `True`.

<a id="keep-the-polling-interval-reasonable"></a>
### Keep the Polling Interval Reasonable

Avoid setting the polling interval (`INSTA_CHECK_INTERVAL` option or `-c` flag) too aggressively. Use a minimum of 1 hour - longer is better. For example, I set it to 12 hours on test accounts, resulting in only 2 checks per day.

Also consider to randomize the check interval, as explained [here](#check-intervals).

**Important**: When monitoring multiple users in a single process, the effective request rate is multiplied by the number of targets. For example, monitoring 5 users with a 1-hour interval means 5 requests per hour. To maintain the same per-account request rate, increase the check interval proportionally. If you normally use 1 hour for a single user, consider using 5 hours (or more) when monitoring 5 users. The tool automatically staggers requests between targets, but the overall request frequency should still be adjusted based on the total number of monitored users.

<a id="use-hour-range-checking"></a>
### Use Hour-Range Checking

The tool supports limiting fetching updates to specific hours of the day, which helps reduce detection by avoiding requests during times when automated activity might be more suspicious.

When hour-range checking is enabled, the tool will only fetch updates (posts, reels, stories, profile changes, followers/followings) during the configured time windows. Outside these hours, the tool will skip fetching updates but will continue running and wait for the next allowed time window.

To enable this feature, set `CHECK_POSTS_IN_HOURS_RANGE` to `True` and configure the allowed hour ranges using:
- `MIN_H1` and `MAX_H1` - first range of hours (default: 0-4, i.e., midnight to 4:59 AM)
- `MIN_H2` and `MAX_H2` - second range of hours (default: 11-23, i.e., 11:00 AM to 11:59 PM / 23:59)

You can define up to two non-overlapping or overlapping ranges. To disable any range, set both MIN and MAX to 0.

For example, to only allow checks during business hours (9 AM to 5 PM / 17:00), you could set:
- `MIN_H1 = 9`
- `MAX_H1 = 17`
- `MIN_H2 = 0`
- `MAX_H2 = 0`

Hours are specified in 24-hour format (0-23) and are evaluated in your configured time zone (see [Time Zone](#time-zone)).

If you want to see verbose output about when updates are being fetched or skipped, set `HOURS_VERBOSE` to `True`. This is useful for debugging and understanding when the tool is active.

This feature works particularly well when combined with reasonable polling intervals, as it ensures that even if your check interval triggers, requests will only be made during the configured time windows, making your activity pattern look more natural.

<a id="do-not-monitor-too-many-users"></a>
### Do Not Monitor Too Many Users

It is recommended to limit the number of users monitored by a single account, especially if they post frequent updates. When using multi-user monitoring (monitoring multiple users in one process), keep in mind that the total request volume increases with each additional target. In some cases, it may be best to create a separate account for additional users and even run it from a different IP address to reduce the risk of detection.

<a id="use-only-needed-functionality"></a>
### Use Only Needed Functionality

Frequent updates to certain data types, such as new stories or posts/reels, are more likely to flag the account as an automated tool compared to profile changes or lists of followers/followings.

If certain data isn't essential for your use case, consider disabling its retrieval. The tool provides fine-grained control, for example you can skip fetching stories details (`-r`), posts/reels details (`-w`), the list of followings (`-g` flag) and followers (`-f`).

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

<a id="troubleshooting"></a>
## Troubleshooting

In case of issues, run the tool with the `--debug` flag. It shows full HTTP traffic and internal script logic. Create a new issue in Github if you cannot fix it yourself.

### Choosing the Right Logging Level

- **Default Mode**: Silent and clean. Only logs changes (new posts, bio updates, etc.) and critical errors. Best for long-term production use.
- **Verbose Mode (`--verbose`)**: Recommended for most users. Shows when the next check is scheduled and confirms that the loop is running correctly.
- **Debug Mode (`--debug`)**: For developers or fixing issues. Shows full HTTP traffic, internal script logic

<a id="change-log"></a>
## Change Log

See [RELEASE_NOTES.md](https://github.com/misiektoja/instagram_monitor/blob/main/RELEASE_NOTES.md) for details.

<a id="license"></a>
## License

Licensed under GPLv3. See [LICENSE](https://github.com/misiektoja/instagram_monitor/blob/main/LICENSE).
