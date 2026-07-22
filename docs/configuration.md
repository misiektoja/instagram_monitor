# Configuration

Examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace that command with the matching [command prefix](usage.md#command-format). Keep all options after the prefix. A container can see host files only through its mounts, so paths to files in the current directory must start with `/data`.

<a id="configuration-file"></a>
## Configuration File

You can pass most settings as command-line options or save them in a configuration file for later runs.

The easiest method is `instagram_monitor --setup`. The setup wizard checks the settings before saving them. If you allow it to replace an existing configuration, it first creates a backup whose name includes the current date and time.

If you want to edit the file manually, generate a default config template and save it to a file named `instagram_monitor.conf`:

```sh
# On macOS, Linux or Windows Command Prompt (cmd.exe)
instagram_monitor --generate-config > instagram_monitor.conf

# On Windows PowerShell (recommended to avoid encoding issues)
instagram_monitor --generate-config instagram_monitor.conf
```

> **IMPORTANT**: In Windows PowerShell, do not use `>` for this command. Some PowerShell versions write redirected text as UTF-16, which makes Instagram Monitor report a "null bytes" error. Pass the filename to `--generate-config` so Instagram Monitor writes a UTF-8 file itself.

When you include the filename, Instagram Monitor writes the template directly as UTF-8. This avoids PowerShell changing the file encoding during redirection.

Open `instagram_monitor.conf` in a text editor and change the settings you need. The file contains a short explanation above each setting.

Without `--config-file`, Instagram Monitor uses the first configuration it finds in this order:

1. `instagram_monitor.conf` in the current directory
2. `~/.instagram_monitor.conf` in the home directory
3. `instagram_monitor.conf` next to the script

An explicit `--config-file PATH` is always used and the command stops with an error if that file does not exist.

If the same setting appears in more than one place, the item later in this list wins:

1. Built-in defaults
2. The discovered or explicitly selected configuration file
3. Supported private values from `.env` or process environment variables
4. Command-line options

The `.env` and process environment layer applies only to `SESSION_PASSWORD`, `SMTP_PASSWORD`, `WEBHOOK_URL`, `PROXY_URL` and `NTFY_ACCESS_TOKEN`. For these keys, a value in the selected `.env` file replaces a value that was already exported in the shell. Use `--config-file PATH` and `--env-file PATH` if you do not want automatic file discovery.

Save one or more monitoring targets through setup or set `TARGET_USERNAMES` yourself:

```ini
TARGET_USERNAMES = ["target_user_1", "target_user_2"]
```

Usernames written directly after the command and usernames passed through `--targets` are combined. If the command contains any targets, that combined list replaces `TARGET_USERNAMES` for that run. To use only the saved targets, run:

```sh
instagram_monitor --config-file instagram_monitor.conf
```

You can also change most settings and generate a config file through the [Web Dashboard](view-modes.md#web-dashboard-mode).

<a id="no-login-mode-without-session-login"></a>
## No-Login Mode (No Session Login)

This mode does not sign in to Instagram. It can monitor new or deleted regular posts, bio changes and follower or following counts for public accounts. It cannot monitor reels or stories. It also cannot tell you which specific accounts followed or unfollowed the target.

No-login mode needs no Instagram credentials and makes fewer requests than logged-in mode. Instagram can still limit or block public requests, so this mode does not guarantee uninterrupted access.

<a id="logged-in-mode-with-session-login"></a>
## Logged-In Mode (With Session Login)

This mode signs in with an Instagram account. It can access reels, stories and the usernames added to or removed from follower and following lists.

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

You can also import through the [Web Dashboard](view-modes.md#web-dashboard-mode). Open the **Session** page, select the browser and click **Import**. If the browser has several profiles, select the profile that contains the Instagram login you want to use.

The tool reads the cookies from the selected browser profile and saves a session in Instaloader's format. It does not change the browser profile.

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

- **Pick by name** with `--browser-profile`. Use the Firefox profile name (e.g. `default-release`) or the Chromium profile directory (e.g. `Default`, `Profile 1`):

  ```sh
  instagram_monitor --import-browser-session --browser chrome --browser-profile "Profile 1"
  instagram_monitor --import-browser-session --browser firefox --browser-profile "default-release"
  ```

- **Let it prompt you.** If you do not pass `--browser-profile` and several profiles exist, the tool lists them so you can choose.
- **On the [Web Dashboard](view-modes.md#web-dashboard-mode)**, pick the browser, click **Import** and select a profile if prompted.
- **Advanced:** point `--cookie-file` at a specific cookie database (Firefox `cookies.sqlite` or a Chromium `Cookies` file). This overrides `--browser-profile`.

For Chromium-based browsers, the tool finds the cookie database inside the selected profile. It supports both `<profile>/Cookies` and `<profile>/Network/Cookies` layouts.

Chromium-based import does not work inside Docker because the container cannot use the host password service needed to decrypt the cookies. Use Firefox as shown under [Container Operation](usage.md#container-operation). You can also perform a Chromium import with a local PyPI or manual installation.

Using the account normally in the same browser may help Instagram recognize the session. Avoid using the browser account while Instagram Monitor is making requests because simultaneous activity may look unusual.

<a id="user-agent"></a>
#### User Agent

A user agent is text that identifies the browser and operating system making a request. Use the user agent from the same browser profile that supplied the session:

- in Firefox, type `about:support` in the address bar and copy the `User Agent` value under the `Application Basics` section
- in Chrome, Brave or Chromium, open `chrome://version` and copy the `User Agent` value
- set this value through `USER_AGENT`, the `--user-agent` option or the [Web Dashboard](view-modes.md#web-dashboard-mode)

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

Email notifications need the SMTP server details for the email account that sends the messages. Add them to `instagram_monitor.conf` or use the setup wizard.

Send one test message to verify the settings:

```sh
instagram_monitor --send-test-email
```

<a id="storing-secrets"></a>
## Storing Secrets

A `.env` file is a plain text file that holds private values separately from regular configuration. Store `SESSION_PASSWORD`, `SMTP_PASSWORD`, `WEBHOOK_URL`, `NTFY_ACCESS_TOKEN` and `PROXY_URL` there. Do not commit this file or share it.

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
