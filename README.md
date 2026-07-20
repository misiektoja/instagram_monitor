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

Python from PyPI
```sh
pip install instagram_monitor
instagram_monitor --setup
```

Docker Compose

On native Linux export your host identity first. Docker Desktop users on macOS or Windows can skip the two `export` commands.

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
export INSTAGRAM_MONITOR_UID="$(id -u)"
export INSTAGRAM_MONITOR_GID="$(id -g)"
docker compose run --rm instagram_monitor --setup
docker compose up
```

Docker run on macOS or Linux
```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor --setup
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

The fastest way to get started is `--setup`. It asks who to monitor, whether to log in, which interface to use and which alerts you want then saves a ready-to-run configuration. For local installs it can also run the self-check and start monitoring.

Use the command that matches how you run the tool:

On Linux, set `INSTAGRAM_MONITOR_UID="$(id -u)"` and `INSTAGRAM_MONITOR_GID="$(id -g)"` before using Docker Compose. Docker Desktop users on macOS or Windows can skip this step.

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

# Docker image on macOS or Linux
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor --setup
```

Running the tool with no arguments offers the wizard when no target has been saved. With saved targets, it starts monitoring directly. The wizard detects PyPI, script, Docker or Docker Compose installs and shows matching commands.

See the [full Quick Start guide](https://misiektoja.github.io/instagram_monitor/quick-start/) for browser choices, configuration backups and setup recovery.

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

The examples below use a PyPI install. For a manual script install, replace `instagram_monitor` with `python3 instagram_monitor.py` on macOS or Linux and `python instagram_monitor.py` on Windows.

Track a public account without logging in:

```sh
instagram_monitor <target_insta_user>
```

For stories, reels and follower changes, sign in through a supported browser then import the session:

```sh
instagram_monitor --import-browser-session --browser firefox
instagram_monitor -u <your_insta_user> <target_insta_user>
```

Launch the [Web Dashboard](https://misiektoja.github.io/instagram_monitor/view-modes/#web-dashboard-mode) with monitoring:

```sh
instagram_monitor <target_insta_user> --web-dashboard
```

View every command:

```sh
instagram_monitor --help
```

For Docker commands, browser profiles, email alerts, Discord, ntfy and advanced settings, see [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/) and [Usage](https://misiektoja.github.io/instagram_monitor/usage/). Keep private webhook URLs in `.env` or enter them through the setup wizard. See [Webhook Notifications](https://misiektoja.github.io/instagram_monitor/usage/#webhook-notifications) for complete setup and testing instructions.

<a id="change-log"></a>
## Change Log

See [RELEASE_NOTES.md](https://github.com/misiektoja/instagram_monitor/blob/main/RELEASE_NOTES.md) for details.

<a id="maintainers"></a>
## Maintainers

- 👤 **misiektoja** ([@misiektoja](https://github.com/misiektoja))
- 👤 **tomballgithub** ([@tomballgithub](https://github.com/tomballgithub))

<a id="license"></a>
## License

Licensed under GPLv3. See [LICENSE](https://github.com/misiektoja/instagram_monitor/blob/main/LICENSE).
