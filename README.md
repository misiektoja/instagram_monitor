# instagram_monitor

[![GitHub Release](https://img.shields.io/github/v/release/misiektoja/instagram_monitor?style=flat-square&color=blue)](https://github.com/misiektoja/instagram_monitor/releases)
[![PyPI Version](https://img.shields.io/pypi/v/instagram_monitor?style=flat-square&color=teal)](https://pypi.org/project/instagram-monitor/)
[![GitHub Stars](https://img.shields.io/github/stars/misiektoja/instagram_monitor?style=flat-square&color=magenta)](https://github.com/misiektoja/instagram_monitor)
[![Python Versions](https://img.shields.io/badge/python-3.9+-blueviolet?style=flat-square)](https://pypi.org/project/instagram-monitor/)
[![Docker Pulls](https://img.shields.io/docker/pulls/misiektoja/instagram-monitor?style=flat-square&logo=docker)](https://hub.docker.com/r/misiektoja/instagram-monitor)
[![License](https://img.shields.io/github/license/misiektoja/instagram_monitor?style=flat-square&color=blue)](https://github.com/misiektoja/instagram_monitor/blob/main/LICENSE)
[![OpenSSF Scorecard](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.scorecard.dev%2Fprojects%2Fgithub.com%2Fmisiektoja%2Finstagram_monitor&query=%24.score&label=openssf%20scorecard&style=flat-square)](https://scorecard.dev/viewer/?uri=github.com/misiektoja/instagram_monitor)
[![Last Commit](https://img.shields.io/github/last-commit/misiektoja/instagram_monitor?style=flat-square&color=green)](https://github.com/misiektoja/instagram_monitor/commits/main)
[![Maintenance](https://img.shields.io/badge/maintenance-active-brightgreen?style=flat-square)](https://github.com/misiektoja/instagram_monitor)

Powerful, real-time OSINT suite for tracking every activity on Instagram - from story updates and bio changes to follower shifts, providing stunning dashboards and instant alerts to keep you in the loop.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard.png" alt="instagram_monitor_web_dashboard_screenshot" width="100%"/>
</p>

<a id="quick-install-run"></a>
### 🚀 Quick Install & Run

#### Python from PyPI

New to Python or unsure what is installed? Follow the [Python install walkthrough](https://misiektoja.github.io/instagram_monitor/installation/#new-to-python-check-and-install) first.

```sh
pip install instagram_monitor
```

Run setup wizard:

```sh
instagram_monitor --setup
```

The wizard asks for the targets, the Instagram login, the interface and optional notifications. Review the settings before saving them. See [Setup & First Run](https://misiektoja.github.io/instagram_monitor/setup-and-first-run/) for the Instagram login options and the first monitoring run.

#### Docker image - fastest container setup

##### macOS or Windows

Use a macOS shell or Windows PowerShell with a Docker-compatible runtime that provides the `docker` CLI.

```sh
docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

In Windows Command Prompt replace `${PWD}` with `%cd%` above.

##### Linux

Run the container with your numeric user and group IDs (`--user "$(id -u):$(id -g)"` below). This lets the container write files that your host account can edit.

```sh
docker run --rm --pull=always -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

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

Run setup wizard:

```sh
docker compose run --rm --pull=always instagram_monitor --setup
```

For the manual single-file method, optional extras and upgrade commands, see [Installation](https://misiektoja.github.io/instagram_monitor/installation/).

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
- **Error Reporting**: Be notified when monitoring starts failing, and again when it recovers.

### 🛡️ Privacy & Detection Avoidance
- **Be Human Mode**: Simulates random user actions to blend in.
- **Jitter Mode**: Adds human-like delays to HTTP requests.
- **Hour-Range Checking**: Limits activity to specific hours of the day.
- **Identity Budget**: Caps how many follower and following names are fetched per day.
- **Circuit Breaker**: Stops every target after Instagram challenges your account until a restart or a fresh session clears it.
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
- **Follow Analysis**: Inspect mutual, not-following-back and fan relationships offline from saved lists with `--analyze-follows` or the Web Dashboard.
- **Selectable Follower List Source**: Reads follower and following lists from the web REST endpoints Instagram's own app calls, falling back to the older GraphQL queries, with an experimental browser source for when both are broken.
- **Batched Fetching**: Throttle follower/following downloads into delayed batches.
- **Remote Control**: Manage tracking features via signals or the web UI.
- **Docker Ready**: Run via Docker Hub, Docker Compose or local image build with persisted config, dotenv and sessions.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_terminal_dashboard.png" alt="instagram_monitor_terminal_dashboard" width="100%"/>
</p>

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor.png" alt="instagram_monitor_log_screenshot" width="100%"/>
</p>

<a id="common-commands"></a>
## Common Commands

Use [Quick Install & Run](#quick-install-run) above for first-time setup. The table uses PyPI commands. For manual script, direct Docker and Docker Compose equivalents, see [Run Individual Commands](https://misiektoja.github.io/instagram_monitor/setup-and-first-run/#run-individual-commands).

Replace the target placeholders with an Instagram username.

| I want to... | Run this |
| --- | --- |
| Configure the target, credentials and alerts | `instagram_monitor --setup` |
| Start monitoring a public target without a login | `instagram_monitor <target_insta_user>` |
| Start monitoring with an existing logged in session (stories, reels and follower details) | Import a [browser session](https://misiektoja.github.io/instagram_monitor/configuration/#option-3-session-login-using-browser-cookies-recommended) then run `instagram_monitor -u <your_insta_user> <target_insta_user>` |
| Check the selected login, connectivity and targets | `instagram_monitor --doctor` |
| Monitor several accounts without login | `instagram_monitor target_1 target_2` or `instagram_monitor --targets target_1,target_2` |
| Start a browser control panel without targets | `instagram_monitor --web-dashboard` |
| Import an Instagram login from Firefox | Sign in at [instagram.com](https://www.instagram.com/) in Firefox then run `instagram_monitor --import-browser-session --browser firefox` |
| Configure and test webhook alerts | Use the setup wizard or follow [Webhook Notifications](https://misiektoja.github.io/instagram_monitor/usage/#webhook-notifications) |
| Save an SMTP password for email alerts | `instagram_monitor --set-smtp-password` |
| Send a test email | `instagram_monitor --send-test-email` |
| Save a new webhook URL | `instagram_monitor --set-webhook-url` |
| Send a test webhook | `instagram_monitor --send-test-webhook` |
| Write every change to a CSV file | `instagram_monitor <target_insta_user> -b changes.csv` |
| List every supported command-line flag | `instagram_monitor --help` |

Running the tool with no arguments offers the wizard if you have not saved any targets or enabled the Web Dashboard. If targets are already saved, it starts monitoring them.

The tool runs until interrupted (`Ctrl+C`). Use `tmux` or `screen` for persistence. One run can monitor several accounts through `TARGET_USERNAMES` or `--targets`, so a second copy is not needed.

For browser choices, saved targets, configuration backups and setup recovery, see the [full Setup & First Run guide](https://misiektoja.github.io/instagram_monitor/setup-and-first-run/).

For container operation, browser profiles, email and webhook setup, see [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/). For notification choices, proxy settings and output files, see [Usage](https://misiektoja.github.io/instagram_monitor/usage/).

If a run fails, start with [Doctor Preflight](https://misiektoja.github.io/instagram_monitor/troubleshooting/#doctor-preflight).

<a id="documentation"></a>
## Documentation

Full documentation is available at **[misiektoja.github.io/instagram_monitor](https://misiektoja.github.io/instagram_monitor/)**:

| Page | What it covers |
| --- | --- |
| [Installation](https://misiektoja.github.io/instagram_monitor/installation/) | Python walkthrough, PyPI, manual script and Docker installation, upgrades |
| [Setup & First Run](https://misiektoja.github.io/instagram_monitor/setup-and-first-run/) | Setup wizard, login choices, the first monitoring run |
| [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/) | Settings precedence, saved targets, session login, SMTP, storing secrets, check intervals |
| [View Modes](https://misiektoja.github.io/instagram_monitor/view-modes/) | Text output, terminal dashboard and web dashboard |
| [Usage](https://misiektoja.github.io/instagram_monitor/usage/) | Command formats, monitoring, container operation, notifications, proxy, terminal output |
| [Anti-detection](https://misiektoja.github.io/instagram_monitor/anti-detection/) | Avoiding challenges and account suspension |
| [Troubleshooting](https://misiektoja.github.io/instagram_monitor/troubleshooting/) | `--doctor` preflight checks, what to do when something fails, `--verbose` and `--debug` output |
| [Testing](https://misiektoja.github.io/instagram_monitor/testing/) | Running the offline suite, the linter and the docs build |
| [About](https://misiektoja.github.io/instagram_monitor/about/) | Change log, contributing, security, license, support |

<a id="change-log"></a>
## Change Log

See [RELEASE_NOTES.md](https://github.com/misiektoja/instagram_monitor/blob/main/RELEASE_NOTES.md) for details.

<a id="contributing"></a>
## Contributing

Bug reports, documentation fixes and code contributions are welcome. See [CONTRIBUTING.md](https://github.com/misiektoja/instagram_monitor/blob/main/CONTRIBUTING.md) for the development setup, the checks CI enforces and what a change needs before it is merged. Participation is covered by the [Code of Conduct](https://github.com/misiektoja/instagram_monitor/blob/main/CODE_OF_CONDUCT.md).

<a id="security"></a>
## Security

Report a suspected vulnerability privately through [GitHub security advisories](https://github.com/misiektoja/instagram_monitor/security/advisories/new), never as a public issue. [SECURITY.md](https://github.com/misiektoja/instagram_monitor/blob/main/SECURITY.md) covers the reporting process, the supported versions and the security posture of the Web Dashboard, stored secrets and monitored account data.

<a id="maintainers"></a>
## Maintainers

- 👤 **misiektoja** ([@misiektoja](https://github.com/misiektoja))
- 👤 **tomballgithub** ([@tomballgithub](https://github.com/tomballgithub))

<a id="license"></a>
## License

Licensed under GPLv3. See [LICENSE](https://github.com/misiektoja/instagram_monitor/blob/main/LICENSE). Dependency licenses are listed in [THIRD_PARTY_NOTICES.md](https://github.com/misiektoja/instagram_monitor/blob/main/THIRD_PARTY_NOTICES.md).

<a id="support"></a>
## Support

Questions, bug reports and vulnerability reports each have a place, listed in [SUPPORT.md](https://github.com/misiektoja/instagram_monitor/blob/main/SUPPORT.md).

If the project is useful to you, you can support its development through [GitHub Sponsors](https://github.com/sponsors/misiektoja) or [Buy Me a Coffee](https://buymeacoffee.com/misiektoja).
