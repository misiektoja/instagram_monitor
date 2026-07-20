# instagram_monitor

<p align="left">
  <img src="https://img.shields.io/github/v/release/misiektoja/instagram_monitor?style=flat-square&color=blue" alt="GitHub Release" />
  <img src="https://img.shields.io/pypi/v/instagram_monitor?style=flat-square&color=teal" alt="PyPI Version" />
  <img src="https://img.shields.io/github/stars/misiektoja/instagram_monitor?style=flat-square&color=magenta" alt="GitHub Stars" />
  <img src="https://img.shields.io/badge/python-3.9+-blueviolet?style=flat-square" alt="Python Versions" />
  <img src="https://img.shields.io/docker/pulls/misiektoja/instagram-monitor?style=flat-square&logo=docker" alt="Docker Pulls" />
  <img src="https://img.shields.io/github/license/misiektoja/instagram_monitor?style=flat-square&color=blue" alt="License" />
  <img src="https://img.shields.io/github/last-commit/misiektoja/instagram_monitor?style=flat-square&color=green" alt="Last Commit" />
  <img src="https://img.shields.io/badge/maintenance-active-brightgreen?style=flat-square" alt="Maintenance" />
</p>

Powerful, real-time OSINT suite for tracking every activity on Instagram - from story updates and bio changes to follower shifts, providing stunning dashboards and instant alerts to keep you in the loop.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard.png" alt="instagram_monitor_web_dashboard_screenshot" width="100%"/>
</p>

<a id="-quick-install-run"></a>
### 🚀 Quick Install & Run

Python from PyPI (see also the video below)
```sh
pip install instagram_monitor
instagram_monitor --setup
```

Docker Compose
```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
docker compose run --rm instagram_monitor --setup
docker compose up
```

Docker run
```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm -it --init -v "$PWD:/data" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 8000:8000 misiektoja/instagram-monitor --setup
```

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_demo.gif" alt="instagram_monitor demo: install, setup wizard and run" width="100%"/>
</p>

<a id="features"></a>
## Features

### 🔍 Real-time Tracking
- **Profile Activity**: Monitor **new posts, reels** and **stories** in real-time.
- **Private Posts**: Detects **collab posts** leaking from **private accounts** via public collaborators.
- **Audience Insights**: Track changes in **followings** and **followers**.
- **Visual Changes**: Detect updates to **profile pictures** and **visibility** (public/private).
- **Bio Updates**: Stay informed about changes to **user bio**.

### 📥 Media Download
- **Anonymous Stories**: Download story images and videos **without leaving traces**.
- **High-Quality Media**: Save post images, reel videos and profile pictures.
- **Batch Support**: Monitor and download media for **multiple users simultaneously**.

### 📱 Interactive Dashboards
- **Guided Setup**: Interactive wizard writes a ready-to-run config for PyPI, script and Docker workflows.
- **Terminal Dashboard**: Beautiful, live-updating CLI interface with real-time stats.
- **Web Dashboard**: Modern, local web UI with activity feeds and remote controls.
- **Image Support**: View profile pictures and media directly in your terminal (via `imgcat`).

### 🔔 Smart Notifications
- **Multi-Channel**: Instant alerts via **Email**, **Discord webhooks** and native **ntfy** notifications.
- **Rich Alerts**: Attached media (profile pics, stories, posts) in Discord notifications.
- **Error Reporting**: Be notified if the monitoring process hits a snag.

### 🛡️ Privacy & Detection Avoidance
- **Be Human Mode**: Simulates random user actions to blend in.
- **Jitter Mode**: Adds human-like delays to HTTP requests.
- **Hour-Range Checking**: Limits activity to specific hours of the day.
- **Account Flexibility**: Works with or without a logged-in Instagram account.
- **Browser Session Import**: Reuse Firefox, Chrome, Brave or Chromium sessions with profile selection.
- **Browser TLS Impersonation**: Routes traffic through curl_cffi to mimic a real browser's TLS fingerprint and dodge fingerprint-based blocks.
- **Proxy Support**: Route Instagram and webhook traffic through your own proxy.
- **Privacy Substitutions**: Mask or rename identities across all output, logs and notifications.
- **Block Awareness**: Detects shadowbans and flagged sessions to avoid false alerts.

