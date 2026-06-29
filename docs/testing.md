# Testing

The project ships an offline test suite under [tests/](https://github.com/misiektoja/instagram_monitor/tree/main/tests/) built with [pytest](https://docs.pytest.org/). The tests exercise the pure and offline-safe logic (config parsing, time/timespan formatting, scheduling windows, privacy substitutions, webhook/notification helpers, follower diffing, CSV writing, session-flag detection and user-agent generation) and never reach Instagram. The few functions that would normally hit the network are stubbed.

Install the test dependencies and run the suite:

```bash
# from the repository root
pip install -e '.[test]'
python -m pytest
```

The same suite runs automatically on pull requests and on pushes to the `main` and `dev` branches via GitHub Actions across all supported Python versions (see [.github/workflows/tests.yml](https://github.com/misiektoja/instagram_monitor/blob/main/.github/workflows/tests.yml)), and must pass before a release is published to PyPI or Docker Hub.

Online tests that log into Instagram are intentionally out of scope, as automated logins risk triggering challenges or account suspension.
