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
| Direct `docker run` on macOS or Windows PowerShell | `docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest` |
| Direct `docker run` on native Linux | `docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader misiektoja/instagram-monitor:latest` |

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
docker compose up --no-log-prefix
```

If setup did not save the targets, pass them to Compose explicitly:

```sh
docker compose run --rm instagram_monitor target_user_1 target_user_2
```

For a manual script installation:

```sh
python3 instagram_monitor.py <target_insta_user>
```

For a direct `docker run` command on macOS or Windows PowerShell:

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

For direct Docker on macOS or Windows PowerShell, publish the dashboard port before the image name:

```sh
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 127.0.0.1:8000:8000 misiektoja/instagram-monitor:latest <target_insta_user> --web-dashboard
```

On native Linux, use the same port mapping with the host identity:

```sh
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 127.0.0.1:8000:8000 misiektoja/instagram-monitor:latest <target_insta_user> --web-dashboard
```

Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) on the same computer. Inside the container the server listens on `0.0.0.0:8000` so Docker can forward traffic. `0.0.0.0` is a server bind address, not an address to enter in a browser. Dockerfile `EXPOSE 8000` metadata also does not publish the port by itself.

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

Set `ASCII_LOG_SEPARATORS` to `"Auto"` (default) to use ASCII separator-only lines on Windows, `"On"` to use them on every operating system or `"Off"` to preserve Unicode separators in logs everywhere. Terminal separators stay Unicode. Log files and all other logged text remain UTF-8.

- In single-target mode, `<suffix>` is the username.
- In multi-target mode, `<suffix>` is the sorted list of target usernames joined with underscores.

In Logged-In Mode, the tool also saves follower and following usernames in these files:

- `instagram_<username>_followings.json`
- `instagram_<username>_followers.json`

These files provide a baseline for the next run. The tool compares the new lists with the saved lists to find added or removed usernames.

Only a complete list download can replace this baseline. A configured maximum, stop request or interrupted download leaves the last complete file unchanged so a partial result cannot appear as a large follower or following removal.

When the tool downloads follower or following lists, a terminal progress bar shows request counts, elapsed time and estimated time remaining. Intermediate progress is not written to the log. The final result is.

With several targets, only one progress bar is drawn at a time because they share one terminal line. A target whose download starts while another bar is active fetches without a bar rather than waiting for it. The final result is logged either way.

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
docker compose up --no-log-prefix
```

For a background run and live logs:

```sh
docker compose up -d
docker compose logs -f --no-log-prefix
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

If the saved configuration enables the Web Dashboard, add `-p 127.0.0.1:8000:8000` before the image name. The exact monitoring command printed by setup includes this mapping.

Use the same `instagram_monitor_session` volume during browser import and every later logged-in run. Otherwise the later container cannot find the imported session.

### Import Firefox into the Container Session

Finish the setup wizard first. It asks which host environment runs Docker then prints the matching one-time import command. Run Doctor only after that import succeeds.

On Windows, use Docker Desktop or another Docker-compatible runtime in Linux container mode. PowerShell reads the Firefox profile root from `$env:APPDATA\Mozilla\Firefox`. Command Prompt uses `%APPDATA%\Mozilla\Firefox`.

Use the direct Docker command that matches the Firefox profile layout on the host:

```sh
# macOS
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "${HOME}/Library/Application Support/Firefox/Profiles:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox --env-file /data/.env

# Windows PowerShell
docker run --rm -it --init -v "${PWD}:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "$env:APPDATA\Mozilla\Firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox --env-file /data/.env

# Windows Command Prompt
docker run --rm -it --init -v "%cd%:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "%APPDATA%\Mozilla\Firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox --env-file /data/.env

# Linux with a standard Firefox package
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox --env-file /data/.env

# Linux with Firefox from Snap
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "$HOME/snap/firefox/common/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox --env-file /data/.env

# Linux with Firefox from Flatpak
docker run --rm -it --init --user "$(id -u):$(id -g)" -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -v "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" misiektoja/instagram-monitor:latest --import-browser-session --browser firefox --env-file /data/.env
```

The equivalent Docker Compose commands are:

```sh
# macOS
docker compose run --rm -v "${HOME}/Library/Application Support/Firefox/Profiles:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox --env-file /data/.env