### ⚙️ Power Features
- **CSV Logging**: Log all activities and profile changes with timestamps.
- **Flexible Config**: Support for files, dotenv and environment variables.
- **Follower Churn**: Detailed tracking of exactly who followed or unfollowed.
- **Batched Fetching**: Throttle follower/following downloads into delayed batches.
- **Remote Control**: Manage tracking features via signals or the web UI.
- **Docker Ready**: Run via Docker Hub, Docker Compose or local image build with persisted config, dotenv and sessions.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_terminal_dashboard.png" alt="instagram_monitor_terminal_dashboard" width="100%"/>
</p>

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor.png" alt="instagram_monitor_log_screenshot" width="100%"/>
</p>

<a id="documentation"></a>
## Documentation

Full documentation is available at **[misiektoja.github.io/instagram_monitor](https://misiektoja.github.io/instagram_monitor/)**:

- [Installation](https://misiektoja.github.io/instagram_monitor/installation/) - PyPI, Docker and manual install
- [Quick Start](https://misiektoja.github.io/instagram_monitor/quick-start/) - the setup wizard and first run
- [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/) - session login, time zone, SMTP and secrets
- [View Modes](https://misiektoja.github.io/instagram_monitor/view-modes/) - text, terminal and web dashboards
- [Usage](https://misiektoja.github.io/instagram_monitor/usage/) - Docker, notifications, proxy, CSV and more
- [Anti-detection](https://misiektoja.github.io/instagram_monitor/anti-detection/) - avoid challenges and account suspension
- [Troubleshooting](https://misiektoja.github.io/instagram_monitor/troubleshooting/) - the `--doctor` self-check and logging levels

<a id="quick-start"></a>
## Quick Start

<a id="-new-here-run-the-setup-wizard"></a>
### 🧭 New here? Run the setup wizard

The fastest way to get going (since **v3.5**) is the interactive setup wizard. It asks a few plain questions (who to monitor, no-login or logged-in, which interface, optional alerts), then writes a ready-to-run config for you. For local installs it can also start monitoring immediately.

Use the command that matches how you run the tool:

```sh
# PyPI install
instagram_monitor --setup

# Manual Python script on macOS or Linux
python3 instagram_monitor.py --setup

# Manual Python script on Windows
python instagram_monitor.py --setup

# Docker Compose (skip curl if you cloned the repo)
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
docker compose run --rm instagram_monitor --setup

# Docker image
docker run --rm -it --init -v "$PWD:/data" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 8000:8000 misiektoja/instagram-monitor --setup
```

Running the tool with no arguments from an interactive terminal offers the same wizard when no operation is saved. If you save targets in the config, a later no-argument launch starts those targets directly. The wizard detects whether you installed via pip, downloaded the script or run under Docker. Local commands reuse the active Python executable while config and dotenv paths are safely quoted.

Answers stay editable until the final setup summary. You can save them, change one section without losing the others or confirm that you want to discard everything. Firefox and Chromium imports are separate choices. If Chromium support is missing on macOS or Linux, setup offers to install it in one step. Existing config files require confirmation and receive a timestamped backup. A failed secrets write or failed doctor check prevents automatic monitoring startup.

<a id="not-sure-which-mode-you-want"></a>
### Not sure which mode you want?

| I want to... | Run this |
| --- | --- |
| Just try it, no login | `instagram_monitor <target_insta_user>` |
| Be guided through setup | Use the setup command for your install path above |
| Avoid the command line | `instagram_monitor --web-dashboard` then use the browser |
| See stories, reels and who followed/unfollowed | Log in first ([browser session](https://misiektoja.github.io/instagram_monitor/configuration/#option-3-session-login-using-browser-cookies-recommended)), then `instagram_monitor -u <your_insta_user> <target_insta_user>` |

<a id="manual-commands"></a>
### Manual commands

If you prefer to run it in a container, jump to 🐳 [Docker Usage (Recommended)](https://misiektoja.github.io/instagram_monitor/usage/#docker-usage-recommended).

- Track the `target_insta_user` in [No-login mode](https://misiektoja.github.io/instagram_monitor/configuration/#no-login-mode-no-session-login) (no session login):

```sh
instagram_monitor <target_insta_user>
```

Or if you installed [manually](https://misiektoja.github.io/instagram_monitor/installation/#manual-python-based-installation), use `python3` on macOS or Linux and `python` on Windows:

```sh
# macOS or Linux
python3 instagram_monitor.py <target_insta_user>

# Windows
python instagram_monitor.py <target_insta_user>
```

- Track the `target_insta_user` in [Logged-in mode](https://misiektoja.github.io/instagram_monitor/configuration/#option-3-session-login-using-browser-cookies-recommended) (with session login via your web browser):

```sh
# log in to the Instagram account (your_insta_user) in your web browser (Firefox, Chrome, Brave or Chromium)
instagram_monitor --import-browser-session --browser firefox
instagram_monitor -u <your_insta_user> <target_insta_user>
```

- You can also launch the **[Web Dashboard](https://misiektoja.github.io/instagram_monitor/view-modes/#web-dashboard-mode)** along with tracking:

```sh
instagram_monitor <target_insta_user> --web-dashboard
```

To get the list of all supported command-line arguments / flags:

```sh
instagram_monitor --help
```

<a id="webhook-settings"></a>
## Webhook Settings

Instagram Monitor can send activity alerts through Discord or the native [ntfy publish API](https://docs.ntfy.sh/publish/). Webhooks work independently from email. The easiest setup is `instagram_monitor --setup`, where you can choose Discord or ntfy when asked about alerts.

`WEBHOOK_PROVIDER` selects the request format. It defaults to `"discord"` so existing configurations and custom Discord-compatible templates keep working.

<a id="discord"></a>
### Discord

Create a channel webhook in Discord under **Edit Channel > Integrations > Webhooks**, then keep the default provider in `instagram_monitor.conf`:

```ini
WEBHOOK_PROVIDER = "discord"
```

Save the private URL in `.env` as `WEBHOOK_URL` or pass it with `--webhook-url`.

<a id="ntfy"></a>
### ntfy

For ntfy.sh or a self-hosted ntfy server:

1. Choose a hard-to-guess topic such as `instagram-monitor-long-random-value`.
2. Use the complete topic URL such as `https://ntfy.sh/instagram-monitor-long-random-value`.
3. Set the provider in `instagram_monitor.conf`:

```ini
WEBHOOK_PROVIDER = "ntfy"
```

4. Save the topic URL in `.env` as `WEBHOOK_URL`.

Instagram Monitor sends the alert body and event field details as a bounded UTF-8 ntfy message, with the alert subject as its title. Query parameters already present in the topic URL are preserved, which supports the ntfy [`auth` query parameter](https://docs.ntfy.sh/publish/#authentication) for protected topics.

For a protected topic, the setup wizard can collect an ntfy access token through a hidden prompt. It saves the token in `.env` without displaying it. For manual setup, add the token to `.env`:

```ini
NTFY_ACCESS_TOKEN="tk_your_ntfy_access_token"
```

Instagram Monitor sends this value as `Authorization: Bearer <token>`. `NTFY_ACCESS_TOKEN` takes precedence over an `Authorization` entry in `WEBHOOK_HEADERS`.

Static custom headers remain available for advanced Discord or ntfy integrations in `instagram_monitor.conf`:

```python
WEBHOOK_HEADERS = {
    "Authorization": "Basic your_base64_credentials",
}
```

For ntfy, Instagram Monitor always sets the required plain-text `Content-Type`. Prefer `NTFY_ACCESS_TOKEN` in `.env` for Bearer authentication because a token inside `WEBHOOK_HEADERS` is easier to expose or commit accidentally. Header names and values are validated before any request is sent.

Topics on the public ntfy.sh service are public unless protected through an account reservation. Treat an unprotected topic name like a password and do not reuse the example topic above.

Enable the event types you want, then send a test without starting monitoring:

```ini
WEBHOOK_ENABLED = True
WEBHOOK_STATUS_NOTIFICATION = True
WEBHOOK_FOLLOWERS_NOTIFICATION = True
WEBHOOK_ERROR_NOTIFICATION = True
```

```sh
instagram_monitor --send-test-webhook
```

See the [Webhook Notifications guide](https://misiektoja.github.io/instagram_monitor/usage/#webhook-notifications) for full Discord, ntfy, command-line and advanced template settings.

<a id="change-log"></a>
## Change Log

See [RELEASE_NOTES.md](https://github.com/misiektoja/instagram_monitor/blob/main/RELEASE_NOTES.md) for details.

<a id="maintainers"></a>

<a id="maintainers"></a>
## Maintainers

- 👤 **misiektoja** ([@misiektoja](https://github.com/misiektoja))
- 👤 **tomballgithub** ([@tomballgithub](https://github.com/tomballgithub))

<a id="license"></a>

<a id="license"></a>
## License

Licensed under GPLv3. See [LICENSE](https://github.com/misiektoja/instagram_monitor/blob/main/LICENSE).
