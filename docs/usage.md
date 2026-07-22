# Usage

<a id="command-format"></a>
## Command Format by Installation Method

Most examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace only that command with the prefix in this table. Keep the targets and options that follow it.

| Installation | Command prefix |
| --- | --- |
| PyPI | `instagram_monitor` |
| Manual script on macOS or Linux | `python3 instagram_monitor.py` |
| Manual script on Windows | `python instagram_monitor.py` |
| Docker Compose | `docker compose run --rm instagram_monitor` |
| Docker Compose with Web Dashboard | `docker compose run --rm --service-ports instagram_monitor` |
| Direct Docker on macOS or Windows PowerShell | `docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest` |
| Direct Docker on Linux | `docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest` |

For example, the PyPI command `instagram_monitor target1 --doctor` becomes `docker compose run --rm instagram_monitor target1 --doctor` with Compose.

In Windows Command Prompt replace `${PWD}` with `%cd%`. If your runtime reports that `:z` is invalid, remove only that suffix. A direct Docker run of the Web Dashboard also needs `-p 127.0.0.1:8000:8000` before the image name. The current host directory appears as `/data` inside the container, so container paths to its files must start with `/data`.

<a id="monitoring-mode"></a>
## Monitoring Mode

A **target** is an Instagram account you want to monitor. Put one or more target usernames directly after the command, pass a comma-separated list through `--targets` or save a list in `TARGET_USERNAMES`. If the command contains targets, they replace the saved list for that run.

