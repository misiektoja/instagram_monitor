# Test suite

These tests cover logic in `instagram_monitor.py` that can run without network access.
Functions that normally contact Instagram are replaced with test doubles. See
`test_session_flags.py` for an example.

The default suite also builds and installs the project wheel to test the shipped
console command. An optional browser test uses local loopback traffic only and
never contacts Instagram.

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
| `test_proxy_ip.py` | Proxy IP endpoint validation, IPv4/IPv6 parsing, ordered failover and retry timing |
| `test_time_and_dates.py` | `display_time`, `calculate_timespan`, hour formatting, timezone conversions |
| `test_privacy.py` | `apply_privacy_substitutions` (string/dict/list recursion, invalid entries) |
| `test_notifications.py` | Webhook URL validation, Discord markdown escaping, credential masking, payload templating |
| `test_webhook_delivery.py` | `send_webhook` payload formatting, gates and retry behavior with fake HTTP |
| `test_paginated_fetching.py` | `fetch_usernames_paginated` batching, limits, completion state and stop-event behavior |
| `test_dashboard_endpoints.py` | Web Dashboard status, strict atomic settings, private values, media access and isolation, target validation, monitor ownership, session signaling and test-notification endpoints |
| `test_detection_workflows.py` | Posts/reels count change notifications, leaked-collab notification workflows and hostile email content |
| `test_profile_picture_workflows.py` | Profile picture creation, removal, change notifications, CSV rows and file moves |
| `test_story_workflows.py` | Startup story item CSV and dashboard metadata plus independent email/webhook gates and hostile story content |
| `test_media_downloads.py` | Atomic media replacement, type validation, truncation, non-200 responses and download limits |
| `test_request_scoping.py` | Instagram hostname classification, per-session jitter isolation and Instaloader copied sessions |
| `test_session_import.py` | Firefox cookie-domain filtering and canonical session path discovery |
| `test_scheduling.py` | `CHECK_POSTS_IN_HOURS_RANGE` window logic, next-check computation, cycle probability, interval randomization |
| `test_session_flags.py` | Error classification and session/IP flag detection with a stubbed profile resolver |
| `test_parsing_and_useragents.py` | JSON username extraction, follow-string formatting, desktop/mobile user-agent shape |
| `test_csv_and_files.py` | CSV init/append and byte-wise image comparison |
| `test_followers.py` | Follower/following diffing, webhook escaping, CSV side effects |
| `test_documentation.py` | Semantic documentation contracts for commands, concepts and platform variants plus repository metadata: governance files, citation, funding, line endings and the declared editor style |
| `test_packaging.py` | Wheel contents, installed console help/version and config generation |
| `test_browser_e2e.py` | Real Chromium rendering, navigation and target creation against the local dashboard |

## Conventions

* Module-level globals the helpers read are reset to a deterministic baseline by
  the autouse `deterministic_globals` fixture in `conftest.py`. Override them per
  test with `monkeypatch.setattr(im_module, "NAME", value)`.
* Use the `im_module` fixture to access the imported module.
* Keep everything offline. If a code path needs network access, stub it with
  `monkeypatch` rather than skipping the test.

Online tests that log in to Instagram are excluded because automated test logins
could trigger security checks or account suspension.

## Browser E2E

Install the optional browser dependencies and Chromium:

```bash
pip install -e '.[test,e2e]'
python -m playwright install chromium
```

Run the browser test:

```bash
python -m pytest tests/test_browser_e2e.py
```

Without the `e2e` extra the browser module is skipped. CI installs Chromium and
runs it in a dedicated browser job.
