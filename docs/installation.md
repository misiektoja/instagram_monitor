# Installation

## Requirements

Choose one runtime path:

* **Python path**:
  * [Python](https://www.python.org/downloads/) 3.9 or higher
  * Libraries: [instaloader](https://github.com/instaloader/instaloader), `requests`, [curl_cffi](https://github.com/lexiforest/curl_cffi) (for browser TLS impersonation), `python-dateutil`, `pytz`, `tzlocal`, `python-dotenv`, `tqdm`, `rich` (for Terminal Dashboard), `flask` (for Web Dashboard)
* **Container path** (Python is not required on host):
  * Any Docker-compatible runtime such as:
    * [Docker Desktop](https://docs.docker.com/get-started/get-docker/) (macOS, Windows, Linux)
    * [Docker Engine](https://docs.docker.com/engine/install/) (Linux)
    * [Colima](https://colima.run/docs/installation/) with Docker CLI (macOS)
    * [OrbStack](https://docs.orbstack.dev/quick-start) (macOS)
    * [Rancher Desktop](https://docs.rancherdesktop.io/getting-started/installation/) with Moby or Docker CLI enabled (macOS, Windows, Linux)

Tested on:

* **macOS**: Ventura, Sonoma, Sequoia, Tahoe
* **Linux**: Raspberry Pi OS (Bullseye, Bookworm, Trixie), Ubuntu 24/25, Rocky Linux 8.x/9.x, Kali Linux 2024/2025
* **Windows**: 10, 11

It should work on other versions of macOS, Linux, Unix and Windows as well.

<a id="installation"></a>

## Installation

<a id="install-from-pypi"></a>
### Install from PyPI

```sh
pip install instagram_monitor
```

If you also want to import sessions from Chrome, Brave or Chromium (macOS and Linux only), install the optional `browser` extra instead. This is a superset of the base package, so run just this one command (no need to also run `pip install instagram_monitor`):

```sh
pip install "instagram_monitor[browser]"
```

Firefox session import needs no extra and works out of the box.

<a id="install-from-docker-hub"></a>
### Install from Docker Hub

```sh
docker pull misiektoja/instagram-monitor:latest
```

<a id="manual-python-based-installation"></a>
### Manual Python-based Installation

Download the *[instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py)* file to the desired location.

Install dependencies via pip:

```sh
pip install instaloader requests python-dateutil pytz tzlocal python-dotenv tqdm rich flask
```

**Note:** `rich` is required for the Terminal Dashboard, `flask` is required for the Web Dashboard. If Rich or Flask is not installed, the corresponding dashboard is disabled automatically.

**Note:** To import sessions from Chrome, Brave or Chromium (macOS and Linux only), also run `pip install pycookiecheat`.

Alternatively, from the downloaded *[requirements.txt](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/requirements.txt)*:

```sh
pip install -r requirements.txt
```

<a id="upgrading"></a>
### Upgrading

To upgrade to the latest version when installed from PyPI:

```sh
pip install instagram_monitor -U
```

If you installed manually, download the newest *[instagram_monitor.py](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/instagram_monitor.py)* file to replace your existing installation.

If you run from Docker Hub, pull the newer image tag:

```sh
docker pull misiektoja/instagram-monitor:latest
```

If you prefer pinned releases instead of `latest`, pull a specific version tag:

```sh
docker pull misiektoja/instagram-monitor:<version>
```

If you run a locally built image, rebuild it to pick up new changes:

```sh
docker build --pull -t instagram_monitor:local .
```
