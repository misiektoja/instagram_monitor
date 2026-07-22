# How to Prevent Getting Challenged and Account Suspension

As mentioned earlier it is highly recommended to use a dedicated Instagram account when using this tool in session login mode. While the risk of account suspension is generally low (in practice, accounts often stay active long-term), Instagram may still flag it as an automated tool. This can lead to challenges presented by Instagram that must be dismissed manually.

Use a separate account if losing access to your main account would be unacceptable. The practices below may reduce the risk but they are not guarantees.

<a id="sign-in-using-session-mode-with-browser-cookies"></a>
## Sign In Using Session Mode with Browser Cookies

Log in through a supported browser (Firefox, Chrome, Brave or Chromium) and import that saved session instead of sending the password on every start. Follow [Session Login Using Browser Cookies](configuration.md#option-3-session-login-using-browser-cookies-recommended).

<a id="set-the-correct-user-agent"></a>
## Set the Correct User-Agent

Set `USER_AGENT` or `--user-agent` to the value reported by the browser used for the import. This keeps the browser identity in the requests consistent with the imported session. Follow [User Agent](configuration.md#user-agent).

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

By default, it performs about five of these actions over 24 hours. Change the limit with `DAILY_HUMAN_HITS`.

Set `BE_HUMAN_VERBOSE = True` to log each action.

<a id="use-the-jitter-mode"></a>
## Use the Jitter Mode

Jitter mode adds a random delay of 0.8 to 3 seconds before each Instaloader request. It also retries HTTP 429 responses and checkpoint challenges after increasingly long waits of about 60, 120 and 240 seconds.

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
