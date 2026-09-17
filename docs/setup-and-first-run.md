# Setup & First Run

<a id="run-the-setup-wizard"></a>

## Run the setup wizard

This page assumes Instagram Monitor is already installed (see [Installation](installation.md)). It walks through the interactive setup wizard then your first monitoring run. If you opened this page first, choose [PyPI](installation.md#install-from-pypi), the [manual Python script](installation.md#install-the-manual-script), the [Docker image](installation.md#install-from-docker-hub) or [Docker Compose](installation.md#install-with-docker-compose), finish that method's steps then return here.

The wizard asks for targets, a saved login, polling interval, which follower lists to collect, interface, alerts and output files. In login mode it asks whether to collect followers and following, followers only, or counts only with no names at all, because names are the most expensive thing to request and the operation Instagram acts against. It asks where to read them from only when it is going to read them. The [HTTP backend](usage.md#http-transport-backend) keeps its saved value, since its default suits almost every setup. If `curl_cffi` is missing, requests is used until you install it. The experimental [browser source](usage.md#browser-source-experimental) is offered too and needs Playwright.

You can leave targets empty for the Web Dashboard and add accounts in your browser later. Terminal Dashboard and plain-text mode need at least one target. Polling accepts seconds or durations such as `1.5h` and `1h 30m`.

Review or change your answers before saving. Settings go to `instagram_monitor.conf` and private values go to `.env`. Setup asks before replacing a saved secret. See [Storing Secrets](configuration.md#storing-secrets) for backup details.

A rerun uses saved settings as defaults. Declining a section disables it. Setup explains invalid answers and lets you retry. Email setup checks sign-in without sending a message. If the mail server is unreachable, check the saved settings later with `--doctor`.

After saving, the wizard offers the Doctor checks. For a local install it then offers to start monitoring once those checks passed. In a container, it prints the next Docker or Docker Compose commands to run.

Use the tab that matches how you installed the tool. Copy and run only the commands in that tab.

=== "PyPI"

    ```sh
    instagram_monitor --setup
    ```

=== "Manual Python script on macOS or Linux"

    ```sh
    python3 instagram_monitor.py --setup
    ```

=== "Manual Python script on Windows"

    ```powershell
    python instagram_monitor.py --setup
    ```

=== "Docker image on macOS or Windows PowerShell"

    ```sh
    docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
    ```

=== "Docker image on Linux"

    ```sh
    docker run --rm --pull=always -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
    ```

=== "Docker Compose"

    Run setup from the directory used during installation. You do not need to download `docker-compose.yml` again.

    On a native Linux container engine, run these shell commands in the same terminal immediately before setup unless the variables are already set there or you saved the numeric values in the Compose `.env` file during installation. For permanent project values, use the numeric `.env` form under [Install with Docker Compose](installation.md#install-with-docker-compose). Docker-compatible runtimes on macOS and Windows should skip this export block.

    ```sh
    export INSTAGRAM_MONITOR_UID="$(id -u)"
    export INSTAGRAM_MONITOR_GID="$(id -g)"
    ```

    Then run setup by itself:

    ```sh
    docker compose run --rm --pull=always instagram_monitor --setup
    ```

Run interactive setup commands by themselves instead of including them in a multi-command paste.

In Windows Command Prompt replace `${PWD}` with `%cd%`. Windows hosts must use Linux containers. The `:z` suffix is for hosts that use SELinux. If your Docker-compatible runtime reports that it is invalid, remove only `:z`.

In this documentation, a **target** is an Instagram account you want to monitor. The **session account** is the Instagram account that Instagram Monitor uses to sign in. They can be different accounts.

The wizard recommends importing a saved Firefox login. On macOS and Linux it can also import from Chrome, Brave or Chromium. Those three browsers require the optional `pycookiecheat` package. If it is missing, the wizard can install it in a local Python installation.

Activate your virtual environment before running local commands. For a downloaded script, run them from the script directory.

Container setup destinations must stay inside `/data`. That directory is the current host directory mounted into the temporary setup container, so files written there survive `--rm`. The wizard rejects paths such as `/tmp/instagram_monitor.conf` instead of printing a command for a different file.

`--setup` needs somewhere to put both files, so it refuses `--config-file none` and `--env-file none`.

For Docker or Docker Compose, choose **Import from Firefox after setup**. The wizard asks whether Docker runs on macOS, standard Linux, Linux with Snap, Linux with Flatpak, Windows PowerShell or Windows Command Prompt. It then prints the matching command to mount the signed-in host profile read-only once and save the imported login in the persistent `instagram_monitor_session` volume. Windows commands use the Firefox profile under `%APPDATA%\Mozilla\Firefox`.

Firefox import works on macOS, Linux and Windows without an extra package. Containers use Firefox. Chrome, Brave and Chromium import needs the optional browser dependency and works only on macOS and Linux. See [Session Login Using Browser Cookies](configuration.md#option-3-session-login-using-browser-cookies-recommended).

Running without arguments starts the targets saved in `TARGET_USERNAMES`. With only the Web Dashboard enabled, it opens an empty control panel where you can add targets. If neither is saved, an interactive run opens the setup wizard.

<a id="before-you-start"></a>
## Before you start

How much Instagram Monitor can see depends on the target and on the login you give it:

1. A public target can be monitored with no login at all, in [No-Login Mode](configuration.md#no-login-mode-no-session-login). Posts, bio and follower counts are visible, follower and following lists are not.
2. Stories, reels and named follower changes need a session account, in [Logged-In Mode](configuration.md#logged-in-mode-with-session-login).
3. A private target needs a session account that already follows it. Send and get the follow request accepted before the first run.

Logged-in monitoring can trigger a security challenge or a suspension, so use a separate Instagram account if losing access to your main one would be unacceptable. The setup wizard asks which login you want and saves the choice. See the [risk reduction guide](anti-detection.md).

<a id="not-sure-which-command-you-need"></a>
## Not sure which command you need?

The table uses the PyPI command. If you chose another installation, use its [command prefix](usage.md#command-format-by-installation-method) instead of `instagram_monitor`.

| I want to... | Run this |
| --- | --- |
| Set up Instagram Monitor for the first time | Use the setup command for your installation above |
| Try public monitoring without a login | `instagram_monitor <target_insta_user>` |
| Start targets saved in `TARGET_USERNAMES` | `instagram_monitor --config-file instagram_monitor.conf` or `docker compose up --no-log-prefix` |
| Start a browser control panel without targets | `instagram_monitor --web-dashboard` |
| Monitor several accounts | `instagram_monitor target_1 target_2` or `instagram_monitor --targets target_1,target_2` |
| Check the selected login, connectivity and targets | `instagram_monitor --doctor` |
| Import an Instagram login from Firefox | Sign in at [instagram.com](https://www.instagram.com/) in Firefox then run `instagram_monitor --import-browser-session --browser firefox` |
| Save an SMTP password for email alerts | Run `instagram_monitor --set-smtp-password` |
| Send a test email | Run `instagram_monitor --send-test-email` |
| Save a new webhook URL | Run `instagram_monitor --set-webhook-url` |
| Send a test webhook | Run `instagram_monitor --send-test-webhook` |
| Write every change to a CSV file | `instagram_monitor <target_insta_user> -b changes.csv` |
| List every supported command-line flag | `instagram_monitor --help` |
| See stories, reels and follower details | Import a browser session then run `instagram_monitor -u <your_insta_user> <target_insta_user>` |

<a id="run-individual-commands"></a>
## Run Individual Commands

The examples below use PyPI. For a manual script, replace `instagram_monitor` with `python3 instagram_monitor.py` on macOS or Linux. Use `python instagram_monitor.py` on Windows. Docker users should copy the matching prefix under [Command Format by Installation Method](usage.md#command-format-by-installation-method).

Throughout this page `<target_insta_user>` means the Instagram username to monitor and `<your_insta_user>` the account you sign in with.

<a id="save-an-instagram-login"></a>
### Save an Instagram login

A public account needs no login. For stories, reels and detailed follower changes, use [Logged-In Mode](configuration.md#logged-in-mode-with-session-login). Log in to Instagram in a supported browser then import the session. Firefox is the recommended local path:

```sh
instagram_monitor --import-browser-session --browser firefox
```

The import converts the browser login into a saved Instaloader session. The value passed to `-u` later must be the username of that logged-in account. Container users must use the same `instagram_monitor_session` Docker volume for the import and later monitoring runs. The complete import command is under [Container Operation](usage.md#container-operation).

<a id="save-notification-credentials"></a>
### Save notification credentials

The SMTP password is entered through a hidden prompt, checked against the mail server and saved as `SMTP_PASSWORD` in `.env`:

```sh
instagram_monitor --set-smtp-password
```

A webhook URL is the private address used to deliver notifications. Treat it like a password because anyone who has it may be able to post through it. Follow the [webhook setup steps](configuration.md#webhook-settings) then save the link:

```sh
instagram_monitor --set-webhook-url
```

The link is entered through a hidden prompt and saved as `WEBHOOK_URL` in `.env`. This command only saves the link. It does not turn on webhook alerts or send a message. See [Webhook Settings](configuration.md#webhook-settings) to choose your alerts then run `instagram_monitor --send-test-webhook` to test them.

<a id="start-monitoring"></a>
### Start monitoring

Track a public account in [No-Login Mode](configuration.md#no-login-mode-no-session-login). The second command uses the imported session:

```sh
instagram_monitor <target_insta_user>
instagram_monitor -u <your_insta_user> <target_insta_user>
```

Launch the [Web Dashboard](view-modes.md#web-dashboard) with a target or as an empty control panel:

```sh
instagram_monitor <target_insta_user> --web-dashboard
instagram_monitor --web-dashboard
```

A one-off Compose command needs `--service-ports` so the browser can reach the dashboard. A direct Docker command needs a port mapping. Both complete commands are under [Monitoring Mode](usage.md#monitoring-mode).

To check the setup before the first run, without writing anything:

```sh
instagram_monitor --doctor
```

See [Doctor Preflight](troubleshooting.md#doctor-preflight) for what it reports.

View every command-line option plus examples adapted to the detected installation:

```sh
instagram_monitor --help
```

<a id="next-step"></a>
## Next Step

With a login chosen and a first run working, continue to [Configuration](configuration.md) for settings precedence, saved targets, session login, SMTP and secrets. See [View Modes](view-modes.md) for the text, terminal and web dashboards then [Usage](usage.md) for command formats, monitoring, container operation, notifications and output.
