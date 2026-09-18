# Setup & First Run

<a id="run-the-setup-wizard"></a>
## Run the setup wizard

Already installed? Run the setup command below for your installation and follow the prompts. Otherwise, start with [Installation](installation.md).

The wizard setup asks for targets, a saved login, polling interval, which follower lists to collect, interface, alerts and output files. You can review your answers before saving. Regular settings go in `instagram_monitor.conf` and private values go in `.env`. Keep `.env` private.

Press Enter to accept a default or Ctrl+C to cancel. Cancelling before saving leaves your files untouched. Cancelling after saving keeps the saved settings. For changes to an existing setup, see [Configuration File](configuration.md#configuration-file).

After saving, follow the offered Doctor checks and monitoring steps.

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

In this documentation, a **target** is an Instagram account you want to monitor. The **session account** is the Instagram account that Instagram Monitor uses to sign in. They can be different accounts.

Targets can be usernames or complete profile URLs such as `https://www.instagram.com/someuser/`

The wizard recommends importing a saved web browser login.

Container setup destinations must stay inside `/data`, which is the host directory mounted for setup. Files saved there remain on your computer after the container stops.

After saving authentication, the wizard checks whether the target is visible.

<a id="before-you-start"></a>
## Before you start

How much Instagram Monitor can see depends on the target and on the login you give it:

1. A public target can be monitored with no login at all, in [No-Login Mode](configuration.md#no-login-mode-no-session-login). Posts, bio and follower counts are visible, follower and following lists are not.
2. Stories, reels and named follower / following changes need a session account, in [Logged-In Mode](configuration.md#logged-in-mode-with-session-login).
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

Throughout this page `<target_insta_user>` means the Instagram username to monitor, or a complete profile URL, and `<your_insta_user>` the account you sign in with.

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