# Windows PowerShell
docker compose run --rm -v "$env:APPDATA\Mozilla\Firefox:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox --env-file /data/.env

# Windows Command Prompt
docker compose run --rm -v "%APPDATA%\Mozilla\Firefox:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox --env-file /data/.env

# Linux with a standard Firefox package
docker compose run --rm -v "$HOME/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox --env-file /data/.env

# Linux with Firefox from Snap
docker compose run --rm -v "$HOME/snap/firefox/common/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox --env-file /data/.env

# Linux with Firefox from Flatpak
docker compose run --rm -v "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox:/home/instagram/.mozilla/firefox:ro" instagram_monitor --import-browser-session --browser firefox --env-file /data/.env
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

`WEBHOOK_PROVIDER` tells Instagram Monitor which message format the URL expects. The default is `"discord"`. Standard Discord and public `ntfy.sh` URLs automatically select the matching format if this configured value is stale. Self-hosted ntfy and compatible endpoints still use the configured provider. An explicit `--webhook-provider` override always wins.

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

Keep `WEBHOOK_PROVIDER = "discord"` in `instagram_monitor.conf`. Standard Discord webhook URLs are also recognized automatically.

#### ntfy

For ntfy.sh or a self-hosted ntfy server:

1. Choose a hard-to-guess topic such as `instagram-monitor-long-random-value`.
2. In the setup wizard, enter either an ntfy.sh topic name or a complete topic URL such as `https://ntfy.sh/instagram-monitor-long-random-value`. The wizard expands a bare topic name to an ntfy.sh URL. For a self-hosted server, the Web Dashboard or manual configuration, enter the complete HTTPS topic URL.
3. Public `ntfy.sh` URLs are recognized automatically. Set `WEBHOOK_PROVIDER = "ntfy"` in `instagram_monitor.conf` for a self-hosted ntfy server.

