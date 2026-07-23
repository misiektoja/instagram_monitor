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

#### Python from PyPI

```sh
pip install instagram_monitor
```

Run setup by itself:

```sh
instagram_monitor --setup
```

#### Docker image - fastest container setup

##### macOS or Windows

Use a macOS shell or Windows PowerShell with a Docker-compatible runtime that provides the `docker` CLI.

```sh
docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

After setup finishes, start monitoring with the files created by the wizard:

```sh
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --config-file /data/instagram_monitor.conf --env-file /data/.env
```

If setup enabled the Web Dashboard, add `-p 127.0.0.1:8000:8000` before the image name. The exact command printed by setup includes it only when needed.

The setup command pulls the current image. Both commands keep configuration and downloaded files in the current directory. They keep the saved Instagram login in the Docker volume named `instagram_monitor_session`.

In Windows Command Prompt replace `${PWD}` with `%cd%`. Windows hosts must use Linux containers.

##### Linux

`--user "$(id -u):$(id -g)"` runs the container with your numeric user and group IDs. This lets the container write files that your host account can edit.

```sh
docker run --rm --pull=always -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

After setup finishes, start monitoring:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --config-file /data/instagram_monitor.conf --env-file /data/.env
```

If setup enabled the Web Dashboard, add `-p 127.0.0.1:8000:8000` before the image name. The exact command printed by setup includes it only when needed.

#### Docker Compose - shorter recurring commands

Download the Compose file:

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
```

Linux container engine requires to export your numeric user ID and group ID so files created in the current directory belong to you instead of `root`.

```sh
export INSTAGRAM_MONITOR_UID="$(id -u)"
export INSTAGRAM_MONITOR_GID="$(id -g)"
```

Docker-compatible runtimes on macOS and Windows normally do not need these values.

Run setup by itself:

```sh
docker compose run --rm --pull=always instagram_monitor --setup
```

After setup finishes, start monitoring with the shorter recurring command:

```sh
docker compose up --no-log-prefix
```

For the manual single-file method, optional browser support and upgrade commands for every installation method, see [Installation](https://misiektoja.github.io/instagram_monitor/installation/).

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

- [Installation](https://misiektoja.github.io/instagram_monitor/installation/) - PyPI, manual script, Docker installation and upgrades
- [Quick Start](https://misiektoja.github.io/instagram_monitor/quick-start/) - setup wizard, login choices and first run
- [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/) - settings precedence, saved targets, session login, SMTP and secrets
- [View Modes](https://misiektoja.github.io/instagram_monitor/view-modes/) - text, terminal and web dashboards
- [Usage](https://misiektoja.github.io/instagram_monitor/usage/) - command formats, monitoring, container operation, notifications, proxy and output
- [Anti-detection](https://misiektoja.github.io/instagram_monitor/anti-detection/) - avoid challenges and account suspension
- [Troubleshooting](https://misiektoja.github.io/instagram_monitor/troubleshooting/) - the `--doctor` self-check and logging levels

<a id="quick-start"></a>
## Quick Start

<a id="new-here-run-the-setup-wizard"></a>
### New here? Run the setup wizard

The fastest way to get started is `--setup`. It asks who to monitor, whether to log in, which interface to use and which alerts you want then saves a ready-to-run configuration. Private values stay in `.env`.

If Instagram Monitor is not installed yet, use [Quick Install & Run](#-quick-install-run) above or choose a method in the full [Installation guide](https://misiektoja.github.io/instagram_monitor/installation/). Then use only the setup command that matches that installation.

```sh
# PyPI install
instagram_monitor --setup
```

```sh
# Manual Python script on macOS or Linux
python3 instagram_monitor.py --setup
```

```powershell
# Manual Python script on Windows
python instagram_monitor.py --setup
```

```sh
# Docker image on macOS or Windows PowerShell
docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

```sh
# Docker image on Linux
docker run --rm --pull=always -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

For Docker Compose, run setup from the directory that contains the downloaded `docker-compose.yml`. On a native Linux container engine, run these shell commands in the same terminal immediately before setup unless the variables are already set there or you saved the numeric values in the Compose `.env` file during installation. For permanent project values, use the numeric `.env` form in the full [Installation guide](https://misiektoja.github.io/instagram_monitor/installation/#docker-compose). Docker-compatible runtimes on macOS and Windows should skip this export block.

```sh
# Docker Compose on native Linux only
export INSTAGRAM_MONITOR_UID="$(id -u)"
export INSTAGRAM_MONITOR_GID="$(id -g)"
```

```sh
# Docker Compose
docker compose run --rm --pull=always instagram_monitor --setup
```

Running the tool with no arguments offers the wizard if you have not saved any targets or enabled the Web Dashboard. If targets are already saved, it starts monitoring them. The wizard detects the installation method and shows the commands that match it.

Firefox import is the recommended logged-in path for local and container installs. Docker setup asks for the host environment then prints a matching one-time read-only import command for macOS, Linux, Windows PowerShell or Windows Command Prompt. Later runs reuse the Instaloader session saved in the `instagram_monitor_session` volume. Chromium-based import remains unavailable inside containers because it requires the host password service.

See the [full Quick Start guide](https://misiektoja.github.io/instagram_monitor/quick-start/) for browser choices, saved targets, configuration backups and setup recovery.

<a id="not-sure-which-mode-you-want"></a>
### Not sure which command you need?

| I want to... | Run this |
| --- | --- |
| Set up Instagram Monitor for the first time | Use the setup command for your installation above |
| Try public monitoring without a login | `instagram_monitor <target_insta_user>` |
| Start targets saved in `TARGET_USERNAMES` | `instagram_monitor --config-file instagram_monitor.conf` or `docker compose up --no-log-prefix` |
| Start a browser control panel without targets | `instagram_monitor --web-dashboard` |
| Monitor several accounts | `instagram_monitor target_1 target_2` or `instagram_monitor --targets target_1,target_2` |
| Check the selected login, connectivity and targets | `instagram_monitor --doctor` |
| See stories, reels and follower details | Import a [browser session](https://misiektoja.github.io/instagram_monitor/configuration/#option-3-session-login-using-browser-cookies-recommended) then run `instagram_monitor -u <your_insta_user> <target_insta_user>` |

For complete copy-paste commands for every installation method, see [Run Individual Commands](https://misiektoja.github.io/instagram_monitor/quick-start/#run-individual-commands).

For container operation, browser profiles, email alerts, Discord, ntfy and advanced settings, see [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/) and [Usage](https://misiektoja.github.io/instagram_monitor/usage/). Keep private webhook URLs in `.env` or enter them through the setup wizard. See [Webhook Notifications](https://misiektoja.github.io/instagram_monitor/usage/#webhook-notifications) for complete setup and testing instructions.

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
