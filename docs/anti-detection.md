# How to Prevent Getting Challenged and Account Suspension

As mentioned earlier it is highly recommended to use a dedicated Instagram account when using this tool in session login mode. While the risk of account suspension is generally low (in practice, accounts often stay active long-term), Instagram may still flag it as an automated tool. This can lead to challenges presented by Instagram that must be dismissed manually.

Use a separate account if losing access to your main account would be unacceptable. The practices below may reduce the risk but they are not guarantees.

<a id="sign-in-using-session-mode-with-browser-cookies"></a>
## Sign In Using Session Mode with Browser Cookies

Log in through a supported browser (Firefox, Chrome, Brave or Chromium) and import that saved session instead of sending the password on every start. Follow [Session Login Using Browser Cookies](configuration.md#option-3-session-login-using-browser-cookies-recommended).

<a id="set-the-correct-user-agent"></a>
## Set the Correct User-Agent

Every request should look like it came from one browser. Set `USER_AGENT` or `--user-agent` to the value reported by the browser used for the import, so the browser identity matches the imported cookies. Follow [User Agent](configuration.md#user-agent).

Leaving it empty is fine. The tool then generates a current, complete user agent for you. Pairing a Firefox session with a Chrome user agent is not.

The transport follows the same identity. With the default `CURL_CFFI_IMPERSONATE = "auto"`, the TLS fingerprint and the client-hint headers are taken from your `USER_AGENT`, so one setting keeps the whole request consistent. If you pin a browser by hand, pin it to the same one.

<a id="use-a-browser-transport-fingerprint"></a>
## Use a Browser Transport Fingerprint

Instagram can block a request before it ever reads the user agent, going by the TLS fingerprint of the library that sent it. The symptom is `HTTP 429` on the very first request from a clean IP, seen most often on Linux builds including Raspberry Pi OS. No interval or budget helps with this one, because nothing got through.

The default `curl_cffi` backend avoids it by presenting a real browser's fingerprint instead of the system TLS stack's. Keep it:

```ini
HTTP_BACKEND = "curl_cffi"
```

`curl_cffi` is installed with the tool. If it is missing after a manual install, the tool warns you and falls back to `requests`, which cannot impersonate a browser. Since the fallback is silent in the config file, check what is actually in effect with `--doctor` or `--exposure`. See [HTTP Transport Backend](usage.md#http-transport-backend).

<a id="use-the-human-mode"></a>
## Use the Human Mode

Experimental **Be Human** mode adds a small number of feed or profile requests between normal monitoring checks so it behaves more like a real user to reduce bot detection.

It is disabled by default. Enable it through `BE_HUMAN`, the `--be-human` option or the **Settings** page in the Web Dashboard.

It works only in [Logged-In Mode](configuration.md#logged-in-mode-with-session-login).

After a check cycle, the tool may perform one or more of these requests:

- fetch one post from the Explore feed
- open the session account's profile
- fetch one post from a tag listed in `MY_HASHTAGS`
- open the profile of an account followed by the session account

Leaving `MY_HASHTAGS` empty simply skips the hashtag request. The other actions still run.

The followee visit reads only the first page of accounts your session follows before picking one, so the simulation stays a few requests rather than paginating a large following list.

By default, it performs about five of these actions over 24 hours. Change the limit with `DAILY_HUMAN_HITS`.

Set `BE_HUMAN_VERBOSE = True` to log each action.

<a id="set-an-identity-budget"></a>
## Set an Identity Budget

Instagram scores automated collection by how much user-identifiable information a response returns, not by how many requests were sent. Meta describes this in [Predictive Response Optimization](https://arxiv.org/abs/2502.17693): the metric their system optimizes counts each request "weighted by the number of units of user-identifiable information returned to the user".

That means fetching follower and following names is far more expensive than checking counts, posts or stories, even though each is one request. It also means batch sizes and delays matter less than the total number of names you pull per day.

`IDENTITY_BUDGET_PER_DAY` caps that total for the logged-in account. It is shared by every monitored target and every worker in the process and it resets at local midnight. Identity scans run one at a time so two targets cannot spend the same remaining allowance.

```
IDENTITY_BUDGET_PER_DAY = 2000
```

Once the budget is spent, name fetching stops until the next day. Counts, posts, reels, stories and profile changes keep being monitored normally, so you still see that the follower number moved, just not who moved.

REST pages are counted when Instagram returns them, before the tool consumes individual names. The last response can therefore put the recorded total above the configured limit if Instagram returns more accounts than requested. This records the actual exposure and stops another request. GraphQL names are banked in groups of 25 with the last group cut to what the budget still allows, so the recorded total is exact where the fetch stops.

The default is 2000, which clears one full follower and following scan for a typical account with room to repeat it, while stopping a loop that would otherwise read a list many times a day. Names are always counted whether or not you set one, so you can watch your own usage with `--exposure` and adjust. If you have been challenged before, somewhere around 500 to 1000 is a better figure.

Set the budget above the largest list you monitor. A scan needing more names than the budget still allows is skipped in full and says so, because a truncated list is discarded rather than saved, so starting it would spend the rest of the day's allowance and still leave you without a baseline.

You can also set it for one run with `--identity-budget 750`.

A partial fetch is never written to the baseline file. If the budget stops a fetch halfway, the previous complete list stays in place and the comparison is skipped rather than reporting every unfetched account as an unfollow.

<a id="choose-how-follower-lists-are-read"></a>
## Choose How Follower Lists Are Read

`FOLLOW_LIST_SOURCE` selects the surface the follower and following lists are read from. The default `auto` reads them over the REST endpoints Instagram's own web app calls and falls back to the older GraphQL queries only when REST is gone before it returned anybody. Both cost the same number of names, so this choice is about staying on a working surface, not about exposure. Leave it on `auto` unless one surface starts failing for you.

The `browser` source is different. It drives a real browser through the follower dialog instead of calling the API, and a browser session that scrolls those dialogs for hours does not look like a person. **It can cost you the account.** `auto` never picks it. Read [Browser Source](usage.md#browser-source-experimental) before turning it on, and only with an account you can afford to lose.

It also has to agree with the rest of the session. The browser runs Chromium, so `HTTP_BACKEND` must be `curl_cffi` and your user agent and impersonation target must name the same browser family. Monitoring refuses to start on a mismatch and the Web Dashboard refuses a settings change that would create one, rather than let one session reach Instagram as two different clients. See [Follower List Source](usage.md#follower-list-source).

<a id="let-the-circuit-breaker-stop-the-account"></a>
## Let the Circuit Breaker Stop the Account

When Instagram returns a confirmed challenge, checkpoint, temporary limit or expired session, monitoring pauses for the account.

`CIRCUIT_BREAKER` is enabled by default. An account-level failure stops all targets using that account for the rest of the run. Restarting checks the saved session once before starting any target workers. The check allows one request with a 30-second timeout and no automatic retries or redirects. Success resumes monitoring. Failure leaves the account paused and explains what to fix.

```
* Circuit breaker: Instagram acted against session account your_account (challenge). Stopping all Instagram requests for this account
```

The second line names the required action. Complete account verification in a browser or re-import an expired session, then start the tool with your usual command. A temporary limit, reported as `feedback_required`, has nothing to clear: make no requests from the account and the network for several hours before restarting. See [Instagram Says Try Again Later](troubleshooting.md#instagram-says-try-again-later). No separate clearing command is needed. Importing a session reuses its login check and releases the stop only after the session is saved. In the Web Dashboard, importing or successfully refreshing the session also resumes targets paused by the account stop. Targets you stopped manually remain stopped.

Each process restart can make another check. Configure a restart delay if a service manager restarts failed runs automatically.

Rate limits, network errors and Instagram API changes do not trip the breaker. Only responses that act against the account do. A rejected or redirected request that reads like an expired session is confirmed with one public profile fetch first, so a single mislabelled request cannot stop every target. If the session still signs in, the run says so and the breaker stays armed.

The email and webhook alert for a flagged account also carries the client identity behind it: the transport in effect, the browser `curl_cffi` impersonated and the browser user agent. That is usually what you need to decide whether the transport caused the flag. It means those values reach your notification service, so leave account-level alerts off if that matters for your webhook destination. Routine per-target error alerts carry no identity.

The safety ledger also fails closed. If `instagram_monitor_exposure.json` cannot be read or saved, authenticated monitoring stops before another identity scan. That includes invalid counts or stop records. Repair the named field or restore file access, then restart. Automatic recovery preserves daily counts and never replaces an unreadable ledger. `--clear-breaker` remains available for explicit local-state repair, including resetting an unusable ledger, but is not part of normal recovery. Fields the tool does not recognize are left alone.

<a id="check-your-exposure"></a>
## Check Your Exposure

`--exposure` prints a report that can be pasted into a support issue or [discussion #128](https://github.com/misiektoja/instagram_monitor/discussions/128):

```
instagram_monitor --exposure
```

It shows the Instagram Monitor version, operating system, Python version, HTTP backend, follower-list source, session mode, identity total, sanitized failure counts and circuit-breaker state. The backend and list source are the ones in effect, so the report names the browser `curl_cffi` impersonated and says when a `curl_cffi` setting fell back to `requests` because the package is missing. It omits the account name, target names, stored error text and local file paths. Failures are grouped so you can tell the three problems apart:

| Group | Meaning | What helps |
|---|---|---|
| A | The transport was blocked, usually a first-request HTTP 429 | [HTTP Transport Backend](usage.md#http-transport-backend) |
| B | Instagram changed an API, so a query stopped returning data | Update to the latest version |
| C | Instagram acted against the account | Lower the identity budget, raise the interval, monitor fewer targets |

The ledger remains local. It is never transmitted anywhere and nothing reads it but the tool. It lives next to your output directory as `instagram_monitor_exposure.json`, but the pasteable report does not print that path.

<a id="use-the-jitter-mode"></a>
## Use the Jitter Mode

Jitter mode adds a random delay of about 0.8 to 6 seconds before Instagram requests made by Instaloader. It also retries Instagram HTTP 429 responses and checkpoint challenges after increasingly long waits of about 60, 120 and 240 seconds. Media downloads, webhooks, proxy IP checks and other non-Instagram requests do not inherit these delays or backoff rules.

The extra waits make monitoring slower. They may help with temporary rate limits but they do not guarantee that Instagram will accept the requests.

Enable it through `ENABLE_JITTER` or `--enable-jitter`.

Set `JITTER_VERBOSE = True` to log each delayed request and retry.

<a id="keep-the-polling-interval-reasonable"></a>
## Keep the Polling Interval Reasonable

The polling interval controls how long the tool waits between checks. Use at least one hour through `INSTA_CHECK_INTERVAL` or `-c 3600`. A longer interval sends fewer requests. There is no interval that guarantees protection from limits.

Instagram Monitor randomizes the interval by default. See [Check Intervals](usage.md#check-intervals).

Each target adds requests. Five targets checked every hour create about five times the target-check traffic of one target checked every hour. To keep a similar total rate, increase the interval as you add targets. The tool spreads target checks across the interval but does not reduce the total number of checks.

<a id="use-hour-range-checking"></a>
## Use Hour-Range Checking

Hour-range checking limits Instagram requests to selected parts of the day. It can reduce the total request count and keep requests within hours you choose.

Inside the allowed windows, the tool checks posts, reels, stories, profile details and follower or following data. Outside them, the process stays running but waits without fetching those updates.

To enable this feature, set `CHECK_POSTS_IN_HOURS_RANGE` to `True` and configure the allowed hour ranges using:

- `MIN_H1` and `MAX_H1` set the first range. The default `0` to `4` means midnight through 4:59 AM
- `MIN_H2` and `MAX_H2` set the second range. The default `11` to `23` means 11:00 AM through 11:59 PM

You can define one or two ranges. The ranges may overlap. To disable a range, set both its `MIN` and `MAX` value to `0`.

**Note**: You can also enable this feature and configure the allowed hour ranges live via the **Settings** menu in the **Web Dashboard**.

For example, use these values to allow checks from 9:00 AM through 5:59 PM:

- `MIN_H1 = 9`
- `MAX_H1 = 17`
- `MIN_H2 = 0`
- `MAX_H2 = 0`

Hours are specified in 24-hour format (0-23) and are evaluated in your configured time zone (see [Time Zone](configuration.md#time-zone)).

Set `HOURS_VERBOSE = True` to log when a check is allowed or skipped.

The polling interval still applies inside each allowed window. A scheduled check outside a window waits for a later allowed time.

<a id="do-not-monitor-too-many-users"></a>
## Do Not Monitor Too Many Users

Limit the number of targets monitored through one session account. Each target increases the total number of Instagram requests. If you need many targets, split them into smaller groups with longer intervals. Separate session accounts may also be appropriate but each account remains subject to Instagram's limits.

<a id="use-only-needed-functionality"></a>
## Use Only Needed Functionality

Disable checks you do not need. This reduces request volume. You can skip story details with `-r`, post or reel details with `-w`, the following list with `-g` and the follower list with `-f`.

You can also turn these checks on or off through the **Settings** page in the Web Dashboard.

<a id="use-two-factor-authentication-2fa"></a>
## Use Two-Factor Authentication (2FA)

Activate 2FA on the account used for monitoring. It adds credibility to your account and reduces the likelihood of security flags.

<a id="avoid-using-vpns"></a>
## Avoid Using VPNs

Avoid frequent changes to the public IP address or geographic region used by the session. For example, switching VPN regions between runs may cause Instagram to request a security check.

<a id="use-the-account-for-normal-activities"></a>
## Use the Account for Normal Activities

Before monitoring, confirm that the account works normally in the browser used for [session import](configuration.md#option-3-session-login-using-browser-cookies-recommended). Resolve any login or security prompts there first.

Do not use the same browser session while Instagram Monitor is actively making requests. Simultaneous activity from the browser and tool may cause additional security checks.
