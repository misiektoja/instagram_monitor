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
| `test_codeql_workflow.py` | CodeQL source suppression filtering, preserved findings and upload ordering |
| `test_codeql_boundaries.py` | Long input formatting, profile path validation, private dashboard errors and secret presence diagnostics |
| `test_notification_receipts.py` | SMTP acceptance despite cleanup failures, receipt controls and unchanged notification content |
| `test_configuration_notification_boundaries.py` | Invalid output settings, CLI precedence and strict webhook fields with legacy JSON support |
| `test_boundary_regressions.py` | Real notification transports, literal secret resolution and malformed startup paths |
| `test_resource_boundaries.py` | Optional network work stops after real transport resource exhaustion |
| `test_release_boundaries.py` | Real HTTP retries, Discord mention safety, unrenderable templates, SMTP password round trips, split terminal writes and the width cap without wcwidth |
| `test_compact_commands.py` | Literal short command prefixes, real help output and dependency hints |
| `test_release_safety.py` | Credential preservation, private error rendering, runtime timing validation and saved-state compatibility |
| `test_recovery_safety.py` | Real dotenv reloads, setup backups, oversized counts and provider-error privacy |
| `test_secret_policy.py` | Shared credential priority, reload ownership and setup destination conflicts |
| `test_smtp_error_privacy.py` | Short and escaped passwords in rejected SMTP sign-ins through commands, setup, Doctor and delivery |
| `test_setup_resolution_regressions.py` | Saved dotenv destinations, empty secrets, export precedence and recovery paths |
| `test_dotenv_quoted_keys.py` | Quoted dotenv keys, export prefixes, multiline values and duplicate removal |
| `test_config_generation.py` | Config inline-comment splitting, value formatting, `generate_config_with_current_values` round-trip, config replacement backups and confirmation, dotenv secret writes and removals |
| `test_proxy_ip.py` | Proxy IP endpoint validation, IPv4/IPv6 parsing, ordered failover and retry timing |
| `test_startup_summary_channels.py` | Summary rows naming the webhook provider, the mail server, the masked recipient, the delivery confirmations and the runtime |
| `test_time_and_dates.py` | `display_time`, `calculate_timespan`, hour formatting, timezone conversions |
| `test_privacy.py` | `apply_privacy_substitutions` (string/dict/list recursion, invalid entries) |
| `test_notifications.py` | Webhook URL validation, Discord markdown escaping, credential masking, payload templating |
| `test_webhook_delivery.py` | `send_webhook` payload formatting, gates and retry behavior with fake HTTP |
| `test_paginated_fetching.py` | `fetch_usernames_paginated` batching, limits, completion state and stop-event behavior |
| `test_profile_resolution.py` | Resolving a target through search and GraphQL instead of the retired profile endpoint, id caching and the failure class that keeps the account running |
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
| `conftest.py` | Shared fixtures and import setup: module globals, exported secrets and stubbed dependencies are reset between tests |
| `test_config_loading.py` | Config files read as data, rejected content and the settings each released template still carries |
| `test_config_effects.py` | Config-file settings reaching the code that consumes them |
| `test_startup_summary.py` | The startup summary block driven through the real command-line path |
| `test_help_screen.py` | The `--help` screen: the shared argument group names, the task-grouped examples and the startup banner |
| `test_setup_wizard.py` | The staged setup wizard, its destination checks and its safety gates |
| `test_install_method_commands.py` | Install-method detection and the command examples it drives |
| `test_doctor.py` | `--doctor` preflight checks: every section, the delivery tests and the exit code |
| `test_error_hints.py` | The action-oriented error hint classifier |
| `test_terminal_color.py` | The colour engine: theme resolution, line rules, quoted content and the shipped theme keys |
| `test_tls_verification.py` | Every request honouring `VERIFY_SSL`, what is reported while it is off and its shipped default |
| `test_exposure_ledger.py` | The identity exposure ledger, the daily budget and the account circuit breaker |
| `test_account_recovery.py` | Single-request restart and import recovery, preserved counters, concurrent starts and dashboard resumption |
| `test_missed_alert_recovery.py` | The recovery alert sent to a channel that never received the failure alert |
| `test_account_safety_loop.py` | The real monitoring loop stopping an account Instagram keeps refusing, and leaving a transient fault alone |
| `test_human_simulation.py` | The BeHuman activity simulation guards |
| `test_impersonate_validation.py` | curl_cffi impersonation target validation |
| `test_http_backend.py` | The curl_cffi transport adapter driven against a loopback server |
| `test_concurrency_and_caches.py` | Shared cache eviction and probe deduplication |
| `test_monitor_restart.py` | The monitoring restart loop used when live settings change |
| `test_follow_list_source.py` | The follower and following list sources: the web REST endpoints and the GraphQL fallback |
| `test_request_backoff.py` | The jitter back-off giving up with the real cause, so a rate limit or a challenge is never read as a missing endpoint |
| `test_follow_list_browser.py` | The experimental browser follower list source, with no browser started |
| `test_follow_analysis.py` | The offline follow relationship analysis behind `--analyze-follows` |
| `test_imgcat_display.py` | Terminal image display argument handling |
| `test_notification_escaping.py` | Source-level sweep proving every value reaching an HTML notification body is escaped |
| `test_email_html.py` | HTML notification bodies: escaping, the ntfy plain form and the plain-text match |
| `test_documentation.py` | Semantic documentation contracts for commands, concepts and platform variants plus repository metadata: governance files, citation, funding, line endings, the declared editor style, the pinned linter and release integrity |
| `test_packaging.py` | Wheel contents, installed console help/version and config generation |
| `test_browser_e2e.py` | Real Chromium rendering, navigation and target creation against the local dashboard |
| `test_moved_private_settings.py` | Kept credentials across dotenv destination changes and startup error handling |

## Conventions

* Module-level globals the helpers read are reset to a deterministic baseline by
  the autouse `deterministic_globals` fixture in `conftest.py`. Override them per
  test with `monkeypatch.setattr(im_module, "NAME", value)`.
* Use the `im_module` fixture to access the imported module.
* Exported secrets are cleared before every test, because loading a dotenv writes
  them into `os.environ` and nothing removes them again. Set the one a test needs
  with `monkeypatch.setenv` inside that test.
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
