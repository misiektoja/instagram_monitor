# Contributing

instagram_monitor is a real-time OSINT tool for tracking Instagram activity. Bug reports, documentation fixes and code contributions are welcome.

## Before contributing

Open an issue or a [discussion](https://github.com/misiektoja/instagram_monitor/discussions) before starting substantial work, so an approach is agreed before you write it. Suspected vulnerabilities go through [SECURITY.md](SECURITY.md), never a public issue.

Contribute only code you have the right to license under GPL-3.0-or-later.

Never commit session cookies, Instagram or SMTP passwords, webhook URLs, ntfy tokens, generated configuration files, log files or downloaded media. Keep scratch files and local test state out of commits. Secret scanning and gitleaks run on every change, but they are a backstop, not the first line of defense.

## Development setup

```sh
git clone https://github.com/misiektoja/instagram_monitor.git
cd instagram_monitor
pip install -e '.[test]'
```

Add the `e2e` extra and a browser when you touch the Web Dashboard:

```sh
pip install -e '.[test,e2e]'
python -m playwright install --with-deps chromium
```

## Development checks

Run these before submitting a change:

```sh
python -m pytest
mkdocs build --strict
```

The default suite is offline. It never contacts Instagram and network functions are replaced with local test doubles. See [Testing](https://misiektoja.github.io/instagram_monitor/testing/) for what it covers.

Browser tests are excluded from the default run and need Chromium:

```sh
python -m pytest tests/test_browser_e2e.py
```

CI additionally runs the suite on Python 3.9 through 3.14, a Windows setup-wizard smoke test and container checks that build the image and exercise Docker Compose. The supported Python floor is 3.9, so avoid syntax and standard-library features added after it.

A change to monitoring, session handling or detection is not verified by the offline suite alone. Exercise it against a real account and say so in the pull request, without usernames or credentials.

## What a change needs

- **Tests.** New behavior needs a test. A bug fix needs a test that fails without it. Match the existing files in `tests/`.
- **Documentation.** User-facing behavior belongs under `docs/`. The documentation build is strict and the suite asserts documentation contracts, so a new setting or option that is missing from the docs will fail CI.
- **A release-notes entry.** Add it under the unreleased section of [RELEASE_NOTES.md](RELEASE_NOTES.md), following the existing category and `**BUGFIX:**`, `**IMPROVE:**`, `**NEW:**` or `**SECURITY:**` prefixes. Write it for a user, not as an implementation log.
- **A Conventional Commits message.** Use the scope the repository already uses for that area, for example `fix(dashboard):`, `test(webhook):` or `docs(usage):`.

Pull requests target `dev`. The pull request template lists the checks to report.

## Code style

The codebase favors complete implementations over minimal patches, explicit validation of anything Instagram supplies and one concise summary comment directly above each shared function. Follow the surrounding code rather than introducing a new style.
