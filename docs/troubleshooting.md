# Troubleshooting

Examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace that command with the matching [command prefix](usage.md#command-format-by-installation-method). The setup wizard and `--help` also print commands for the detected installation.

<a id="doctor-preflight"></a>
## Doctor Preflight

Before a long monitoring run, check the current configuration:

```sh
instagram_monitor --doctor
```

Doctor writes no files. Before the checks start it states how many Instagram requests it will make: one for connectivity, one for the saved session and one for each monitored profile. Results use `[PASS]`, `[WARN]`, `[FAIL]` and `[SKIP]`. Checks cover **Environment**, **Configuration**, **Session**, **Connectivity**, **Targets** and **Notifications**. Secret values are not displayed. Follow the reported fixes then use **Next steps** to start monitoring.

Missing optional packages are warnings you can ignore when you do not use those features. Login checks apply only to Logged-In Mode. An empty target list is valid for the Web Dashboard. Other modes need at least one target.

A configuration file Instagram Monitor cannot accept is reported by Doctor as a `FAIL` naming the line and the reason, instead of stopping the command before the checks run. This means you can point Doctor at a configuration you are still fixing. A proxy setting that would stop every request is handled the same way, so Doctor reports it and carries on with the proxy switched off while a monitoring run still stops. See [Routing Traffic Through a Proxy](usage.md#routing-traffic-through-a-proxy) for the commands that behave this way. Settings that a later release removed are reported as a `WARN` and ignored, so an older configuration file still runs.

Each failure and warning includes a `To fix:` action and a `Guide:` link to the relevant documentation page where one applies. The command returns a nonzero exit status if a check or approved delivery test fails, so scripts can detect the failure. Doctor accepts normal login, target and file options. Use them to check the saved setup or one exact combination:

```sh
instagram_monitor --doctor
instagram_monitor -u <your_insta_user> <target_insta_user> --doctor
```

For Docker Compose use:

```sh
docker compose run --rm instagram_monitor --doctor
```

Doctor exits after the report and does not start monitoring or the Web Dashboard. The Compose command therefore does not need `--service-ports`. The setup wizard also offers to run Doctor after saving.

For more detail, add `--debug` to Doctor or a normal run. Debug output includes HTTP details and internal decisions. It may also contain private data. Remove cookies, passwords, tokens and webhook URLs before sharing it.

<a id="common-problems"></a>
## Common Problems

Every failure is reported in the same three-part shape: what went wrong, a `To fix:` action and a `Guide:` link to the page that covers it. The fix command matches how you installed the tool and carries the `--config-file` or `--env-file` you started with, so it can be pasted as it is. `--debug` appends a `Technical detail:` line for bug reports. Secrets are redacted from all three.

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| Instagram answers `Try Again Later` | A temporary limit on the account or address | [Instagram Says Try Again Later](#instagram-says-try-again-later) |
| A run without a session answers `Please wait a few minutes` | Anonymous requests from this IP address are rate limited | [Anonymous Runs Are Rate Limited](#anonymous-runs-are-rate-limited) |
| Stories, reels or follower details are missing | The run has no logged in session | [Logged-In Mode](configuration.md#logged-in-mode-with-session-login) |
| Follower and following lists stop working | The session was invalidated or rate limited | [Follower and Following Lists Stop Working](#follower-and-following-lists-stop-working) |
| The dashboard does not open in a container | The port is not published | [Container Dashboard Does Not Open](#container-dashboard-does-not-open) |
| The run stops naming a file and a line number | A configuration line is not a plain `SETTING = value` assignment | [Configuration File](configuration.md#configuration-file) |
| Emails never arrive | Incomplete SMTP settings | [SMTP Settings](configuration.md#smtp-settings) then run `instagram_monitor --send-test-email` |
| Webhook alerts never arrive | Provider mismatch or a stale destination | [Webhook Settings](configuration.md#webhook-settings) then run `instagram_monitor --send-test-webhook` |
| `instagram_monitor` is not found after installation | The shell has not picked up the new command | [Installation and Command Problems](#installation-and-command-problems) |
| Escape sequences such as `[36m` printed as text or no colour at all | The terminal cannot display ANSI colour or colour was switched off | [Terminal Colours Look Wrong](#terminal-colours-look-wrong) |
| `Instagram could not be reached` or `Instagram's address could not be resolved` | A network problem between this machine and Instagram | [Connection Errors During Monitoring](#connection-problems) |
| `This process ran out of file descriptors` | The operating system limit on open files was reached | [Too Many Open Files](#too-many-open-files) |

A continuing outage produces a `* Monitoring degraded` reminder once an hour, even when the [liveness reminder](usage.md#liveness-reminder) is switched off. `* Monitoring recovered` marks recovery. Use `--verbose` to see the first failed check.

<a id="connection-problems"></a>
<a id="connection-errors-during-monitoring"></a>
## Connection Errors During Monitoring

When a check fails, Instagram Monitor prints the error, a `To fix:` action and a `Guide:` link where one applies, then retries automatically at the next interval. You do not need to restart the tool. A command in the fix text matches how you installed the tool and carries the `--config-file` or `--env-file` you started with, so it can be pasted as it is.

`Instagram could not be reached` means a check got no answer from Instagram, and `Instagram's address could not be resolved` means the lookup of the name failed before any request was made. Both are retried on their own and the report names how long until the next check, so a short outage needs no action. A failure that lasts produces the hourly `Monitoring degraded` reminder and `Monitoring recovered` when it clears.

Every other problem reads the same way: all print `* Error:` with what went wrong, a `To fix:` action and a `Guide:` link. A problem the run recovers from prints `* Warning:` with the same two lines under it.

A failure the tool could not place still names an action: it asks you to re-run with `--debug` and links the page explaining the output modes.

Failures show an error and a `To fix:` action. A continuing outage produces a `* Monitoring degraded` reminder once an hour, even when the [liveness reminder](usage.md#liveness-reminder) is switched off. `* Monitoring recovered` marks recovery. Follow any new instructions if the failure changes.

A message naming `Could not resolve host` means the machine could not look up Instagram's address. This is a DNS problem on your side rather than an Instagram block. It is common on devices that start monitoring before the network is fully up, such as a Raspberry Pi booting from cold. Check that name lookups work:

```sh
ping www.instagram.com
```

If that fails too, fix DNS first. When you use a VPN or a proxy, confirm it is running and allowed to resolve names. Monitoring recovers on its own once lookups succeed, so no action is needed inside Instagram Monitor.

Other connection errors point elsewhere. `Max retries exceeded` or a timeout usually means the connection dropped or a proxy is unreachable, see [routing traffic through a proxy](usage.md#routing-traffic-through-a-proxy). `429` or `Too Many Requests` means Instagram is rate-limiting you, see [keep the polling interval reasonable](anti-detection.md#keep-the-polling-interval-reasonable). On a run without a session, `Please wait a few minutes before you try again` means the limit is on your IP address, see [anonymous runs are rate limited](#anonymous-runs-are-rate-limited). A `429` on the very first request of a run is usually a blocked TLS fingerprint rather than a rate limit, see [use a browser transport fingerprint](anti-detection.md#use-a-browser-transport-fingerprint). A message about a redirect, a login or wrong credentials means the saved session expired, see [session import](configuration.md).

For the underlying transport detail behind any of these, add `--debug`. Normal output omits it because it names internal HTTP library errors rather than anything you can act on.

<a id="instagram-says-try-again-later"></a>
## Instagram Says Try Again Later

A `400 Bad Request` naming `feedback_required` means Instagram is limiting what the logged-in account or your IP address may do for a while. Instagram shows this as a "Try Again Later" notice. It is not a checkpoint: Instagram in your browser may keep working, there is nothing to clear there and re-importing the session does not lift it. The circuit breaker stops the account so no further request is made and `--exposure` counts it as `action_block`.

Make no requests from that account and that network for several hours, then run `instagram_monitor --doctor` again. If the same session works from another network, such as a mobile connection, the limit is on your IP address rather than the account. Once it passes, raise `INSTA_CHECK_INTERVAL`, monitor fewer users and follow the [anti-detection guidance](anti-detection.md). A limit that returns soon after monitoring resumes means the account is still being watched, so wait longer before the next attempt.

<a id="anonymous-runs-are-rate-limited"></a>
## Anonymous Runs Are Rate Limited

A `401 Unauthorized` naming `Please wait a few minutes before you try again` on a run without a session means Instagram is rate-limiting anonymous requests from your IP address. The limit is per address, so it counts every device and tool behind it, and it is often reached on the very first request of a run. Raising the check interval does not lift a limit the run did not cause.

A session login is limited per account instead, so [importing a session](configuration.md#option-3-session-login-using-browser-cookies-recommended) usually works from the same address. Otherwise wait for the limit to pass or run from another network. If the same run works over a mobile connection, the limit is on the home address rather than on anything in the configuration.

<a id="profile-lookups-report-a-retired-endpoint"></a>
## Profile Lookups Report a Retired Endpoint

In September 2026 Instagram retired `api/v1/users/web_profile_info/` for accounts that are signed in. It answers `400 feedback_required` no matter how healthy the account is, while GraphQL, search and the profile page keep working for the same session in the same second. Runs without a login are unaffected, because they read profiles from `i.instagram.com` instead.

Version 3.9.1 and earlier read every profile through that endpoint, so a signed-in run on those versions fails at the first lookup of every target. Re-importing the session does not help. Upgrade to 4.0 or later.

A signed-in run now resolves the target's user id through Instagram's search and reads the profile over GraphQL, so it does not use the retired endpoint at all. Resolved ids are saved to `instagram_monitor_user_ids.json` beside the other state files and reused by later runs, so an established target is not looked up again on every start. An id is dropped and resolved again if Instagram reports a different name for it. A target that is the signed-in account itself takes its id from the session and is never searched for.

Search does not list every account, so the retired endpoint is still tried for a target search cannot find. That failure is reported as `endpoint_retired` rather than `action_block`: it does not stop the account and it does not trip the circuit breaker. When you see it, check that the target name is spelled correctly and that the profile still exists.

The endpoint that reports a target's reels count directly, `api/v1/users/<id>/info/`, stopped answering around the same time, and it fails often enough that changing account or IP address does not help. Reels are therefore **not monitored by default**. Posts and stories are unaffected, and a reel counts towards the posts number either way, so a new reel still moves the posts count.

Turn reels on with `FETCH_REELS = True` or `--fetch-reels`, and off again with `--no-fetch-reels`. `--setup` asks as well. With reels on, the count is worked out by reading the target's whole reel list, which is many requests per check and is often refused, so expect repeated errors while Instagram is refusing it. A count is reused while the target's posts count stays where it was and read again when that number moves.

<a id="container-dashboard-does-not-open"></a>
## Container Dashboard Does Not Open

Open the default dashboard at [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Do not enter `http://0.0.0.0:8000/` in the browser. `0.0.0.0` is the server bind address inside the container.

For a one-off Compose run, the command must contain `--service-ports` before the service name:

```sh
docker compose run --rm --service-ports instagram_monitor <target_insta_user> --web-dashboard
```

For direct Docker, the command must contain `-p 127.0.0.1:8000:8000` before the image name:

```sh
docker run --rm -it --init -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 127.0.0.1:8000:8000 misiektoja/instagram-monitor:latest <target_insta_user> --web-dashboard
```

Check the `PORTS` column while the container is running:

```sh
docker ps
```

`127.0.0.1:8000->8000/tcp` means the port is published correctly. A value containing only `8000/tcp` means the server can listen inside the container but the host browser cannot reach it. Dockerfile `EXPOSE 8000` does not publish the port.

<a id="dashboard-returns-403-or-415"></a>
## Dashboard Returns 403 or 415

The dashboard has no login, so it verifies how a request reached it. See [Request Protection](view-modes.md#request-protection) for what the two rules cover.

**HTTP 403 with "unrecognized Host header"** means the browser addressed the server under a name it does not answer to. Open it at [http://127.0.0.1:8000/](http://127.0.0.1:8000/). If you deliberately reach it under another name, such as a machine name on your own network or a reverse proxy, list that name:

```ini
WEB_DASHBOARD_ALLOWED_HOSTS = ["monitor.lan"]
```

**HTTP 403 with "cross-site" or "cross-origin"** means the request did not come from the dashboard page. Reload the dashboard in a normal browser tab rather than driving it from another page.

**HTTP 415** means a request meant to change something arrived without a JSON body. When you call the API yourself, send `Content-Type: application/json`:

```sh
curl -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/monitoring/stop
```

<a id="follower-and-following-lists-stop-working"></a>
## Follower and Following Lists Stop Working

If counts, posts and stories still update but follower or following lists fail, Instagram has most likely changed the endpoint that serves them rather than acted against your account. `--exposure` tells the two apart: failures counted under **Instagram API changed** are this case, failures under **account challenged** are not.

The tool reads those lists from Instagram's own web REST endpoints and falls back to the older GraphQL queries on its own when the REST endpoint is missing or unreadable. If both fail, pin the other surface and try once:

```sh
instagram_monitor <target_insta_user> --follow-list-source graphql
```

Report which source works at [Discussions](https://github.com/misiektoja/instagram_monitor/discussions). Do not leave a failing source running: every retry adds requests to an account that is already getting errors.

There is a third, experimental source that reads the lists out of a real browser instead of calling the API. It excludes the suggested accounts shown below the list. It is slow, needs Playwright and carries a real risk to the logged-in account, so try it only if you accept that. See [Browser Source](usage.md#browser-source-experimental).

Common browser source errors:

- **The browser source runs a chrome browser, but ...**: the browser channel and the rest of the session name different browsers. Set `HTTP_BACKEND` to `curl_cffi`, `CURL_CFFI_IMPERSONATE` to `auto` and `USER_AGENT` to a browser from the channel's family or leave `USER_AGENT` empty. See [Browser Source](usage.md#browser-source-experimental).
- **The browser could not start**: Playwright is installed but the browser is not. Run `playwright install chromium` or set `FOLLOW_LIST_BROWSER_CHANNEL` to a browser already installed here, such as `chrome`.
- **The login page, so this session is not logged in**: the cookies handed to the browser are no longer valid. Refresh the session and try again.
- **A challenge page**: complete account verification in an ordinary browser, then restart or re-import the session. The circuit breaker checks recovery without requiring a separate clearing command.
- **The profile's followers or following control could not be clicked**: set `FOLLOW_LIST_BROWSER_HEADLESS = False` to inspect the profile. The browser source supports both direct list links and count links that open a dialog. If the counts open normally but the tool still fails, update it and report the layout error.
- **No profile links appeared after clicking the control**: the list did not finish loading. Inspect it with `FOLLOW_LIST_BROWSER_HEADLESS = False` and raise `FOLLOW_LIST_BROWSER_TIMEOUT` if it loads slowly. This browser error does not mean an API query returned empty data.
- **Rendered only N of about M**: the dialog stopped growing early, usually from a slow connection. Raise `FOLLOW_LIST_BROWSER_SCROLL_DELAY` and `FOLLOW_LIST_BROWSER_TIMEOUT`. The short list is discarded, not saved over your baseline.

Run `instagram_monitor --doctor` to confirm Playwright and the browser are installed before a real run.

<a id="too-many-open-files"></a>
## Too Many Open Files

`This process ran out of file descriptors` means the operating system limit on open files was reached. It is a local limit and not an Instagram problem. Raise it with `ulimit -n 4096` in the shell that starts the tool or set `LimitNOFILE=` in the systemd unit, then restart the tool.

<a id="terminal-colours-look-wrong"></a>
## Terminal Colours Look Wrong

If escape sequences such as `[36m` appear as literal text, the terminal does not understand ANSI colour. Start the tool with `--no-color` or set `COLORED_OUTPUT = False` in the configuration file. On Windows, `pip install colorama` fixes the classic Command Prompt.

If colour is missing where you expect it, check in this order: `--no-color` on the command line, `COLORED_OUTPUT` in the configuration file, a `NO_COLOR` environment variable and whether output is redirected or piped. Colour is switched off in all of those cases and also when `TERM` is unset or set to `dumb`.

Log files never contain colour by design. To colour a saved log while reading it, see [Coloring Log Output with GRC](usage.md#coloring-log-output-with-grc).

To change which colours are used, see [Terminal Colours](configuration.md#terminal-colours).

<a id="choosing-the-right-logging-level"></a>
## Choosing the Right Logging Level

- **Default mode** reports activity changes and important errors
- **Verbose mode (`--verbose`)** adds occasional state changes, a line naming where each delivered alert went and a complete startup summary without private values. Set `DELIVERY_CONFIRMATIONS = False` to keep verbose mode without those delivery lines
- **Debug mode (`--debug`)** adds sanitized request flow, scheduling details and internal diagnostics

Delivery confirmations name the recipient or webhook provider. `DELIVERY_CONFIRMATIONS = False` hides these optional success messages. Monitoring events, send attempts and errors remain visible.

Both `--verbose` and `--debug` show the complete startup summary, including notification settings and credential sources. Use it to check which configuration is active without displaying private values.

Start with `--doctor`. If the suggested fix does not resolve the issue, retry with `--debug` and include only sanitized output when opening a GitHub issue.

You can also change Verbose and Debug modes through the **Settings** page in the Web Dashboard.

<a id="verbose-and-debug-output"></a>
## Verbose and Debug Output

`--verbose` adds the decisions a run made, in the same `*` lines as the rest of the output:

```sh
instagram_monitor <target_insta_user> --verbose
```

`--debug` traces what the tool is doing in timestamped `[DEBUG HH:MM:SS]` lines:

```sh
instagram_monitor <target_insta_user> --debug
```

Lines with details read `Operation: key=value, key=value`. Fields depend on the operation. Some results report `outcome=OK`, `failed` or `skipped`. Lines printed while a target is monitored carry its username in square brackets after the timestamp.

<a id="installation-and-command-problems"></a>
## Installation and Command Problems

If Python or `pip` is missing, use the [Python install walkthrough](installation.md#new-to-python-check-and-install).

If `instagram_monitor` is not found after installation, close the terminal and open it again. On Windows with Python Install Manager, run `py install --refresh` to refresh command aliases. For a pipx installation, run `pipx ensurepath` then reopen the terminal. If you downloaded the script, use the [manual command](usage.md#command-format-by-installation-method) from its directory.

If `pip` reports an externally managed environment, follow the pipx steps in [Installation](installation.md#install-instagram-monitor). Use `pipx upgrade instagram_monitor` for later upgrades.

If the tool cannot import a dependency, install the dependencies with the same Python interpreter that runs the script. On macOS or Linux use `python3 -m pip install -r requirements.txt`. On Windows use `python -m pip install -r requirements.txt`. Match the requirements file to your downloaded script.

If a new terminal cannot find your saved settings, return to the directory used during setup or pass both `--config-file` and `--env-file` explicitly. Run `instagram_monitor --doctor` to see which settings are loaded.

## Invalid saved settings and state

Timing values must be finite and within the documented range. Normal startup checks effective timing settings before monitoring. A configuration syntax error reports its file, line number and parser message without echoing source text that may contain credentials.

If a saved follower or following file has an invalid structure, monitoring stops before replacing it. Correct the named file or move it aside to start a fresh baseline. Keep a copy if you need the old history. Older valid records and extra trailing metadata remain accepted.

Malformed path settings and color-theme values are reported by Doctor with the setting name. Invalid color values are ignored while rendering help so you can still find the configuration commands.
