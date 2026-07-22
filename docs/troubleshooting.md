# Troubleshooting

Examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace that command with the matching [command prefix](usage.md#command-format). The setup wizard and `--help` also print commands for the detected installation.

<a id="doctor-preflight"></a>
## Doctor Preflight

Before a long monitoring run, check the current configuration:

```sh
instagram_monitor --doctor
```

Doctor does not change files. It reports `PASS`, `WARN` or `FAIL` for optional packages, configuration, private values, login session, Instagram connection, target usernames and notification settings. Login session checks apply only to Logged-In Mode.

In an interactive terminal, Doctor can offer one real delivery test for each configured notification channel that passes its checks. Each prompt defaults to No. Answering Yes to the email prompt sends one test email. Answering Yes to the webhook prompt sends one Discord or ntfy message. Doctor never offers delivery tests when it runs without an interactive terminal.

Each failure includes a `To fix:` action. The command returns a nonzero exit status if a check or approved delivery test fails, so scripts can detect the failure. Doctor accepts normal login, target and file options. Use them to check the saved setup or one exact combination:

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

<a id="choosing-the-right-logging-level"></a>
## Choosing the Right Logging Level

- **Default mode** logs detected changes and important errors.
- **Verbose mode (`--verbose`)** also logs the previous check time, next check time and interval. Use it to confirm that a background process is still checking targets.
- **Debug mode (`--debug`)** adds HTTP details and internal decisions for troubleshooting.

You can also change Verbose and Debug modes through the **Settings** page in the Web Dashboard.
