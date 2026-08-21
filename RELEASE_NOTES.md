# instagram_monitor release notes

This is a high-level summary of the most important changes.

# Changes in 3.9 (TBD)

Version **3.9** prevents empty follower alerts without hiding count changes when complete Instagram lists are unavailable, accepts webhook services hosted at a root HTTPS endpoint and hardens notifications, media downloads and long-running Web Dashboard monitoring. The Web Dashboard now refuses requests that another website triggers in your browser, answers only the addresses you actually open it at and never hands a saved credential to a destination you did not enter it for. Webhook delivery tests finally send with the shipped defaults, human mode no longer needs hashtags configured, and Instagram text can no longer drive your terminal or carry a formula into an exported CSV. A failed check now tells you what to do about it instead of printing raw transport errors. The project itself gains a published security policy with private vulnerability reporting, guided issue and pull request templates, contribution and dependency licensing documentation plus continuous supply chain scanning that audits dependencies, publishes an SBOM and scans the container image.

**Features and improvements**:

- **IMPROVE:** **Guided issue reporting and contribution** - Opening an issue now offers a **bug report** or **feature request** form that asks for the version, install method, operating system, login method and `--doctor` output up front, so a report arrives with what is needed to act on it. Suspected vulnerabilities are routed to private reporting instead of a public issue. New [CONTRIBUTING.md](https://github.com/misiektoja/instagram_monitor/blob/main/CONTRIBUTING.md), [CODE_OF_CONDUCT.md](https://github.com/misiektoja/instagram_monitor/blob/main/CODE_OF_CONDUCT.md) and a pull request template describe the development setup, the checks CI enforces and what a change needs before it is merged.
- **IMPROVE:** **Published security policy** - [SECURITY.md](https://github.com/misiektoja/instagram_monitor/blob/main/SECURITY.md) explains how to report a vulnerability privately through **GitHub security advisories**, which versions receive fixes and what you are responsible for when you deploy the tool: the Web Dashboard has no login screen and belongs on loopback, secrets belong in **`.env`** with owner-only permissions and configuration files are parsed rather than executed.
- **IMPROVE:** **Dependency transparency** - New [THIRD_PARTY_NOTICES.md](https://github.com/misiektoja/instagram_monitor/blob/main/THIRD_PARTY_NOTICES.md) lists every runtime, optional, build and documentation dependency with its license and what it is used for, names the container base image and records the instaloader patches this tool carries. The test suite fails when a newly declared dependency is missing from it.
- **IMPROVE:** **Continuous supply chain scanning** - A **supply chain workflow** now audits the resolved dependency tree with **`pip-audit`**, publishes a **CycloneDX SBOM** of everything a user actually installs, scans the container image for fixable high and critical vulnerabilities and continues the existing credential history scan. It runs on every change and again weekly, so a vulnerability published after a merge is still caught. **Dependabot** now also tracks Python dependencies and the documentation site build, alongside the actions and base image it already watched.
- **IMPROVE:** **Automated code and project security scanning** - **CodeQL** now analyzes the Python source with GitHub's `security-extended` query set on every change and weekly, reporting anything it finds as a code scanning alert. **OpenSSF Scorecard** scores the project's security practices, including branch protection, action pinning and dependency update automation, and publishes the result as a badge on the project page.

**Bug fixes**:

- **BUGFIX:** **Private configuration backups** - Replacing a configuration file through the setup wizard or `--generate-config` created its timestamped `.bak` copy with default permissions, so a configuration you had kept owner-only left a world-readable backup beside it. Backups are now created owner-only from the start and keep the permissions of the file they copy
- **BUGFIX:** **Hardened error notifications** - Error text is now HTML-escaped in email alerts, so an Instagram response quoted inside an error message can no longer inject markup into a message you trust. The session-flag alert also stops losing its `<anonymous>` placeholder to the mail client when no session account is configured. A new check reads the source itself, so a future notification that forgets to escape Instagram-supplied text fails the build
- **BUGFIX:** **Connectivity check respects configuration** - The startup internet check now honors `CHECK_INTERNET_URL` and `CHECK_INTERNET_TIMEOUT` from the config file or dotenv instead of the built-in defaults frozen when the tool loads, so a custom probe address for a restricted network is no longer silently ignored
- **BUGFIX:** **Doctor diagnoses a broken configuration** - **`--doctor`** now reports a configuration file it cannot accept as a `FAIL` naming the line and the reason, instead of exiting before the checks run. Previously a rejected configuration stopped the command before Doctor produced any output, in exactly the situation Doctor exists for. You can now point Doctor at a configuration you are still fixing
- **BUGFIX:** **Actionable errors while monitoring** - A failed check now prints the same `To fix:` action and `Guide:` link that setup and **`--doctor`** already showed, instead of leaving you with the raw error. **DNS failures** get their own advice naming the real cause rather than being reported as a generic network problem, which matters on devices that start monitoring before the network is up. Transport errors also no longer end with a link to the **libcurl C API documentation**, which buried the actual reason under implementation detail: a failed name lookup now reads `Could not resolve host: www.instagram.com` and says that monitoring resumes on its own once DNS works. Add **`--debug`** when you need the underlying transport detail
- **IMPROVE:** **Consistent Doctor guidance** - Every Doctor failure and warning now ends with a `To fix:` action and, where one applies, a `Guide:` link to the matching documentation page. Session, connectivity and target advice comes from the same hints monitoring uses, so a problem reads the same wherever you hit it
- **BUGFIX:** **Unconfigured notifications are not reported as broken** - Leaving **`WEBHOOK_URL`** at its shipped `your_webhook_url` placeholder now counts as "not configured" instead of failing **`--doctor`** with `Webhook URL is not a complete HTTPS URL`, which happened on a default installation that never set up webhooks. The placeholder is no longer treated as a real destination anywhere, so an enabled webhook that was never filled in reports missing setup once rather than logging a delivery error on every alert. Doctor also checks **`SENDER_EMAIL`** and **`RECEIVER_EMAIL`** before connecting: working SMTP credentials with placeholder addresses used to pass as `Email (SMTP) login works` and then fail on every notification
- **BUGFIX:** **Readable Doctor progress line** - The transient status **`--doctor`** shows while it works now replaces the previous step cleanly. A shorter message left the tail of the longer one behind, producing lines such as `Contacting Instagram ...testuser ...`
- **BUGFIX:** **Older configuration files keep loading** - A configuration file generated by version 3.0 no longer stops startup. It contains `DISCORD_EMBED_DESCRIPTION_LIMIT`, `DISCORD_EMBED_TITLE_LIMIT`, `DISCORD_FIELD_NAME_LIMIT`, `DISCORD_FIELD_VALUE_LIMIT` and `DISCORD_MAX_FIELDS`, which were renamed to their `WEBHOOK_` equivalents in version 3.1 and became an error when configuration files started being parsed rather than executed. Settings a later release removed are now **ignored with a note** telling you which lines you can delete, while a misspelled setting is still reported as an error
- **SECURITY:** **Notification text stays out of request URLs** - ntfy titles and messages are now sent as request headers or as the request body instead of query parameters. Alert text can contain follower names, captions and biographies, and servers and proxies routinely record full URLs in access logs. Webhook requests also no longer follow redirects, so a moved destination cannot collect custom **`WEBHOOK_HEADERS`** intended for the address you configured.
- **SECURITY:** **Clean container security scans** - The runtime image now removes **`pip`** and its unused build-time packages after application dependencies are installed. This removes pip's vendored **`msgpack`** and **`setuptools`** copies behind the two fixable high-severity findings, reduces the software shipped in production and does not change how the image starts.
- **SECURITY:** **Triaged CodeQL boundaries** - Potentially expensive terminal-color, email address and SMTP hostname expressions now use bounded matching or direct parsing without narrowing accepted configuration values. Webhook requests are centralized behind HTTPS validation, certificate verification and redirect refusal, while intentional local dashboard diagnostics and path choices remain explicitly documented for the scanner.
- **SECURITY:** **Dashboard thumbnails load only from this tool** - The **Last Fetched** panel now shows a thumbnail only when the monitor already saved the image locally. Opening the dashboard no longer makes your browser request anything from Instagram's servers, which would reveal your address and link it to the accounts you watch. Items whose download failed show a placeholder.
- **SECURITY:** **Narrower dashboard write surface** - Generated config files must now be named `*.conf`, so that endpoint cannot overwrite a script or a dotfile in your working directory, and the dashboard view mode accepts only its two real values instead of storing any text it is sent. Media file names built from Instagram-supplied post codes are reduced to the characters a real post code uses before they become a path.
- **SECURITY:** **Session import limited to detected profiles** - The Web Dashboard now imports Firefox cookies only from the profiles it detected and listed, so a request cannot point it at another file on your computer. The cookie database path is also encoded before it is opened, so a path containing `?` can no longer append its own SQLite options. A missing file is reported as a normal error instead of an unexpected failure. The `--cookie-file PATH` option is unchanged for deliberate command-line use.
- **SECURITY:** **Pinned release automation** - Every GitHub Actions workflow now pins third-party actions to a specific commit with the version recorded alongside it, so a moved tag cannot change what runs in the jobs that hold publishing credentials. Release tags and workflow inputs reach build scripts through the environment and are checked against the characters an image tag may contain, instead of being pasted into a shell command.
- **SECURITY:** **Configuration files are read, not executed** - A configuration file is now parsed as a list of settings instead of being run as Python. Only `SETTING = value` lines with a recognized setting name and a plain value (text, number, `True`, `False`, `None`, list, tuple or dictionary) are accepted. Imports, function calls and any other code are refused, naming the offending line, and a rejected file applies nothing. Previously the first configuration searched is the one in your **current directory**, so starting the tool inside a downloaded archive or a shared directory containing an `instagram_monitor.conf` would run whatever that file contained. Existing valid configurations, including generated and wizard-written ones, load unchanged.
- **SECURITY:** **Safe media links in the Web Dashboard** - Post, story and thumbnail links supplied by Instagram are now limited to `http` and `https` and escaped before they are shown, matching the activity feed. A crafted media URL can no longer inject markup or a `javascript:` link into the **Last Fetched** panel. Confirmed with a browser test that runs a hostile URL through a real Chromium.
- **BUGFIX:** **Clear impersonation errors** - An unsupported **`CURL_CFFI_IMPERSONATE`** or **`--impersonate`** value now stops the tool at startup with a message naming supported targets, and the Web Dashboard rejects it before saving. Previously it was accepted and every Instagram request then failed as a generic connection error, so the suggested fix pointed at your network instead of the setting.
- **IMPROVE:** **Cheaper human mode** - The BeHuman followee visit now reads only the first page of accounts your session follows before picking one, instead of paginating the entire list. On an account following thousands, one simulated visit previously cost dozens of extra API requests, which worked against the very detection risk the feature exists to reduce.
- **IMPROVE:** **Multi-target monitoring no longer waits on the progress bar** - Targets share one terminal line, so only one follower download can draw a progress bar. A target that starts while another bar is active now fetches immediately without one, instead of waiting for the other download to finish. With batched fetching and long inter-batch delays that wait could previously last many minutes.
- **BUGFIX:** **Faster recovery from a flagged session** - The shared check that distinguishes a deleted target from a blocked session or IP no longer holds its lock across the network request. Other targets hitting the same failure wait for that one result instead of each blocking on a held lock for the length of an Instagram request and its retries. Only one request is still made per interval.
- **BUGFIX:** **Follower churn is reported when the total does not change** - A follow and an unfollow between two checks now logs **Followers list changed** (and the followings equivalent) with the unchanged count. The message existed but could never appear, because it was evaluated before the comparison that detects the change. Notifications were already correct.
- **BUGFIX:** **Terminal restored after quitting the dashboard** - Pressing **q** in the terminal dashboard, or interrupting with Ctrl+C, now restores the terminal's normal typing and echo modes before the tool exits. The keyboard handler switches the terminal out of line mode while running, and that state could previously be left behind on exit.
- **BUGFIX:** **CLEAR_SCREEN is honoured from a config file** - Setting **`CLEAR_SCREEN = False`** in a configuration file now prevents the terminal from being cleared at startup. The screen was previously cleared before the configuration was read, so only the built-in default applied. `COLORED_OUTPUT` is read at the same point, so it also applies to the startup banner.
- **BUGFIX:** **Accurate web dashboard startup errors** - A failure while starting the dashboard server is now reported as a port conflict only when the address really is in use or refused. Other startup failures show their own cause instead of a misleading "port is in use" message.
- **BUGFIX:** **Reliable dashboard media links** - Media still being refreshed each check is no longer dropped from the dashboard's link table ahead of older one-off entries once the 1000-item limit is reached, so **View Media** and **Play Video** keep working during long runs.
- **BUGFIX:** **Working webhook delivery tests** - **`--send-test-webhook`** and the dashboard **Test Webhook** button now send even when the status, followers and errors switches are all off, which is the shipped default. Previously they reported a failure without sending anything or explaining why, so a correct webhook URL looked broken. Real event notifications still follow their configured switches, and a suppressed one is now explained under `--debug`.
- **BUGFIX:** **Human mode without hashtags** - Leaving **`MY_HASHTAGS`** empty now skips only the hashtag request instead of aborting the whole simulation and raising repeated warnings and error notifications. The Explore, profile and followee actions continue to run.
- **BUGFIX:** **Stable long-running dashboard sessions** - Saved settings and session changes now restart a target's monitoring context through a loop instead of re-entering it, so hundreds of live changes in one session can no longer exhaust Python's recursion limit and stop a monitor. A restart after a flagged session also keeps your **`SKIP_FOLLOW_CHANGES`** choice, which it previously reset.
- **SECURITY:** **Image viewer launched without a shell** - Displaying a profile picture, post or story thumbnail through **`IMGCAT_PATH`** no longer builds a shell command string. The viewer is launched with a direct argument list, so a configured viewer path or **`OUTPUT_DIR`** containing shell characters is passed through literally instead of being interpreted.
- **SECURITY:** **Terminal-safe Instagram text** - Biographies, captions, story text, comments and usernames are stripped of terminal control sequences before anything is printed or logged. A crafted profile can no longer clear your screen, retitle your terminal window or overwrite a line you already read. The tool's own colours and normal layout are unchanged.
- **SECURITY:** **Spreadsheet-safe CSV export** - Instagram text starting with `=`, `+`, `-`, `@`, a tab or a carriage return is written with a leading apostrophe, so opening the exported CSV cannot execute a formula a monitored account placed in its biography or caption. Follower and post counts stay numeric.
- **SECURITY:** **Visible container bind change** - Starting the Web Dashboard inside a container still switches the bind address to `0.0.0.0` so Docker can forward traffic, but now says so, shows the `-p 127.0.0.1:PORT:PORT` form that keeps it on your machine and warns what publishing it openly would expose.
- **BUGFIX:** **Reliable follower and following notifications** - Email and webhook alerts now ignore reported count fluctuations only after a complete list comparison confirms that no usernames changed. No-login mode, skipped or failed list fetches and configured fetch limits retain count-change alerts. Webhook and avatar validation also accepts root HTTPS endpoints with or without a trailing slash (closes [#118](https://github.com/misiektoja/instagram_monitor/issues/118) and [#119](https://github.com/misiektoja/instagram_monitor/issues/119))
- **BUGFIX:** **Safe follower and following baselines** - Stopped, interrupted and intentionally limited username downloads no longer overwrite or become the saved comparison baseline. The last complete list remains available for a future complete comparison while reported count monitoring continues.
- **BUGFIX:** **Reliable live dashboard control** - Saved settings and session changes now wake every active target without losing the shared refresh signal. A monitor that does not stop within the timeout retains ownership of its target so a duplicate monitoring thread cannot start.
- **BUGFIX:** **Reliable story and dashboard media state** - New story-item webhooks no longer depend on email notification settings. Consecutive stories, posts and reels start with fresh media state so an item without a download cannot reuse the prior item's file or dashboard URL. Absolute output directories now use registered dashboard media links.
- **BUGFIX:** **Safe atomic media downloads** - Images and videos are streamed to bounded temporary files, checked for complete HTTP 200 delivery and validated by media signature before atomically replacing saved files. Truncated responses, oversized bodies and HTML error pages leave existing files unchanged.
- **BUGFIX:** **Strict live settings** - Web Dashboard updates now reject malformed types, unsafe URLs, invalid ports, out-of-range intervals and reversed hour ranges before changing any live value. Valid interval changes also recompute liveness scheduling immediately.
- **BUGFIX:** **Scoped Instagram jitter** - Human-like delays and long Instagram rate-limit backoff now apply only to Instaloader's Instagram sessions. Webhooks, media downloads and proxy or IP checks remain independent.
- **BUGFIX:** **Safer browser sessions** - Firefox fallback cookie imports accept only `instagram.com` and real subdomains instead of suffix lookalikes. Clearing a dashboard session removes canonical and supported legacy Instaloader files.
- **SECURITY:** **Protected Web Dashboard requests** - The dashboard now answers only requests addressed to `127.0.0.1`, `localhost`, `::1` or your configured `WEB_DASHBOARD_HOST`, so a web page that points its own domain at your machine can no longer reach it through your browser. Anything that changes state must come from the dashboard page itself and send `Content-Type: application/json`, so another site can no longer stop your monitoring, force extra Instagram polling, clear your activity log or fire test notifications. Rejected requests return **HTTP 403** or **HTTP 415**. The new **`WEB_DASHBOARD_ALLOWED_HOSTS`** setting lists extra names you deliberately open the dashboard at, and the single entry `"*"` restores the previous accept-any behavior. Scripts that call the API keep working when they address `127.0.0.1` and send a JSON content type.
- **SECURITY:** **Saved credentials stay with their destination** - Changing **`SMTP_HOST`** or **`SMTP_PORT`** from the dashboard without typing the password again now clears the saved SMTP password instead of offering it to the new mail server. Re-enter it in the same save to keep email working. Pointing **`WEBHOOK_URL`** at a different server likewise clears **`NTFY_ACCESS_TOKEN`**, which is sent to that destination as a bearer credential. Changing only the ntfy topic on the same server keeps the token. The dashboard **CSV file name** field also accepts a file name only, so it can no longer choose where the monitor writes. An absolute `CSV_FILE` path set in the config or with `-b` keeps working and still round-trips through the form unchanged.
- **SECURITY:** **Loopback dashboard data boundaries** - Dashboard media URLs now serve only files registered by the monitor. Webhook and proxy URLs stay out of settings responses, usernames are validated before reaching paths or rendered actions and clearing a session removes supported Instaloader session locations without accepting path-like usernames. The dashboard still has no login screen and should stay bound to `127.0.0.1`.
- **SECURITY:** **Notification HTML boundaries** - Instagram-controlled biographies, captions, mentions, hashtags, locations, usernames and comments are escaped before entering HTML email bodies.
- **IMPROVE:** **Clearer ntfy webhook customization** - The generated configuration now states that **`WEBHOOK_TEMPLATE`**, **`WEBHOOK_USERNAME`** and **`WEBHOOK_AVATAR_URL`** apply only to Discord and are ignored by ntfy, which needs no template. Customize ntfy delivery through **`WEBHOOK_HEADERS`** such as `X-Priority` or `X-Tags`.

# Changes in 3.8.1 (04 Aug 2026)

Version **3.8.1** streamlines first-time setup and diagnostics, adds portable logs and prevents webhook noise from repeated monitoring failures.

**Features and improvements**:

- **IMPROVE:** **Clear timezone recovery** - When automatic detection fails, the startup error now identifies the optional `tzlocal` dependency, shows how to install it and explains that `LOCAL_TIMEZONE` can be set manually
- **IMPROVE:** **Portable log separators** - The new `ASCII_LOG_SEPARATORS` setting controls whether separator-only lines saved to log files use ASCII hyphens. `"Auto"` enables them on Windows by default, `"On"` enables them on every operating system and `"Off"` preserves Unicode separators. Terminal separators stay Unicode. Log files and all other logged text remain UTF-8.
- **IMPROVE:** **Flexible setup intervals** - The setup wizard accepts polling interval durations such as `30s`, `2m`, `1.5h`, `1h 30m` and `1d` while still saving the value as seconds
- **IMPROVE:** **Actionable Doctor output** - Details remain attached to their checks, final target-specific log destinations are validated and `pycookiecheat` is clearly identified as a Chromium-only import dependency that Firefox does not need
- **IMPROVE:** **Beginner Python installation walkthroughs** - New Windows, macOS and Linux instructions guide first-time Python users from checking prerequisites through installation and the setup wizard

**Bug fixes**:

- **BUGFIX:** **Thresholded monitoring alerts** - `ERROR_FAILURE_THRESHOLD` now applies consistently to email and webhook errors so repeated session failures alert once at the configured count instead of sending a webhook on every retry. Alerts for flagged sessions remain immediate (closes [#116](https://github.com/misiektoja/instagram_monitor/issues/116))

# Changes in 3.8 (30 Jul 2026)

Version **3.8** strengthens **Discord and ntfy webhook delivery**, adds safer **private URL setup**, improves **proxy IP detection** and brings better notification controls.

**Features and improvements**:

- **IMPROVE:** Added ordered **proxy IP lookup fallback endpoints** with backward-compatible single-URL configuration, IPv4 and IPv6 validation plus documented privacy controls (thanks [@tomballgithub](https://github.com/tomballgithub), from [#113](https://github.com/misiektoja/instagram_monitor/pull/113))
- **NEW:** Added private **webhook URL setup** through `--set-webhook-url` with hidden entry and complete HTTPS destination validation
- **IMPROVE:** Added stricter **webhook request validation** for destinations, avatars, templates, transforms and expanded headers plus Discord mention suppression
- **IMPROVE:** Added **bounded webhook delivery** with isolated requests, capped rate-limit delays, one retry for temporary failures and automatic provider correction across CLI, Doctor and Web Dashboard flows
- **IMPROVE:** Added **native ntfy image attachments** with a 5 MiB limit and automatic text-only fallback when image preparation or upload fails
- **IMPROVE:** Made the **status, follower and error webhook controls** enable webhook delivery for the current run
- **IMPROVE:** Split the startup notification summary into compact **email and webhook rows** across concise, verbose and logged views

**Bug fixes**:

- **BUGFIX:** Stopped startup summaries and Web Dashboard setting-change logs from writing private webhook URLs to logs
- **BUGFIX:** Kept long ntfy messages below its 4 KB attachment boundary, added a visible truncation explanation and preserved complete UTF-8 characters
- **BUGFIX:** Restored green `On` and red `Off` status cues in compact notification rows without coloring category text
- **BUGFIX:** Made `SIGHUP` apply rotated proxy credentials to active Instaloader sessions and redetect Discord or ntfy when the private webhook destination changes
- **BUGFIX:** Made proxy IP failover try every configured endpoint before the long retry delay, reject invalid successful responses without crashing and preserve custom endpoint lists in generated configuration

# Changes in 3.7.1 (24 Jul 2026)

**Bug fixes**:

- **BUGFIX:** Updated the built-in guide link to the renamed **Setup & First Run** page so CLI help and recovery guidance no longer point to the retired Quick Start URL

# Changes in 3.7 (23 Jul 2026)

Version **3.7** makes **Docker onboarding portable across macOS, Linux and Windows**. It adds **host-aware Firefox session import** and keeps setup files safe on the persistent **`/data` bind mount**. Generated recovery commands now preserve **targets, custom files and Web Dashboard ports** from import through Doctor and launch.

**Features and improvements**:

- **IMPROVE:** Kept Firefox session import as the **recommended Docker setup choice** while deferring the import until setup files are saved. The wizard now asks which host environment runs Docker then prints the matching read-only import command for macOS, standard Linux, Snap, Flatpak, Windows PowerShell or Windows Command Prompt
- **NEW:** Added **Windows-host Firefox session import** for direct Docker and Docker Compose through the normal `%APPDATA%\Mozilla\Firefox` profile root with shell-specific PowerShell and Command Prompt commands
- **IMPROVE:** Expanded direct Docker and Docker Compose Firefox import documentation with **complete commands for every supported host profile layout**
- **IMPROVE:** Preserved **setup guidance across one-time session imports** by keeping terminal history visible and repeating the exact Doctor and monitoring commands after a successful Firefox import
- **IMPROVE:** Printed the **install-aware monitoring command** after a successful Doctor run while preserving explicit targets, selected files and Web Dashboard port publishing

**Bug fixes**:

- **BUGFIX:** Stopped the setup wizard from offering **Doctor before a deferred Firefox session import succeeds**, avoiding expected authentication failures during incomplete Docker setup
- **BUGFIX:** Removed **Linux user mapping from generated macOS Docker commands** while preserving host UID and GID mapping for Linux commands
- **BUGFIX:** Anchored **default container setup files** to the bind-mounted **`/data` directory** so the generated configuration and dotenv files survive the temporary setup container
- **BUGFIX:** Preserved **Web Dashboard port publishing** in Docker and Docker Compose monitoring commands printed after Firefox import then replaced container-only `0.0.0.0` browser links with the reachable loopback URL
- **BUGFIX:** Rejected **Docker setup destinations outside `/data`** instead of saving ephemeral files then printing commands for different paths
- **BUGFIX:** Generated direct Docker commands with **`${PWD}` for macOS, Linux and Windows PowerShell** then switched to `%cd%` for Windows Command Prompt while retaining Linux user mapping
- **BUGFIX:** Prevented local setup from offering **immediate monitoring after a declined or failed browser import** unless Doctor validates an existing session
- **BUGFIX:** Rejected **conflicting standalone actions and setup targets** instead of silently ignoring part of the command
- **BUGFIX:** Matched generated Docker and one-off Compose port publishing to a **non-default Web Dashboard port**
- **BUGFIX:** Restricted terminal time highlighting to valid complete clock values so Docker mappings such as `8000:8000` are no longer partially colored as dates
- **BUGFIX:** Prevented a **Windows traceback after Ctrl+C** when monitoring was started directly from setup. The setup parent now treats its duplicate console interrupt as the same clean termination already handled by the monitoring child

# Changes in 3.6.1 (22 Jul 2026)

**Features and improvements**:

- **IMPROVE:** Added automatic Firefox profile discovery for native Linux, Snap and Flatpak installations. CLI and Web Dashboard session imports now locate all three layouts and de-duplicate cookie databases
- **IMPROVE:** Improved CLI and `--doctor` recovery guidance with installation-aware Firefox session import commands and direct links for session, rate-limit, proxy, SMTP, webhook and configuration errors

**Bug fixes**:

- **BUGFIX:** Made the Compose service pass `/data/.env` explicitly so `docker compose up` loads saved secrets even when config does not set `DOTENV_FILE`

# Changes in 3.6 (22 Jul 2026)

Version **3.6** focuses on flexible, dependable notifications and safer guided configuration. It adds native ntfy support with protected-topic authentication, interactive delivery checks in `--doctor` and an editable setup summary, while preserving Discord compatibility and strengthening Docker defaults, saved launch behavior and Web Dashboard exposure.

**Features and Improvements**:

- **NEW:** Added native **ntfy webhook notifications** for status, follower and error events. Set `WEBHOOK_PROVIDER = "ntfy"` and save a complete ntfy topic URL in `WEBHOOK_URL` or select ntfy in the setup wizard or Web Dashboard. The setup wizard also accepts a bare ntfy.sh topic name and expands it to a complete URL
- **NEW:** Added **authentication for protected ntfy topics** via `NTFY_ACCESS_TOKEN` support with Bearer authentication, hidden setup wizard collection and precedence over custom `Authorization` headers in `WEBHOOK_HEADERS`
- **IMPROVE:** Preserved Discord as the default webhook provider for backward compatibility, including custom payload templates, headers, transformations, proxy routing and Discord image attachments
- **IMPROVE:** Added provider validation to `--doctor`, provider visibility in startup and dashboard summaries plus a `--webhook-provider {discord,ntfy}` command-line option
- **IMPROVE:** Extended interactive **`--doctor`** runs with separate tests for email and webhook channels. Each approved test sends one real message. Doctor never writes files and non-interactive runs remain message-free
- **IMPROVE:** Sent native ntfy messages as bounded UTF-8 text with the alert subject as the title, event field details in the body and existing topic query parameters preserved for authentication
- **IMPROVE:** Added an editable setup summary so answers can be reviewed before saving
- **IMPROVE:** Simplified browser onboarding with separate Firefox and Chromium choices plus optional `pycookiecheat` installation
- **IMPROVE:** Made generated commands portable across Python installations and custom config paths
- **IMPROVE:** Added confirmation, backups and validation when replacing configuration files
- **BUGFIX:** No-argument launches now honor saved targets and Web Dashboard mode
- **BUGFIX:** Improved Docker and Compose support for Linux user mappings, persistent sessions and saved interface choices
- **SECURITY:** Limited Docker Web Dashboard publishing to the host loopback interface

# Changes in 3.5 (01 Jul 2026)

Version **3.5** focuses on making the tool easier to use, configure and recover when something goes wrong, especially for non-technical users who asked for a simpler path. It brings guided setup, broader browser-session import, clearer diagnostics and friendlier recovery hints so first runs and everyday troubleshooting require less manual digging.

**Features and Improvements**:

- **NEW:** Added an **interactive setup wizard** to make first-time setup easy for non-technical users. Run it with the `--setup` flag or launch the tool with no arguments from an interactive terminal and accept the prompt. The wizard asks a short series of questions, then writes a ready-to-run `instagram_monitor.conf`, routes secrets to a `.env` file and can start monitoring right away for local installs. It auto-detects whether the tool was installed via pip, run from a downloaded script, run under Docker or run via Docker Compose and tailors the suggested commands accordingly
- **NEW:** Added **session import from Chromium-based browsers** (Chrome, Brave and Chromium) in addition to Firefox, via the new `--import-browser-session --browser {firefox,chrome,brave,chromium}` flags and a browser dropdown on the **Web Dashboard** Session page. Firefox stays the recommended source as it requires no additional dependencies, while Chromium-based browsers use the optional [`pycookiecheat`](https://github.com/n8henrie/pycookiecheat) package and work on macOS and Linux only. On Windows, where Chrome's app-bound encryption (Chrome 127+) blocks external cookie access, the tool detects the platform and recommends Firefox instead.
- **NEW:** Added **unified per-profile selection across all browsers**. A single `--browser-profile` flag now picks a profile for any browser - a Firefox profile name (e.g. `default-release`) or a Chromium profile directory (e.g. `Default`, `Profile 1`) - with an interactive prompt when several exist and a profile picker on the Web Dashboard import flow. `--cookie-file` is the advanced explicit-database override for every browser. For Chromium-based browsers the cookie database is resolved directly, so both the legacy `<profile>/Cookies` and the newer `<profile>/Network/Cookies` layouts work
- **NEW:** Added an **ASCII art startup banner** that prints on launch. It uses pure ASCII for broad terminal compatibility and follows the configured color theme, replacing the previous plain one-line version header
- **IMPROVE:** The **startup summary** now prints a **concise view** on the terminal that leads with the monitored targets and hides settings left at their default or turned off, so the banner stays on screen and the key details (targets, session mode, polling interval, where output goes) are no longer buried in noise. The full configuration is still written to the log for troubleshooting and can be shown on the terminal with `--verbose`/`--debug`
- **NEW:** Added an **animated demo** (install, setup wizard and run) at the top of the README and docs home, generated from a committed [VHS](https://github.com/charmbracelet/vhs) tape ([demo.tape](demo/demo.tape)) so it can be re-rendered as the tool evolves
- **NEW:** Added a **[docker-compose.yml](docker-compose.yml)** and a **[.env.example](.env.example)** so Docker users can get started with `docker compose up` instead of long `docker run` commands, with secrets kept in a copyable dotenv template
- **IMPROVE:** Running the tool with **no arguments** from an interactive terminal now shows a **short welcome with the most common commands** and an offer to launch the setup wizard, instead of dumping the full help text
- **NEW:** Published a **documentation site** at [misiektoja.github.io/instagram_monitor](https://misiektoja.github.io/instagram_monitor/), built with MkDocs Material and deployed via GitHub Actions. The README is now a concise landing page and the full reference guide
- **IMPROVE:** The Web Dashboard now shows an actionable **"No targets yet"** empty state with an Add Target button instead of a permanent "Loading targets..." placeholder when no targets are configured
- **IMPROVE:** A broken hand-edited config file now reports the **offending line and a `To fix:` hint** instead of a raw traceback
- **NEW:** Added a **`--doctor` preflight self-check**. Version 3.5 introduced it as a read-only PASS/WARN/FAIL report with no email or webhook delivery. It covers optional dependencies, the config file and secrets, session validity, Instagram connectivity, target resolution and notification configuration with a `To fix:` next step on each failure plus a non-zero exit code if any check fails. The setup wizard offers to run it at the end
- **IMPROVE:** Added **action-oriented error hints**. Common failures (invalid or expired session, challenge/checkpoint, rate limiting, missing session file, target not found, network problems, SMTP and webhook delivery errors) now print a concise `To fix:` next step instead of just the raw error
- **IMPROVE:** Renamed the session modes from numbered **Mode 1 / Mode 2** to intent-based **No-login** and **Logged-in** across console output, the Web Dashboard, the config template and the README, so you no longer have to remember which number means what
- **IMPROVE:** Added an **examples section to `--help`** with copy-pasteable commands for guided setup, anonymous tracking, logged-in tracking and the web dashboard. The examples auto-detect how the tool was launched (pip, downloaded script, Docker or Docker Compose) and print matching commands the same way the setup wizard does
- **IMPROVE:** The old `--import-firefox-session` flag is kept as a backward-compatible alias for `--import-browser-session --browser firefox`
- **IMPROVE:** Expanded the **offline pytest suite** to increase coverage of critical monitoring workflows, including webhook delivery, paginated follower/following fetching, Web Dashboard endpoints, posts/reels count detection, leaked-collab reporting, profile-picture creation/removal/change handling, install-method detection and startup story item metadata/CSV updates.
- **IMPROVE:** Suppressed **Instaloader's intermittent retry noise** (the repeated `JSON Query to graphql/query: 403 Forbidden ...` lines it prints to stderr) during normal runs and the `--doctor`/`--setup` preflight, since those attempts usually succeed on a later try. The final failure is still shown, while verbose or debug mode keeps the full chatter

**Bug fixes**:

- **BUGFIX:** Repaired **logged-in post and reel fetching** after Instagram retired the GraphQL `doc_id 8845758582119845` (`xdt_shortcode_media`) in June 2026, which returned null data and crashed `Post._obtain_metadata` with `TypeError: 'NoneType' object is not subscriptable` as soon as a field outside the timeline node (such as tagged users) was read. Added a compatibility patch that migrates to `doc_id 27128499623469141` (`PolarisPostRootQuery`) and reshapes the response to the legacy fields (ports [instaloader/instaloader#2706](https://github.com/instaloader/instaloader/pull/2706), see [#2704](https://github.com/instaloader/instaloader/issues/2704))
- **BUGFIX:** Guarded **`latest_post_reel`** against a null GraphQL `data` response so a deprecated query or a temporary block surfaces a clean, actionable `To fix:` message instead of a raw `TypeError`

# Changes in 3.4 (16 Jun 2026)

**Features and Improvements**:

- **NEW:** Added a **pluggable HTTP transport backend** with browser TLS (JA3/JA4) impersonation via [curl_cffi](https://github.com/lexiforest/curl_cffi), now the default, to avoid fingerprint-based blocks where Instagram returns a spurious `HTTP 429` on the very first request even from a clean IP (most often on Linux OS TLS stacks whose fingerprint Instagram treats as automation). Both the anonymous and logged-in paths use the selected backend and it transparently falls back to `requests` when curl_cffi is unavailable. Configurable via the `HTTP_BACKEND` / `CURL_CFFI_IMPERSONATE` config options or the `--http-backend` / `--impersonate` flags, with `CURL_CFFI_IMPERSONATE` defaulting to `auto` so the impersonated browser is aligned with the configured user agent, keeping the TLS and client-hint headers consistent (including with a Firefox-imported session)
- **NEW:** Added **detection of leaked collab posts on private accounts** (enabled by default). When a private account co-authors a post with a public account, that post stays visible in the private account's timeline media via the public `web_profile_info` endpoint. The monitor surfaces these otherwise hidden posts (with owner, collaborators, media download and notifications) and reports new ones over time, even for accounts you do not follow. Only probes accounts whose posts are not otherwise viewable. Disable via the `DETECT_COLLAB_POSTS` config option or the `--no-detect-collab-posts` flag. Inspired by [InstagramPrivSniffer](https://github.com/obitouka/InstagramPrivSniffer)
- **IMPROVE:** The anonymous post path now populates **tagged users and co-authors** from `web_profile_info` instead of leaving the list empty
- **IMPROVE:** Centralized repeated timestamp label and newline handling in `print_cur_ts()` (thanks [@tomballgithub](https://github.com/tomballgithub), from [#100](https://github.com/misiektoja/instagram_monitor/pull/100))
- **IMPROVE:** Added Jinja2 as a direct dependency for Web Dashboard template rendering

**Bug fixes**:

- **BUGFIX:** Fixed the configured proxy and TLS certificate settings being dropped on the anonymous mobile profile lookup (`web_profile_info`), which caused that request to bypass the proxy and go out over the real IP
- **BUGFIX:** Restored the progress bar unit label after paused follower/following batch waits so later progress output keeps the expected label (thanks [@tomballgithub](https://github.com/tomballgithub), from [#103](https://github.com/misiektoja/instagram_monitor/pull/103))
- **BUGFIX:** Fixed **flagged-account detection** not sending email or webhook alerts. The notification was gated behind `ERROR_FAILURE_THRESHOLD` so the script terminated before the count was reached. A flagged session or IP now alerts the operator immediately, bypassing the threshold and de-duped so one shared flag alerts once across all monitored targets (fixes [#108](https://github.com/misiektoja/instagram_monitor/issues/108))

# Changes in 3.3 (01 Jun 2026)

Huge thanks to everyone who contributed to this release, with a special shout-out to [@tomballgithub](https://github.com/tomballgithub) who drove most of the work behind these changes and to [@BlueXAyman](https://github.com/BlueXAyman) for the Instaloader GraphQL profile metadata patch.

**Features and Improvements**:

- **NEW:** Added **proxy support** for routing Instagram and webhook traffic through a proxy, with an optional client certificate, automatic masking of proxy credentials in output, runtime toggling without a restart and support for multiple IP-lookup services (`--enable-proxy` / `--proxy-url` / `--proxy-cert` / `--enable-proxy-webhooks` flags or the matching `PROXY_*` config options)
- **NEW:** Added **privacy substitution** support to redact or replace monitored target identities (display names, usernames, captions) across console output, logs, dashboards and webhook payloads, applied at display time so the real identity is never leaked
- **NEW:** Added **shadowban and flagged-account detection**, including a canonical-account probe that distinguishes a removed or renamed account from a temporarily flagged one and smarter logic on whether to keep idling or exit while an account is flagged (closes [#78](https://github.com/misiektoja/instagram_monitor/issues/78))
- **NEW:** Added **advanced control over fetching followers and followings**, with batched fetching, configurable total limits and correct handling of stop and recheck events during long fetches
- **NEW:** Added a **`SKIP_WRAP_MESSAGES`** config option to suppress the wrap messages emitted during request monkey-patching
- **IMPROVE:** Hardened **IP-address lookups** with retries, interruptible backoff waits and credential masking, plus extra retries when the proxy is temporarily unavailable
- **IMPROVE:** Switched elapsed-time tracking to a **monotonic timer** for accurate runtime statistics
- **IMPROVE:** Refined the **progress bar**: fit its text during PAUSE, show remaining time above two hours in hours rather than minutes, drop decimals from minute and hour values and handle PAUSED states more robustly
- **IMPROVE:** Hardened type handling across the code base to satisfy static type checking with pyright
- **IMPROVE:** Enforced **gitleaks secret scanning** in CI, added **Dependabot** version updates and bumped the Docker base image and GitHub Actions dependencies
- **IMPROVE:** Added an **offline test suite** (pytest) covering config parsing, time formatting, scheduling windows, privacy substitutions, notification helpers, follower diffing, CSV writing and session-flag detection, with no network access, running automatically in CI across Python 3.9 to 3.14

**Bug fixes**:

- **BUGFIX:** Added a compatibility **patch for Instaloader GraphQL profile metadata** to fix 400 Bad Request on GraphQL query: invalid request when using session mode
- **BUGFIX:** Decoupled follower/following **webhook notifications** from the email notification flags so they fire independently and only when something actually changed
- **BUGFIX:** Fixed **`hours_to_check()`** behavior when the feature is disabled (fixes [#80](https://github.com/misiektoja/instagram_monitor/issues/80))
- **BUGFIX:** Guarded against **`posts_count`** being `None` during post-count comparisons
- **BUGFIX:** Hardened **`update_ui_data`** debug formatting against non-dict payloads

# Changes in 3.2 (10 Apr 2026)

**Features and Improvements**:

- **NEW:** Added Docker support with a slim runtime image (closes [#13](https://github.com/misiektoja/instagram_monitor/issues/13) and [#75](https://github.com/misiektoja/instagram_monitor/issues/75))
- **NEW:** Implemented separate error counters for BeHuman simulation and the main monitoring loop
- **IMPROVE:** Added configurable failure threshold and improved alerting for Instagram human mode issues (closes [#63](https://github.com/misiektoja/instagram_monitor/issues/63))
- **IMPROVE:** Improved progress bar stability and output handling with thread-safe suppression and safer width bounds (thanks [@tomballgithub](https://github.com/tomballgithub), from [#69](https://github.com/misiektoja/instagram_monitor/pull/69))
- **IMPROVE:** Improved progress bar ETA and rate calculations for early updates (thanks [@tomballgithub](https://github.com/tomballgithub), from [#69](https://github.com/misiektoja/instagram_monitor/pull/69))
- **IMPROVE:** Suppressed noisy TLS-on-HTTP Werkzeug parse logs in console output (fixes [#67](https://github.com/misiektoja/instagram_monitor/issues/67))
- **IMPROVE:** Added GitHub Actions workflow for publishing packages to PyPI and auto-building/attaching zip and tar.gz assets to published releases

**Bug fixes**:

- **BUGFIX:** Used nominal interval for human-mode probability on restricted schedules (fixes [#64](https://github.com/misiektoja/instagram_monitor/issues/64))
- **BUGFIX:** Triggered error notifications exactly at the configured failure threshold (fixes [#71](https://github.com/misiektoja/instagram_monitor/issues/71))
- **BUGFIX:** Made single-target recheck state consistent and returned accurate recheck-all status (fixes [#68](https://github.com/misiektoja/instagram_monitor/issues/68))
- **BUGFIX:** Avoided joining current or main thread in target stop path (fixes [#73](https://github.com/misiektoja/instagram_monitor/issues/73))
- **BUGFIX:** Normalized non-ASCII characters to avoid output issues (fixes [#76](https://github.com/misiektoja/instagram_monitor/issues/76))
- **BUGFIX:** Ensured request monkey-patch is applied when progress bar setup is initialized (fixes [#77](https://github.com/misiektoja/instagram_monitor/issues/77))
- **BUGFIX:** Made requests monkey-patch setup thread-safe for progress bar jitter and serialized HTTP paths
- **BUGFIX:** Restored anonymous profile lookup on Instaloader 4.15.1 via `web_profile_info` fallback

# Changes in 3.1 (07 Feb 2026)

**Features and Improvements**:

- **NEW:** Implemented custom **webhook configuration support** allowing custom templates and headers, defaults to Discord compatibility (thanks [@tomballgithub](https://github.com/tomballgithub));
- **IMPROVE:** Enhanced **request jitter** with **exponential backoff** and improved **429 error handling**
- **IMPROVE:** Improved **webhook robustness** with retries and custom User-Agent
- **IMPROVE:** Updated **human mode display** to include verbosity option
- **IMPROVE:** Updated **webhook URL validation** to accept both HTTP and HTTPS schemes

**Bug fixes**:

- **BUGFIX:** Corrected **timestamp issue** in debug mode (fixes [#62](https://github.com/misiektoja/instagram_monitor/issues/62))
- **BUGFIX:** Prevented **deadlock** in `close_pbar` by making STDOUT_LOCK re-entrant (fixes [#60](https://github.com/misiektoja/instagram_monitor/issues/60))
- **BUGFIX:** Ensured **verbose flags** display messages independently of debug mode (fixes [#59](https://github.com/misiektoja/instagram_monitor/issues/59))
- **BUGFIX:** Handled **empty caption edges** in mobile API to prevent index error in anonymous mode
- **BUGFIX:** Added **input validation bounds**, safe thread cleanup and reels_count null checks

# Changes in 3.0 (23 Jan 2026)

Welcome to version **3.0** — our biggest and most ambitious release to date! This update introduces a completely redesigned experience with a powerful new **Dual Dashboard system** (Web and Terminal), **Webhook / Discord notifications**, native **Color support**, custom **Output directory** feature and advanced **Follower Churn detection**.

A huge thank you to our amazing contributors [@Sha-Dox](https://github.com/Sha-Dox), [@tomballgithub](https://github.com/tomballgithub), [@YouveGotMeowxy](https://github.com/YouveGotMeowxy) and [@jl-nr](https://github.com/jl-nr) for their invaluable code, ideas and testing that made this release possible.

![Web dashboard screenshot](https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard.png)

**Features and Improvements**:

- **NEW:** Added a comprehensive **dashboard system** accessible in terminal and web, including a Rich-powered **Terminal Dashboard** and a Flask-powered **Web Dashboard** with real-time stats, activity feeds and interactive controls; check the [Terminal Dashboard](https://misiektoja.github.io/instagram_monitor/view-modes/#terminal-dashboard-mode) and [Web Dashboard](https://misiektoja.github.io/instagram_monitor/view-modes/#web-dashboard-mode) for more info
- **NEW:** Added **webhook notifications** system compatible with **Discord** and other webhook services for all monitored events with support for sending local image files; check the [Webhook Notifications](https://misiektoja.github.io/instagram_monitor/usage/#webhook-notifications) for more info
- **NEW:** Implemented native **color output** support for terminal, enhancing user experience with customizable **color themes** (see `COLORED_OUTPUT` and `COLOR_THEME` config options). You can still use the old **grc** method if you prefer to only color the logs
- **NEW:** Added **follower churn detection** (`--followers-churn` flag or `FOLLOWERS_CHURN_DETECTION` config option) - forces the tool to download and compare the full list of followers/followings even if the total count hasn't changed, allowing the detection of user handle changes or simultaneous additions and removals; check the [Follower Churn Detection](https://misiektoja.github.io/instagram_monitor/usage/#follower-churn-detection) for more info
- **NEW:** Added **custom output directory** feature to organize all files into target-specific subdirectories (**images**, **videos**, **logs**, **json**, **csvs**) which significantly improves organization for multi-target monitoring; check the [Output Directory](https://misiektoja.github.io/instagram_monitor/usage/#output-directory) for more info (closes [#35](https://github.com/misiektoja/instagram_monitor/issues/35))
- **NEW:** Added **skip follow changes** option (`--skip-follow-changes` flag or `SKIP_FOLLOW_CHANGES` config option) - allows to completely silence and disable follow-related tracking (console prints, activity logs, email/webhook notifications and CSV saving) while still maintaining live statistics in the dashboards; note that enabling this automatically disables **follower churn detection** as detailed tracking is suppressed; check the [Skipping Follow Changes](https://misiektoja.github.io/instagram_monitor/usage/#skipping-follow-changes) for more info
- **NEW:** Implemented **debug mode** (`--debug` flag or `DEBUG_MODE` config option) - provides full technical logging including every API request and internal state changes
- **NEW:** Introduced **verbose mode** (`--verbose` flag or `VERBOSE_MODE` config option) - provides a middle-ground logging level that shows timing details, next check schedule and loop completion messages without the exhaustive detail of Debug Mode
- **NEW:** Added support for **12-hour time format** (`TIME_FORMAT_12H` config option) across the entire tool including dashboards, console output, activity logs and email notifications
- **NEW:** Implemented **HTML formatting** for **email notifications** for better readability
- **NEW:** Added **dashboard view modes** - toggle between **'User'** and **'Config'** modes across both dashboards with a single keypress ('m') or button click; includes synchronized state throughout the tool
- **NEW:** Implemented **per-target logging** - in multi-target mode, each user gets their own log file; common messages (like the summary screen) are automatically broadcasted to all active logs
- **IMPROVE:** Enhanced **CSV path resolution** - CSV files are now automatically placed in a `csvs/` subdirectory when `OUTPUT_DIR` and relative path is used. In **multi-target mode**, the tool always enforces **per-user files** (even with absolute paths) to ensure data isolation
- **IMPROVE:** Enhanced `CHECK_POSTS_IN_HOURS_RANGE` logic to support **disabling hour ranges** and updated status message (to disable any range, set both `MIN` and `MAX`to 0);

... and many other improvements (check the list of commits for the release if you are interested)

**Bug fixes**:

- **BUGFIX:** Fixed recent post detection logic in anonymous mode (fixes [#34](https://github.com/misiektoja/instagram_monitor/issues/34))
- **BUGFIX:** Expanded tabs to spaces in log files for consistent alignment

# Changes in 2.0.4 (04 Jan 2026)

**Features and Improvements**:

- **IMPROVE:** standardized **visual appearance** of **progress bar** to unify its width in both terminal and log files

**Bug fixes**:

- **BUGFIX:** Fixed **progress bar display issues** - Ensured `close_pbar()` is called before any print statements in the `try` block to prevent interleaved output and duplicate progress bars (thanks [@tomballgithub](https://github.com/tomballgithub))

# Changes in 2.0.3 (03 Jan 2026)

**Features and Improvements**:

- **NEW:** **Multi-user monitoring in a single process** - Monitor multiple Instagram users simultaneously without spawning separate processes. Simply pass multiple usernames as arguments or use the `--targets` flag with comma-separated values
- **NEW:** **Automatic request staggering** - When monitoring multiple users, requests are automatically spread across the **check interval** to avoid triggering **Instagram's anti-bot mechanisms**. Configurable via `MULTI_TARGET_STAGGER` or `--targets-stagger` flag
- **NEW:** **Progress bar for downloading followers/followings** - When fetching lists of followers or followings, a real-time progress bar is displayed showing download progress, statistics (names per request, total requests, elapsed time, estimated remaining time) and completion status. Progress updates are shown in the terminal only (to avoid log file clutter), with the final state written to the log file for reference (thanks [@tomballgithub](https://github.com/tomballgithub))
- **NEW:** **Per-user CSV files in multi-target mode** - When monitoring multiple users, each user gets their own **CSV file** (e.g., `instagram_data_user1.csv`, `instagram_data_user2.csv`) using the configured CSV filename as a prefix. **Single-user mode** continues to use the exact filename specified
- **NEW:** **Improved log file naming** - **Multi-target log files** now use **sorted usernames** joined with underscores (e.g., `instagram_monitor_user1_user2_user3.log`), preventing **filename collisions** when monitoring different user sets
- **NEW:** **Per-thread output buffer** - Enhanced **redirect detection** to use **thread-specific output buffers**, ensuring accurate **session error detection** in **multi-target mode**
- **IMPROVE:** **Enhanced session error notifications** - **Session error emails** now include both the **session account** (logged-in user or anonymous) and the **target user** that triggered the error, providing better context for debugging
- **NEW:** Added `MULTI_TARGET_STAGGER`, `MULTI_TARGET_STAGGER_JITTER`, and `MULTI_TARGET_SERIALIZE_HTTP` configuration options for fine-tuning **multi-target behavior**
- **NEW:** Added `TARGET_USERNAMES` configuration option to specify multiple targets in **config file** (**CLI arguments** take precedence)
- **IMPROVE:** **Thread-safe logging** with lock protection to prevent **interleaved output** when multiple targets write simultaneously
- **IMPROVE:** **File save messages** now include the **username** (e.g., *"Story video saved for {user} to '{filename}'"*) for better clarity when monitoring **multiple users**
- **IMPROVE:** Enhanced **error messages** for **Instagram challenge/shadow ban detection** - when Instagram requires a challenge/re-login or temporarily shadow bans the IP, error messages now provide clear, informative explanations instead of cryptic **KeyError 'data'** messages
- **IMPROVE:** **Follower/following count comparison** - Enhanced display of reported vs actual follower/following counts with improved accuracy by refreshing profile data after fetching lists to ensure current reported counts are compared with actual fetched counts (thanks [@tomballgithub](https://github.com/tomballgithub))
- **IMPROVE:** **Enhanced initialization progress messages** - During script initialization, progress messages now show what's happening during profile loading, including loading profile from username, fetching reels count (when applicable), checking for stories (when applicable) and loading own profile (when logged in). This provides better visibility into the initialization process and helps with debugging account ban issues (thanks [@tomballgithub](https://github.com/tomballgithub))
- **IMPROVE:** **Standardized formatting** in print statements

**Bug fixes**:

- **BUGFIX:** Fixed **redirect detection buffer** that was using broken shared/local variable logic, now properly uses **per-thread output tracking**
- **BUGFIX:** Fixed **follower/following count comparison logic** - Removed inefficient helper functions that were fetching full lists just to get counts, simplified comparison function with proper type hints and fixed order of operations to ensure accurate reported vs actual count comparisons

**Dependencies**:

- **NEW:** Added **tqdm** dependency for **progress bar** functionality

# Changes in 1.9.1 (18 Dec 2025)

**Features and Improvements**:

- **IMPROVE:** Enhanced `CHECK_POSTS_IN_HOURS_RANGE` logic: hour ranges now gate **fetching updates** (not just posts/reels), covering additional monitored activity (thanks [@tomballgithub](https://github.com/tomballgithub))
- **NEW:** Added `HOURS_VERBOSE` for debugging hour-based update gating (prints whether updates are **fetched** or **skipped**) (thanks [@tomballgithub](https://github.com/tomballgithub))
- **IMPROVE:** Refactored **hour-range calculations**: de-duplicate overlapping ranges, ignore invalid hours and prevent crashes on misconfiguration
- **IMPROVE:** Improved **Be Human** action probability when **hour-range mode** is enabled (scales to the configured **active-hour window**) (thanks [@tomballgithub](https://github.com/tomballgithub))
- **IMPROVE:** Added **messaging for sleep time** if HOURS_VERBOSE is enabled to give insight into when next check will be (thanks [@tomballgithub](https://github.com/tomballgithub))
- **IMPROVE:** **Liveness check** logic is now recomputed after config/env/CLI overrides are applied and after check-interval changes via **signals**
- **IMPROVE:** Improved **Firefox session import** handling (safer **SQLite connection** usage; clarified error message; consistent session path handling)
- **IMPROVE:** Enhanced **sleep message output** and refined **hour range checks for updates**

**Bug fixes**:

- **BUGFIX:** Fixed missing current-hour (`cur_h`) assignment that could break hour-range gating
- **BUGFIX:** Restored Python 3.9 compatibility in type hints (replaced `datetime | None` with `Optional[datetime]`)

# Changes in 1.8.1 (30 Nov 2025)

**Features and Improvements**:

- **IMPROVE:** Improved error handling for **check intervals**

**Bug fixes**:

- **BUGFIX:** Corrected bug in `compare_images()` function (thanks [@jl-nr](https://github.com/jl-nr))

# Changes in 1.8 (18 Jun 2025)

**Features and Improvements**:

- **NEW:** Added **mobile-web JSON fallback** to restore **post details fetching** in **mode 1 (no session)**; reel details still require **mode 2 (session login)**
- **IMPROVE:** Added missing exception handling in several areas and included display of exception types for better debugging

**Bug fixes**:

- **BUGFIX:** Guarded has_public_story behind login check due to recent Instagram API anonymous session changes

# Changes in 1.7 (13 Jun 2025)

**Features and Improvements**:

- **NEW:** Introduced new experimental **Be Human** mode that makes the tool behave more like a real user to reduce bot detection by performing random feed / profile / hashtag / followee actions. It is disabled by default, check the [Human Mode](https://misiektoja.github.io/instagram_monitor/anti-detection/#use-the-human-mode) for more info.
- **NEW:** Added new **Jitter** mode which allows to force every HTTP call made by Instaloader to go through a built-in jitter/back-off layer to look more human. It is disabled by default, check the [Jitter Mode](https://misiektoja.github.io/instagram_monitor/anti-detection/#use-the-jitter-mode) for more info.
- **NEW:** Added config options and flags to set desktop and mobile Instagram user agent strings. Check [User Agent](https://misiektoja.github.io/instagram_monitor/configuration/#user-agent) for more info.
- **NEW:** Ensured all Instagram requests now include the appropriate user agent, if not specified - they are randomly generated per session

**Bug fixes**:

- **BUGFIX:** Fixed config file generation to work reliably on Windows systems

# Changes in 1.6.2 (22 May 2025)

**Bug fixes**:

- **BUGFIX:** Extended try block to suppress full stack trace
- **BUGFIX:** Corrected VERSION assignment syntax in source code

# Changes in 1.6 (21 May 2025)

**Features and Improvements**:

- **NEW:** The tool can now be installed via pip: `pip install instagram_monitor`
- **NEW:** Added support for external config files, environment-based secrets and dotenv integration with auto-discovery
- **NEW:** Added full support for Instagram reels (not just video posts) and optimized post/reel fetching to reduce API calls
- **NEW:** Added `--import-firefox-session` to load session from Firefox cookies with detection of all profiles (replaces old script)
- **IMPROVE:** Improved detail extraction for posts and reels (via mobile API)
- **NEW:** Added notification for follow-request acceptance and for removed posts/reels
- **NEW:** Display access scope and session user info, including reels count
- **IMPROVE:** Enhanced session-login logic to auto‐load or create Instaloader sessions
- **IMPROVE:** Display whether the user can access all content of the monitored account
- **IMPROVE:** Enhanced startup summary to show loaded config, dotenv and empty profile pic template file paths
- **IMPROVE:** Auto detect and display availability of `imgcat` binary for profile picture preview
- **IMPROVE:** Simplified and renamed command-line arguments for improved usability
- **NEW:** Implemented SIGHUP handler for dynamic reload of secrets from dotenv files
- **NEW:** Added configuration option to control clearing the terminal screen at startup
- **IMPROVE:** Changed connectivity check to use Instagram API endpoint for better reliability
- **IMPROVE:** Added check for missing pip dependencies with install guidance
- **IMPROVE:** Allow disabling liveness check by setting interval to 0 (default changed to 12h)
- **IMPROVE:** Improved handling of log file creation
- **IMPROVE:** Refactored CSV file initialization and processing
- **NEW:** Added support for `~` path expansion across all file paths
- **IMPROVE:** Added validation for configured time zones
- **IMPROVE:** Refactored code structure to support packaging for PyPI
- **IMPROVE:** Enforced configuration option precedence: code defaults < config file < env vars < CLI flags
- **IMPROVE:** Made empty profile picture template path configurable
- **IMPROVE:** Only show profile picture template status if the file exists
- **IMPROVE:** Renamed Caption to Description in logs and email bodies
- **IMPROVE:** Email notifications now auto-disable if SMTP config is invalid
- **IMPROVE:** Minimum required Python version increased to 3.9
- **IMPROVE:** Removed short option for `--send-test-email` to avoid ambiguity

**Bug fixes**:

- **BUGFIX:** Fixed data key error, however due to Instagram changes, post/reel details can no longer be fetched in mode 1 (no session), though count differences are still reported
- **BUGFIX:** Fixed post location fetching after Instagram broke legacy endpoints
- **BUGFIX:** Corrected public vs. private story checks and iteration ([#9](https://github.com/misiektoja/instagram_monitor/issues/9))
- **BUGFIX:** Fixed rare issue with reporting changed profile pic even though timestamp is the same
- **BUGFIX:** Fixed issue where manually defined `LOCAL_TIMEZONE` wasn't applied correctly
- **BUGFIX:** Fixed imgcat command under Windows (use `echo. &` instead of `echo ;`)

# Changes in 1.5 (03 Nov 2024)

**Features and Improvements**:

- **NEW:** Possibility to skip getting posts details (new **-w** / **--skip_getting_posts_details** parameter)
- **IMPROVE:** Print message changed when empty followers list is returned
- **IMPROVE:** Added message about fetching user's latest post/reel (as it might take a while)

**Bug fixes**:

- **BUGFIX:** Fixed bug with saving removed followers/followings to CSV file when empty list is returned and count is > 0
- **BUGFIX:** Fixed wrong CSV entry timestamp in case posts number decreases

# Changes in 1.4 (02 Aug 2024)

**Features and Improvements**:

- **NEW:** Detection when user changes profile visibility from public to private and vice-versa; the code already supported both private and public profiles, however it did not inform the user when the profile visibility has changed; now the tool will notify about it in the console and also via email notifications (**-s**) and CSV file records (**-b**)
- **IMPROVE:** Added info about used mode of the tool in the main screen, so it is easier to correlate it with the description in the README

**Bug fixes**:

- **BUGFIX:** Indentation fixes in the code

# Changes in 1.3 (14 Jun 2024)

**Features and Improvements**:

- **NEW:** Added new parameter (**-z|*8 / **--send_test_email_notification**) which allows to send test email notification to verify SMTP settings defined in the script
- **IMPROVE:** Checking if correct version of Python (>=3.8) is installed
- **IMPROVE:** Possibility to define email sending timeout (default set to 15 secs)

**Bug fixes**:

- **BUGFIX:** Fixed "SyntaxError: f-string: unmatched (" issue in older Python versions
- **BUGFIX:** Fixed "SyntaxError: f-string expression part cannot include a backslash" issue in older Python versions

# Changes in 1.2 (07 Jun 2024)

**Features and Improvements**:

- **IMPROVE:** pyright complained the code is too complex to analyze, so it has been simplified little bit (so it does not complain anymore)
- **IMPROVE:** Changed email notifications string in SIGUSR1 signal handler

**Bug fixes**:

- **BUGFIX:** Fixed nasty bug terminating the script in case of issues while processing story items (yes, copy & paste bug ;-))

# Changes in 1.1 (03 Jun 2024)

**Features and Improvements**:

- **NEW:** Support for **detecting multiple stories** (if session login is used)
- **NEW:** **Fully anonymous download of user's story images & videos** (thumbnail image will be also attached in email notifications and displayed in the terminal if imgcat is installed); yes, user won't know you watched their stories 😉
- **NEW:** **Download of user's post images & videos** (thumbnail image will be also attached in email notifications and displayed in the terminal if imgcat is installed)
- **NEW:** **Detection of changed profile pictures**; since Instagram user's profile picture URL seems to change from time to time, the tool detects changed profile picture by doing binary comparison of saved jpg files; initially it saves the profile pic to *instagram_{user}_profile_pic.jpg* file after the tool is started; then during every check the new picture is fetched and the tool does binary comparison if it has changed or not; in case of changes the old profile picture is moved to *instagram_{user}_profile_pic_old.jpg* file and the new one is saved to *instagram_{user}_profile_pic.jpg* and also to file named *instagram_{user}_profile_pic_YYmmdd_HHMM.jpg* (so we can have history of all profile pictures); in order to control the feature there is a new **DETECT_CHANGED_PROFILE_PIC** variable set to True by default; the feature can be disabled by setting it to *False* or by enabling **-k** / **--do_not_detect_changed_profile_pic** parameter
- **NEW:** **Detection of empty profile pictures**; Instagram does not signal the fact of empty user's profile image in their API, that's why we can detect it by using empty profile image template (which seems to be the same on binary level for all users); to use this feature put [instagram_profile_pic_empty.jpg](instagram_profile_pic_empty.jpg) file in the dir from which you run the script; this way the tool will be able to detect when user does not have profile image set; it is not mandatory, but highly recommended as otherwise the tool will treat empty profile pic as regular one, so for example user's removal of profile picture will be detected as changed profile picture
- **NEW:** **Attaching changed profile pics and stories/posts images directly in email notifications** (when **-s** parameter is used)
- **NEW:** Feature allowing to **display the profile picture and stories/posts images right in your terminal** (if you have *imgcat* installed); put path to your *imgcat* binary in **IMGCAT_PATH** variable (or leave it empty to disable this functionality)
- **IMPROVE:** Improvements for running the code in **Python under Windows**
- **NEW:** **Automatic detection of local timezone** if you set LOCAL_TIMEZONE variable to 'Auto' (it is default now); requires tzlocal pip module
- **NEW:** Support for honoring last-modified timestamp for saved profile pics (it turned out it reflects timestamp when the picture has been actually added by the user)
- **IMPROVE:** Information about time zone and posts checking hours is displayed in the start screen now
- **NEW:** Fetching of post's location and comments + likes list is back (however needs to be enabled via -t parameter as it highly increases the risk that Instagram will mark the account as an automated tool)
- **NEW:** Added new parameter **-r** / **--skip_getting_story_details** to skip getting detailed info about stories and its images/videos, even if session login is used; you will still get generic information about new stories in such case
- **NEW:** Added new parameter **-t** / **--get_more_post_details** to get more detailed info about new posts like its location and comments + likes list, only possible if session login is used; if not enabled you will still get generic information about new posts; it is disabled by default as for some unknown reasons it highly increases the risk of the account being flagged as an automated tool
- **NEW:** Added new parameter **-k** / **--do_not_detect_changed_profile_pic** which allows to disable detection of changed user's profile picture
- **IMPROVE:** Email sending function send_email() has been rewritten to detect invalid SMTP settings + possibility to attach images
- **IMPROVE:** Strings converted to f-strings for better code visibility
- **IMPROVE:** Rewritten get_date_from_ts(), get_short_date_from_ts(), get_hour_min_from_ts() and get_range_of_dates_from_tss() functions to automatically detect it time object is timestamp (int/float) or datetime
- **IMPROVE:** Better checking for wrong command line arguments
- **IMPROVE:** Help screen reorganization
- **IMPROVE:** pep8 style convention corrections

**Bug fixes**:

- **BUGFIX:** Improved exception handling while processing JSON files
- **BUGFIX:** Escaping of potentially dangerous variables in HTML email templates
- **BUGFIX:** Fix for saving empty followers/followings list to JSON file when the tool is started and Instagram API returns empty list

# Changes in 1.0 (25 Apr 2024)

**Features and Improvements**:

- **NEW:** Support for Instagram users having no posts yet
- **NEW:** Support for handling private profiles
- **IMPROVE:** Improvements in monitoring Instagram user activity without session

**Bug fixes**:

- **BUGFIX:** Disabled fetching location, list of likes and comments for posts due to errors after recent Instagram changes (HTTP Error 400)
