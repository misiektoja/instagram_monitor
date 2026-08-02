# Installation

Choose one installation method. You do not need both Python and Docker.

PyPI is usually the easiest local option. If you are new to Python or unsure whether Python is ready, follow [New to Python: check and install](#new-to-python-install-everything).

The direct Docker image is the fastest container option. Docker Compose takes one extra download but gives you shorter commands for later runs.

<a id="requirements"></a>
## Requirements

Choose either the Python path or the container path.

**Python path**:

- [Python](https://www.python.org/downloads/) 3.9 or higher
- Core libraries: [instaloader](https://github.com/instaloader/instaloader), `requests`, [curl_cffi](https://github.com/lexiforest/curl_cffi), `python-dateutil`, `pytz`, `tzlocal`, `python-dotenv`, `tqdm`, `rich`, `flask`, `jinja2`
- [pycookiecheat](https://github.com/n8henrie/pycookiecheat) is optional and is needed only to import cookies from Chrome, Brave or Chromium

**Container path** (Python is included in the image):

- Any Docker-compatible runtime such as:
    - [Docker Desktop](https://docs.docker.com/get-started/get-docker/) (macOS, Windows, Linux)
    - [Docker Engine](https://docs.docker.com/engine/install/) (Linux)
    - [Colima](https://colima.run/docs/installation/) with Docker CLI (macOS)
    - [OrbStack](https://docs.orbstack.dev/quick-start) (macOS)
    - [Rancher Desktop](https://docs.rancherdesktop.io/getting-started/installation/) with Moby or Docker CLI enabled (macOS, Windows, Linux)
- The Docker Compose v2 plugin if you choose the Compose method

The published image already contains Python and all core libraries. You do not need a local Python installation for Docker.

The examples use the `docker` command. Check that it works with `docker --version`. If you choose Compose, also check `docker compose version`.

Tested on:

* **macOS**: Tahoe, Sequoia, Sonoma, Ventura
* **Linux**: Raspberry Pi OS (Trixie, Bookworm, Bullseye), Ubuntu 24/25, Rocky Linux 8.x/9.x, Kali Linux 2026/2025/2024
* **Windows**: 11, 10

It should work on other versions of macOS, Linux, Unix and Windows as well.

<a id="new-to-python-install-everything"></a>
## New to Python: check and install

Use this section if you are new to Python or do not know what is already installed. The platform sections only prepare Python and `pip`. Everyone then uses the same Instagram Monitor installation and setup commands. Instagram Monitor requires Python 3.9 or newer and is currently tested through Python 3.14.

### Check whether Instagram Monitor is already installed

Open Windows PowerShell on Windows or Terminal on macOS and Linux then run:

    instagram_monitor --version

If this prints an Instagram Monitor version, skip to [Run the setup wizard](#run-the-setup-wizard). If the command is not recognized or not found, continue with the section for your operating system.

### Windows 10 or 11

Open Windows PowerShell. Select **Start**, type `PowerShell` then open **Windows PowerShell**.

Check Python and `pip`:

    python --version
    pip --version

If both commands work and Python reports version 3.9 or newer, skip to [Install Instagram Monitor](#install-instagram-monitor-after-python-check).

If either command fails:

1. Open the official [Python Install Manager in Microsoft Store](https://apps.microsoft.com/detail/9NQ7512CXL7T), select **View in Store** then select **Install**. If Microsoft Store is unavailable, download the manager from [python.org](https://www.python.org/downloads/).

2. Close PowerShell then open it again.

3. Run `python --version`. Python Install Manager downloads the current Python release if no runtime is installed.

4. Check both commands again:

        python --version
        pip --version

If `pip` is still not recognized, run `py install --refresh`, close PowerShell then open it again. `py install` belongs to Python Install Manager and is used only to repair its Python commands.

See the official [Python Install Manager troubleshooting table](https://docs.python.org/3/using/windows.html#troubleshooting) if either check is still unavailable.

### macOS

Open Terminal. Press **Command+Space**, type `Terminal` then press **Return**.

Check Python and `pip`:

    python3 --version
    pip --version

If both commands work and Python reports version 3.9 or newer, skip to [Install Instagram Monitor](#install-instagram-monitor-after-python-check).

If either command fails:

1. Open the official [Python downloads for macOS](https://www.python.org/downloads/macos/). Select the latest stable Python 3.14 release then download its **macOS 64-bit universal2 installer**. This single installer supports Apple Silicon and Intel Macs.

2. Open the downloaded `.pkg` file. Keep the standard options, select **Continue** through the installer then enter your macOS password when requested.

3. Open the new **Python 3.14** folder in Applications then double-click **Install Certificates.command**. Wait until its Terminal window reports `update complete` then close that window.

4. Close Terminal then open it again.

5. Check both commands again:

        python3 --version
        pip --version

The official [Using Python on macOS](https://docs.python.org/3/using/mac.html) guide shows every installer screen and explains the installed applications.

### Ubuntu, Debian, Raspberry Pi OS or Kali

Open Terminal then check Python and `pip`:

    python3 --version
    pip --version

If both commands work and Python reports version 3.9 or newer, skip to [Install Instagram Monitor](#install-instagram-monitor-after-python-check).

If either command fails, install the missing packages:

    sudo apt update
    sudo apt install python3 python3-pip

The package manager keeps an existing current package instead of reinstalling it. Terminal may ask for your password. Type the password you use to sign in then press **Enter**. Terminal does not show password characters while you type.

Check both commands again:

    python3 --version
    pip --version

If Python reports a version older than 3.9, follow your distribution's instructions to install a supported Python version before continuing. For another Linux distribution, install Python 3.9 or newer plus `pip` through its package manager.

<a id="install-instagram-monitor-after-python-check"></a>
### Install Instagram Monitor

Every operating system uses the same command:

    pip install instagram_monitor

Verify the installation:

    instagram_monitor --version

On Linux, `pip` may report that the system Python is externally managed. If that happens, install Instagram Monitor with the isolated `pipx` tool instead:

    sudo apt install pipx
    pipx ensurepath
    pipx install instagram_monitor

Close Terminal, open it again then run `instagram_monitor --version`.

<a id="run-the-setup-wizard"></a>
### Run the setup wizard

Every operating system uses the same command:

    instagram_monitor --setup

The setup wizard can import a signed-in Firefox session, save the accounts to monitor and configure the polling interval, interface and alerts. Continue to [Setup & First Run](setup-and-first-run.md) for a walkthrough of its questions.

<a id="installation"></a>
## Choose an Installation Method

| Method | Best for | Command used in later examples |
| --- | --- | --- |
| PyPI | Local users who already have Python or followed the beginner steps above | `instagram_monitor [OPTIONS] [TARGET ...]` |
| Manual script | Users who want to download and run one Python file | `python3 instagram_monitor.py [OPTIONS] [TARGET ...]` on macOS/Linux or `python instagram_monitor.py [OPTIONS] [TARGET ...]` on Windows |
| Docker Hub image | Users who want the fastest container setup | `docker run ... misiektoja/instagram-monitor:latest [OPTIONS] [TARGET ...]` |
| Docker Compose | Users who prefer shorter recurring commands after setup | `docker compose run --rm instagram_monitor [OPTIONS] [TARGET ...]` |

Later pages use the short PyPI command unless Docker behaves differently. If you chose another method, keep the options after `instagram_monitor` but replace `instagram_monitor` with the command in the table. The setup wizard and `--help` also print commands for the detected installation.

<a id="install-from-pypi"></a>
### Install from PyPI

```sh
pip install instagram_monitor
instagram_monitor --version
```

Each command below that uses square brackets installs the base `instagram_monitor` package plus the named optional dependency. Run only the command that matches your needs. You do not need to run the plain install command first.

Firefox session import needs no extra dependency. To import sessions from Chrome, Brave or Chromium on macOS or Linux install the browser extra:

```sh
pip install "instagram_monitor[browser]"
```

This installs Instagram Monitor and the optional `pycookiecheat` dependency.

<a id="manual-python-based-installation"></a>
### Install the Manual Script

Download the script and dependency list into the same directory:

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt
```

You can also download [instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py) and [requirements.txt](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt) in a browser or use the files from a cloned repository.

Install the core dependencies:

```sh
pip install -r requirements.txt
```

You can install the core dependencies directly if you downloaded only the script:

```sh
pip install instaloader requests curl_cffi python-dateutil pytz tzlocal python-dotenv tqdm rich flask jinja2
```

To import from Chrome, Brave or Chromium on macOS or Linux, also install `pycookiecheat`:

```sh
pip install "pycookiecheat>=0.8"
```

Verify the script:

```sh
python3 instagram_monitor.py --version
```

Use `python instagram_monitor.py --version` on Windows.

<a id="install-from-docker-hub"></a>
### Install from Docker Hub

The published [`misiektoja/instagram-monitor`](https://hub.docker.com/r/misiektoja/instagram-monitor) image supports `linux/amd64` and `linux/arm64`.

No separate image download is required. Its first-run command uses `docker run --pull=always` to pull the current image and start the setup wizard in one step, so for Docker installing and setting up are a single command:

```sh
docker run --rm --pull=always -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest --setup
```

On a native Linux container engine, add `--user "$(id -u):$(id -g)"` immediately after `--init`. [Setup & First Run](setup-and-first-run.md#new-here-run-the-setup-wizard) shows the exact command for macOS shells, Windows PowerShell and native Linux engines then explains what the wizard asks.

Normal monitoring commands reuse the installed image and do not check for a newer release. The [upgrade instructions](#upgrade-a-direct-docker-installation) pull explicitly when you choose to upgrade.

Normal runs make the current directory available as `/data` in the container. Configuration and output written there remain on the host after the temporary container stops. The Docker volume named `instagram_monitor_session` keeps the saved Instagram login. On a native Linux container engine, the command also passes your numeric user and group IDs so new files belong to you.

The macOS shell and Windows PowerShell examples use `${PWD}`. In Windows Command Prompt use `%cd%` for the current directory. Native Linux examples use `$PWD` and add the host user mapping.

On Windows, configure Docker Desktop or another Docker-compatible runtime to use Linux containers. Guided setup supports Firefox import from the normal `%APPDATA%\Mozilla\Firefox` profile root and prints shell-specific commands for PowerShell or Command Prompt.

The `:z` suffix lets Docker relabel the mounted directory on hosts that use SELinux. If your Docker-compatible runtime reports that `:z` is invalid, remove only `:z` and keep the rest of the mount.

The published image includes all core dependencies but not the optional Chromium browser extra. Firefox works inside a container because its cookie database can be mounted as a read-only file. Chrome, Brave and Chromium need the host password service to decrypt cookies. A container cannot use that service.

<a id="docker-compose"></a>
### Install with Docker Compose

Compose adds a reusable project file and shorter commands for later runs. Create or choose a directory for Instagram Monitor and download the Compose file there:

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
```

You can also download [docker-compose.yml](https://github.com/misiektoja/instagram_monitor/blob/main/docker-compose.yml) in a browser or use the file from a cloned repository.

On a native Linux container engine, the container does not automatically know which host user should own new files. Export your numeric user ID and group ID so configuration, logs and downloads created by the container belong to your account instead of `root`:

```sh
export INSTAGRAM_MONITOR_UID="$(id -u)"
export INSTAGRAM_MONITOR_GID="$(id -g)"
```

Run these commands in the same terminal that you will use for setup and later Compose commands. A new terminal will not keep the exported values. To make them permanent for this project, put the numeric results from `id -u` and `id -g` in the Compose `.env` file:

```ini
INSTAGRAM_MONITOR_UID=1000
INSTAGRAM_MONITOR_GID=1000
```

The values above are only examples. Use the numbers returned on your system. The setup wizard keeps unrelated entries in this file. Docker-compatible runtimes on macOS and Windows normally handle bind-mount ownership, so users on those systems can usually skip this step. If `/data` is not writable, set the host user and group IDs as shown above.

Compose makes the current host directory available as `/data` inside the container. This is called a bind mount. The setup wizard creates `instagram_monitor.conf` and `.env` there, so the files remain on your computer when the container is replaced. A separate Docker volume named `instagram_monitor_session` keeps the saved Instagram login. From this directory your first command is the setup wizard:

```sh
docker compose run --rm --pull=always instagram_monitor --setup
```

The `--pull=always` flag pulls the current image first, so no separate pull command is needed during onboarding. On a native Linux container engine, export the UID and GID shown above in the same terminal before you run setup. See [Setup & First Run](setup-and-first-run.md#new-here-run-the-setup-wizard) for the wizard walkthrough.

<a id="build-image-locally"></a>
### Build the Docker Image Locally

From a cloned repository:

```sh
docker build --pull --tag instagram-monitor:local .
docker run --rm instagram-monitor:local --version
```

To use this image through Compose, comment out `image:` in `docker-compose.yml` and uncomment `build: .`.

<a id="next-step"></a>
## Next Step

Continue to [Setup & First Run](setup-and-first-run.md). It shows the setup wizard command for every installation method then explains login choices and the first monitoring run.

<a id="upgrading"></a>
## Upgrading

Upgrading the package or image does not upgrade or remove your configuration, `.env` secrets or downloaded files. Keep those files in the same working directory or another persistent location. Container users should also keep the `instagram_monitor_session` volume because it contains the saved Instagram login.

### Upgrade a PyPI Installation

```sh
pip install --upgrade instagram_monitor
instagram_monitor --version
```

Retain the optional browser extra if you use Chrome, Brave or Chromium import:

```sh
pip install --upgrade "instagram_monitor[browser]"
```

### Upgrade a Manual Installation

Replace [instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py) and [requirements.txt](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt) with the newest copies. You can download them in a browser, use the files from an updated clone or run:

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt
pip install --upgrade -r requirements.txt
python3 instagram_monitor.py --version
```

Refresh the dependencies even when `requirements.txt` appears unchanged because a new release may add or change a required library.

Use `python instagram_monitor.py --version` on Windows. If you modified the script itself, save your changes before replacing it then reapply them to the new version.

### Upgrade a Docker Compose Installation

Stop an attached run with `Ctrl+C`. From the directory that contains `docker-compose.yml` run:

```sh
docker compose pull
docker compose up --no-log-prefix
```

Compose replaces the service container with one based on the current `latest` image. The host files `instagram_monitor.conf` and `.env` remain in place with all downloaded output. The named `instagram_monitor_session` volume also remains available.

### Upgrade a Direct Docker Installation

Stop the current run then pull the current image:

```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm misiektoja/instagram-monitor:latest --version
```

Start the tool again with the same `/data` mount, `instagram_monitor_session` volume and options you used before. If your command uses a version such as `3.8` instead of `latest`, replace that version yourself when you want to upgrade. Each release publishes `latest` plus tags in `vX.Y.Z` and `X.Y.Z` forms.

For example, to pin version 3.8:

```sh
docker pull misiektoja/instagram-monitor:3.8
```

### Upgrade a Locally Built Docker Image

Update the cloned repository then rebuild while refreshing the base image:

```sh
docker build --pull --tag instagram-monitor:local .
docker run --rm instagram-monitor:local --version
```

### Repair an Older Container Session Volume

This section applies only if a session volume created by an older release reports `Permission denied` after an upgrade. Current releases set up new volumes automatically. To repair an older Compose volume once, run:

```sh
docker compose run --rm --user 10001:10001 --entrypoint chmod instagram_monitor 1777 /home/instagram/.config/instaloader
```

For the direct Docker volume named `instagram_monitor_session`, use:

```sh
docker run --rm --user 10001:10001 --entrypoint chmod -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest 1777 /home/instagram/.config/instaloader
```

### Check Upgrade

After any upgrade, run the doctor command for your installation:

```sh
instagram_monitor --doctor
```

For Docker Compose use `docker compose run --rm instagram_monitor --doctor`. For a direct image use the normal `/data` and session mounts plus `--doctor`.
