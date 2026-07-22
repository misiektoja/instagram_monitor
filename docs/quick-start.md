# Quick Start

<a id="new-here-run-the-setup-wizard"></a>
## New here? Run the setup wizard

First complete one method on the [Installation](installation.md) page. The fastest way to configure that installation is the interactive setup wizard. It asks who to monitor, whether to use a login session, which interface to start and whether to enable alerts. Before saving, you can review the summary and edit one section without losing the other answers. It then writes a ready-to-run configuration while private values stay in `.env`.

For local installs the wizard can also run the doctor check and start monitoring immediately. In a container it prints the exact follow-up commands for the detected Docker or Docker Compose path.

Before running the Docker Compose setup command on Linux, export `INSTAGRAM_MONITOR_UID="$(id -u)"` and `INSTAGRAM_MONITOR_GID="$(id -g)"` as shown under [Install with Docker Compose](installation.md#docker-compose).

Use the command that matches how you run the tool:

```sh
# PyPI install
instagram_monitor --setup

# Manual Python script on macOS or Linux
python3 instagram_monitor.py --setup

# Manual Python script on Windows
python instagram_monitor.py --setup

# Docker Compose (skip curl if you cloned the repository)
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
docker compose run --rm instagram_monitor --setup

# Docker image on macOS or Windows PowerShell
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup

# Docker image on Linux
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

In Windows Command Prompt replace `${PWD}` with `%cd%`. If your Docker-compatible runtime rejects the `:z` mount suffix, remove only that suffix.

The wizard asks for Instagram targets, recommends Firefox-based import and lets you choose email alerts, webhook alerts or both. On macOS and Linux it offers Chrome, Brave and Chromium as a separate cookie import path. If the optional `pycookiecheat` package is missing, setup can install it into the active Python environment before continuing.

The wizard detects PyPI, downloaded-script, Docker and Docker Compose installations then prints matching commands. Local commands reuse the active Python executable. Config and dotenv paths are quoted for the active operating system.

It writes regular settings to `instagram_monitor.conf` while private values go only to `.env`.

Firefox import works in every local installation without an extra package. Chrome, Brave and Chromium import is available on macOS and Linux with the optional browser dependency. Container setup uses Firefox only because Chromium cookie decryption needs the host keyring. See [Session Login Using Browser Cookies](configuration.md#option-3-session-login-using-browser-cookies-recommended).

Running the tool with no arguments from an interactive terminal offers the wizard when neither saved targets nor a saved Web Dashboard are available. If you save targets in `TARGET_USERNAMES`, a later no-argument launch starts those targets. If you save the Web Dashboard without targets, it starts as a browser control panel where you can add targets.

<a id="not-sure-which-mode-you-want"></a>
## Not sure which command you need?

The short commands in this table use PyPI. Keep the options and replace `instagram_monitor` with the prefix under [Command Format by Installation Method](usage.md#command-format) when you use another installation.

| I want to... | Run this |
| --- | --- |
| Set up Instagram Monitor for the first time | Use the setup command for your installation above |
| Try public monitoring without a login | `instagram_monitor <target_insta_user>` |
| Start targets saved in `TARGET_USERNAMES` | `instagram_monitor --config-file instagram_monitor.conf` or `docker compose up` |
| Start a browser control panel without targets | `instagram_monitor --web-dashboard` |
| Monitor several accounts | `instagram_monitor target_1 target_2` or `instagram_monitor --targets target_1,target_2` |
| Check the selected login, connectivity and targets | `instagram_monitor --doctor` |
| See stories, reels and follower details | Import a browser session then run `instagram_monitor -u <your_insta_user> <target_insta_user>` |

<a id="manual-commands"></a>
## Run Individual Commands

The examples below use PyPI. For a manual script replace `instagram_monitor` with `python3 instagram_monitor.py` on macOS or Linux and `python instagram_monitor.py` on Windows. Docker and Docker Compose users should use the prefixes under [Command Format by Installation Method](usage.md#command-format).

Track a public account in [No-Login Mode](configuration.md#no-login-mode-without-session-login):

```sh
instagram_monitor <target_insta_user>
```

For stories, reels and detailed follower changes, log in to Instagram in a supported browser then import the session. Firefox is the recommended local path:

```sh
instagram_monitor --import-browser-session --browser firefox
instagram_monitor -u <your_insta_user> <target_insta_user>
```

The browser import saves an Instaloader session. Keep using the same `-u` username during monitoring. Container users must reuse the same named session volume and mount Firefox for the one-time import as shown under [Container Operation](usage.md#container-operation).

Launch the [Web Dashboard](view-modes.md#web-dashboard-mode) with a target or as an empty control panel:

```sh
instagram_monitor <target_insta_user> --web-dashboard
instagram_monitor --web-dashboard
```

Compose one-off Web Dashboard commands need `--service-ports`. Direct Docker commands need the loopback port mapping. Both complete forms are under [Monitoring Mode](usage.md#monitoring-mode).

View every command-line option plus examples adapted to the detected installation:

```sh
instagram_monitor --help
```
