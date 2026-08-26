# Troubleshooting

Examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace that command with the matching [command prefix](usage.md#command-format). The setup wizard and `--help` also print commands for the detected installation.

<a id="doctor-preflight"></a>
## Doctor Preflight

Before a long monitoring run, check the current configuration:

```sh
instagram_monitor --doctor
```

Doctor does not change files. It uses `[PASS]`, `[WARN]` and `[FAIL]` markers for the Python version, required and optional packages, configuration, private values, login session, Instagram connection, target usernames and notification settings. A missing optional package is a `WARN` naming the feature it powers, so you can ignore the ones you do not use. Running with no target is a `PASS` when the Web Dashboard is enabled, since targets can be added there, and a `WARN` otherwise, since nothing would be monitored. Login session checks apply only to Logged-In Mode. The Configuration section names the configuration file and the dotenv file it loaded, then lists which secrets are in effect and whether each one came from the dotenv file, an environment variable or the configuration file. Secret names are listed, never their values. The report closes with a `Summary` line and a link back to this page.

A configuration file Instagram Monitor cannot accept is reported by Doctor as a `FAIL` naming the line and the reason, instead of stopping the command before the checks run. This means you can point Doctor at a configuration you are still fixing. Settings that a later release removed are reported as a `WARN` and ignored, so an older configuration file still runs.

In an interactive terminal, Doctor can offer one real delivery test for each configured notification channel that passes its checks. A webhook that is turned on with no alert types selected is reported as a `WARN` and gets no delivery test, since no webhook could ever be sent. Each prompt defaults to No. Answering Yes to the email prompt sends one test email. Answering Yes to the webhook prompt sends one Discord or ntfy message. Doctor never offers delivery tests when it runs without an interactive terminal.

Each failure and warning includes a `To fix:` action, and a `Guide:` link to the relevant documentation page where one applies. The command returns a nonzero exit status if a check or approved delivery test fails, so scripts can detect the failure. Doctor accepts normal login, target and file options. Use them to check the saved setup or one exact combination:

```sh
instagram_monitor --doctor
instagram_monitor -u <your_user> <target> --doctor
```

For Docker Compose use:

```sh
docker compose run --rm instagram_monitor --doctor
```

Doctor exits after the report and does not start monitoring or the Web Dashboard. The Compose command therefore does not need `--service-ports`. The setup wizard also offers to run Doctor after saving.

For more detail, add `--debug` to Doctor or a normal run. Debug output includes HTTP details and internal decisions. It may also contain private data. Remove cookies, passwords, tokens and webhook URLs before sharing it.

<a id="connection-errors-during-monitoring"></a>
## Connection Errors During Monitoring

When a check fails, Instagram Monitor prints the error, a `To fix:` action and a `Guide:` link where one applies, then retries automatically at the next interval. You do not need to restart the tool.

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
docker compose run --rm --service-ports instagram_monitor <target> --web-dashboard
```

For direct Docker, the command must contain `-p 127.0.0.1:8000:8000` before the image name:

```sh
docker run --rm -it --init -v "$PWD:/data:z" -v instagram_monitor_session:/home/instagram/.config/instaloader -p 127.0.0.1:8000:8000 misiektoja/instagram-monitor:latest <target> --web-dashboard
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

<a id="choosing-the-right-logging-level"></a>
## Choosing the Right Logging Level

- **Default mode** logs detected changes and important errors.
- **Verbose mode (`--verbose`)** also logs the previous check time, next check time and interval. Use it to confirm that a background process is still checking targets.
- **Debug mode (`--debug`)** adds HTTP details and internal decisions for troubleshooting.

You can also change Verbose and Debug modes through the **Settings** page in the Web Dashboard.
