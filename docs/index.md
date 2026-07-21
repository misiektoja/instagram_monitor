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

Docker run

On macOS or Windows with Docker Desktop:

```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --config-file /data/instagram_monitor.conf --env-file /data/.env
```

The Docker Desktop command uses macOS shell or Windows PowerShell syntax. In Windows Command Prompt replace `${PWD}` with `%cd%`.

On Linux, pass your host user and group so the container can write to the current directory:

```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --config-file /data/instagram_monitor.conf --env-file /data/.env
```

For the manual single-file method, optional browser support and upgrade commands for every method, see [Installation](installation.md).

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
