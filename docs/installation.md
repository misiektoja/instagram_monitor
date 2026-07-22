# Installation

Choose one installation method. You do not need both Python and Docker. PyPI is usually the easiest local option. Docker Compose is usually the easiest container option because it keeps your settings, private values, downloaded files and saved Instagram login when the container is replaced.

<a id="requirements"></a>
## Requirements

Choose either the Python path or the container path.

**Python path**:

- [Python](https://www.python.org/downloads/) 3.9 or higher
- The installer adds the required Python libraries automatically
- `pycookiecheat` is optional and is needed only to import cookies from Chrome, Brave or Chromium

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

* **macOS**: Ventura, Sonoma, Sequoia, Tahoe
* **Linux**: Raspberry Pi OS (Bullseye, Bookworm, Trixie), Ubuntu 24/25, Rocky Linux 8.x/9.x, Kali Linux 2024/2025
* **Windows**: 10, 11

It should work on other versions of macOS, Linux, Unix and Windows as well.

<a id="installation"></a>
## Choose an Installation Method

| Method | Best for | Command used in later examples |
| --- | --- | --- |
| PyPI | Most local users | `instagram_monitor [OPTIONS] [TARGET ...]` |
| Manual script | Users who want to download and run one Python file | `python3 instagram_monitor.py [OPTIONS] [TARGET ...]` on macOS/Linux or `python instagram_monitor.py [OPTIONS] [TARGET ...]` on Windows |
| Docker Compose | Users who want a reusable container setup | `docker compose run --rm instagram_monitor [OPTIONS] [TARGET ...]` |
| Docker Hub image | Users who want to write each Docker option themselves | `docker run ... misiektoja/instagram-monitor:latest [OPTIONS] [TARGET ...]` |

Later pages use the short PyPI command unless Docker behaves differently. If you chose another method, keep the options after `instagram_monitor` but replace `instagram_monitor` with the command in the table. The setup wizard and `--help` also print commands for the detected installation.

<a id="install-from-pypi"></a>
### Install from PyPI

```sh
pip install instagram_monitor
instagram_monitor --version
```

Firefox session import needs no extra dependency. To import sessions from Chrome, Brave or Chromium on macOS or Linux, install the browser extra:

```sh
pip install "instagram_monitor[browser]"
```

The second command installs the base package too. You do not need to run both install commands.

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

<a id="docker-compose"></a>
### Install with Docker Compose

Create or choose a directory for Instagram Monitor. Download the Compose file into that directory, then run these commands from there:

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
docker compose pull
docker compose run --rm instagram_monitor --version
```

You can also download [docker-compose.yml](https://github.com/misiektoja/instagram_monitor/blob/main/docker-compose.yml) in a browser or use the file from a cloned repository.

On Linux, the container does not automatically know which host user should own new files. Export your numeric user ID and group ID so configuration, logs and downloads created by the container belong to your account instead of `root`:

```sh
export INSTAGRAM_MONITOR_UID="$(id -u)"
export INSTAGRAM_MONITOR_GID="$(id -g)"
```

Run these commands in the same terminal that you will use for setup and later Compose commands. A new terminal will not keep the exported values. To make them permanent for this project, put the numeric results from `id -u` and `id -g` in the Compose `.env` file:

```ini
INSTAGRAM_MONITOR_UID=1000
INSTAGRAM_MONITOR_GID=1000
```

The values above are only examples. Use the numbers returned on your system. The setup wizard keeps unrelated entries in this file. Docker Desktop normally handles file ownership on macOS and Windows, so users on those systems can skip this step.

Compose makes the current host directory available as `/data` inside the container. This is called a bind mount. The setup wizard creates `instagram_monitor.conf` and `.env` there, so the files remain on your computer when the container is replaced. A separate Docker volume named `instagram_monitor_session` keeps the saved Instagram login. Continue with [Quick Start](quick-start.md#new-here-run-the-setup-wizard).

<a id="install-from-docker-hub"></a>
### Install from Docker Hub

The published [`misiektoja/instagram-monitor`](https://hub.docker.com/r/misiektoja/instagram-monitor) image supports `linux/amd64` and `linux/arm64`:

```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm misiektoja/instagram-monitor:latest --version
```

Docker uses the copy of the image already stored on your computer. Run `docker pull` again when you want to upgrade. Normal monitoring commands do not download a newer image automatically.

Normal runs make the current directory available as `/data` in the container. Configuration and output written there remain on the host after the temporary container stops. The Docker volume named `instagram_monitor_session` keeps the saved Instagram login. On Linux, the command also passes your numeric user and group IDs so new files belong to you. [Quick Start](quick-start.md#new-here-run-the-setup-wizard) shows the complete commands for Docker Desktop and Linux.

Docker Desktop examples use `${PWD}` in macOS shells and Windows PowerShell. In Windows Command Prompt use `%cd%` for the current directory. Linux examples use `$PWD` and add the host user mapping.

The `:z` suffix lets Docker relabel the mounted directory on hosts that use SELinux. If your Docker-compatible runtime reports that `:z` is invalid, remove only `:z` and keep the rest of the mount.

The published image includes all core dependencies but not the optional Chromium browser extra. Firefox works inside a container because its cookie database can be mounted as a read-only file. Chrome, Brave and Chromium need the host password service to decrypt cookies. A container cannot use that service.

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

Continue to [Quick Start](quick-start.md). It shows the setup wizard command for every installation method then explains login choices and the first monitoring run.

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
docker compose up
```

Compose replaces the service container with one based on the current `latest` image. The host files `instagram_monitor.conf` and `.env` remain in place with all downloaded output. The named `instagram_monitor_session` volume also remains available.

### Upgrade a Direct Docker Installation

Stop the current run then pull the current image:

```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm misiektoja/instagram-monitor:latest --version
```

Start the tool again with the same `/data` mount, `instagram_monitor_session` volume and options you used before. If your command uses a version such as `3.6` instead of `latest`, replace that version yourself when you want to upgrade. Each release publishes `latest` plus tags in `vX.Y` and `X.Y` forms.

For example, to pin version 3.6:

```sh
docker pull misiektoja/instagram-monitor:3.6
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