To monitor one public account in [No-Login Mode](configuration.md#no-login-mode-without-session-login), pass its username:

```sh
instagram_monitor <target_insta_user>
```

For [Logged-In Mode](configuration.md#logged-in-mode-with-session-login), set the username of the account used to sign in through `SESSION_USERNAME` or `-u`. This session account can be different from the target:

```sh
instagram_monitor -u <your_insta_user> <target_insta_user>
```

You can monitor multiple accounts in one process with positional arguments or `--targets`:

```sh
instagram_monitor target_user_1 target_user_2 target_user_3
instagram_monitor --targets target_user_1,target_user_2,target_user_3
```

The setup wizard can save targets in `TARGET_USERNAMES`. To use that saved list with PyPI or a manual installation, do not put usernames on the command line:

```sh
instagram_monitor --config-file instagram_monitor.conf
```

Docker Compose uses the same saved targets when you run:

```sh
docker compose up
```

If setup did not save the targets, pass them to Compose explicitly:

```sh
docker compose run --rm instagram_monitor target_user_1 target_user_2
```

For a manual script installation:

```sh
python3 instagram_monitor.py <target_insta_user>
```

For a direct image on Docker Desktop:

```sh
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest <target_insta_user>
```

For a direct image on Linux:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest <target_insta_user>
```

Launch the [Web Dashboard](view-modes.md#web-dashboard-mode) with targets or by itself as a browser control panel:

```sh
instagram_monitor <target_insta_user> --web-dashboard
instagram_monitor --web-dashboard
```

For a one-off Compose run, `--service-ports` makes the dashboard port available to the host:

```sh
docker compose run --rm --service-ports instagram_monitor <target_insta_user> --web-dashboard
```

For direct Docker, add `-p 127.0.0.1:8000:8000` before the image name. Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) on the same computer.

The configuration file search order and setting precedence are documented under [Configuration File](configuration.md#configuration-file). To select another file explicitly, use `--config-file`:


```sh
instagram_monitor <target_insta_user> --config-file /path/instagram_monitor_new.conf
```

The tool runs until you press `Ctrl+C`. On macOS, Linux or Unix, tools such as `tmux` or `screen` can keep it running after you disconnect from a terminal.

You can add or remove targets directly through the Web Dashboard without restarting the tool.

With several targets, the tool spreads their first checks across `INSTA_CHECK_INTERVAL` instead of starting every check at once. This is called staggering. Set a fixed delay in seconds between target starts with:

```sh
instagram_monitor target_user_1 target_user_2 --targets-stagger 300
```

The tool saves text output to `instagram_monitor_<suffix>.log`. Change the name through `INSTA_LOGFILE`. Disable file logging through `DISABLE_LOGGING` or `-d`.

- In single-target mode, `<suffix>` is the username.
- In multi-target mode, `<suffix>` is the sorted list of target usernames joined with underscores.

In Logged-In Mode, the tool also saves follower and following usernames in these files:

- `instagram_<username>_followings.json`
- `instagram_<username>_followers.json`

These files provide a baseline for the next run. The tool compares the new lists with the saved lists to find added or removed usernames.

When the tool downloads follower or following lists, a terminal progress bar shows request counts, elapsed time and estimated time remaining. Intermediate progress is not written to the log. The final result is.

Profile pictures are saved as `instagram_<username>_profile_pic*.jpg`.

Downloaded post and reel media use these names:

- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.jpg`
- `instagram_<username>_post/reel_YYYYmmdd_HHMMSS.mp4`

Downloaded story media use these names:

- `instagram_<username>_story_YYYYmmdd_HHMMSS.jpg`
- `instagram_<username>_story_YYYYmmdd_HHMMSS.mp4`

<a id="docker-usage-recommended"></a>
<a id="container-operation"></a>
## Container Operation

See [Docker installation](installation.md#docker-compose) for installation, Linux file ownership, local image builds, upgrades and old volume repair. This section covers everyday use after setup.

<a id="docker-compose-easiest"></a>
### Docker Compose

Compose makes the current host directory available as `/data` inside the container. The wizard creates or updates `instagram_monitor.conf` and `.env` in that host directory. Logs, JSON files, CSV files and downloaded media are also written there. The Docker volume named `instagram_monitor_session` stores the saved Instagram login separately.

Start the saved targets and interface in the foreground:

```sh
docker compose up
```

For a background run and live logs:

```sh
docker compose up -d
docker compose logs -f
```

Stop and remove the service container:

```sh
docker compose down
```

This command does not delete files in the current directory or the `instagram_monitor_session` volume.

When the Web Dashboard is enabled, open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) on the host. Compose exposes the port only to that computer. Other devices cannot connect unless you change the published address.

Compose makes `instagram_monitor.conf` available as `/data/instagram_monitor.conf`. Instagram Monitor also loads `/data/.env` when setup selected it. Do not replace a wizard-created `.env` with `.env.example` because `.env` may contain private login or notification values.

<a id="common-run-scenarios"></a>
### Direct Docker

In direct Docker commands, refer to files from the current host directory through `/data`:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest <target_insta_user> --config-file /data/instagram_monitor.conf --env-file /data/.env
```

Use the same `instagram_monitor_session` volume during browser import and every later logged-in run. Otherwise the later container cannot find the imported session.

### Import Firefox into the Container Session

On Linux, mount the Firefox profile read-only:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox
```

With Compose on Linux:

```sh
docker compose run --rm -v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox
```

On macOS, mount one explicit Firefox cookie database:

```sh
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "${HOME}/Library/Application Support/Firefox/Profiles/<profile>/cookies.sqlite:/cookies/cookies.sqlite:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox --cookie-file /cookies/cookies.sqlite
```

Firefox works inside Docker because its cookie database can be mounted as a read-only file. Chrome, Brave and Chromium need the host password service to decrypt their cookies. A container cannot use that service. Import from those browsers through a local PyPI or manual installation instead.

Do not add `:z` or `:Z` to the whole Firefox profile mount. Those suffixes can change SELinux labels on the host files. If SELinux blocks the read-only mount, close Firefox and copy `cookies.sqlite` to a dedicated directory before mounting that copy.

After importing, run with `-u <your_insta_user>`. This must be the username logged in through Firefox. Reuse the same named session volume.

<a id="email-notifications"></a>
## Email Notifications

Status email notifications cover posts, reels, stories, following changes, bio updates, profile picture changes and visibility changes. Enable them in one of these ways:

- set `STATUS_NOTIFICATION` to `True`
- or use the `-s` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> -s
```

Follower emails report accounts that followed or unfollowed the target. Enable them separately:

- set `FOLLOWERS_NOTIFICATION` to `True`
- or use the `-m` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> -m
```

Error emails are enabled by default when email is configured. Disable them in one of these ways:

- set `ERROR_NOTIFICATION` to `False`
- or use the `-e` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> -e
```

Email requires [SMTP settings](configuration.md#smtp-settings). Run `instagram_monitor --send-test-email` before a long monitoring session.

Example email:

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_email_notifications.png" alt="instagram_monitor_email_notifications" width="80%"/>
</p>

<a id="webhook-notifications"></a>
## Webhook Notifications

Instagram Monitor can send event notifications to **Discord** or **ntfy**. A webhook is a URL that accepts a message from another application. Webhook settings do not affect email settings.

`WEBHOOK_PROVIDER` tells Instagram Monitor which message format the URL expects. The default is `"discord"`.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_discord.png" alt="instagram_monitor_discord_screenshot" width="80%"/>
</p>

<a id="1-configure-discord-webhook"></a>
### 1. Choose a Provider

#### Discord

To create a Discord Webhook URL:

1.  **Create a Server**: Click the **+** (Plus) icon on the left sidebar ("Add a Server") -> **Create My Own** -> **For me and my friends**.
2.  **Create/Edit a Channel**: In your new server, find the **#general** channel (or create a new one). Click the **Edit Channel** icon (⚙️ gear) next to the channel name.
3.  **Create Webhook**: Go to **Integrations** in the left menu -> **Webhooks** -> **New Webhook**.
4.  **Copy URL**: Click on the new webhook (often named "Spidey Bot", you can rename it) and click **Copy Webhook URL**.

Keep `WEBHOOK_PROVIDER = "discord"` in `instagram_monitor.conf`.

#### ntfy

For ntfy.sh or a self-hosted ntfy server:

1. Choose a hard-to-guess topic such as `instagram-monitor-long-random-value`.
2. In the setup wizard, enter either an ntfy.sh topic name or a complete topic URL such as `https://ntfy.sh/instagram-monitor-long-random-value`. The wizard expands a bare topic name to an ntfy.sh URL. For a self-hosted server, the Web Dashboard or manual configuration, enter the complete HTTP or HTTPS URL.
3. Set `WEBHOOK_PROVIDER = "ntfy"` in `instagram_monitor.conf`.

Instagram Monitor sends the alert subject as the ntfy title. The alert text and event details become the message. Existing query parameters in the topic URL are preserved, including the ntfy [`auth` query parameter](https://docs.ntfy.sh/publish/#authentication).

For a protected topic, the setup wizard asks for the ntfy access token in a hidden prompt and stores it in `.env`. For manual setup, add:

```ini
NTFY_ACCESS_TOKEN="tk_your_ntfy_access_token"
```

The tool sends the token as `Authorization: Bearer <token>`. It replaces any `Authorization` value in `WEBHOOK_HEADERS`.

Advanced integrations can set fixed HTTP headers:

```python
WEBHOOK_HEADERS = {
    "Authorization": "Basic your_base64_credentials",
}
```

For ntfy, Instagram Monitor sets the required plain-text `Content-Type`. Store Bearer tokens in `NTFY_ACCESS_TOKEN` inside `.env`. A token in the regular config is easier to expose or commit accidentally. The tool validates header names and values before sending a request.

Anyone who knows an unprotected ntfy.sh topic name can read or publish to it. Reserve and protect the topic through an ntfy account when possible. Otherwise use a long random name, keep it private and do not copy the example name above.

<a id="2-enable-in-the-tool"></a>
### 2. Enable in the Tool

Choose one method:

- set `WEBHOOK_ENABLED = True`, select `WEBHOOK_PROVIDER` and put `WEBHOOK_URL` in `.env`
- use an [environment variable](configuration.md#storing-secrets) for `WEBHOOK_URL`
- pass `--webhook-url`. If the URL is already saved, pass `--webhook`
- enable it through the **Settings** page in the Web Dashboard

```sh
# Enable Discord with URL
instagram_monitor <target_insta_user> --webhook-provider discord --webhook-url "https://discord.com/api/webhooks/..."

# Enable ntfy with a topic URL
instagram_monitor <target_insta_user> --webhook-provider ntfy --webhook-url "https://ntfy.sh/your-private-topic"

# Enable or disable a URL that is already saved
instagram_monitor <target_insta_user> --webhook
instagram_monitor <target_insta_user> --no-webhook
```

<a id="3-test-your-settings"></a>
### 3. Test Your Settings

Send a test notification before starting monitoring:

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

Example:
```sh
# Enable all three event groups
instagram_monitor <target_insta_user> --webhook-url "..." --webhook-status --webhook-followers --webhook-errors
```

Equivalent configuration options:
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

Follower churn detection downloads the complete follower and following lists on every check. It compares usernames even when the total counts have not changed. This can detect cases where:

- one account unfollows while another follows, so the count stays the same
- a username changes without changing the total count

To enable follower churn detection:

- set `FOLLOWERS_CHURN_DETECTION` to `True`
- or use the `--followers-churn` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

This feature requires [Logged-In Mode](configuration.md#logged-in-mode-with-session-login). It is disabled when `SKIP_FOLLOW_CHANGES` is active.

```sh
instagram_monitor <target_insta_user> --followers-churn
```

This feature sends many more Instagram requests because it downloads both complete lists at every interval. Large accounts increase the request count further. Review the [risk reduction guide](anti-detection.md) before enabling it.

<a id="skipping-follow-changes"></a>
## Skipping Follow Changes

Skip Follow Changes keeps follower and following counts visible in the dashboards but suppresses detailed change reporting.

When enabled:

- **Notifications**: Email and Webhook alerts for follower/following changes are suppressed.
- **Reporting**: Console prints and activity logs for these changes are disabled.
- **CSV Export**: No "Followers Count" or "Followings Count" entries are written to the CSV file.
- **Requests**: Complete list downloads are skipped, which reduces data transfer and Instagram requests.

To enable skipping follow changes:

- set `SKIP_FOLLOW_CHANGES` to `True` in your config
- or use the `--skip-follow-changes` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

```sh
instagram_monitor <target_insta_user> --skip-follow-changes
```

<a id="advanced-followerfollowing-fetching"></a>
## Advanced Follower/Following Fetching

By default, the tool downloads each complete follower or following list without an intentional pause. For large accounts, split the download into batches to add pauses or set a maximum number of usernames to fetch.

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

The values select one of these modes. The tool prints the selected mode at startup and warns about invalid combinations.

- **Disabled**: fetch everything at once (default)
- **Maximum of N accounts**: set only `*_LIMIT_TO_FETCH`
- **Batches of Y accounts with a Z-second delay**: set `*_PER_BATCH` and `*_DELAY_PER_BATCH`
- **Maximum of N accounts in batches of Y with a Z-second delay**: set all three values

This feature requires [Logged-In Mode](configuration.md#logged-in-mode-with-session-login).

<a id="routing-traffic-through-a-proxy"></a>
## Routing Traffic Through a Proxy

A proxy is another server that forwards network requests. Instagram sees the proxy's public IP address instead of the monitor's address. Instagram Monitor can send Instagram traffic and optional webhook traffic through an HTTP or HTTPS proxy.

To enable a proxy:

- set `PROXY_ENABLED` to `True` and `PROXY_URL` to your proxy URL
- or use the `--enable-proxy` and `--proxy-url` flags

```sh
instagram_monitor <target_insta_user> --enable-proxy --proxy-url "http://user:pass@host:port"
```

Additional options:

- `PROXY_CERT_PATH` or `--proxy-cert` selects a local certificate used to verify the proxy connection
- `PROXY_WEBHOOKS` or `--enable-proxy-webhooks` also sends webhook requests through the proxy. It is off by default because some proxies do not allow these requests

`PROXY_URL` may contain a username and password. The tool masks it in output. Store it through an [environment variable or `.env` file](configuration.md#storing-secrets).

```ini
PROXY_ENABLED = True
PROXY_URL = "http://user:pass@host:port"
PROXY_CERT_PATH = ""
PROXY_WEBHOOKS = False
```

The Python `requests` library reads `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` from the process environment even when `PROXY_ENABLED` is `False`. Check and unset those variables if you need a direct connection.

<a id="http-transport-backend"></a>
## HTTP Transport Backend

The HTTP backend is the library used to send requests to Instagram. Choose one of these values:

- `curl_cffi` (default): sends requests via [curl_cffi](https://github.com/lexiforest/curl_cffi), impersonating a real browser's TLS (JA3/JA4) and HTTP/2 fingerprint. This avoids fingerprint-based blocks where Instagram returns a spurious `HTTP 429` on the very first request even from a clean IP, a pattern most often seen on Linux builds (including Raspberry Pi OS) whose system TLS stack presents a fingerprint Instagram treats as automation.
- `requests`: the stock `requests` / `urllib3` transport using the system TLS stack (the historical behavior).

Both login modes use the selected backend. If `curl_cffi` is selected but not installed, the tool warns you and uses `requests` instead.

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

Privacy substitutions replace selected text in console output, logs, CSV files, notifications and dashboards. Use them to display a label instead of a real Instagram username or to mask other text.

Provide a list of `(search, replace)` tuples via the `PRIVACY_SUBSTITUTIONS` config option:

```ini
PRIVACY_SUBSTITUTIONS = [ ("a.username", "Sarah"), ("some.other.user", "XXX") ]
```

The replacement happens before output is displayed, logged or sent. Internal keys and file paths do not change, so the tool still uses the original usernames to find data. Invalid entries are ignored with a warning.

<a id="shadowban-and-flagged-account-detection"></a>
## Shadowban and Flagged Account Detection

Instagram may block a session or IP address in a way that makes every profile lookup fail. A single failed lookup cannot show whether the target disappeared or whether the session was blocked.

When a target lookup fails for an unclear reason, the tool also checks a known public account. The default is `instagram`. If both lookups fail, it treats the session or IP address as the likely cause and does not report that the target disappeared. It waits when recovery is possible. Otherwise it exits.

This check runs automatically. Advanced users can change these settings:

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

To save activity and profile changes in a CSV file, set `CSV_FILE` or pass `-b`:

```sh
instagram_monitor <target_insta_user> -b instagram_username.csv
```

The tool creates the file if it does not exist.

The output path depends on whether the path is absolute or relative and whether `OUTPUT_DIR` is set:

1. **Absolute path**
    * With one target, the exact path is used.
    * With several targets, the username is added to each filename. For example, `/path/file.csv` becomes `/path/file_user1.csv`.
2. **Relative path with `OUTPUT_DIR`**
    * With one target, the file is `OUTPUT_DIR/csvs/<filename>`.
    * With several targets, each file is `OUTPUT_DIR/<username>/csvs/<filename>`.
3. **Relative path without `OUTPUT_DIR`**
    * With one target, the path is relative to the current directory.
    * With several targets, one file per target is created in the current directory as `<CSV_FILE_basename>_<username>.csv`.

<a id="output-directory"></a>
## Output Directory

By default, the tool saves JSON files, images, videos, logs and CSV files in the directory where you start it.

You can specify a custom root directory for all output files using the `-o` / `--output-dir` flag or `OUTPUT_DIR` configuration option:

```sh
instagram_monitor <target_insta_user> -o /path/to/downloads
```

Inside Docker, use a path under `/data`, such as `-o /data/downloads`. The files then appear in the host directory named `downloads`.

The directory layout depends on the number of targets:

- **Single-target mode**: Files are organized into subdirectories directly under `OUTPUT_DIR`:
    - `OUTPUT_DIR/images/`
    - `OUTPUT_DIR/videos/`
    - `OUTPUT_DIR/json/`
    - `OUTPUT_DIR/logs/`
    - `OUTPUT_DIR/csvs/`

- **Multi-target mode**: Each target gets a separate subdirectory:
    - `OUTPUT_DIR/<username>/images/`
    - `OUTPUT_DIR/<username>/videos/`
    - `OUTPUT_DIR/<username>/json/`
    - `OUTPUT_DIR/<username>/logs/`
    - `OUTPUT_DIR/<username>/csvs/`

Summary messages and errors that apply to the whole process are written to every active target log.

<a id="detection-of-changed-profile-pictures"></a>
## Detection of Changed Profile Pictures

Profile picture changes appear in console output. They can also be sent by email, Discord or ntfy when the matching status notification settings are enabled.

This feature is enabled by default. To disable it, either:

- set the `DETECT_CHANGED_PROFILE_PIC` to `False`
- or use the `-k` flag
- or toggle it via the **Settings** menu in the **Web Dashboard**

<a id="how-it-works"></a>
### How It Works

Since Instagram periodically changes the profile picture URL even when the image is the same, the tool performs a binary comparison of JPEG files to detect actual changes.

On the first run, the tool saves the current profile picture as `instagram_<username>_profile_pic.jpg`.

On later checks, it downloads the current image and compares its bytes with the saved image.

If a change is detected, the old picture is moved to `instagram_<username>_profile_pic_old.jpg` and the new one is saved to:

- `instagram_<username>_profile_pic.jpg` (current)
- `instagram_<username>_profile_pic_YYmmdd_HHMM.jpg` (for history)

<a id="empty-profile-picture-detection"></a>
### Empty Profile Picture Detection

Instagram does not provide a separate API value for an account with no profile picture. Instagram Monitor recognizes the default empty image by comparing it with a template.

To enable this:

- download the [instagram_profile_pic_empty.jpg](https://raw.githubusercontent.com/misiektoja/instagram_monitor/main/instagram_profile_pic_empty.jpg) file
- place it in the directory where you run the manual script. PyPI and Docker installations already include it. A copy in the current directory takes priority over the included template

Without the template, removing a profile picture is reported as an image change instead of a removal.

<a id="detecting-collab-posts-on-private-accounts"></a>
## Detecting Collab Posts on Private Accounts

Instagram lets several accounts co-author one collaboration post. When a private account collaborates with a public account, Instagram may still return that post through its public profile endpoint. Instagram Monitor reports these visible collaboration posts even when it cannot read the private account's other posts.

This feature is enabled by default. To disable it, either:

- set the `DETECT_COLLAB_POSTS` to `False`
- or use the `--no-detect-collab-posts` flag

<a id="collab-posts---how-it-works"></a>
### Collab Posts - How It Works

The check runs only when the session cannot normally view a target's posts, such as a private account that the session account does not follow.

On the first run, the tool shows the newest visible collaboration post and saves a baseline. It does not send later alerts for posts already in that baseline. When the post or reel count changes, the tool looks for newly visible collaboration posts. It reports their date, owner, collaborators, likes, comments, caption and media through enabled output channels. Media is saved like other post media.

This behavior was inspired by [InstagramPrivSniffer](https://github.com/obitouka/InstagramPrivSniffer). The [Instagram collaboration help page](https://help.instagram.com/3526836317546926) describes how accepted collaboration posts also appear on a collaborator's profile. Use this feature only for legitimate research.

<a id="displaying-images-in-your-terminal"></a>
## Displaying Images in Your Terminal

`imgcat` displays supported image files inside compatible terminals. If it is installed, Instagram Monitor can use it for profile pictures, stories, reels and posts.

To do this, set the path to your `imgcat` binary in the `IMGCAT_PATH` configuration option.

If you set only the command name, Instagram Monitor searches for it in `PATH`.

Leave `IMGCAT_PATH` empty to disable terminal images.

The published Docker image does not include `imgcat`. Use a local installation or add the tool in a custom image if terminal image display is required. Saved images remain available through the `/data` mount without `imgcat`.

<a id="check-intervals"></a>
## Check Intervals

The polling interval is the number of seconds between scheduled checks. Set it through `INSTA_CHECK_INTERVAL` or `-c`:

```sh
instagram_monitor <target_insta_user> -c 3600
```

**Note**: You can also adjust check intervals and randomization timers live via the **Settings** menu in the **Web Dashboard**.

Use at least 3600 seconds unless you have a specific reason to send more frequent requests. Shorter intervals create more Instagram traffic and may increase the chance of limits.

By default, the actual wait changes on each cycle. The range is:

```
[ INSTA_CHECK_INTERVAL (-c) - RANDOM_SLEEP_DIFF_LOW (-i) ]
                            to
[ INSTA_CHECK_INTERVAL (-c) + RANDOM_SLEEP_DIFF_HIGH (-j) ]
```

This means each check will happen after a random delay centered around `INSTA_CHECK_INTERVAL` with some variation defined by `RANDOM_SLEEP_DIFF_LOW` and `RANDOM_SLEEP_DIFF_HIGH`.

So having the check interval set to 1 hour (-c 3600), `RANDOM_SLEEP_DIFF_LOW` set to default 15 mins (-i 900) and `RANDOM_SLEEP_DIFF_HIGH` set to default 3 mins (-j 180) means that the check interval will be with every iteration picked from the range of 45 mins to 1 hour and 3 mins.

The console and email notifications show the wait selected for the current cycle.

To restrict checks to selected times of day, set `CHECK_POSTS_IN_HOURS_RANGE = True` and configure `MIN_H1`, `MAX_H1`, `MIN_H2` and `MAX_H2`. See [Use Hour-Range Checking](anti-detection.md#use-hour-range-checking).

<a id="signal-controls-macoslinuxunix"></a>
## Signal Controls (macOS/Linux/Unix)

On macOS, Linux and Unix, operating system signals can change a running process without restarting it.

Supported signals:

| Signal | Description |
| ----------- | ----------- |
| USR1 | Toggle status email notifications (`-s`) |
| USR2 | Toggle follower email notifications (`-m`) |
| TRAP | Increase the activity check interval by 5 minutes |
| ABRT | Decrease the activity check interval by 5 minutes |
| HUP | Reload private values from the `.env` file |

Send a signal with `kill` or `pkill`. For example:

```sh
pkill -USR1 -f "instagram_monitor <target_insta_user>"
```

For a Docker Compose service, send the signal through Docker:

```sh
docker compose kill --signal SIGUSR1 instagram_monitor
```

For direct Docker, assign a stable container name with `--name instagram-monitor` when starting it then use `docker kill --signal SIGUSR1 instagram-monitor`.

A local Windows process supports only a limited signal set. Linux containers can receive the Docker signals above even when Docker Desktop runs on Windows.

<a id="coloring-log-output-with-grc"></a>
## Coloring Log Output with GRC

Instagram Monitor can color live terminal output through `COLORED_OUTPUT` and `COLOR_THEME`. To color saved log files when viewing them later, you can use [GRC](https://github.com/garabik/grc).

Add to your GRC config (`~/.grc/grc.conf`):

```
# monitoring log file
.*_monitor.*\.log
conf.monitor_logs
```

Copy [conf.monitor_logs](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/grc/conf.monitor_logs) to `~/.grc/`. Then view a log through `grc`:

```sh
grc tail -F -n 100 instagram_monitor_<username>.log
```
