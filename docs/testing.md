# Testing

The [tests directory](https://github.com/misiektoja/instagram_monitor/tree/main/tests/) contains a [pytest](https://docs.pytest.org/) suite for contributors. It checks configuration parsing, time formatting, scheduling, privacy substitutions, notifications, follower comparisons, CSV output, session error handling and user agent generation. The tests do not contact Instagram. Network functions are replaced with local test doubles.

Install the test dependencies and run the suite:

```bash
# from the repository root
pip install -e '.[test]'
python -m pytest
```

GitHub Actions runs the same suite for pull requests and pushes to `main` or `dev`. It tests every supported Python version. See the [test workflow](https://github.com/misiektoja/instagram_monitor/blob/main/.github/workflows/tests.yml). The suite must pass before a release is published to PyPI or Docker Hub.

The suite intentionally excludes tests that sign in to Instagram because automated test logins could trigger security checks or suspension.
