# Getting help

Start with the documentation at [misiektoja.github.io/instagram_monitor](https://misiektoja.github.io/instagram_monitor/). [Installation](https://misiektoja.github.io/instagram_monitor/installation/), [Setup & First Run](https://misiektoja.github.io/instagram_monitor/setup-and-first-run/) and [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/) cover most first-run problems, and [Troubleshooting](https://misiektoja.github.io/instagram_monitor/troubleshooting/) covers the rest.

## Check your setup first

The tool diagnoses itself. Run it before asking anything, and include its output when you do:

```sh
instagram_monitor --doctor
```

It checks the environment, configuration, session, targets, notifications and connectivity, and names the line number and reason for anything invalid.

Instagram challenges, sudden empty results or a flagged session are usually anti-detection problems rather than bugs. [Anti-detection](https://misiektoja.github.io/instagram_monitor/anti-detection/) explains what triggers them and how to recover.

## Where to ask

| You want to | Go to |
| --- | --- |
| Ask a question or discuss an idea | [Discussions](https://github.com/misiektoja/instagram_monitor/discussions) |
| Report something broken | [Bug report](https://github.com/misiektoja/instagram_monitor/issues/new?template=bug_report.yml) |
| Request a capability | [Feature request](https://github.com/misiektoja/instagram_monitor/issues/new?template=feature_request.yml) |
| Report a vulnerability | [Private security advisory](https://github.com/misiektoja/instagram_monitor/security/advisories/new), never a public issue |
| Contribute a change | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Before you post

Include the version, how you installed it (PyPI, manual script or Docker), your operating system, whether you use a logged-in session and the `--doctor` output. Run the failing command with `--debug` and attach the relevant part of the log.

Never post session cookies, Instagram or SMTP passwords, webhook URLs, ntfy tokens or a complete configuration file. Redact monitored usernames if they matter to you. See [SECURITY.md](SECURITY.md).

## What to expect

This is a project maintained in spare time, so replies are best effort with no response time attached. Only the latest release receives fixes, as [SECURITY.md](SECURITY.md) describes, so reproduce the problem on the current version before reporting it.

If the project is useful to you, you can support its development through [GitHub Sponsors](https://github.com/sponsors/misiektoja) or [Buy Me a Coffee](https://buymeacoffee.com/misiektoja).
