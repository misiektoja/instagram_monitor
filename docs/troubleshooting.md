# Troubleshooting

Examples on this page use the PyPI command `instagram_monitor`. For a manual script or container, keep the shown options and use the matching prefix under [Command Format by Installation Method](usage.md#command-format). The setup wizard and `--help` print commands for the detected installation.

<a id="doctor-preflight"></a>
## Doctor Preflight

Before starting a long monitoring run, use the built-in self-check:

```sh
instagram_monitor --doctor
```

Doctor never writes files. It first performs passive checks and prints a `PASS` / `WARN` / `FAIL` report covering optional dependencies, the config file and secrets, session validity in Logged-In Mode, Instagram connectivity, target resolution and email or webhook configuration.

In an interactive terminal, each notification channel that passes its passive checks gets a separate optional delivery prompt. Both prompts default to No. Approving the email prompt delivers one real test email. Approving the webhook prompt publishes one real Discord or ntfy notification. Declining either prompt sends nothing. Noninteractive doctor runs never offer or send delivery tests.

Each failure includes a `To fix:` next step. The command exits nonzero if any passive check or approved delivery test fails, which also makes it useful in scripts. It honors the same flags as a normal run, so you can check only the saved setup or one exact login and target combination:

```sh
instagram_monitor --doctor
instagram_monitor -u <your_user> <target> --doctor
```

For Docker Compose use:

```sh
docker compose run --rm instagram_monitor --doctor
```

Doctor exits after the report and does not start the Web Dashboard, so this Compose check does not need `--service-ports`. The setup wizard offers to run doctor at the end.

For deeper issues, add `--debug` to a doctor check or normal run. It shows full HTTP traffic and internal script logic. Remove or mask cookies, passwords, tokens and private webhook URLs before sharing output in a GitHub issue.

<a id="choosing-the-right-logging-level"></a>
## Choosing the Right Logging Level

- **Default Mode**: Clean and quiet. Logs changes (new posts, bio updates, etc.) and critical errors. Best for long-term production use.
- **Verbose Mode (`--verbose`)**: Adds per-check timing details (last check, next check schedule and interval) to plain text output. Handy for background or headless runs without a dashboard, where you want to confirm in the log that the loop is running.
- **Debug Mode (`--debug`)**: For developers or fixing issues. Shows full HTTP traffic and internal script logic.

Both **Verbose** and **Debug** modes can also be toggled live through the **Settings** menu in the **Web Dashboard**.
