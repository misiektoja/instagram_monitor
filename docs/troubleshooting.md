# Troubleshooting

Examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace that command with the matching [command prefix](usage.md#command-format). The setup wizard and `--help` also print commands for the detected installation.

<a id="doctor-preflight"></a>
## Doctor Preflight

Before a long monitoring run, check the current configuration:

```sh
instagram_monitor --doctor
```

Doctor does not change files. It opens with the raw `manual`, `pip`, `docker` or `compose` install method, then uses `[PASS]`, `[WARN]`, `[FAIL]` and `[SKIP]` markers, colour-coded by status when colour output is on, and groups its rows into **Environment** for the Python version and the required and optional packages, **Configuration** for the settings and the private values in effect, **Session** for the saved login, **Connectivity** for the endpoint and the Instagram connection, **Targets** for the monitored usernames and **Notifications** for the alert channels. A section with nothing to report is left out. A missing optional package is a `WARN` naming the feature it powers, so you can ignore the ones you do not use. Running with no target is a `PASS` when the Web Dashboard is enabled, since targets can be added there, and a `WARN` otherwise, since nothing would be monitored. Login session checks apply only to Logged-In Mode. The Configuration section names the configuration file and the dotenv file it loaded, then lists which secrets are in effect and whether each one came from the dotenv file, an environment variable or the configuration file. Secret names are listed, never their values. An explicitly selected dotenv path that does not exist is reported as a warning with the path and recovery command. It also names the log and CSV files each target would write and reports whether they can be created, or says so when either is disabled, including the ones `-b` and `-d` asked for on the command line. The report carries a `Summary` line and a link back to this page. The summary is printed after any approved delivery tests and counts their results, so the sentence and the exit code always describe the same run. It then ends with a **Next steps** block naming the command that starts monitoring, carrying the same `--config-file` and `--env-file` this run checked. It carries the targets this run used, leaves them out when the configuration file already supplies them and otherwise shows `<target_insta_user>` for you to replace, unless the Web Dashboard is enabled and targets can be added there. While a check is failing it asks for the failures first.

A configuration file Instagram Monitor cannot accept is reported by Doctor as a `FAIL` naming the line and the reason, instead of stopping the command before the checks run. This means you can point Doctor at a configuration you are still fixing. Settings that a later release removed are reported as a `WARN` and ignored, so an older configuration file still runs.

The Configuration section also reports whether [TLS verification](configuration.md#tls-verification) is on, and warns while it is off. It names the identity this run would present: the [HTTP backend](usage.md#http-transport-backend), the browser `curl_cffi` impersonates once `Auto` has resolved, and the browser and mobile user agents. The `requests` backend is a `WARN` in that row, since it presents this machine's own TLS fingerprint whatever `USER_AGENT` claims. Settings that control timing and counts, such as `INSTA_CHECK_INTERVAL`, the follower batch limits and the check-hour ranges, are checked for usable values and every one that fails is named in a single row. That covers a value that is not a number at all, such as a quoted `"3600"`, and the rows that would read it are left out rather than stopping the report. A monitoring run stops at startup with the same setting name, value and required format. It resolves `LOCAL_TIMEZONE`. It reports the detected zone when the setting is `Auto` and fails when the zone is invalid or cannot be detected.

The Notifications section signs in to the configured SMTP server and checks webhook settings without sending a message, and each ready row lists the alert categories that channel would deliver.

In an interactive terminal, Doctor can offer one real delivery test for each configured notification channel that passes its checks. A channel that is switched off is reported as disabled and is not validated further. A channel that is switched on but cannot deliver gets no delivery test, since nothing could ever be sent. An invalid webhook setting, such as a destination that is missing or is not a complete HTTPS URL, is reported as a `FAIL`. A channel that is only incomplete, such as a webhook with no alert types selected or email alerts with no SMTP host, is reported as a `WARN`. Each prompt defaults to No. Answering Yes to the email prompt sends one test email. Answering Yes to the webhook prompt sends one Discord or ntfy message. Ctrl+C at either prompt ends the run rather than declining one test and asking the next. Doctor never offers delivery tests when it runs without an interactive terminal.

Each failure and warning includes a `To fix:` action, and a `Guide:` link to the relevant documentation page where one applies. The command returns a nonzero exit status if a check or approved delivery test fails, so scripts can detect the failure. Doctor accepts normal login, target and file options. Use them to check the saved setup or one exact combination:

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

<a id="connection-errors-during-monitoring"></a>
## Connection Errors During Monitoring

When a check fails, Instagram Monitor prints the error, a `To fix:` action and a `Guide:` link where one applies, then retries automatically at the next interval. You do not need to restart the tool. A command in the fix text matches how you installed the tool and carries the `--config-file` or `--env-file` you started with, so it can be pasted as it is.

Every other problem reads the same way. A setting the tool cannot use, a file it cannot read or write, a mail or webhook delivery that failed, a proxy it cannot reach and an optional library that is missing all print `* Error:` with what went wrong, a `To fix:` action and a `Guide:` link. A problem the run recovers from prints `* Warning:` with the same two lines under it. A missing library names the exact install command for the Python you are running. Secret values are removed from all of it.

A failure the tool could not place still names an action: it asks you to re-run with `--debug` and links the page explaining the output modes.

The banner that says nothing changed prints in any mode: `* Monitoring healthy for <instagram_user>` with what was checked, followed by `Liveness check, timestamp:`. It is timed rather than counted in checks, so it appears once per `LIVENESS_CHECK_INTERVAL` of quiet, measured from the last thing the run printed. That setting defaults to 86400 seconds, a day. Set it to 0 to switch the banner off. A monitoring failure is reported as `* Error: <what failed> (retrying in <time>)`, with the `To fix:` paragraph under it the first time that category appears. Every monitor in this family prints that same line. During a long outage the failure is reported in full once, then the tool stays quiet and reminds you once an hour with `* Monitoring degraded for <instagram_user>`, the summary of what is still failing, when it started and how many checks have failed so far, so a two-day outage is a handful of lines rather than one block per check. The reminder has its own clock and does not depend on `LIVENESS_CHECK_INTERVAL`, so it keeps coming when the banner is off. When the failure clears, `* Monitoring recovered for <instagram_user>` reports how long it lasted. An outage that starts failing differently is still one outage: a lost connection that reads as a timeout on one check and as an unreachable host on the next prints nothing new, a change to another kind of failure that clears on its own is one line, `* Monitoring failure changed for <instagram_user>. <what fails now>`, and a change to a failure that needs you is reported in full.

A redirect or a rejected request usually means the saved session. When the failure was not recognized well enough to suggest anything else, the `To fix:` line names the session and the exact re-import command instead.

A message naming `Could not resolve host` means the machine could not look up Instagram's address. This is a DNS problem on your side rather than an Instagram block, and it is common on devices that start monitoring before the network is fully up, such as a Raspberry Pi booting from cold. Check that name lookups work:

```sh
ping www.instagram.com
```

If that fails too, fix DNS first. When you use a VPN or a proxy, confirm it is running and allowed to resolve names. Monitoring recovers on its own once lookups succeed, so no action is needed inside Instagram Monitor.

Other connection errors point elsewhere. `Max retries exceeded` or a timeout usually means the connection dropped or a proxy is unreachable, see [routing traffic through a proxy](usage.md#routing-traffic-through-a-proxy). `429` or `Too Many Requests` means Instagram is rate-limiting you, see [check intervals](anti-detection.md). A message about a redirect, a login or wrong credentials means the saved session expired, see [session import](configuration.md).

For the underlying transport detail behind any of these, add `--debug`. Normal output omits it because it names internal HTTP library errors rather than anything you can act on.

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

The dashboard has no login, so it verifies how a request reached it. See [Request Protection](view-modes.md#dashboard-request-protection) for what the two rules cover.

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

There is a third, experimental source that reads the lists out of a real browser instead of calling the API. It is slow, needs Playwright and carries a real risk to the logged-in account, so try it only if you accept that. See [Browser Source](usage.md#browser-source-experimental).

Common browser source errors:

- **The browser source runs a chrome browser, but ...**: the browser channel and the rest of the session name different browsers. Set `HTTP_BACKEND` to `curl_cffi`, `CURL_CFFI_IMPERSONATE` to `auto` and `USER_AGENT` to a browser from the channel's family, or leave `USER_AGENT` empty. See [Browser Source](usage.md#browser-source-experimental).
- **The browser could not start**: Playwright is installed but the browser is not. Run `playwright install chromium`, or set `FOLLOW_LIST_BROWSER_CHANNEL` to a browser already installed here, such as `chrome`.
- **The login page, so this session is not logged in**: the cookies handed to the browser are no longer valid. Refresh the session and try again.
- **A challenge page**: clear the challenge in an ordinary browser first. This also trips the circuit breaker.
- **Rendered only N of about M**: the dialog stopped growing early, usually from a slow connection. Raise `FOLLOW_LIST_BROWSER_SCROLL_DELAY` and `FOLLOW_LIST_BROWSER_TIMEOUT`. The short list is discarded, not saved over your baseline.

Run `instagram_monitor --doctor` to confirm Playwright and the browser are installed before a real run.

<a id="choosing-the-right-logging-level"></a>
## Choosing the Right Logging Level

- **Default mode** logs detected changes and important errors.
- **Verbose mode (`--verbose`)** also logs operational events such as follower and following counts, an alert channel switched off because its settings are still placeholders and a line naming where each delivered alert went. It prints nothing per check, so an uneventful run stays quiet. Set `DELIVERY_CONFIRMATIONS = False` to keep verbose mode without the `* Email delivered` and `* Webhook delivered` lines, which is worth doing when alerts are frequent.
- **Debug mode (`--debug`)** adds HTTP details, internal decisions, how many settings the configuration file supplied and the previous check time, next check time and interval for each cycle. Use it to confirm that a background process is still checking targets. Each line names the operation, then lists its details as comma-separated `key=value` fields such as the URL, the HTTP `status` and, for the steps that report one, `outcome=OK` or `outcome=failed`. A `--debug` run leaves the terminal as it was instead of clearing it, so the output you are comparing against stays on screen. `--verbose` clears it like an ordinary run.

Either mode also expands the startup summary with the detected install method and the names of the secrets that came from the dotenv file, the environment or the configuration file. Secret values never appear. The same view names the webhook service alerts go to and whether that channel is switched on, plus the mail server that sends them with the recipient address masked. Each channel's own settings are indented under it. It also reports whether the delivery confirmations are printed and the process id, Python version and operating system the run is on.

You can also change Verbose and Debug modes through the **Settings** page in the Web Dashboard.

## Invalid saved settings and state

Timing values must be finite and within the documented range. Normal startup checks effective timing settings before monitoring. A configuration syntax error reports its file, line number and parser message without echoing source text that may contain credentials.

If a saved follower or following file has an invalid structure, monitoring stops before replacing it. Correct the named file or move it aside to start a fresh baseline. Keep a copy if you need the old history. Older valid records and extra trailing metadata remain accepted.
