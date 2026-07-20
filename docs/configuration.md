# Configuration

<a id="configuration-file"></a>
## Configuration File

Most settings can be configured via command-line arguments.

If you want to have it stored persistently, generate a default config template and save it to a file named `instagram_monitor.conf`:

```sh
# On macOS, Linux or Windows Command Prompt (cmd.exe)
instagram_monitor --generate-config > instagram_monitor.conf

# On Windows PowerShell (recommended to avoid encoding issues)
instagram_monitor --generate-config instagram_monitor.conf
```

> **IMPORTANT**: On **Windows PowerShell**, using redirection (`>`) can cause the file to be encoded in UTF-16, which will lead to "null bytes" errors when running the tool. It is highly recommended to provide the filename directly as an argument to `--generate-config` to ensure UTF-8 encoding.

Edit the `instagram_monitor.conf` file and change any desired configuration options (detailed comments are provided for each).

**Note**: Since **v3.0**, you can also change nearly all configuration settings and generate config file via the **[Web Dashboard](view-modes.md#web-dashboard-mode)**.

<a id="no-login-mode-without-session-login"></a>
## No-Login Mode (No Session Login)

In this mode, the tool operates without logging in to an Instagram account.

You can still monitor basic user activity such as new or deleted posts (excluding reels and stories due to Instagram API limitations), bio changes and changes in follower/following counts. However, you won't see which specific followers/followings were added or removed.

This mode requires no setup, is easy to use and is resistant to Instagram's anti-bot mechanisms and CAPTCHA challenges.

<a id="logged-in-mode-with-session-login"></a>
## Logged-In Mode (With Session Login)

In this mode, the tool uses an Instagram session login to access additional data. This includes detailed insights into new posts, reels and stories, also about added or removed followers/followings.

**Important**: It is highly recommended to use a dedicated Instagram account when using this tool in session login mode. While the risk of account suspension is generally low (in practice, accounts often stay active long-term), Instagram may still flag it as an automated tool. This can lead to challenges presented by Instagram that must be dismissed manually. To minimize any chance of detection, make sure to follow the best practices outlined [here](anti-detection.md).

<a id="option-1-basic-session-login-not-recommended"></a>
### Option 1: Basic Session Login (not recommended)

You can provide your Instagram username (`your_insta_user`) and password directly in the `instagram_monitor.conf` configuration file, [environment variable](#storing-secrets) or via the `-u` and `-p` flags.

However, this triggers a full login every time the tool runs, increasing the chance of detection and account lockouts.

If you store the `SESSION_PASSWORD` in a dotenv file you can update its value and send a `SIGHUP` signal to the process to reload the file with the new password without restarting the tool. More info in [Storing Secrets](#storing-secrets) and [Signal Controls (macOS/Linux/Unix)](usage.md#signal-controls-macoslinuxunix).

<a id="option-2-session-login-via-instaloader-better-but-can-be-detected"></a>
### Option 2: Session Login via Instaloader (better, but can be detected)

A better approach is to use `Instaloader` to perform a one-time login and save the session:

```sh
instaloader -l <your_insta_user>
```

This saves the session locally. However, frequent follower/following/stories changes can still lead to detection, as Instagram may flag this as automated behavior.

For device consistency, set `USER_AGENT` to match Instaloader's Chrome user agent (see [User Agent](#user-agent) below).

<a id="option-3-session-login-using-browser-cookies-recommended"></a>
### Option 3: Session Login Using Browser Cookies (recommended)

The most reliable method is to reuse an existing Instagram session from your web browser, along with manually specifying the user agent. Firefox is recommended for best compatibility and lowest detection risk, but since **v3.5** Chrome, Brave and Chromium are also supported.

Log in to your account (`your_insta_user`) in the browser, then run:

```sh
instagram_monitor --import-browser-session --browser firefox
```

`--browser` accepts `firefox` (default), `chrome`, `brave` or `chromium`. The older `--import-firefox-session` flag still works as an alias for `--browser firefox`.

Since **v3.0**, you can also perform this import easily via the **[Web Dashboard](view-modes.md#web-dashboard-mode)** (no command line required). Simply open the dashboard, go to the **Session** page, pick the browser from the dropdown and click **Import**. If the browser has a single profile it is imported directly; if several exist you can choose which one.

The tool detects the browser's available profiles. If only one exists it is imported directly; if several are found it lets you select one, then imports the session and saves it via Instaloader.

Profile selection works the same way for every browser (see [Selecting a browser profile](#selecting-a-browser-profile) below). To pick a specific Firefox profile by name:

```sh
instagram_monitor --import-browser-session --browser firefox --browser-profile "default-release"
```

You can adjust the default Firefox cookie directory permanently via `FIREFOX_*_COOKIE` configuration options.

<a id="which-browsers-are-supported"></a>
#### Which browsers are supported

The `--browser` flag (and the dashboard dropdown) accepts these values:

| `--browser` | Application it reads | Platforms |
| --- | --- | --- |
| `firefox` (default) | Mozilla Firefox | macOS, Linux, Windows |
| `chrome` | Google Chrome | macOS, Linux |
| `brave` | Brave | macOS, Linux |
| `chromium` | The standalone open-source Chromium browser | macOS, Linux |

**About the `chromium` option:** Chromium is the unbranded open-source browser that Google Chrome is built on. It is a **separate application** from Chrome, with its own profile and cookie store, and is a common default browser on many Linux distributions. Pick `chromium` only if you actually run that browser; if you use Google Chrome, pick `chrome`.

**Not currently supported:** Microsoft Edge, Opera, Vivaldi, Arc and other Chromium-based browsers. They share the Chromium engine but each keeps its own separate cookie store, and the underlying [`pycookiecheat`](https://github.com/n8henrie/pycookiecheat) library only handles the browsers listed above. If you use one of these, log in with Firefox (or Chrome/Brave/Chromium) for the import instead.

<a id="importing-from-chrome-brave-or-chromium"></a>
#### Importing from Chrome, Brave or Chromium

These browsers encrypt their cookies, so importing from them requires the optional [`pycookiecheat`](https://github.com/n8henrie/pycookiecheat) package and works only on **macOS and Linux**. If you installed from PyPI, pull it in with the `browser` extra:

```sh
pip install "instagram_monitor[browser]"
```

If you run the downloaded script or installed from `requirements.txt`, install it directly instead:

```sh
pip3 install pycookiecheat
```

Then import the session:

```sh
instagram_monitor --import-browser-session --browser chrome
```

On **Windows** this is not possible: Chrome's app-bound encryption (Chrome 127+) blocks any external program from reading its cookies. The tool detects Windows and recommends using Firefox instead.

<a id="selecting-a-browser-profile"></a>
#### Selecting a browser profile

Every supported browser can have multiple profiles, each with its own cookies (Firefox: `default-release`, `Finance`, ...; Chromium-based: `Default`, `Profile 1`, ...). The same options work for all of them:

- **Pick by name** with `--browser-profile`. Use the Firefox profile name (e.g. `default-release`) or the Chromium profile directory (e.g. `Default`, `Profile 1`):

  ```sh
  instagram_monitor --import-browser-session --browser chrome --browser-profile "Profile 1"
  instagram_monitor --import-browser-session --browser firefox --browser-profile "default-release"
  ```

- **Let it prompt you.** If you do not pass `--browser-profile` and several profiles exist, the tool lists them so you can choose.
- **On the [Web Dashboard](view-modes.md#web-dashboard-mode)**, pick the browser, click **Import** and select a profile if prompted.
- **Advanced:** point `--cookie-file` at a specific cookie database (Firefox `cookies.sqlite` or a Chromium `Cookies` file). This overrides `--browser-profile`.

For Chromium-based browsers the tool resolves the cookie database itself, so it works with both the legacy `<profile>/Cookies` and the newer `<profile>/Network/Cookies` layouts.

Inside **Docker** Chromium-based import is also unavailable, because the container cannot reach the host's keyring used to decrypt the cookies. Use Firefox there (see the [Docker Usage examples](usage.md#docker-usage-recommended)), or run the Chromium import directly on the host.

The session login method has the added benefit of blending tool activity with regular user behavior. Interacting with Instagram via the browser every few days (scrolling, liking posts etc.) helps maintain session trust. However, avoid overlapping browser activity with tool activity, as simultaneous actions can trigger suspicious behavior flags.

<a id="user-agent"></a>
#### User Agent

It is also recommended to use the exact user agent string from the web browser you imported the session from:
- in Firefox, type `about:support` in the address bar and copy the `User Agent` value under the `Application Basics` section
- in Chrome, Brave or Chromium, open `chrome://version` and copy the `User Agent` value
- set this value via the `USER_AGENT` configuration option or by using the `--user-agent` flag (since **v3.0**, you can also do it easily via the **[Web Dashboard](view-modes.md#web-dashboard-mode)**)

If you created the session with Instaloader instead (Option 2 above), match Instaloader's user agent rather than a browser's. Instaloader logs in with a Chrome user agent, so set `USER_AGENT` to a matching Chrome string to keep the same device consistency. You can print the exact value Instaloader uses with:

```sh
python3 -c "from instaloader.instaloadercontext import default_user_agent; print(default_user_agent())"
```

With the default `auto` impersonation (see [HTTP Transport Backend](usage.md#http-transport-backend)) the curl_cffi TLS fingerprint follows whichever user agent you set, so a Chrome user agent here yields a Chrome TLS fingerprint.

<a id="time-zone"></a>
## Time Zone

By default, time zone is auto-detected using `tzlocal`. You can set it manually in `instagram_monitor.conf`:

```ini
LOCAL_TIMEZONE='Europe/Warsaw'
```

You can get the list of all time zones supported by pytz like this:

```sh
python3 -c "import pytz; print('\n'.join(pytz.all_timezones))"
```

Since **v3.0** you can also change from the default 24-hour time format to a 12-hour format via the `TIME_FORMAT_12H` config option.

<a id="smtp-settings"></a>
## SMTP Settings

If you want to use email notifications functionality, configure SMTP settings in the `instagram_monitor.conf` file.

Verify your SMTP settings by using `--send-test-email` flag (the tool will try to send a test email notification):

```sh
instagram_monitor --send-test-email
```

<a id="storing-secrets"></a>
## Storing Secrets

It is recommended to store secrets like `SESSION_PASSWORD`, `SMTP_PASSWORD`, `WEBHOOK_URL`, `NTFY_ACCESS_TOKEN` or `PROXY_URL` as either an environment variable or in a dotenv file.

Set the needed environment variables using `export` on **Linux/Unix/macOS/WSL** systems:

```sh
export SESSION_PASSWORD="your_instagram_session_password"
export SMTP_PASSWORD="your_smtp_password"
export WEBHOOK_URL="https://discord.com/api/webhooks/..."
export NTFY_ACCESS_TOKEN="tk_your_ntfy_access_token"
```

On **Windows Command Prompt** use `set` instead of `export` and on **Windows PowerShell** use `$env`.

Alternatively store them persistently in a dotenv file (recommended). The repo ships a [.env.example](https://github.com/misiektoja/instagram_monitor/blob/main/.env.example) you can copy as a starting point:

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

By default the tool will auto-search for dotenv file named `.env` in current directory and then upward from it.

You can specify a custom file with `DOTENV_FILE` or `--env-file` flag:

```sh
instagram_monitor <target_insta_user> --env-file /path/.env-instagram_monitor
```

 You can also disable `.env` auto-search with `DOTENV_FILE = "none"` or `--env-file none`:

```sh
instagram_monitor <target_insta_user> --env-file none
```

As a fallback, you can also store secrets in the configuration file or source code.
