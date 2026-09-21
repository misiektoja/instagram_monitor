# Configuration

Examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace that command with the matching [command prefix](usage.md#command-format-by-installation-method). Keep all options after the prefix. A container can see host files only through its mounts, so paths to files in the current directory must start with `/data`.

<a id="configuration-file"></a>
## Configuration File

You can pass most settings as command-line options or save them in a configuration file for later runs.

The easiest way to create this file is `instagram_monitor --setup`.

To edit every available setting yourself, generate a default configuration file:

```sh
# On macOS, Linux or Windows Command Prompt (cmd.exe)
instagram_monitor --generate-config > instagram_monitor.conf

# On Windows PowerShell (recommended to avoid encoding issues)
instagram_monitor --generate-config instagram_monitor.conf
```

> **Windows PowerShell:** Pass the filename directly to `--generate-config`. PowerShell redirection can write UTF-16, which the tool rejects with a "null bytes" error. With a filename, the tool writes the file as UTF-8.

When the named file already exists, `--generate-config` asks before replacing it and keeps a timestamped `.bak` backup next to it. Add `--force` to replace it without the question.

The file contains a short explanation above each setting.

By default the tool looks for a configuration file named `instagram_monitor.conf` in the current directory, the home directory (`~`) and the script directory. Use `--config-file` to name another location or `--config-file none` to disable automatic config discovery for one run.

A configuration file is read as data, not executed. The tool accepts only `SETTING = value` lines where the name is one of the documented settings and the value is a plain literal such as a string, number, `True`, `False`, `None`, a list or a dictionary. Comments and blank lines are fine.

Imports, function calls, expressions and unknown settings are rejected with the setting and line number to correct.

If the same setting appears in more than one place, the item later in this list wins:

1. Built-in defaults
2. The discovered or explicitly selected configuration file
3. Values from the selected `.env` file
4. Secret environment variables
5. Command-line options

By default the tool looks for a configuration file named `instagram_monitor.conf` in the current directory, the home directory (`~`) and the script directory. Use `--config-file` to name another location or `--config-file none` to disable automatic config discovery for one run.

<a id="monitored-target"></a>
## Monitored Target

The Instagram usernames are positional arguments. At least one is required to start monitoring:

```sh
instagram_monitor <target_insta_user>
```

Several usernames can follow the command. `--targets` takes the same list in one comma-separated value and both forms are combined.

To stop repeating them, save the list in the configuration file:

```ini
TARGET_USERNAMES = ["target_user_1", "target_user_2"]
```

Each target may be a username or a complete profile URL such as `https://www.instagram.com/target_user_1/`.

Then `instagram_monitor` alone starts monitoring those accounts. A username on the command line still wins and replaces the whole saved list, so you can watch someone else for one run without editing the file:

```sh
instagram_monitor other_user
```

You can also change most settings and generate a config file through the [Web Dashboard](view-modes.md#web-dashboard). Targets you add or remove in the browser are saved into `TARGET_USERNAMES` when you press **Generate Config**, so the next start monitors the same list.

<a id="no-login-mode-no-session-login"></a>
## No-Login Mode (No Session Login)

This mode does not sign in to Instagram. It can monitor new or deleted regular posts, bio changes and follower or following counts for public accounts. Follower and following notifications report count changes without usernames because complete list comparison is unavailable. It cannot monitor reels or stories. It also cannot tell you which specific accounts followed or unfollowed the target.

No-login mode needs no Instagram credentials and makes fewer requests than logged-in mode. Instagram can still limit or block public requests, so this mode does not guarantee uninterrupted access.

<a id="logged-in-mode-with-session-login"></a>
## Logged-In Mode (With Session Login)

This mode signs in with an Instagram account. It can access reels, stories and the usernames added to or removed from follower and following lists. Reels are off by default because the endpoint Instagram used to report them with stopped answering reliably. See [Profile Lookups Report a Retired Endpoint](troubleshooting.md#profile-lookups-report-a-retired-endpoint).

Logged-in monitoring can cause Instagram to show a security challenge, limit the session or suspend the account. There is no known request rate that guarantees safety. Use a separate Instagram account if losing access to your main account would be unacceptable, then follow the [risk reduction guide](anti-detection.md).

<a id="option-1-basic-session-login-not-recommended"></a>
### Option 1: Basic Session Login (not recommended)

You can provide the session account username and password in `instagram_monitor.conf`, through an [environment variable](#storing-secrets) or with the `-u` and `-p` options.

However, this triggers a full login every time the tool runs, increasing the chance of detection and account lockouts.

If `SESSION_PASSWORD` is in a `.env` file, a running process on macOS, Linux or Unix can reload it after a `SIGHUP` signal. See [Storing Secrets](#storing-secrets) and [Signal Controls](usage.md#signal-controls-macoslinuxunix).

<a id="option-2-session-login-via-instaloader-better-but-can-be-detected"></a>
### Option 2: Session Login via Instaloader (better, but can be detected)

This method uses the Instaloader command to sign in once and save the resulting session:

```sh
instaloader -l <your_insta_user>
```

Later runs reuse the saved session instead of sending the password again. Instagram can still detect or limit the monitoring requests.

The local command above stores the session in your user profile. Docker containers have a separate file system, so create the session inside the `instagram_monitor_session` volume that later monitoring runs use:

```sh
docker compose run --rm --entrypoint instaloader instagram_monitor -l <your_insta_user>
```

For a direct image, mount the normal session volume and override the entry point:

```sh
docker run --rm -it -v instagram_monitor_session:/home/instagram/.config/instaloader --entrypoint instaloader misiektoja/instagram-monitor:latest -l <your_insta_user>
```

For device consistency, set `USER_AGENT` to match Instaloader's Chrome user agent (see [User Agent](#user-agent) below).

<a id="option-3-session-login-using-browser-cookies-recommended"></a>
### Option 3: Session Login Using Browser Cookies (recommended)

This method reuses an Instagram login that already works in a supported browser. Firefox has the widest platform support. Chrome, Brave and Chromium are also supported on macOS and Linux but need an optional package.

Log in to your account (`your_insta_user`) in the browser, then run:

```sh
instagram_monitor --import-browser-session --browser firefox
```

`--browser` accepts `firefox` (default), `chrome`, `brave` or `chromium`. The older `--import-firefox-session` flag still works as an alias for `--browser firefox`.

You can also import through the [Web Dashboard](view-modes.md#web-dashboard). Open the **Session** page, select the browser and click **Import**. If the browser has several profiles, select the profile that contains the Instagram login you want to use.

The tool reads the cookies from the selected browser profile and saves a session in Instaloader's format. It does not change the browser profile.

Profile selection works the same way for every browser (see [Selecting a browser profile](#selecting-a-browser-profile) below). To pick a specific Firefox profile by name:

```sh
instagram_monitor --import-browser-session --browser firefox --browser-profile "default-release"
```

On Windows, Firefox profiles from the regular installer and from the Microsoft Store are discovered automatically. Discovery covers `%APPDATA%\Mozilla\Firefox\Profiles` and the Store package's own profile folder under `%LOCALAPPDATA%\Packages\Mozilla.Firefox_*\LocalCache\Roaming\Mozilla\Firefox\Profiles`, and follows `APPDATA` and `LOCALAPPDATA` when a roaming or redirected user profile moves them off the home directory. Store profiles are listed as **Microsoft Store**, so the `default-release` profile that both installs create can be told apart. Importing inside a container covers the regular installer only, because the command mounts a single fixed path.

On Linux, Firefox profiles installed natively, through Snap or through Flatpak are discovered automatically. You can adjust the default Firefox cookie directory permanently via the `FIREFOX_*_COOKIE` configuration options, which are searched before the paths found automatically. The advanced `--cookie-file` option covers any other layout and overrides automatic discovery.

<a id="which-browsers-are-supported"></a>
#### Which browsers are supported

The `--browser` flag (and the dashboard dropdown) accepts these values:

| `--browser` | Application it reads | Platforms |
| --- | --- | --- |
| `firefox` (default) | Mozilla Firefox | macOS, Linux, Windows |
| `chrome` | Google Chrome | macOS, Linux |
| `brave` | Brave | macOS, Linux |
| `chromium` | The standalone open-source Chromium browser | macOS, Linux |

**About `chromium`:** Chromium is a separate browser application from Google Chrome. It has its own profiles and cookies. Choose `chromium` only if that is the browser you use. Choose `chrome` for Google Chrome.

**Not currently supported:** Microsoft Edge, Opera, Vivaldi, Arc and other Chromium-based browsers. Each application stores its cookies separately. The [`pycookiecheat`](https://github.com/n8henrie/pycookiecheat) library used by Instagram Monitor supports only the browsers in the table. To import a session, log in through one of those supported browsers.

<a id="importing-from-chrome-brave-or-chromium"></a>
#### Importing from Chrome, Brave or Chromium

Chrome, Brave and Chromium encrypt their cookies. Instagram Monitor uses the optional [`pycookiecheat`](https://github.com/n8henrie/pycookiecheat) package to decrypt them on macOS and Linux. For a PyPI installation, install it with the `browser` extra:

```sh
pip install "instagram_monitor[browser]"
```

If you run the downloaded script or installed from `requirements.txt`, install it directly instead:

```sh
pip install "pycookiecheat>=0.8"
```

Then import the session:

```sh
instagram_monitor --import-browser-session --browser chrome
```

On Windows, Chrome 127 and newer prevent external programs from reading these cookies through app-bound encryption. Use Firefox import instead.

<a id="selecting-a-browser-profile"></a>
#### Selecting a browser profile

Every supported browser can have several profiles with separate cookies. Use one of these methods:

- **Pick by name** with `--browser-profile`. Use the Firefox profile name (e.g. `default-release`) or, for Chromium-based browsers, either the profile directory (e.g. `Default`, `Profile 1`) or the display name the picker shows (e.g. `Your Chrome`):

    ```sh
    instagram_monitor --import-browser-session --browser chrome --browser-profile "Profile 1"
    instagram_monitor --import-browser-session --browser firefox --browser-profile "default-release"
    ```

- **Let it prompt you.** If you do not pass `--browser-profile` and several profiles exist, the tool lists them so you can choose. Profiles signed in to Instagram are marked with `*`, so you do not have to guess which one holds the session. When exactly one is signed in it is the default and Enter selects it.
- **On the [Web Dashboard](view-modes.md#web-dashboard)**, pick the browser, click **Import** and select a profile if prompted. Profiles signed in to Instagram are marked with `*` and the only signed-in one is preselected. The dashboard imports only from the profiles it detected, so it cannot be pointed at another file or profile on your computer. Use `--cookie-file PATH` on the command line when you deliberately want a database from somewhere else.
- **Advanced:** point `--cookie-file` at a specific cookie database (Firefox `cookies.sqlite` or a Chromium `Cookies` file). This overrides `--browser-profile`.

For Chromium-based browsers, the tool finds the cookie database inside the selected profile. It supports both `<profile>/Cookies` and `<profile>/Network/Cookies` layouts. On Linux it looks for the distribution install first, then Snap and Flatpak builds of Chromium and Brave.

Chromium-based browsers encrypt their cookies with a key held in your keychain or keyring. If you deny that prompt or the keyring is locked, the import says so instead of blaming a missing login.

Chromium-based import does not work inside Docker. Use Firefox as shown under [Import Firefox into the Container Session](usage.md#import-firefox-into-the-container-session). To import from Chromium, run a local PyPI or manual installation instead.

How you use the account in that browser afterwards matters too. See [Use the Account for Normal Activities](anti-detection.md#use-the-account-for-normal-activities).

<a id="user-agent"></a>
#### User Agent

A user agent is text that identifies the browser and operating system making a request. Use the user agent from the same browser profile that supplied the session:

- in Firefox, type `about:support` in the address bar and copy the `User Agent` value under the `Application Basics` section
- in Chrome, Brave or Chromium, open `chrome://version` and copy the `User Agent` value
- set this value through `USER_AGENT`, the `--user-agent` option or the [Web Dashboard](view-modes.md#web-dashboard)

If you created the session with Instaloader instead (Option 2 above), match Instaloader's user agent rather than a browser's. Instaloader logs in with a Chrome user agent, so set `USER_AGENT` to a matching Chrome string to keep the same device consistency. You can print the exact value Instaloader uses with:

```sh
python3 -c "from instaloader.instaloadercontext import default_user_agent; print(default_user_agent())"
```

With the default `auto` setting under [HTTP Transport Backend](usage.md#http-transport-backend), `curl_cffi` selects a matching browser network profile. For example, a Chrome user agent selects a Chrome profile.

<a id="time-zone"></a>
## Time Zone

Instagram Monitor detects the local time zone automatically. Set `LOCAL_TIMEZONE` in `instagram_monitor.conf` if the detected value is wrong or if monitoring should use another time zone:

```ini
LOCAL_TIMEZONE='Europe/Warsaw'
```

You can get the list of all time zones supported by pytz like this:

```sh
python3 -c "import pytz; print('\n'.join(pytz.all_timezones))"
```

Set `TIME_FORMAT_12H = True` to display times in 12-hour format instead of the default 24-hour format.

<a id="smtp-settings"></a>
## SMTP Settings

Email notifications need SMTP server details for the sending account. Add them to `instagram_monitor.conf` or use the setup wizard. Setup checks the login without sending an email. To replace only the password, run `instagram_monitor --set-smtp-password`. Password entry is hidden and preserves spaces.

Every alert is sent as both HTML and plain text in one message. Mail clients that render HTML show the account name, the counts and the values that changed in bold. Post, story and profile links are clickable. Clients that do not render HTML fall back to the plain text, which is unchanged.

Send one test message to verify the settings:

```sh
instagram_monitor --send-test-email
```

<a id="webhook-settings"></a>
## Webhook Settings

Instagram Monitor can send event notifications to **Discord** or **ntfy**. A webhook is a URL that accepts a message from another application. Webhook settings do not affect email settings.

`WEBHOOK_PROVIDER` tells Instagram Monitor which message format the URL expects. The default is `"discord"`. Standard Discord and public `ntfy.sh` URLs automatically select the matching format if this configured value is stale. Self-hosted ntfy and compatible endpoints still use the configured provider. An explicit `--webhook-provider` override always wins.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_discord.png" alt="instagram_monitor_discord_screenshot" width="80%"/>
</p>

<a id="ntfy"></a>
### ntfy

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

<a id="discord"></a>
### Discord

To create a Discord Webhook URL:

1.  **Create a Server**: Click the **+** (Plus) icon on the left sidebar ("Add a Server") -> **Create My Own** -> **For me and my friends**.
2.  **Create/Edit a Channel**: In your new server, find the **#general** channel (or create a new one). Click the **Edit Channel** icon (⚙️ gear) next to the channel name.
3.  **Create Webhook**: Go to **Integrations** in the left menu -> **Webhooks** -> **New Webhook**.
4.  **Copy URL**: Click on the new webhook (often named "Spidey Bot", you can rename it) and click **Copy Webhook URL**.

Keep `WEBHOOK_PROVIDER = "discord"` in `instagram_monitor.conf`. Standard Discord webhook URLs are also recognized automatically.

<a id="saving-the-webhook-url"></a>
### Saving the Webhook URL

Choose one method:

- set `WEBHOOK_ENABLED = True`, select `WEBHOOK_PROVIDER` and put `WEBHOOK_URL` in `.env`
- use an [environment variable](#storing-secrets) for `WEBHOOK_URL`
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

Webhook and avatar URLs must be complete HTTPS links with a hostname and no embedded credentials. Root endpoints work with or without a trailing slash. Known Discord and `ntfy.sh` destinations correct a stale configured provider at runtime. A URL passed through `--webhook-url` may remain visible in shell history or process listings, so prefer `--set-webhook-url` for normal setup. A `WEBHOOK_URL` left unset, or left at its `your_webhook_url` placeholder, switches webhook alerts off at startup instead of failing at the first alert, and `--verbose` reports why.

<a id="advanced-discord-format-customization"></a>
### Advanced Discord-format customization

`WEBHOOK_USERNAME` and `WEBHOOK_AVATAR_URL` customize Discord-format messages. `WEBHOOK_TEMPLATE` supports `title`, `description`, `version`, `image_url`, `fields`, `fields_str`, `color`, `timestamp`, `username` and `avatar_url` placeholders. Use a dictionary or a JSON string encoding an object. Lists, non-JSON strings and unknown placeholders are rejected before delivery. Legacy JSON strings with doubled object braces still work and quotes or braces in alert text remain literal. Every payload sets `allowed_mentions` to `{"parse": []}` so alert text cannot trigger Discord mentions. Retries retain the original destination and credentials when settings are reloaded.

`WEBHOOK_TEMPLATE`, `WEBHOOK_USERNAME` and `WEBHOOK_AVATAR_URL` apply only to Discord and are ignored when `WEBHOOK_PROVIDER` is `"ntfy"`. The ntfy provider needs no template: it sends the alert body as a native ntfy message with the subject as its title. Customize ntfy delivery through `WEBHOOK_HEADERS` (for example `X-Priority` or `X-Tags`).

`WEBHOOK_TRANSFORMS` applies configured string methods before the template and headers are rendered. Invalid templates, avatar URLs, transforms or expanded headers fail before any request is attempted. Dictionary payloads always replace `allowed_mentions` with `{"parse": []}` so notification text cannot trigger `@everyone`, `@here` or user mentions.

Webhook delivery uses an isolated session with a 10-second timeout and at most two attempts. It accepts every HTTP 2xx response, retries HTTP 429 according to a server delay capped at 5 seconds and retries HTTP 5xx once. Other HTTP 4xx responses fail immediately.

<a id="proxy-ip-lookup-endpoints"></a>
### Proxy IP Lookup Endpoints

When proxy routing is enabled, Instagram Monitor checks the proxy exit address through `IP_ADDRESS_URL`. The setting accepts one complete HTTP or HTTPS URL or an ordered non-empty list:

```ini
IP_ADDRESS_URL = [
    "https://checkip.amazonaws.com",
    "https://api.ipify.org?format=json",
    "https://api.my-ip.io/v2/ip.json",
]
```

Each retry cycle tries every configured endpoint in order before the long retry delay. A response is accepted only when a recognized JSON field or plain-text body contains a valid IPv4 or IPv6 address. Empty lists, incomplete URLs and URLs with embedded credentials are rejected with an unavailable status instead of crashing monitoring.

Each public lookup service can observe the proxy exit IP. Set one trusted endpoint or a self-hosted service if you do not want fallback requests sent to multiple providers. These lookup requests do not include Instagram session credentials.


<a id="terminal-colours"></a>
## Terminal Colours

`COLORED_OUTPUT` controls whether live terminal output is coloured. It defaults to `True`. `--no-color` disables colour for one run. Colour also switches itself off when output is redirected or piped, when `TERM` is unset or `dumb` and when the standard [`NO_COLOR`](https://no-color.org/) environment variable is set. Log files are always written with the escape sequences stripped.

Usernames are `bright_cyan underline`, the numeric user ID is `bright_magenta` and links are `blue underline`. A `Yes` or `No` answer is coloured only as the whole value of a labelled row, so an ordinary `no` inside a sentence stays plain. Generated configuration files ship the `COLOR_THEME` block commented out, so these defaults apply and a later change to them reaches you. Overrides you added are written back as a real block when setup rebuilds the file, so they are not lost. A configuration file written by an earlier version sets every colour explicitly and therefore keeps the old ones: delete its `COLOR_THEME` block to follow the current defaults, or edit the values you want to keep. Such a file still loads unchanged.

`COLOR_THEME` overrides individual colours. It is merged over the built-in theme, so name only the parts you want to change:

```ini
COLOR_THEME = { "header": "bright_cyan" }
```

The `--help` screen is coloured too. Group headings, option names, the values those options take, the example commands and the comments above them each get their own colour, so the screen can be scanned instead of read.

On Windows, install the optional `colorama` package for colour in the classic Command Prompt. Windows Terminal needs nothing extra.

To colour saved log files when you view them later, see [Coloring Log Output with GRC](usage.md#coloring-log-output-with-grc).

<a id="storing-secrets"></a>
## Storing Secrets

A `.env` file is a plain text file that holds private values separately from regular configuration. Store `SESSION_PASSWORD`, `SMTP_PASSWORD`, `WEBHOOK_URL`, `NTFY_ACCESS_TOKEN` and `PROXY_URL` there. Do not commit this file or share it.

The recommended way to save a Discord or ntfy destination is:

```sh
instagram_monitor --set-webhook-url
```

Paste the complete HTTPS URL at the hidden prompt. Instagram Monitor validates it then updates only `WEBHOOK_URL` in `.env` without displaying the value. Standard Discord and public `ntfy.sh` URLs select the matching request format automatically. While `WEBHOOK_PROVIDER` is left at its default, that detection is silent and `--verbose` reports it. A warning appears only when your configuration file sets a provider the URL disagrees with. Configure `WEBHOOK_PROVIDER` in `instagram_monitor.conf` for a self-hosted or compatible endpoint. Use `--env-file PATH` with this command to select another dotenv destination.

Discord alerts carry the same emphasis as the HTML email, since Discord renders markdown in an embed. Bold values stay bold and links stay clickable. Only Discord gets that wording: ntfy receives the plain body, because it would show the markers literally.

The mail server password has its own command:

```sh
instagram_monitor --set-smtp-password
```

Enter the password at the hidden prompt after configuring `SMTP_HOST`, `SMTP_USER`, `SENDER_EMAIL` and `RECEIVER_EMAIL`. The command checks mail sign-in before saving `SMTP_PASSWORD` to `.env`. No email is sent. An exported `SMTP_PASSWORD` overrides the saved value at startup.

You can use operating system environment variables instead of a file. Set them with `export` on Linux, Unix, macOS or WSL:

```sh
export SESSION_PASSWORD="your_instagram_session_password"
export SMTP_PASSWORD="your_smtp_password"
export WEBHOOK_URL="https://discord.com/api/webhooks/..."
export NTFY_ACCESS_TOKEN="tk_your_ntfy_access_token"
```

On **Windows Command Prompt** use `set` instead of `export` and on **Windows PowerShell** use `$env`.

To keep the values between terminal sessions, store them in `.env`. The repository includes an [.env.example](https://github.com/misiektoja/instagram_monitor/blob/main/.env.example) template:

```sh
test -e .env || cp .env.example .env
```

This leaves an existing `.env` untouched, including any secrets saved by the setup wizard.

```ini
SESSION_PASSWORD="your_instagram_session_password"
SMTP_PASSWORD="your_smtp_password"
WEBHOOK_URL="https://discord.com/api/webhooks/..."
NTFY_ACCESS_TOKEN="tk_your_ntfy_access_token"
```

By default, the tool looks for `.env` in the current directory. If it is not there, the search continues in each parent directory.

Select another file with `DOTENV_FILE` or `--env-file`:

```sh
instagram_monitor <target_insta_user> --env-file /path/.env-instagram_monitor
```

You can also disable `.env` auto-search with `DOTENV_FILE = "none"` or `--env-file none`:

```sh
instagram_monitor <target_insta_user> --env-file none
```

As a fallback, you can store secrets in the configuration file. Avoid putting secrets directly in the source code.

A forgotten `export` can shadow the dotenv file invisibly, so `--debug` names every secret and the source it resolved from, never the value:

```text
[DEBUG 12:00:00] Secret resolution: name=SESSION_PASSWORD, source=environment, value=set
[DEBUG 12:00:00] Secret resolution: name=SMTP_PASSWORD, source=dotenv file, value=set
```

<a id="tls-verification"></a>
## TLS Verification

Instagram Monitor verifies the TLS certificate of every server it contacts: Instagram, the connectivity check endpoint, the proxy IP lookup, downloaded media, the mail server that delivers email alerts and, when enabled, the webhook service.

Set `VERIFY_SSL` to `False` only on a network that intercepts TLS with its own certificate authority, such as a corporate proxy. With verification off, an intercepted connection cannot be told apart from the real service, and `PROXY_CERT_PATH` is ignored because there is nothing left to check the certificate against.

The startup summary shows `TLS verification` and [`--doctor`](troubleshooting.md#doctor-preflight) reports a warning while it is off.
