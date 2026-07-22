# How to Prevent Getting Challenged and Account Suspension

As mentioned earlier it is highly recommended to use a dedicated Instagram account when using this tool in session login mode. While the risk of account suspension is generally low (in practice, accounts often stay active long-term), Instagram may still flag it as an automated tool. This can lead to challenges presented by Instagram that must be dismissed manually.

To minimize any chance of detection, make sure to follow the best practices outlined below.

<a id="sign-in-using-session-mode-with-browser-cookies"></a>
## Sign In Using Session Mode with Browser Cookies

Use your web browser (Firefox, Chrome, Brave or Chromium) to log in, ensuring the session looks natural and consistent to Instagram. Follow instructions described [here](configuration.md#option-3-session-login-using-browser-cookies-recommended)

<a id="set-the-correct-user-agent"></a>
## Set the Correct User-Agent

Always pass the exact user agent string from the web browser you imported the session from by using `USER_AGENT` configuration option or the `--user-agent` flag. This helps maintain device consistency during automated actions. Follow instructions described [here](configuration.md#user-agent)

<a id="use-the-human-mode"></a>
## Use the Human Mode

Since v1.7, the tool includes a new experimental **Be Human** mode that makes it behave more like a real user to reduce bot detection.

It is disabled by default, but you can enable it via `BE_HUMAN` configuration option, `--be-human` flag or by toggling it via the **Settings** menu in the **Web Dashboard**.

It is used only with session login (Logged-in mode).

After each check cycle, the tool will randomly do one or more of these harmless actions:

- View your explore feed: pulls a single post from Instagram's explore feed
- Open your own profile, as if tapping your avatar
- Browse a hashtag: fetches one post from a random tag listed in `MY_HASHTAGS` configuration option
- Look at a profile of someone you follow

By default it does around 5 of these actions spread over 24 hours, but you can adjust it via `DAILY_HUMAN_HITS` option.

If you are interested in your human actions set `BE_HUMAN_VERBOSE` option to `True`.

<a id="use-the-jitter-mode"></a>
## Use the Jitter Mode

Since v1.7, the tool allows to force every HTTP call made by Instaloader to go through a built-in jitter/back-off layer to look more human.

This adds random delay (0.8-3 s) before each request and automatically retries on Instagram's 429 "too many requests" or checkpoint challenges, with exponential back-off (60 s → 120 s → 240 s) and a little extra jitter.

This significantly reduces detection risk, but also makes the tool slower.

You can enable this feature via `ENABLE_JITTER` configuration option or `--enable-jitter` flag.

If you want to see verbose output for HTTP jitter/back-off wrappers set `JITTER_VERBOSE` option to `True`.

<a id="keep-the-polling-interval-reasonable"></a>
## Keep the Polling Interval Reasonable

Avoid setting the polling interval (`INSTA_CHECK_INTERVAL` option or `-c` flag) too aggressively. Use a minimum of 1 hour - longer is better. For example, I set it to 12 hours on test accounts, resulting in only 2 checks per day.

Also consider to randomize the check interval, as explained [here](usage.md#check-intervals).

**Important**: When monitoring multiple users in a single process, the effective request rate is multiplied by the number of targets. For example, monitoring 5 users with a 1-hour interval means 5 requests per hour. To maintain the same per-account request rate, increase the check interval proportionally. If you normally use 1 hour for a single user, consider using 5 hours (or more) when monitoring 5 users. The tool automatically staggers requests between targets, but the overall request frequency should still be adjusted based on the total number of monitored users.

<a id="use-hour-range-checking"></a>
## Use Hour-Range Checking

The tool supports limiting fetching updates to specific hours of the day, which helps reduce detection by avoiding requests during times when automated activity might be more suspicious.

When hour-range checking is enabled, the tool will only fetch updates (posts, reels, stories, profile changes, followers/followings) during the configured time windows. Outside these hours, the tool will skip fetching updates but will continue running and wait for the next allowed time window.

To enable this feature, set `CHECK_POSTS_IN_HOURS_RANGE` to `True` and configure the allowed hour ranges using:

- `MIN_H1` and `MAX_H1` - first range of hours (default: 0-4, i.e., midnight to 4:59 AM)
- `MIN_H2` and `MAX_H2` - second range of hours (default: 11-23, i.e., 11:00 AM to 11:59 PM / 23:59)

You can define up to two non-overlapping or overlapping ranges. To disable any range, set both MIN and MAX to 0.

**Note**: You can also enable this feature and configure the allowed hour ranges live via the **Settings** menu in the **Web Dashboard**.

For example, to only allow checks during business hours (9 AM to 5 PM / 17:00), you could set:

- `MIN_H1 = 9`
- `MAX_H1 = 17`
- `MIN_H2 = 0`
- `MAX_H2 = 0`

Hours are specified in 24-hour format (0-23) and are evaluated in your configured time zone (see [Time Zone](configuration.md#time-zone)).

If you want to see verbose output about when updates are being fetched or skipped, set `HOURS_VERBOSE` to `True`. This is useful for debugging and understanding when the tool is active.

This feature works particularly well when combined with reasonable polling intervals, as it ensures that even if your check interval triggers, requests will only be made during the configured time windows, making your activity pattern look more natural.

<a id="do-not-monitor-too-many-users"></a>
## Do Not Monitor Too Many Users

It is recommended to limit the number of users monitored by a single account, especially if they post frequent updates. When using multi-user monitoring (monitoring multiple users in one process), keep in mind that the total request volume increases with each additional target. In some cases, it may be best to create a separate account for additional users and even run it from a different IP address to reduce the risk of detection.

<a id="use-only-needed-functionality"></a>
## Use Only Needed Functionality

Frequent updates to certain data types, such as new stories or posts/reels, are more likely to flag the account as an automated tool compared to profile changes or lists of followers/followings.

If certain data isn't essential for your use case, consider disabling its retrieval. The tool provides fine-grained control, for example you can skip fetching stories details (`-r`), posts/reels details (`-w`), the list of followings (`-g` flag) and followers (`-f`).

**Note**: All of these fine-grained tracking options can also be toggled live via the **Settings** menu in the **Web Dashboard**.

<a id="use-two-factor-authentication-2fa"></a>
## Use Two-Factor Authentication (2FA)

Activate 2FA on the account used for monitoring. It adds credibility to your account and reduces the likelihood of security flags.

<a id="avoid-using-vpns"></a>
## Avoid Using VPNs

Refrain from logging in via VPNs, especially with IPs in different regions. Sudden location changes can trigger Instagram's security systems.

<a id="use-the-account-for-normal-activities"></a>
## Use the Account for Normal Activities

If you have created a new account for monitoring and you are using [Session Login Using Browser Cookies](configuration.md#option-3-session-login-using-browser-cookies-recommended), make sure to behave like a regular user for several days. New accounts are more closely monitored by Instagram's bot detection systems. Watch content, post stories or reels and leave comments - this helps establish a natural activity pattern.

Once you start using the tool, try to blend its actions with normal usage. However, avoid overlapping browser activity with tool activity, as simultaneous actions can trigger suspicious behavior flags.
