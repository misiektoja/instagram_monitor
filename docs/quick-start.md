# Quick Start

<a id="new-here-run-the-setup-wizard"></a>
## New here? Run the setup wizard

Quick Start configures an existing installation. If you opened this page first, choose [PyPI](installation.md#install-from-pypi), the [manual Python script](installation.md#manual-python-based-installation), the [Docker image](installation.md#install-from-docker-hub) or [Docker Compose](installation.md#docker-compose). Complete that method's prerequisites and return here.

Then use the interactive setup wizard. It asks which Instagram accounts to monitor, whether to use a saved login, which interface to start and which alerts to enable. You can review and change your answers before saving. Regular settings go in `instagram_monitor.conf`. Private values such as passwords and webhook URLs go in `.env`.

For a local install, the wizard can check the setup and start monitoring immediately. In a container, it prints the next Docker or Docker Compose commands to run.

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

    On a native Linux container engine, run these shell commands in the same terminal immediately before setup unless the variables are already set there or you saved the numeric values in the Compose `.env` file during installation. For permanent project values, use the numeric `.env` form under [Install with Docker Compose](installation.md#docker-compose). Docker-compatible runtimes on macOS and Windows should skip this export block.

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

The wizard detects PyPI, a downloaded script, Docker or Docker Compose and prints matching commands. It also formats file paths for the current operating system.

Container setup destinations must stay inside `/data`. That directory is the current host directory mounted into the temporary setup container, so files written there survive `--rm`. The wizard rejects paths such as `/tmp/instagram_monitor.conf` instead of printing a command for a different file.

For Docker or Docker Compose, choose **Import from Firefox after setup**. The wizard asks whether Docker runs on macOS, standard Linux, Linux with Snap, Linux with Flatpak, Windows PowerShell or Windows Command Prompt. It then prints the matching command to mount the signed-in host profile read-only once and save the imported login in the persistent `instagram_monitor_session` volume. Windows commands use the Firefox profile under `%APPDATA%\Mozilla\Firefox`.

Firefox import works in every local installation without an extra package. Chrome, Brave and Chromium import works on macOS and Linux with the optional browser dependency. Container setup uses Firefox because Chromium cookie decryption needs a password service from the host that is not available inside the container. See [Session Login Using Browser Cookies](configuration.md#option-3-session-login-using-browser-cookies-recommended).

If no targets or Web Dashboard setting have been saved, running the tool with no arguments opens the wizard in an interactive terminal. If `TARGET_USERNAMES` contains saved targets, the same command starts monitoring them. If only the Web Dashboard is enabled, it starts an empty browser control panel where you can add targets.

<a id="not-sure-which-mode-you-want"></a>
## Not sure which command you need?

The table uses the PyPI command. If you chose another installation, use its [command prefix](usage.md#command-format) instead of `instagram_monitor`.

| I want to... | Run this |
| --- | --- |
| Set up Instagram Monitor for the first time | Use the setup command for your installation above |
| Try public monitoring without a login | `instagram_monitor <target_insta_user>` |
| Start targets saved in `TARGET_USERNAMES` | `instagram_monitor --config-file instagram_monitor.conf` or `docker compose up --no-log-prefix` |
| Start a browser control panel without targets | `instagram_monitor --web-dashboard` |
| Monitor several accounts | `instagram_monitor target_1 target_2` or `instagram_monitor --targets target_1,target_2` |
| Check the selected login, connectivity and targets | `instagram_monitor --doctor` |
| See stories, reels and follower details | Import a browser session then run `instagram_monitor -u <your_insta_user> <target_insta_user>` |

<a id="run-individual-commands"></a>
## Run Individual Commands

The examples below use PyPI. For a manual script, replace `instagram_monitor` with `python3 instagram_monitor.py` on macOS or Linux. Use `python instagram_monitor.py` on Windows. Docker users should copy the matching prefix under [Command Format by Installation Method](usage.md#command-format).

Track a public account in [No-Login Mode](configuration.md#no-login-mode-without-session-login):

```sh
instagram_monitor <target_insta_user>
```

For stories, reels and detailed follower changes, use [Logged-In Mode](configuration.md#logged-in-mode-with-session-login). Log in to Instagram in a supported browser then import the session. Firefox is the recommended local path:

```sh
instagram_monitor --import-browser-session --browser firefox
instagram_monitor -u <your_insta_user> <target_insta_user>
```

The import converts the browser login into a saved Instaloader session. The value passed to `-u` must be the username of that logged-in account. Container users must use the same `instagram_monitor_session` Docker volume for the import and later monitoring runs. The complete import command is under [Container Operation](usage.md#container-operation).

Launch the [Web Dashboard](view-modes.md#web-dashboard-mode) with a target or as an empty control panel:

```sh
instagram_monitor <target_insta_user> --web-dashboard
instagram_monitor --web-dashboard
```

A one-off Compose command needs `--service-ports` so the browser can reach the dashboard. A direct Docker command needs a port mapping. Both complete commands are under [Monitoring Mode](usage.md#monitoring-mode).

View every command-line option plus examples adapted to the detected installation:

```sh
instagram_monitor --help
```
