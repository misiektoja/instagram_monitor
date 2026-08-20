# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability.

Report it privately through [GitHub security advisories](https://github.com/misiektoja/instagram_monitor/security/advisories/new), which keeps the report visible only to the maintainer until an advisory is published. If you cannot use that, email <misiektoja-github@rm-rf.ninja>.

Do not include session cookies, Instagram or SMTP passwords, webhook URLs, ntfy tokens or the accounts you monitor in a report. Include the affected version, the impact, the preconditions to reproduce it and a sanitized proof when you have one.

The maintainer will acknowledge the report and coordinate disclosure once a fix is available.

## Supported versions

Security fixes are made on the default branch and shipped in the next release to [PyPI](https://pypi.org/project/instagram_monitor/), the [GitHub releases](https://github.com/misiektoja/instagram_monitor/releases) and the [Docker image](https://hub.docker.com/r/misiektoja/instagram-monitor). Only the latest released version is supported. Earlier versions receive no backports.

## Security posture

This tool holds credentials for your own Instagram account and records what other accounts do. Both matter when you deploy it.

- **The Web Dashboard has no login screen.** It binds to `127.0.0.1` by default and answers only requests addressed to a host it recognizes. Anything that changes state must come from the dashboard page itself. Treat any bind address other than loopback as publishing your session and your monitoring data. In a container, publish it as `-p 127.0.0.1:PORT:PORT`.
- **Secrets belong in `.env`, not in the configuration file.** `--set-webhook-url` and the setup wizard write to `.env` and set owner-only permissions on POSIX systems. See [Configuration](https://misiektoja.github.io/instagram_monitor/configuration/).
- **Configuration files are parsed, not executed.** Only recognized `SETTING = value` lines with plain values are accepted, so a configuration file found in the working directory cannot run code.
- **Instagram-controlled text is untrusted input.** Biographies, captions, comments and usernames are stripped of terminal control sequences, escaped before entering HTML email and dashboard output and prefixed before entering CSV exports.
- **Monitoring an account is subject to the law where you are.** The tool is intended for accounts you own or are authorized to observe. See [Anti-detection](https://misiektoja.github.io/instagram_monitor/anti-detection/) for the account-safety side of the same question.

## Supply chain

Every GitHub Actions workflow pins third-party actions to a commit SHA with the version recorded alongside it. The test suite fails when a pin or its version comment is missing. Dependencies, actions and the container base image are tracked by Dependabot. Each change runs secret scanning, a dependency vulnerability audit, an SBOM build and a container image scan. CodeQL analyzes the Python source with the `security-extended` query set, and OpenSSF Scorecard scores the repository's security practices. See [.github/workflows/supply-chain.yml](https://github.com/misiektoja/instagram_monitor/blob/main/.github/workflows/supply-chain.yml) and [THIRD_PARTY_NOTICES.md](https://github.com/misiektoja/instagram_monitor/blob/main/THIRD_PARTY_NOTICES.md).

The default branch and the development branch are protected by rulesets that block deletion and force pushes and require changes to arrive through a pull request.
