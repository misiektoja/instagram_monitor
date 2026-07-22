# Offline test suite

These tests cover logic in `instagram_monitor.py` that can run without network access.
Functions that normally contact Instagram are replaced with test doubles. See
`test_session_flags.py` for an example.

## Running

From the repository root:

```bash
pip install -e '.[test]'
python -m pytest
```

`pyproject.toml` puts the repository root first on `sys.path`. `conftest.py`
enforces the same order. The tests therefore use the working tree instead of an
installed copy of the package.

## Layout

| File | Area under test |
| --- | --- |
| `test_config_generation.py` | Config inline-comment splitting, value formatting, `generate_config_with_current_values` round-trip |
| `test_time_and_dates.py` | `display_time`, `calculate_timespan`, hour formatting, timezone conversions |
| `test_privacy.py` | `apply_privacy_substitutions` (string/dict/list recursion, invalid entries) |
| `test_notifications.py` | Webhook URL validation, Discord markdown escaping, credential masking, payload templating |
| `test_webhook_delivery.py` | `send_webhook` payload formatting, gates and retry behavior with fake HTTP |
| `test_paginated_fetching.py` | `fetch_usernames_paginated` batching, limits and stop-event behavior |
| `test_dashboard_endpoints.py` | Web Dashboard status, settings, config, session and test-notification endpoints |
| `test_detection_workflows.py` | Posts/reels count change notifications and leaked-collab notification workflows |
| `test_profile_picture_workflows.py` | Profile picture creation, removal, change notifications, CSV rows and file moves |
| `test_story_workflows.py` | Startup story item CSV writing and dashboard update metadata with fake Instaloader data |
| `test_scheduling.py` | `CHECK_POSTS_IN_HOURS_RANGE` window logic, next-check computation, cycle probability, interval randomization |
| `test_session_flags.py` | Error classification and session/IP flag detection with a stubbed profile resolver |
| `test_parsing_and_useragents.py` | JSON username extraction, follow-string formatting, desktop/mobile user-agent shape |
| `test_csv_and_files.py` | CSV init/append and byte-wise image comparison |
| `test_followers.py` | Follower/following diffing, webhook escaping, CSV side effects |

## Conventions

* Module-level globals the helpers read are reset to a deterministic baseline by
  the autouse `deterministic_globals` fixture in `conftest.py`. Override them per
  test with `monkeypatch.setattr(im_module, "NAME", value)`.
* Use the `im_module` fixture to access the imported module.
* Keep everything offline. If a code path needs network access, stub it with
  `monkeypatch` rather than skipping the test.

Online tests that log in to Instagram are excluded because automated test logins
could trigger security checks or account suspension.
