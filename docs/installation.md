# Installation

Choose one installation method and keep using its command format throughout the documentation. PyPI is the simplest local installation. Docker Compose is the recommended container installation because it keeps configuration, secrets, output files and the Instaloader session outside the replaceable container.

<a id="requirements"></a>
## Requirements

Choose one runtime path:

* **Python path**:
  * [Python](https://www.python.org/downloads/) 3.9 or higher
  * Core libraries: `instaloader`, `requests`, `curl_cffi`, `python-dateutil`, `pytz`, `tzlocal`, `python-dotenv`, `tqdm`, `rich`, `flask`, `jinja2`
  * Optional Chromium cookie import library: `pycookiecheat`
* **Container path** (Python is not required on the host):
  * Any Docker-compatible runtime such as:
    * [Docker Desktop](https://docs.docker.com/get-started/get-docker/) (macOS, Windows, Linux)
    * [Docker Engine](https://docs.docker.com/engine/install/) (Linux)
    * [Colima](https://colima.run/docs/installation/) with Docker CLI (macOS)
    * [OrbStack](https://docs.orbstack.dev/quick-start) (macOS)
    * [Rancher Desktop](https://docs.rancherdesktop.io/getting-started/installation/) with Moby or Docker CLI enabled (macOS, Windows, Linux)
  * The Docker Compose v2 plugin if you choose Docker Compose

The published image already contains Python and all core libraries. You do not need a local Python installation for Docker.

Container commands use the Docker-compatible `docker` CLI. Check the runtime with `docker --version`. If you choose Compose, check the plugin with `docker compose version`.

Tested on:

* **macOS**: Ventura, Sonoma, Sequoia, Tahoe
* **Linux**: Raspberry Pi OS (Bullseye, Bookworm, Trixie), Ubuntu 24/25, Rocky Linux 8.x/9.x, Kali Linux 2024/2025
* **Windows**: 10, 11

It should work on other versions of macOS, Linux, Unix and Windows as well.

<a id="installation"></a>
## Choose an Installation Method

| Method | Best for | Command used in later examples |
| --- | --- | --- |
| PyPI | The easiest local install and automatic upgrades | `instagram_monitor [OPTIONS] [TARGET ...]` |
| Manual script | A portable single-file local install | `python3 instagram_monitor.py [OPTIONS] [TARGET ...]` on macOS/Linux or `python instagram_monitor.py [OPTIONS] [TARGET ...]` on Windows |
| Docker Compose | A persistent container with files in the current directory and a reusable login session | `docker compose run --rm instagram_monitor [OPTIONS] [TARGET ...]` |
| Docker Hub image | Direct container runs without a Compose file | `docker run ... misiektoja/instagram-monitor:latest [OPTIONS] [TARGET ...]` |

The examples on Configuration, Usage, View Modes and Troubleshooting use the shorter PyPI command unless container behavior needs a dedicated example. Replace that command with the matching form above. The setup wizard and `--help` also detect the active installation and print matching commands.

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

An extra includes the base package so you do not need to run both install commands.

<a id="manual-python-based-installation"></a>
### Install the Manual Script

Download [instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py) and [requirements.txt](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt) to the same directory. Then install the core dependencies:

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

Download the project Compose file into the directory where you want to keep the configuration and output:

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
docker compose pull
docker compose run --rm instagram_monitor --version
```

You can also download [docker-compose.yml](https://github.com/misiektoja/instagram_monitor/blob/main/docker-compose.yml) in a browser or use the file from a cloned repository.

On Linux, export your host user and group before setup so the non-root container can write to the current directory:

```sh
export INSTAGRAM_MONITOR_UID="$(id -u)"
export INSTAGRAM_MONITOR_GID="$(id -g)"
```

Keep these variables set for later `docker compose` commands. Alternatively store their numeric values as `INSTAGRAM_MONITOR_UID` and `INSTAGRAM_MONITOR_GID` in Compose's `.env` file. The setup wizard preserves unrelated entries in that file. Docker Desktop on macOS and Windows normally handles bind-mount ownership without this override.

Compose mounts the current directory at `/data` and stores the Instaloader login in a named volume. The setup wizard creates `instagram_monitor.conf` and `.env` on the host so upgrades or container replacement do not remove them. Continue with [Quick Start](quick-start.md#new-here-run-the-setup-wizard).

<a id="install-from-docker-hub"></a>
### Install from Docker Hub

The published [`misiektoja/instagram-monitor`](https://hub.docker.com/r/misiektoja/instagram-monitor) image supports `linux/amd64` and `linux/arm64`:

```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm misiektoja/instagram-monitor:latest --version
```

Normal runs mount the current directory at `/data` so configuration and output survive the temporary container. They also use the named volume `instagram_monitor_session` so the Instaloader login survives. On Linux, pass your host identity so setup can write through the bind mount. [Quick Start](quick-start.md#new-here-run-the-setup-wizard) shows both Docker Desktop and Linux commands.

Docker Desktop examples use `${PWD}` in macOS shells and Windows PowerShell. In Windows Command Prompt use `%cd%` for the current directory. Linux examples use `$PWD` and add the host user mapping.

The Compose file and direct commands use the `/data:z` mount form for SELinux hosts. If a Docker-compatible runtime rejects the `:z` suffix, remove only that suffix and keep the `/data` mount.

The published image includes all core dependencies but not the optional Chromium browser extra. Firefox is the practical browser import path inside a container because its cookie database can be mounted read-only. Chrome, Brave and Chromium rely on the host keyring, which is unavailable in the container.

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

Configuration files, dotenv secrets and downloaded output are not part of the PyPI package or Docker image. Keep them in your working directory or another persistent path and reuse them after an upgrade. Container users should also keep the named Instaloader session volume.

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

Replace `instagram_monitor.py` with the newest copy. Download the current `requirements.txt` and refresh the dependencies too because a new release may add a required library:

```sh
pip install --upgrade -r requirements.txt
python3 instagram_monitor.py --version
```

Use `python instagram_monitor.py --version` on Windows. If you modified the script itself, save your changes before replacing it then reapply them to the new version.

### Upgrade a Docker Compose Installation

Stop an attached run with `Ctrl+C`. From the directory that contains `docker-compose.yml` run:

```sh
docker compose pull
docker compose up
```

Compose recreates the service from the current `latest` image when needed. The bind-mounted `instagram_monitor.conf`, `.env` and output files remain on the host. The named Instaloader session volume also remains attached.

### Upgrade a Direct Docker Installation

Stop the current run then pull the current image:

```sh
docker pull misiektoja/instagram-monitor:latest
docker run --rm misiektoja/instagram-monitor:latest --version
```

Start the tool again with the same `/data` bind mount, `instagram_monitor_session` volume and options you used before. If you pin a versioned tag such as `3.6`, change that tag explicitly when you want to move to another release. Published releases update `latest` and also publish both `vX.Y` and `X.Y` tags.

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

Images built with current releases initialize new Instaloader session volumes for mapped non-root users. If an older Compose session volume reports `Permission denied` after an upgrade, repair its mode once:

```sh
docker compose run --rm --user 10001:10001 --entrypoint chmod instagram_monitor 1777 /home/instagram/.config/instaloader
```

For the direct Docker volume named `instagram_monitor_session`, use:

```sh
docker run --rm --user 10001:10001 --entrypoint chmod -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest 1777 /home/instagram/.config/instaloader
```

After any upgrade, run the doctor command for your installation:

```sh
instagram_monitor --doctor
```

For Docker Compose use `docker compose run --rm instagram_monitor --doctor`. For a direct image use the normal `/data` and session mounts plus `--doctor`.
