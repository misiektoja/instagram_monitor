# Usage

<a id="docker-usage-recommended"></a>
## Docker Usage (Recommended)

Running via [Docker](https://www.docker.com) is the easiest setup for most users and avoids local Python dependency management.

<a id="docker-compose-easiest"></a>
### Docker Compose (Easiest)

The repo ships a [docker-compose.yml](https://github.com/misiektoja/instagram_monitor/blob/main/docker-compose.yml) that wraps the volume mounts, port and session persistence for you, so you do not have to remember long `docker run` commands. If you cloned the repo, you already have this file.

If you are starting from an empty directory, download it first:

```sh
curl -fsSLO https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/docker-compose.yml
```

On native Linux map the service to your host identity before the first setup command. This lets the non-root container write the generated config, dotenv and output files through the `/data` bind mount. Docker Desktop users on macOS or Windows can skip these exports.

```sh
export INSTAGRAM_MONITOR_UID="$(id -u)"
export INSTAGRAM_MONITOR_GID="$(id -g)"
```

Export the same values again before a later `docker compose up`. Alternatively store their numeric values in Compose's `.env` file. The setup wizard preserves unrelated entries already present in that file.

1. Generate a config. The image makes the Web Dashboard listen on the container network while Compose publishes it only on host loopback:

```sh
docker compose run --rm instagram_monitor --setup
```

2. If you saved the targets, start them with the interface selected in setup:

```sh
docker compose up
```

If you did not save the targets, use the complete `docker compose run` command printed by setup instead. Compose auto-loads `instagram_monitor.conf` and the application auto-loads `.env` from the current directory. The wizard creates or updates `.env` when you enter a secret, so do not replace it with `.env.example` after setup.

When Web Dashboard was selected, open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). The port is bound only to the Docker host. Other machines cannot connect through the host network unless you deliberately change the published address.

To monitor specific targets from the command line instead, override the command:

```sh
docker compose run --rm --service-ports instagram_monitor target1 target2 --web-dashboard
```

<a id="docker-hub-image"></a>
### Docker Hub Image

A prebuilt multi-architecture image is available on Docker Hub: [`misiektoja/instagram-monitor`](https://hub.docker.com/r/misiektoja/instagram-monitor)

Run and show help:

```sh
docker run --rm -it misiektoja/instagram-monitor --help
```

<a id="build-image-locally"></a>
### Build Image Locally

If you want to build from source:

```sh
docker build -t instagram_monitor:local .
docker run --rm -it instagram_monitor:local --help
```

If you prefer the local image, replace `misiektoja/instagram-monitor` with `instagram_monitor:local` in the Docker commands below.

<a id="common-run-scenarios"></a>
### Common Run Scenarios

**Shell note:** The examples below use Bash/Zsh variables (`$PWD`, `$HOME`) and map the container to the current macOS or Linux identity. In PowerShell omit `--user "$(id -u):$(id -g)"`, use `${PWD}` and `${HOME}` and remove the `:z` suffix if your runtime rejects it. The image's default non-root identity is used on Windows.

1. Basic monitoring with persistent data and session storage:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor <target_insta_user>
```

This keeps generated files in your current directory and keeps Instaloader sessions in the Docker volume `instagram_monitor_session`.

2. Use config file and dotenv from your current directory:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor <target_insta_user> --config-file /data/instagram_monitor.conf --env-file /data/.env
```

3. Run Web Dashboard and access it from host browser:

The official image automatically makes a loopback-configured dashboard listen on the container network. Publish it only on host loopback:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 127.0.0.1:8000:8000 misiektoja/instagram-monitor <target_insta_user> --web-dashboard
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) on your host.

4. Import Firefox session cookies on Linux host:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor --import-browser-session --browser firefox
```

5. Import Firefox session cookies on macOS host from explicit cookie file:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "$HOME/Library/Application Support/Firefox/Profiles/<profile>/cookies.sqlite:/cookies/cookies.sqlite:ro" misiektoja/instagram-monitor --import-browser-session --browser firefox --cookie-file /cookies/cookies.sqlite
```

Firefox is the practical choice inside Docker because its cookies are plain files that can be mounted read-only. Importing from Chrome, Brave or Chromium (`--browser chrome|brave|chromium`) relies on the host's keyring for decryption, which is not available in the container, so run those imports directly on the host instead.

The `/data:z` suffix supplies a shared SELinux label on enforcing Linux hosts and is ignored elsewhere. Do not add `z` or `Z` to an entire Firefox profile without understanding the host relabeling effect. If SELinux blocks that read-only profile mount, close Firefox and copy the needed cookie database to a dedicated directory before mounting it.

Images built with this version initialize new Instaloader session volumes with permissions that support a mapped non-root UID. If an older Compose session volume reports `Permission denied` after upgrading, repair its root mode once before using the mapped identity:

```sh
docker compose run --rm --user 10001:10001 --entrypoint chmod instagram_monitor 1777 /home/instagram/.config/instaloader
```

For the direct Docker volume named `instagram_monitor_session`, use:

```sh
docker run --rm --user 10001:10001 --entrypoint chmod -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor 1777 /home/instagram/.config/instaloader
```

Once imported, run with `-u <your_insta_user>` as usual and the session file from the persistent volume will be reused.

<a id="monitoring-mode"></a>
## Monitoring Mode

To monitor specific user activity in [No-login mode](configuration.md#no-login-mode-no-session-login) (no session login), just type Instagram username as a command-line argument (`target_insta_user` in the example below):

```sh
instagram_monitor <target_insta_user>
```

To monitor specific user activity in [Logged-in mode](configuration.md#logged-in-mode-with-session-login) (with session login), you also need to specify your Instagram account name (`your_insta_user` in the example below) via `SESSION_USERNAME` configuration option or `-u` flag:

```sh
instagram_monitor -u <your_insta_user> <target_insta_user>
```

Since **v3.0** you can also launch the **[Web Dashboard](view-modes.md#web-dashboard-mode)** along with tracking:

```sh
instagram_monitor -u <your_insta_user> <target_insta_user> --web-dashboard
```

By default, the tool looks for a configuration file named `instagram_monitor.conf` in:
 - current directory
 - home directory (`~`)
 - script directory

 If you generated a configuration file as described in [Configuration](configuration.md#configuration-file), but saved it under a different name or in a different directory, you can specify its location using the `--config-file` flag:

```sh
instagram_monitor <target_insta_user> --config-file /path/instagram_monitor_new.conf
```

The tool runs until interrupted (`Ctrl+C`). Use `tmux` or `screen` for persistence.

You can monitor multiple Instagram users in **one process** by passing multiple target usernames:

```sh
instagram_monitor target_user_1 target_user_2 target_user_3
```

**Note**: You can also add and remove monitoring targets directly via the **[Web Dashboard](view-modes.md#web-dashboard-mode)** without restarting the tool.

To reduce the chance of triggering Instagram anti-bot mechanisms, the tool will **stagger** the start of each target's monitoring loop (auto-spread across your `INSTA_CHECK_INTERVAL` by default). You can override it with:

```sh
instagram_monitor target_user_1 target_user_2 --targets-stagger 300
```

The tool automatically saves its output to an `instagram_monitor_<suffix>.log` file. It can be changed in the settings via `INSTA_LOGFILE` configuration option or disabled completely via `DISABLE_LOGGING` / `-d` flag.

- In single-target mode, `<suffix>` is the username.
- In multi-target mode, `<suffix>` is the sorted list of target usernames joined with underscores.

The tool in Logged-in mode (session login) also saves the list of followings & followers to these files:
- `instagram_<username>_followings.json`
- `instagram_<username>_followers.json`

Thanks to this we do not need to re-fetch it every time the tool is restarted and we can also detect changes since the last usage of the tool.

When downloading lists of followers or followings, a **progress bar** is displayed showing real-time download progress, including statistics such as names per request, total requests, elapsed time and estimated remaining time. Progress updates are shown in the terminal only (to avoid cluttering log files), with the final completion state written to the log file for reference.

The tool also saves the user profile picture to `instagram_<username>_profile_pic*.jpg` files.

It also saves downloaded posts/reels images & videos to:
- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.jpg`
- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.mp4`

And downloaded stories images & videos to:
- `instagram_<username>_story_YYYYmmdd_HHMMSS.jpg`
- `instagram_<username>_story_YYYYmmdd_HHMMSS.mp4`

<a id="email-notifications"></a>
## Email Notifications

To enable email notifications for various events (such as new posts, reels and stories, changes in followings, bio updates, changes in profile picture and visibility):
- set `STATUS_NOTIFICATION` to `True`
- or use the `-s` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> -s
```

To also get email notifications about changed followers:
- set `FOLLOWERS_NOTIFICATION` to `True`
- or use the `-m` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> -m
```

To disable sending an email on errors (enabled by default):
- set `ERROR_NOTIFICATION` to `False`
- or use the `-e` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> -e
```

Make sure you defined your SMTP settings earlier (see [SMTP settings](configuration.md#smtp-settings)).

Example email:

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_email_notifications.png" alt="instagram_monitor_email_notifications" width="80%"/>
</p>

<a id="webhook-notifications"></a>
## Webhook Notifications

The tool supports native **Discord** and **ntfy** webhook notifications for all monitored events (posts, reels, stories, followings, followers, bio, profile visibility, profile picture changes and errors). Email and webhooks work independently.

`WEBHOOK_PROVIDER` selects the request format. It defaults to `"discord"` so existing configurations and custom Discord-compatible templates keep working.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_discord.png" alt="instagram_monitor_discord_screenshot" width="80%"/>
</p>

<a id="1-configure-discord-webhook"></a>
### 1. Choose a Provider

#### Discord

If you are new to Discord, follow these steps to get your **Webhook URL**:

1.  **Create a Server**: Click the **+** (Plus) icon on the left sidebar ("Add a Server") -> **Create My Own** -> **For me and my friends**.
2.  **Create/Edit a Channel**: In your new server, find the **#general** channel (or create a new one). Click the **Edit Channel** icon (⚙️ gear) next to the channel name.
3.  **Create Webhook**: Go to **Integrations** in the left menu -> **Webhooks** -> **New Webhook**.
4.  **Copy URL**: Click on the new webhook (often named "Spidey Bot", you can rename it) and click **Copy Webhook URL**.

Keep `WEBHOOK_PROVIDER = "discord"` in `instagram_monitor.conf`.

#### ntfy

For ntfy.sh or a self-hosted ntfy server:

1. Choose a hard-to-guess topic such as `instagram-monitor-long-random-value`.
2. Use the complete topic URL such as `https://ntfy.sh/instagram-monitor-long-random-value`.
3. Set `WEBHOOK_PROVIDER = "ntfy"` in `instagram_monitor.conf`.

Instagram Monitor sends the alert body and event field details as a bounded UTF-8 ntfy message, with the alert subject as its title. Query parameters already present in the topic URL are preserved, which supports the ntfy [`auth` query parameter](https://docs.ntfy.sh/publish/#authentication) for protected topics.

For a protected topic, the setup wizard can collect an ntfy access token through a hidden prompt and save it privately in `.env`. For manual setup, add:

```ini
NTFY_ACCESS_TOKEN="tk_your_ntfy_access_token"
```

The token is sent as `Authorization: Bearer <token>` and takes precedence over an `Authorization` entry in `WEBHOOK_HEADERS`.

Static custom headers remain available for advanced Discord or ntfy integrations:

```python
WEBHOOK_HEADERS = {
    "Authorization": "Basic your_base64_credentials",
}
```

For ntfy, Instagram Monitor always sets the required plain-text `Content-Type`. Prefer `NTFY_ACCESS_TOKEN` in `.env` for Bearer authentication because a token inside `WEBHOOK_HEADERS` is easier to expose or commit accidentally. Header names and values are validated before any request is sent.

Topics on the public ntfy.sh service are public unless protected through an account reservation. Treat an unprotected topic name like a password and do not reuse the example topic above.

<a id="2-enable-in-the-tool"></a>
### 2. Enable in the Tool
- set `WEBHOOK_ENABLED` to `True`, select `WEBHOOK_PROVIDER` and set `WEBHOOK_URL` to your copied Discord or ntfy URL in `instagram_monitor.conf`
- or use an [environment variable](configuration.md#storing-secrets) or a dotenv file for `WEBHOOK_URL`
- or use the `--webhook-url` flag (alternatively use the `--webhook` flag if URL is already in config)
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
# Enable Discord with URL
instagram_monitor <target_insta_user> --webhook-provider discord --webhook-url "https://discord.com/api/webhooks/..."

# Enable ntfy with a topic URL
instagram_monitor <target_insta_user> --webhook-provider ntfy --webhook-url "https://ntfy.sh/your-private-topic"

# Explicitly enable/disable if URL is in config
instagram_monitor <target_insta_user> --webhook
instagram_monitor <target_insta_user> --no-webhook
```

<a id="3-test-your-settings"></a>
### 3. Test your settings
You can verify your configuration by sending a test notification:

```sh
# Verify settings from configuration file
instagram_monitor --send-test-webhook

# Verify a specific provider and URL from command line
instagram_monitor --webhook-provider ntfy --webhook-url "https://ntfy.sh/your-private-topic" --send-test-webhook
```

<a id="4-advanced-configuration"></a>
### 4. Advanced Configuration
By default, all webhook notification types (status, followers, errors) are **disabled**. You must explicitly enable what you want the tool to send:

- Use `--webhook-status` to toggle status notifications (new posts, reels, stories, bio, visibility, profile pic)
- Use `--webhook-followers` to toggle follower/following change notifications
- Use `--webhook-errors` to toggle error notifications

Example with explicit control:
```sh
# Enable webhooks and specifically choose what to send
instagram_monitor <target_insta_user> --webhook-url "..." --webhook-status --webhook-followers --webhook-errors
```

Configuration file options (all disabled by default):
```ini
WEBHOOK_ENABLED = False
WEBHOOK_PROVIDER = "discord"  # Use "ntfy" for an ntfy topic URL
WEBHOOK_URL = "https://discord.com/api/webhooks/..."
WEBHOOK_USERNAME = "Instagram Monitor"
WEBHOOK_AVATAR_URL = ""
WEBHOOK_STATUS_NOTIFICATION = False
WEBHOOK_FOLLOWERS_NOTIFICATION = False
WEBHOOK_ERROR_NOTIFICATION = False
```

<a id="follower-churn-detection"></a>
## Follower Churn Detection

When enabled, the tool fetches the full list of followers and followings on **every check** (not just when counts change) and compares usernames to detect changes. This is useful for scenarios where:

- Someone unfollows and someone else follows at the same time (count stays the same)
- You want to track exactly who followed/unfollowed even without count changes
- You need comprehensive monitoring of all follower/following activity

To enable follower churn detection:
- set `FOLLOWERS_CHURN_DETECTION` to `True`
- or use the `--followers-churn` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

**Note**: This feature is automatically disabled if `SKIP_FOLLOW_CHANGES` is active, as detailed tracking is not possible when follow-related reporting is suppressed. It also requires [Logged-in mode](configuration.md#logged-in-mode-with-session-login).

```sh
instagram_monitor <target_insta_user> --followers-churn
```

**Note**: This feature requires [Logged-in mode](configuration.md#logged-in-mode-with-session-login) (session login) to access the Instagram API and it will increase API calls since it fetches the full follower/following lists every check interval, so the risk of account suspension is higher.

<a id="skipping-follow-changes"></a>
## Skipping Follow Changes

If you want to track followers/followings counts in the dashboards, but don't want to get any notifications or logs when they change, you can enable the "Skip Follow Changes" mode.

When enabled:
- **Notifications**: Email and Webhook alerts for follower/following changes are suppressed.
- **Reporting**: Console prints and activity logs for these changes are disabled.
- **CSV Export**: No "Followers Count" or "Followings Count" entries are written to the CSV file.
- **Performance**: High-overhead downloading of full lists is skipped, saving bandwidth and reducing API call volume.

To enable skipping follow changes:
- set `SKIP_FOLLOW_CHANGES` to `True` in your config
- or use the `--skip-follow-changes` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> --skip-follow-changes
```

<a id="advanced-followerfollowing-fetching"></a>
## Advanced Follower/Following Fetching

By default the tool fetches the full follower and following lists in one go. On large accounts this can be a strong signal to Instagram's automated detection. To reduce that risk you can fetch them gradually, in batches with a delay in between and up to an optional total cap.

Configure it with these options in `instagram_monitor.conf`:

```ini
# Number of accounts to fetch before pausing (0 = no batching)
FOLLOWERS_PER_BATCH = 0
FOLLOWEES_PER_BATCH = 0

# Delay in seconds between batches (0 = no delay)
FOLLOWER_DELAY_PER_BATCH = 0
FOLLOWEE_DELAY_PER_BATCH = 0

# Total number of accounts to fetch across all batches (0 = no limit)
FOLLOWER_LIMIT_TO_FETCH = 0
FOLLOWEE_LIMIT_TO_FETCH = 0
```

Depending on which values you set, the tool runs in one of these modes (it prints the active mode on startup and warns if the combination is invalid):

- **Disabled**: fetch everything at once (default)
- **Maximum of N accounts**: only `*_LIMIT_TO_FETCH` is set
- **Batches of Y accounts with Z second delay**: `*_PER_BATCH` and `*_DELAY_PER_BATCH` are set
- **Maximum of N accounts in batches of Y with Z second delay**: all three are set

**Note**: This feature requires [Logged-in mode](configuration.md#logged-in-mode-with-session-login) (session login).

<a id="routing-traffic-through-a-proxy"></a>
## Routing Traffic Through a Proxy

You can route the tool's Instagram traffic (and optionally webhook traffic) through an HTTP or HTTPS proxy. This is useful for pinning the monitor to a stable egress IP or for keeping it on the same network identity over time.

To enable a proxy:
- set `PROXY_ENABLED` to `True` and `PROXY_URL` to your proxy URL
- or use the `--enable-proxy` and `--proxy-url` flags

```sh
instagram_monitor <target_insta_user> --enable-proxy --proxy-url "http://user:pass@host:port"
```

Additional options:
- `PROXY_CERT_PATH` (or `--proxy-cert`): path to a local SSL certificate to use for the proxied connection
- `PROXY_WEBHOOKS` (or `--enable-proxy-webhooks`): also send webhook POST requests through the proxy (some proxies do not allow POST, so this is off by default)

`PROXY_URL` may contain credentials, so it is treated as a secret: the tool masks it in all output and you can store it via an [environment variable or dotenv file](configuration.md#storing-secrets).

```ini
PROXY_ENABLED = True
PROXY_URL = "http://user:pass@host:port"
PROXY_CERT_PATH = ""
PROXY_WEBHOOKS = False
```

**Note**: Even when `PROXY_ENABLED` is `False`, the underlying `requests` library still honors the `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` environment variables. If those are set in your shell or service unit they are applied silently, so unset them if you want a guaranteed direct connection.

<a id="http-transport-backend"></a>
## HTTP Transport Backend

All Instagram traffic flows through a configurable HTTP transport backend:

- `curl_cffi` (default): sends requests via [curl_cffi](https://github.com/lexiforest/curl_cffi), impersonating a real browser's TLS (JA3/JA4) and HTTP/2 fingerprint. This avoids fingerprint-based blocks where Instagram returns a spurious `HTTP 429` on the very first request even from a clean IP, a pattern most often seen on Linux builds (including Raspberry Pi OS) whose system TLS stack presents a fingerprint Instagram treats as automation.
- `requests`: the stock `requests` / `urllib3` transport using the system TLS stack (the historical behavior).

Both the no-login and logged-in paths use the selected backend. If `curl_cffi` is selected but not installed, the tool prints a warning and transparently falls back to `requests`.

Select the backend with `HTTP_BACKEND` (or `--http-backend`) and choose which browser curl_cffi impersonates with `CURL_CFFI_IMPERSONATE` (or `--impersonate`):

```ini
HTTP_BACKEND = "curl_cffi"
CURL_CFFI_IMPERSONATE = "auto"
```

`CURL_CFFI_IMPERSONATE` defaults to `auto`, which picks the impersonation target that matches your `USER_AGENT` so the TLS, HTTP/2 and client-hint headers stay consistent with the browser identity. This matters when you import a Firefox session and set a matching Firefox `USER_AGENT`: `auto` then presents a Firefox TLS fingerprint instead of pairing a Firefox user agent with Chrome client-hint headers. You can also pin a specific target such as `chrome`, `safari`, `safari_ios`, `edge` or `firefox`:

```sh
instagram_monitor <target_insta_user> --http-backend curl_cffi --impersonate firefox
```

See the [curl_cffi documentation](https://github.com/lexiforest/curl_cffi) for the full list of impersonation targets available in your installed version.

<a id="privacy-substitutions"></a>
## Privacy Substitutions

If you want to hide or rename identities in everything the tool produces (console output, logs, CSV, emails, webhooks and both dashboards), use privacy substitutions. For example you can replace a real Instagram username with a friendlier label or mask it entirely.

Provide a list of `(search, replace)` tuples via the `PRIVACY_SUBSTITUTIONS` config option:

```ini
PRIVACY_SUBSTITUTIONS = [ ("a.username", "Sarah"), ("some.other.user", "XXX") ]
```

Every occurrence of a search term is replaced with its replacement before anything is displayed, logged or sent. Internal keys and file paths are kept intact, so the substitution affects only what you see, not how the tool locates data. Invalid entries are ignored with a warning.

<a id="shadowban-and-flagged-account-detection"></a>
## Shadowban and Flagged Account Detection

Instagram sometimes flags a session or IP (challenge, checkpoint or shadowban) instead of a monitored target actually disappearing. When that happens, a profile lookup can fail in a way that looks identical to the target being deleted or renamed, which previously could trigger misleading alerts.

To tell the two apart, the tool probes a canonical, always-present public account (by default `instagram`) whenever a target lookup fails ambiguously. If that probe also fails, the tool concludes the session/IP is flagged rather than the target being gone and it idles and recovers instead of reporting a false change. When the session can recover it keeps waiting, otherwise it exits cleanly.

This runs automatically. The behavior can be tuned via these config options:

```ini
# Canonical public account used to probe whether the session/IP is flagged
FLAGGED_PROBE_USERNAME = "instagram"

# Seconds to reuse a flag-probe result so simultaneous target failures do not each hit the network
FLAGGED_PROBE_TTL = 300
```

<a id="reducing-jitter-log-noise"></a>
## Reducing Jitter Log Noise

When **Jitter Mode** (or debug/verbose output) is enabled, the HTTP back-off wrapper prints a `WRAP-REQ` / `WRAP-SEND` line for every request, which can be overwhelming. Set `SKIP_WRAP_MESSAGES` to `True` to suppress those per-request lines while keeping the rest of the jitter behavior:

```ini
SKIP_WRAP_MESSAGES = True
```

<a id="csv-export"></a>
## CSV Export

If you want to save all Instagram user's activities and profile changes to a CSV file, set `CSV_FILE` or use `-b` flag:

```sh
instagram_monitor <target_insta_user> -b instagram_username.csv
```

The file will be automatically created if it does not exist.

The tool uses the following logic for CSV path resolution:

1.  **Absolute Path**:
    *   **Single-target mode**: The file is saved exactly where specified.
    *   **Multi-target mode**: The absolute path is used as a base; separate files are created for each user (e.g., `/path/file_user1.csv`). Isolation is preserved.
2.  **Relative Path + `OUTPUT_DIR`**: If you provide a relative path and have `OUTPUT_DIR` configured, the file is saved in the `csvs/` subdirectory:
    *   **Single-target mode**: `OUTPUT_DIR/csvs/<filename>` (uses basename of your input)
    *   **Multi-target mode**: `OUTPUT_DIR/<username>/csvs/<filename>` (uses basename of your input)
3.  **Relative Path + no `OUTPUT_DIR`**:
    *   **Single-target mode**: Saved as specified in the current working directory.
    *   **Multi-target mode**: One file per user is created in the current working directory using a suffix: `<CSV_FILE_basename>_<username>.csv`.

<a id="output-directory"></a>
## Output Directory

By default, the tool saves all generated files (JSON, images, videos, logs) in the current working directory.

You can specify a custom root directory for all output files using the `-o` / `--output-dir` flag or `OUTPUT_DIR` configuration option:

```sh
instagram_monitor <target_insta_user> -o /path/to/downloads
```

The tool will organize files into subdirectories:

- **Output structure**: The layout depends on whether you monitor one or multiple users:

  - **Single-target mode**: All files are organized into subdirectories directly under `OUTPUT_DIR`:
    - `OUTPUT_DIR/images/`
    - `OUTPUT_DIR/videos/`
    - `OUTPUT_DIR/json/`
    - `OUTPUT_DIR/logs/`
    - `OUTPUT_DIR/csvs/`

  - **Multi-target mode**: Each user gets their own isolated subdirectory:
    - `OUTPUT_DIR/<username>/images/`
    - `OUTPUT_DIR/<username>/videos/`
    - `OUTPUT_DIR/<username>/json/`
    - `OUTPUT_DIR/<username>/logs/`
    - `OUTPUT_DIR/<username>/csvs/`

Common messages (like the summary screen or global errors) are automatically broadcasted to all active log files.

This helps keep your files organized, especially when monitoring multiple users.

<a id="detection-of-changed-profile-pictures"></a>
## Detection of Changed Profile Pictures

The tool can detect when a monitored user changes their profile picture. Notifications appear in the console and (if the `-s` flag is enabled) via email.

This feature is enabled by default. To disable it, either:

- set the `DETECT_CHANGED_PROFILE_PIC` to `False`
- or use the `-k` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

<a id="how-it-works"></a>
### How It Works

Since Instagram periodically changes the profile picture URL even when the image is the same, the tool performs a binary comparison of JPEG files to detect actual changes.

On the first run, it saves the current profile picture to `instagram_<username>_profile_pic.jpg`

On each subsequent check a new image is fetched and it is compared byte-for-byte with the saved image.

If a change is detected, the old picture is moved to `instagram_<username>_profile_pic_old.jpg` and the new one is saved to:
- `instagram_<username>_profile_pic.jpg` (current)
- `instagram_<username>_profile_pic_YYmmdd_HHMM.jpg` (for history)

<a id="empty-profile-picture-detection"></a>
### Empty Profile Picture Detection

The tool also has built-in detection of empty profile pictures. Instagram does not indicate an empty user's profile image in their API; that's why the tool detects it by using an empty profile image template (which appears to be identical on a binary level for all users).

To enable this:
- download the [instagram_profile_pic_empty.jpg](https://raw.githubusercontent.com/misiektoja/instagram_monitor/main/instagram_profile_pic_empty.jpg) file
- place it in the directory where you run the tool. **Note**: If installed via `pip`, this file is already bundled; however, any local file in your working directory will take **priority** over the bundled default.

Without this file, the tool will treat an empty profile picture as a regular image. For example, if a user removes their profile picture, it would be treated as a change rather than a removal.

<a id="detecting-collab-posts-on-private-accounts"></a>
## Detecting Collab Posts on Private Accounts

Instagram's collaboration feature lets two accounts co-author a single post. When a **private** account co-authors a post with a **public** account, that post stays visible on the private account's profile through the public `web_profile_info` endpoint even though the rest of the account is hidden. The tool surfaces these otherwise hidden posts.

This feature is enabled by default. To disable it, either:

- set the `DETECT_COLLAB_POSTS` to `False`
- or use the `--no-detect-collab-posts` flag

<a id="collab-posts---how-it-works"></a>
### Collab Posts - How It Works

The probe runs only for accounts whose posts are not otherwise viewable, meaning private profiles you do not follow.

On the first run the tool displays the newest collab post currently visible, the same way it shows a regular account's latest post and records a baseline so it does not re-alert on the ones already there. On later checks, when the account's post or reel count changes, it looks for newly leaked collab posts and reports each one with its date, owner, collaborators, likes, comments, caption and media through the console, email and webhook notifications. Media is saved like any other post.

This was inspired by [InstagramPrivSniffer](https://github.com/obitouka/InstagramPrivSniffer). Meta has confirmed that this visibility is intended behavior of the [collaboration feature](https://help.instagram.com/3526836317546926) rather than a vulnerability. Use it only for legitimate research and investigation.

<a id="displaying-images-in-your-terminal"></a>
## Displaying Images in Your Terminal

If you have `imgcat` installed, you can use the feature of displaying profile pictures and stories/reels/posts images right in your terminal.

To do this, set the path to your `imgcat` binary in the `IMGCAT_PATH` configuration option.

If you specify only the binary name, it will be auto-searched in your PATH.

Set it to empty to disable this feature.

<a id="check-intervals"></a>
## Check Intervals

If you want to customize polling interval, use `-c` flag (or `INSTA_CHECK_INTERVAL` configuration option):

```sh
instagram_monitor <target_insta_user> -c 3600
```

**Note**: You can also adjust check intervals and randomization timers live via the **Settings** menu in the **Web Dashboard**.

It is generally not recommended to use values lower than 1 hour as it will be quickly picked up by Instagram automated tool detection mechanisms.

In order to make the tool's behavior less suspicious for Instagram, by default the polling interval is randomly picked from the range:

```
[ INSTA_CHECK_INTERVAL (-c) - RANDOM_SLEEP_DIFF_LOW (-i) ]
                         ⇄
[ INSTA_CHECK_INTERVAL (-c) + RANDOM_SLEEP_DIFF_HIGH (-j) ]
```

This means each check will happen after a random delay centered around `INSTA_CHECK_INTERVAL` with some variation defined by `RANDOM_SLEEP_DIFF_LOW` and `RANDOM_SLEEP_DIFF_HIGH`.

So having the check interval set to 1 hour (-c 3600), `RANDOM_SLEEP_DIFF_LOW` set to default 15 mins (-i 900) and `RANDOM_SLEEP_DIFF_HIGH` set to default 3 mins (-j 180) means that the check interval will be with every iteration picked from the range of 45 mins to 1 hour and 3 mins.

That's why the check interval information is printed in the console and email notifications as it is essentially a random number.

On top of that you can also define that fetching updates should be done only in specific hour ranges by setting `CHECK_POSTS_IN_HOURS_RANGE` to `True` and then defining proper values for `MIN/MAX_H1/H2` configuration options (see [Use Hour-Range Checking](anti-detection.md#use-hour-range-checking) for more information).

<a id="signal-controls-macoslinuxunix"></a>
## Signal Controls (macOS/Linux/Unix)

The tool has several signal handlers implemented which allow to change behavior of the tool without a need to restart it with new configuration options / flags.

List of supported signals:

| Signal | Description |
| ----------- | ----------- |
| USR1 | Toggle email notifications for new posts, reels & stories, changed followings, bio, profile picture, visibility (-s) |
| USR2 | Toggle email notifications for new followers (-m) |
| TRAP | Increase the user activity check interval (by 5 mins) |
| ABRT | Decrease the user activity check interval (by 5 mins) |
| HUP | Reload secrets from .env file |

Send signals with `kill` or `pkill`, e.g.:

```sh
pkill -USR1 -f "instagram_monitor <target_insta_user>"
```

As Windows supports limited number of signals, this functionality is available only on Linux/Unix/macOS.

<a id="coloring-log-output-with-grc"></a>
## Coloring Log Output with GRC

The tool has native **color output** support for terminal since v3.0 (see `COLORED_OUTPUT` and `COLOR_THEME` config options), but you can also use [GRC](https://github.com/garabik/grc) to color logs.

Add to your GRC config (`~/.grc/grc.conf`):

```
# monitoring log file
.*_monitor.*\.log
conf.monitor_logs
```

Now copy the [conf.monitor_logs](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/grc/conf.monitor_logs) to your `~/.grc/` and log files should be nicely colored when using `grc` tool.

Example:

```sh
grc tail -F -n 100 instagram_monitor_<username>.log
```
