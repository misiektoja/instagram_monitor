# Testing

The [tests directory](https://github.com/misiektoja/instagram_monitor/tree/main/tests/) contains a [pytest](https://docs.pytest.org/) suite for contributors. It checks configuration parsing, time formatting, scheduling, privacy substitutions, notifications, follower comparisons, CSV output, session error handling and user agent generation. It also builds the wheel, installs its console command and verifies documentation contracts. The tests do not contact Instagram. Network functions are replaced with local test doubles.

Install the test dependencies and run the suite:

```bash
# from the repository root
pip install -e '.[test]'
python -m pytest
```

GitHub Actions runs the same suite for pull requests and pushes to `main` or `dev`. It tests every supported Python version plus the installed command on Windows. See the [test workflow](https://github.com/misiektoja/instagram_monitor/blob/main/.github/workflows/tests.yml). The workflow also performs a strict MkDocs build, container smoke checks and a real Chromium dashboard flow. The suite must pass before a release is published to PyPI or Docker Hub.

The suite intentionally excludes tests that sign in to Instagram because automated test logins could trigger security checks or suspension.

## Browser E2E

The browser test starts the dashboard on an ephemeral loopback port. Chromium
loads the rendered page, verifies target status, opens target management and
adds a target without starting Instagram monitoring.

Install the optional browser dependencies:

```bash
pip install -e '.[test,e2e]'
python -m playwright install chromium
```

Run the browser test:

```bash
python -m pytest tests/test_browser_e2e.py
```

The default test dependency set does not install Chromium. In that environment
pytest reports the browser module as skipped.
