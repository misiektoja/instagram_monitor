# Quick Start

<a id="-new-here-run-the-setup-wizard"></a>
## 🧭 New here? Run the setup wizard

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
## Not sure which mode you want?

| I want to... | Run this |
| --- | --- |
| Just try it, no login | `instagram_monitor <target_insta_user>` |
| Be guided through setup | Use the setup command for your install path above |
| Avoid the command line | `instagram_monitor --web-dashboard` then use the browser |
| See stories, reels and who followed/unfollowed | Log in first ([browser session](configuration.md#option-3-session-login-using-browser-cookies-recommended)), then `instagram_monitor -u <your_insta_user> <target_insta_user>` |

<a id="manual-commands"></a>
## Manual commands

If you prefer to run it in a container, jump to 🐳 [Docker Usage (Recommended)](usage.md#docker-usage-recommended).

- Track the `target_insta_user` in [No-login mode](configuration.md#no-login-mode-no-session-login) (no session login):

```sh
instagram_monitor <target_insta_user>
```

Or if you installed [manually](installation.md#manual-python-based-installation):

```sh
python3 instagram_monitor.py <target_insta_user>
```

- Track the `target_insta_user` in [Logged-in mode](configuration.md#option-3-session-login-using-browser-cookies-recommended) (with session login via your web browser):

```sh
# log in to the Instagram account (your_insta_user) in your web browser (Firefox, Chrome, Brave or Chromium)
instagram_monitor --import-browser-session --browser firefox
instagram_monitor -u <your_insta_user> <target_insta_user>
```

- You can also launch the **[Web Dashboard](view-modes.md#web-dashboard-mode)** along with tracking:

```sh
instagram_monitor <target_insta_user> --web-dashboard
```

To get the list of all supported command-line arguments / flags:

```sh
instagram_monitor --help
```