Instagram Monitor sends the alert subject as the ntfy title. The alert text and event details become the message. Existing query parameters in the topic URL are preserved, including the ntfy [`auth` query parameter](https://docs.ntfy.sh/publish/#authentication). Long ntfy messages are visibly truncated below ntfy's 4 KB boundary so they remain notifications instead of temporary attachments.

The title and message are sent as request headers or as the request body, never as query parameters. Alert text can contain follower names, captions and biographies, and servers and proxies commonly record full URLs in their access logs. Webhook requests also do not follow redirects, so a moved destination cannot receive headers meant for the address you configured.

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

Header values support the same placeholders as `WEBHOOK_TEMPLATE`. Instagram Monitor validates headers before and after placeholder expansion so formatted values cannot introduce invalid names, non-string values or line breaks. For ntfy, Instagram Monitor sets the required plain-text `Content-Type`. Store Bearer tokens in `NTFY_ACCESS_TOKEN` inside `.env`. A token in the regular config is easier to expose or commit accidentally.

When an alert includes a downloaded local image, Instagram Monitor uploads it as a native ntfy attachment up to 5 MiB. If image preparation or upload fails, it sends the alert as text so an image problem cannot suppress the notification. Existing remote image URLs remain links in the message.

Anyone who knows an unprotected ntfy.sh topic name can read or publish to it. Reserve and protect the topic through an ntfy account when possible. Otherwise use a long random name, keep it private and do not copy the example name above.

<a id="2-enable-in-the-tool"></a>
### 2. Enable in the Tool

Choose one method:

- set `WEBHOOK_ENABLED = True`, select `WEBHOOK_PROVIDER` and put `WEBHOOK_URL` in `.env`
- use an [environment variable](configuration.md#storing-secrets) for `WEBHOOK_URL`
- save it through the hidden `--set-webhook-url` prompt
- pass `--webhook-url` for one run. If the URL is already saved, pass `--webhook`
- enable it through the **Settings** page in the Web Dashboard

```sh
# Save a private destination without displaying it
instagram_monitor --set-webhook-url

# Enable Discord with URL
instagram_monitor <target_insta_user> --webhook-provider discord --webhook-url "https://discord.com/api/webhooks/..."

# Enable ntfy with a topic URL
instagram_monitor <target_insta_user> --webhook-provider ntfy --webhook-url "https://ntfy.sh/your-private-topic"

# Enable or disable a URL that is already saved
instagram_monitor <target_insta_user> --webhook
instagram_monitor <target_insta_user> --no-webhook
```

Webhook and avatar URLs must be complete HTTPS links with a hostname and no embedded credentials. Root endpoints work with or without a trailing slash. Known Discord and `ntfy.sh` destinations correct a stale configured provider at runtime. A URL passed through `--webhook-url` may remain visible in shell history or process listings, so prefer `--set-webhook-url` for normal setup.

<a id="3-test-your-settings"></a>
### 3. Test Your Settings

Send a test notification before starting monitoring:

```sh
# Verify settings from configuration file
instagram_monitor --send-test-webhook

# Verify a specific provider and URL from command line
instagram_monitor --webhook-provider ntfy --webhook-url "https://ntfy.sh/your-private-topic" --send-test-webhook
```

A test notification is always delivered when the URL and provider are valid. It does not require the event switches below, so you can confirm delivery before deciding which notifications to enable.

<a id="4-advanced-configuration"></a>
### 4. Advanced Configuration

By default, all webhook notification types (status, followers, errors) are **disabled**. You must explicitly enable what you want the tool to send. Enabling an event flag also enables the webhook master switch:

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

`WEBHOOK_USERNAME` and `WEBHOOK_AVATAR_URL` customize Discord-format messages. `WEBHOOK_TEMPLATE` supports `title`, `description`, `version`, `image_url`, `fields`, `fields_str`, `color`, `timestamp`, `username` and `avatar_url` placeholders. A dictionary or list is sent as JSON while a string is sent as the raw body for compatible advanced integrations.

`WEBHOOK_TEMPLATE`, `WEBHOOK_USERNAME` and `WEBHOOK_AVATAR_URL` apply only to Discord and are ignored when `WEBHOOK_PROVIDER` is `"ntfy"`. The ntfy provider needs no template: it sends the alert body as a native ntfy message with the subject as its title. Customize ntfy delivery through `WEBHOOK_HEADERS` (for example `X-Priority` or `X-Tags`).

`WEBHOOK_TRANSFORMS` applies configured string methods before the template and headers are rendered. Invalid templates, avatar URLs, transforms or expanded headers fail before any request is attempted. Dictionary payloads always replace `allowed_mentions` with `{"parse": []}` so notification text cannot trigger `@everyone`, `@here` or user mentions.

Webhook delivery uses an isolated session with a 10-second timeout and at most two attempts. It accepts every HTTP 2xx response, retries HTTP 429 according to a server delay capped at 5 seconds and retries HTTP 5xx once. Other HTTP 4xx responses fail immediately.

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

After a complete list comparison, email and webhook alerts require at least one added or removed username. Reported count fluctuations with an unchanged complete list are ignored. When a complete comparison is unavailable because list fetching is disabled, fails or uses a configured maximum, alerts fall back to reported count changes without claiming which usernames changed.

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

<a id="follow-relationship-analysis"></a>
## Follow Relationship Analysis

Follow relationship analysis reports mutual, not-following-back and fan relationships for a target. It works entirely offline: it reads the follower and following lists the monitor has already saved and makes no additional Instagram requests.

The categories are:

- **Mutual**: the number of accounts that follow the target and that the target follows back
- **Not following back**: accounts the target follows that do not follow the target back
- **Fans**: accounts that follow the target while the target does not follow them back

Both saved lists are required. The analysis shows each snapshot's save time and warns when the two files are at least one hour apart, since changes between those downloads can be misclassified.

Run it with the `--analyze-follows` flag. It prints the analysis and exits without starting the monitoring loop:

```sh
instagram_monitor <target_insta_user> --analyze-follows
```

Multiple targets are supported (positional usernames or `TARGET_USERNAMES` from the config):

```sh
instagram_monitor user1 user2 --analyze-follows
```

Usable targets are still reported when another target has missing or malformed data. The command exits successfully when at least one target could be analyzed and returns a nonzero status when none could be analyzed.

The analysis needs the saved lists `instagram_<user>_followers.json` and `instagram_<user>_followings.json`. These are produced when the monitor runs in [Logged-In Mode](configuration.md#logged-in-mode-with-session-login) with follower and following fetching enabled. They are read from the JSON directory described in [Output Directory](#output-directory), so they resolve under `OUTPUT_DIR/json/` for a single target, `OUTPUT_DIR/<username>/json/` for multiple targets, or the working directory when no output directory is set. If both output layouts contain a complete pair, the newest coherent pair is used. This keeps analysis correct after changing between single-target and multi-target monitoring or after adding a target through the Web Dashboard.

If the lists have not been downloaded yet, the command names the directory it searched and explains that the monitor has to run once first. Older saved files may contain partial lists from a private account, an interrupted download or a configured fetch limit. In that case the analysis covers only the saved handles and prints a note. Current monitoring keeps the last complete baseline instead of replacing it with a partial fetch. When the newest output layout is incomplete or malformed, an older complete pair is used when available and the result includes a warning. Otherwise malformed data or invalid usernames make that target unavailable instead of crashing the command.

The command and Web Dashboard show complete counts for all three categories. Mutual accounts are count-only. The not-following-back and fan categories list at most the first 500 usernames alphabetically. This bounds terminal output, API responses and browser rendering for large accounts.

The same analysis is available in the **Web Dashboard**. Use the **Follow analysis** chart button next to a configured target. Privacy substitutions apply to the target and relationship usernames shown in the modal.

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

A maximum intentionally produces a partial list. Partial lists are not compared with or saved over the last complete baseline. Reported count changes remain available without claiming which usernames changed.

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
- `IP_ADDRESS_URL` selects one trusted IP lookup URL or an ordered non-empty list of fallback URLs

`PROXY_URL` may contain a username and password. The tool masks it in output. Store it through an [environment variable or `.env` file](configuration.md#storing-secrets).

```ini
PROXY_ENABLED = True
PROXY_URL = "http://user:pass@host:port"
PROXY_CERT_PATH = ""
PROXY_WEBHOOKS = False
IP_ADDRESS_URL = [
    "https://checkip.amazonaws.com",
    "https://api.ipify.org?format=json",
    "https://api.my-ip.io/v2/ip.json",
]
```

The proxy IP check tries each endpoint in order without pausing between different providers. It waits for the long retry delay only after the complete list fails. Only valid IPv4 or IPv6 responses are displayed. See [Proxy IP Lookup Endpoints](configuration.md#proxy-ip-lookup-endpoints) for validation and privacy details.

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

The target is checked against that list at startup and when saved from the Web Dashboard. An unrecognized value stops the tool with a message naming supported targets, rather than letting every Instagram request fail later as a connection error.

<a id="privacy-substitutions"></a>
## Privacy Substitutions

Privacy substitutions replace selected text in console output, logs, CSV files, notifications and dashboards. Use them to display a label instead of a real Instagram username or to mask other text.

Provide a list of `(search, replace)` tuples via the `PRIVACY_SUBSTITUTIONS` config option:

```ini
PRIVACY_SUBSTITUTIONS = [ ("a.username", "Sarah"), ("some.other.user", "XXX") ]
```

The replacement happens before output is displayed, logged or sent. Internal keys and file paths do not change, so the tool still uses the original usernames to find data. Invalid entries are ignored with a warning.

<a id="terminal-safe-output"></a>
## Terminal-Safe Output

Biographies, captions, story text, comments and usernames come from Instagram and can contain terminal control sequences. Printed unchanged, those could clear your screen, retitle the window or overwrite a line you already read. The tool removes control characters from everything it prints and logs, keeping only tabs, newlines and its own colour codes. Nothing is lost from readable text.

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

When **Jitter Mode** (or debug/verbose output) is enabled, the Instagram HTTP backoff wrapper prints a `WRAP-REQ` line for each delayed request. Set `SKIP_WRAP_MESSAGES` to `True` to suppress those lines while keeping the rest of the jitter behavior:

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

A biography, caption or other Instagram text that starts with `=`, `+`, `-`, `@`, a tab or a carriage return is written with a leading apostrophe. Spreadsheet software treats those characters as the start of a formula, so the apostrophe keeps the exported text as text. Numbers such as follower counts are unaffected.

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

Images and videos are streamed to a temporary file beside the destination with a 100 MiB limit. The monitor accepts only a complete HTTP 200 response with a recognized image or video signature then replaces the destination atomically. A truncated response, an HTML error page or another invalid response leaves an existing saved file untouched.

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

A local Windows process supports only a limited signal set. Linux containers can receive the Docker signals above when a Docker-compatible runtime runs them on Windows.

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
