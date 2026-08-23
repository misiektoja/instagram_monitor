# Contributing

instagram_monitor is a real-time OSINT tool for tracking Instagram activity. Bug reports, documentation fixes and code contributions are welcome.

## Before contributing

Open an issue or a [discussion](https://github.com/misiektoja/instagram_monitor/discussions) before starting substantial work, so an approach is agreed before you write it. [SUPPORT.md](SUPPORT.md) lists where usage questions and bug reports belong. Suspected vulnerabilities go through [SECURITY.md](SECURITY.md), never a public issue.

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

Browser tests run as part of the default suite but skip when Chromium is absent, so a fresh clone still gets a green run. Install the browser to actually exercise them:

```sh
pip install -e '.[test,e2e]'
python -m playwright install chromium
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

[.editorconfig](.editorconfig) records the whitespace rules the repository already follows: UTF-8, LF line endings, a final newline, no trailing whitespace, four-space indentation for Python and the dashboard template and two spaces for YAML, TOML and JSON. Most editors apply it automatically, a few need a plugin. The test suite checks tracked files against the same rules, so a change made in an editor that ignores them will fail CI.
