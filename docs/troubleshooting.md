# Troubleshooting

If something is not working (or you just want to confirm your setup before leaving it running), start with the built-in self-check:

```sh
instagram_monitor --doctor
```

Doctor never writes files. It first performs passive checks and prints a `PASS` / `WARN` / `FAIL` report covering optional dependencies, the config file and secrets, session validity (in Logged-in mode), Instagram connectivity, whether your target accounts resolve and whether email/webhook notifications are configured.

In an interactive terminal, each notification channel that passes its passive checks gets a separate optional delivery prompt. Both prompts default to No. Approving the email prompt delivers one real test email. Approving the webhook prompt publishes one real Discord or ntfy notification. Declining either prompt sends nothing. Noninteractive doctor runs never offer or send delivery tests.

Each failure includes a `To fix:` next step. The command exits non-zero if any passive check or approved delivery test fails, so it is also handy in scripts. It honours the same flags as a normal run, so `instagram_monitor -u <your_user> <target> --doctor` checks that exact setup. The setup wizard also offers to run it at the end.

For deeper issues, run the tool with the `--debug` flag. It shows full HTTP traffic and internal script logic. Create a new issue in Github if you cannot fix it yourself.

<a id="choosing-the-right-logging-level"></a>
## Choosing the Right Logging Level

- **Default Mode**: Clean and quiet. Logs changes (new posts, bio updates, etc.) and critical errors. Best for long-term production use.
- **Verbose Mode (`--verbose`)**: Adds per-check timing details (last check, next check schedule and interval) to plain text output. Handy for background or headless runs without a dashboard, where you want to confirm in the log that the loop is running.
- **Debug Mode (`--debug`)**: For developers or fixing issues. Shows full HTTP traffic and internal script logic.

**Note**: Both **Verbose** and **Debug** modes can be toggled live via the **Settings** menu in the **Web Dashboard**.
