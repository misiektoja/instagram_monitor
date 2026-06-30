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

### 🚀 Quick Install & Run

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_demo.gif" alt="instagram_monitor demo: install, setup wizard and run" width="100%"/>
</p>

Python from PyPI
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
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard.png" alt="instagram_monitor_web_dashboard_screenshot" width="100%"/>
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
- **Multi-Channel**: Instant alerts via **Email** and **Webhooks** (**Discord** etc.).
- **Rich Alerts**: Attached media (profile pics, stories, posts) directly in notifications.
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

## Documentation

Full documentation is available at **[misiektoja.github.io/instagram_monitor](https://misiektoja.github.io/instagram_monitor/)**:

- [Installation](https://misiektoja.github.io/instagram_monitor/installation/) - PyPI, Docker and manual install
- [Quick Start](https://misiektoja.github.io/instagram_monitor/quick-start/) - the setup wizard and first run
- [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/) - session login, time zone, SMTP and secrets
- [View Modes](https://misiektoja.github.io/instagram_monitor/view-modes/) - text, terminal and web dashboards
- [Usage](https://misiektoja.github.io/instagram_monitor/usage/) - Docker, notifications, proxy, CSV and more
- [Anti-detection](https://misiektoja.github.io/instagram_monitor/anti-detection/) - avoid challenges and account suspension
- [Troubleshooting](https://misiektoja.github.io/instagram_monitor/troubleshooting/) - the `--doctor` self-check and logging levels

## Quick Start

<a id="-new-here-run-the-setup-wizard"></a>
### 🧭 New here? Run the setup wizard

The fastest way to get going (since **v3.5**) is the interactive setup wizard. It asks a few plain questions (who to monitor, no-login or logged-in, which interface, optional alerts), then writes a ready-to-run config for you. For local installs it can also start monitoring immediately.

Use the command that matches how you run the tool:

```sh
# PyPI install
instagram_monitor --setup

# Manual Python script
python3 instagram_monitor.py --setup

# Docker Compose (skip curl if you cloned the repo)
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
docker compose run --rm instagram_monitor --setup

# Docker image
docker run --rm -it --init -v "$PWD:/data" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 8000:8000 misiektoja/instagram-monitor --setup
```

Running the tool with no arguments from an interactive terminal offers the same wizard. It auto-detects whether you installed via pip, downloaded the script or run under Docker and shows commands that match your setup.

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

Or if you installed [manually](https://misiektoja.github.io/instagram_monitor/installation/#manual-python-based-installation):

```sh
python3 instagram_monitor.py <target_insta_user>
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

## Change Log

See [RELEASE_NOTES.md](https://github.com/misiektoja/instagram_monitor/blob/main/RELEASE_NOTES.md) for details.

<a id="maintainers"></a>

## Maintainers

- 👤 **misiektoja** ([@misiektoja](https://github.com/misiektoja))
- 👤 **tomballgithub** ([@tomballgithub](https://github.com/tomballgithub))

<a id="license"></a>

## License

Licensed under GPLv3. See [LICENSE](https://github.com/misiektoja/instagram_monitor/blob/main/LICENSE).
