"""Synthetic public embed and profile page fixtures shaped like live replies, with no account data or network requests."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


# Builds a public embed profile with a pinned older post and a newer carousel, keyed like Instagram's embed context.
def _payload():
    owner = {"id": "77", "username": "target", "is_private": False}
    posts = []
    for shortcode, timestamp in (("PINNED", 1700000000), ("NEWEST", 1700000300)):
        posts.append({"shortcode_media": {
            "id": str(timestamp), "shortcode": shortcode, "taken_at_timestamp": timestamp,
            "owner": dict(owner), "display_url": "https://example.com/photo.jpg", "is_video": False,
            "edge_liked_by": {"count": 142}, "edge_media_to_comment": {"count": 1},
            "edge_media_to_caption": {"edges": [{"node": {"text": "Example caption"}}]},
            "edge_sidecar_to_children": {"edges": [{"node": {"display_url": "https://example.com/child.jpg"}}]},
        }})
    return {"username": "target", "owner_id": "77", "full_name": "Example", "followers_count": 12,
            "posts_count": 20, "profile_pic_url": "https://example.com/s100x100/avatar.jpg", "is_verified": True,
            "has_public_story": False, "graphql_media": posts}


# Wraps JSON in the nested string used by Instagram's ServerJS payload without executable evaluation.
def _html(payload):
    data = {"require": [["Example", {"contextJSON": json.dumps({"context": payload})}]]}
    return '<html><script>requireLazy([],function(){s.handle(' + json.dumps(data) + ');});</script></html>'


# Represents the logged-out profile page: no post count, a rounded follower count and a timeline it is not read for.
def _page(**changes):
    profile = {"pk": "77", "id": "opaque-query-id", "username": "target", "is_private": False,
               "all_media_count": None, "follower_count": 12000, "following_count": 5,
               "biography": "Page biography", "profile_pic_url": "https://example.com/s150x150/avatar.jpg"}
    profile.update(changes)
    timeline = {"edges": [{"node": {"code": "OTHER", "taken_at": 1700000400, "user": {"username": "partner"}}}]}
    return [{"xig_user_by_username": profile}, {"xig_user_by_username": {"polaris_ordered_timeline_connection": timeline}}]


# Creates an anonymous context whose mobile request fails with the reported deleted schema.
def _bot(im_module, monkeypatch, payload=None):
    response = Mock(status_code=200, text=_html(payload or _payload()), headers={})
    session = Mock()
    session.get.return_value = response
    context = SimpleNamespace(is_logged_in=False, request_timeout=20, _session=session,
                              do_sleep=Mock(), _rate_controller=Mock(), get_iphone_json=Mock(),
                              get_page_data=Mock(return_value=_page()))
    context.get_iphone_json.side_effect = im_module.instaloader.exceptions.QueryReturnedBadRequestException(
        "400 Bad Request: Asset asset://laser.provider/ig_business_category_subvertical has been deleted. You cannot use this schema")
    monkeypatch.setattr(im_module, "ensure_instagram_session_wrapped", lambda session: None)
    monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: None)
    return SimpleNamespace(context=context), response


# Pins the monotonic clock the snapshot and page back-off read, so tests can step through checks.
def _clock(im_module, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(im_module.time, "monotonic", lambda: clock[0])
    return clock


# The embed is the base and the page adds only the following count and biography the embed lacks.
def test_schema_failure_reads_embed_with_page_details(im_module, monkeypatch):
    bot, response = _bot(im_module, monkeypatch)
    profile = im_module.profile_from_username_resilient(bot, "target")
    post, kind = im_module.latest_post_mobile("target", bot)
    assert (profile.userid, profile.username, profile.mediacount, profile.is_private) == (77, "target", 20, False)
    # The page's follower count is rounded and its picture is another size, so both come from the embed
    assert profile.followers == 12
    assert profile.profile_pic_url_no_iphone == "https://example.com/s100x100/avatar.jpg"
    assert (profile.followees, profile.biography) == (5, "Page biography")
    assert (post.shortcode, post.caption, post.likes, post.comments, kind) == ("NEWEST", "Example caption", 142, 1, "post")
    assert bot.context.get_iphone_json.call_count == 1
    assert bot.context._session.get.call_count == 1
    bot.context.get_page_data.assert_called_once_with("target/")
    response.close.assert_called_once()


# The switch is announced once per target, on its own line even while a progress line is open.
def test_fallback_is_announced_once_on_its_own_line(im_module, monkeypatch, capsys):
    bot, _ = _bot(im_module, monkeypatch)
    clock = _clock(im_module, monkeypatch)
    logs = []
    monkeypatch.setattr(im_module, "log_activity", lambda *args, **kwargs: logs.append((args, kwargs)))
    monkeypatch.setattr(im_module._thread_local, "in_partial_line", True, raising=False)
    im_module._anonymous_profile_info(bot, "target")
    clock[0] += 60
    im_module._anonymous_profile_info(bot, "target")
    output = capsys.readouterr().out
    assert output.startswith("\n* ")
    assert output.count("\n* ") == 1
    assert "target" in output
    assert len(logs) == 1 and logs[0][1] == {"user": "target", "level": "system"}


# Authentication, throttling, action blocks and server errors never spend a request on the public sources.
@pytest.mark.parametrize("error_name, message", [
    ("ConnectionException", "JSON Query to api/v1/users/web_profile_info/: 401 Unauthorized"),
    ("TooManyRequestsException", "429 Too Many Requests"),
    ("AbortDownloadException", '400 Bad Request - "fail" status, message "feedback_required"'),
    ("ConnectionException", "500 Internal Server Error"),
])
def test_other_failures_do_not_fall_back(im_module, monkeypatch, error_name, message):
    bot, _ = _bot(im_module, monkeypatch)
    error_type = getattr(im_module.instaloader.exceptions, error_name)
    bot.context.get_iphone_json.side_effect = error_type(message)
    for _ in range(2):
        with pytest.raises(error_type):
            im_module.profile_from_username_resilient(bot, "target")
    # Nothing is remembered, so the next check asks the profile endpoint again rather than the public sources
    assert bot.context.get_iphone_json.call_count == 2
    bot.context._session.get.assert_not_called()
    bot.context.get_page_data.assert_not_called()


# Healthy mobile responses and logged-in callers keep their existing source.
def test_healthy_response_is_unchanged(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    original = {"data": {"user": {"id": "77", "username": "target"}}}
    bot.context.get_iphone_json.side_effect = None
    bot.context.get_iphone_json.return_value = original
    assert im_module._anonymous_profile_info(bot, "target") is original
    bot.context._session.get.assert_not_called()
    bot.context.get_page_data.assert_not_called()


# Even the same schema exception cannot switch a signed-in session onto an anonymous source.
def test_logged_in_schema_failure_does_not_fall_back(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    bot.context.is_logged_in = True
    with pytest.raises(im_module.instaloader.exceptions.QueryReturnedBadRequestException):
        im_module._anonymous_profile_info(bot, "target")
    bot.context._session.get.assert_not_called()
    bot.context.get_page_data.assert_not_called()


# One snapshot serves every lookup of a check and the next check reads fresh data without the refused endpoint.
def test_snapshot_is_shared_within_a_check_and_refreshed_later(im_module, monkeypatch):
    bot, response = _bot(im_module, monkeypatch)
    clock = _clock(im_module, monkeypatch)
    im_module.profile_from_username_resilient(bot, "target")
    clock[0] += 20
    im_module.latest_post_mobile("target", bot)
    im_module.fetch_leaked_collab_posts("target", bot)
    assert (bot.context._session.get.call_count, bot.context.get_page_data.call_count) == (1, 1)
    clock[0] += im_module.PUBLIC_WEB_SNAPSHOT_SECONDS
    changed = _payload()
    changed["followers_count"] = 13
    response.text = _html(changed)
    assert im_module.profile_from_username_resilient(bot, "target").followers == 13
    assert bot.context.get_iphone_json.call_count == 1
    assert (bot.context._session.get.call_count, bot.context.get_page_data.call_count) == (2, 2)


# A failed embed closes its response and keeps the target on the public sources, so no later check repeats the 400.
@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_failed_embed_keeps_the_target_on_public_sources(im_module, monkeypatch, status):
    bot, response = _bot(im_module, monkeypatch)
    response.status_code = status
    for _ in range(2):
        with pytest.raises(RuntimeError, match=f"Public embed fallback failed for target: HTTP {status}"):
            im_module.profile_from_username_resilient(bot, "target")
    assert response.close.call_count == 2
    assert bot.context.get_iphone_json.call_count == 1
    assert bot.context._session.get.call_count == 2
    # The page only adds to a working embed, so a failed embed spends no request on it
    bot.context.get_page_data.assert_not_called()


# The page is optional: a login wall, a limit or another account leaves its fields unknown and skips it for a while.
@pytest.mark.parametrize("failure", ["redirect", "limit", "empty", "other_account", "private"])
def test_page_failure_keeps_embed_snapshot_and_backs_off(im_module, monkeypatch, failure):
    bot, _ = _bot(im_module, monkeypatch)
    clock = _clock(im_module, monkeypatch)
    exceptions = im_module.instaloader.exceptions
    bot.context.get_page_data.side_effect = {
        "redirect": exceptions.ConnectionException("302 Found when accessing https://www.instagram.com/target/"),
        "limit": exceptions.TooManyRequestsException("429 Too Many Requests"),
        "empty": None, "other_account": None, "private": None,
    }[failure]
    bot.context.get_page_data.return_value = {"empty": [], "other_account": _page(pk="88"), "private": _page(is_private=True)}.get(failure)
    profile = im_module.profile_from_username_resilient(bot, "target")
    assert (profile.userid, profile.followers, profile.followees, profile.biography) == (77, 12, None, None)
    for _ in range(3):
        clock[0] += im_module.PUBLIC_WEB_SNAPSHOT_SECONDS
        im_module.profile_from_username_resilient(bot, "target")
    assert bot.context.get_page_data.call_count == 1
    assert bot.context._session.get.call_count == 4
    clock[0] += im_module.PUBLIC_PAGE_RETRY_SECONDS
    im_module.profile_from_username_resilient(bot, "target")
    assert bot.context.get_page_data.call_count == 2


# Instaloader versions without the page reader still get the embed, with following count and bio unknown.
def test_embed_works_without_the_page_reader(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    del bot.context.get_page_data
    profile = im_module.profile_from_username_resilient(bot, "target")
    assert (profile.followers, profile.followees, profile.biography) == (12, None, None)


# Private, mismatched, malformed and unexpectedly empty payloads must not look like successful empty profiles.
@pytest.mark.parametrize("case", ["username", "private", "id", "timestamp", "empty", "count", "only_collab", "not_json", "oversize"])
def test_invalid_embed_is_rejected(im_module, case):
    payload = _payload()
    if case == "username":
        payload["username"] = "different"
    elif case == "private":
        payload["graphql_media"][0]["shortcode_media"]["owner"]["is_private"] = True
    elif case == "id":
        payload["owner_id"] = "unknown"
    elif case == "timestamp":
        payload["graphql_media"][0]["shortcode_media"]["taken_at_timestamp"] = None
    elif case == "empty":
        payload["graphql_media"] = []
    elif case == "count":
        payload["posts_count"] = None
    elif case == "only_collab":
        for entry in payload["graphql_media"]:
            entry["shortcode_media"]["owner"] = {"id": "99", "username": "partner", "is_private": False}
    html = "<script>location.href='/accounts/login/';</script>" if case == "not_json" else _html(payload)
    if case == "oversize":
        html = " " * (4 * 1024 * 1024 + 1)
    with pytest.raises(RuntimeError, match="Public embed fallback failed for target"):
        im_module._parse_public_embed("target", html)


# A collab post owned by a partner appears on the target's grid, so it is kept and can be the latest post.
def test_collab_post_owned_by_a_partner_is_kept(im_module, monkeypatch):
    payload = _payload()
    payload["graphql_media"].append({"shortcode_media": {
        "id": "1700000600", "shortcode": "COLLAB", "taken_at_timestamp": 1700000600,
        "owner": {"id": "99", "username": "partner", "is_private": False},
        "display_url": "https://example.com/collab.jpg", "coauthor_producers": [{"username": "target"}],
    }})
    bot, _ = _bot(im_module, monkeypatch, payload)
    profile = im_module.profile_from_username_resilient(bot, "target")
    post, _ = im_module.latest_post_mobile("target", bot)
    assert profile.userid == 77
    assert len(profile._node["edge_owner_to_timeline_media"]["edges"]) == 3
    assert post.shortcode == "COLLAB"


# A reply that declares a body above the limit is refused before it is read.
def test_declared_oversize_embed_is_refused(im_module, monkeypatch):
    bot, response = _bot(im_module, monkeypatch)
    response.headers = {"content-length": str(4 * 1024 * 1024 + 1)}
    with pytest.raises(RuntimeError, match="Public embed fallback failed for target"):
        im_module.profile_from_username_resilient(bot, "target")
    response.close.assert_called_once()


# Parsing preserves carousel children and supports direct JSON script blocks as well as nested ServerJS strings.
def test_direct_json_preserves_carousel(im_module):
    payload = _payload()
    result = im_module._parse_public_embed("target", '<script type="application/json">' + json.dumps(payload) + '</script>')
    edges = result["edge_owner_to_timeline_media"]["edges"]
    assert edges[1]["node"]["edge_sidecar_to_children"]["edges"][0]["node"]["display_url"].endswith("child.jpg")


# A missing embed picture stays unknown rather than an empty address the picture check would try to download.
def test_missing_embed_picture_is_unknown(im_module, monkeypatch):
    payload = _payload()
    payload.pop("profile_pic_url")
    bot, _ = _bot(im_module, monkeypatch, payload)
    assert im_module.profile_from_username_resilient(bot, "target").profile_pic_url_no_iphone is None


# The recovery uses the configured transport, proxy, TLS policy and rate controller, and never follows a login redirect.
def test_embed_request_respects_network_settings(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    monkeypatch.setattr(im_module, "get_proxies", lambda: {"https": "http://proxy.example:8080"})
    monkeypatch.setattr(im_module, "get_proxies_ssl", lambda: "/example/ca.pem")
    im_module._anonymous_profile_info(bot, "target")
    args, kwargs = bot.context._session.get.call_args
    assert args == ("https://www.instagram.com/target/embed/",)
    assert kwargs["proxies"] == {"https": "http://proxy.example:8080"}
    assert kwargs["verify"] == "/example/ca.pem"
    assert kwargs["allow_redirects"] is False
    bot.context.do_sleep.assert_called_once()
    bot.context._rate_controller.wait_before_query.assert_called_once_with("other")


# Neither missing snapshot attributes nor methods that load metadata directly reach the failing endpoint again.
def test_unknown_fields_do_not_load_lazily(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    profile = im_module.profile_from_username_resilient(bot, "target")
    bot.context.get_json = Mock(side_effect=AssertionError("lazy metadata request"))
    profile._obtain_metadata()
    assert profile.is_business_account is None
    assert profile.external_url is None
    bot.context.get_json.assert_not_called()


# The Reel code helper finds no dedicated Reels list in a public snapshot and spends no request looking.
def test_reel_code_helper_reads_nothing_from_the_snapshot(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    im_module.profile_from_username_resilient(bot, "target")
    assert im_module.get_real_reel_code(bot, "target") is None
    assert bot.context._session.get.call_count == 1


# A failed fallback is explained as an IP limit or a private account, never as an expired session it does not use.
def test_failed_fallback_has_its_own_advice(im_module):
    limited = im_module.classify_recovery_error("RuntimeError: Public embed fallback failed for target: HTTP 401", is_logged_in=False)
    throttled = im_module.classify_recovery_error("RuntimeError: Public embed fallback failed for target: HTTP 429", is_logged_in=False)
    assert limited.code == "instagram.public_fallback_failed"
    assert "anonymous-profile-http-400" in limited.fix
    assert throttled.code == "instagram.rate_limited"
    assert not im_module.is_account_level_failure(im_module.classify_failure_class("Public embed fallback failed for target: HTTP 401"))


# Drives startup and later checks with the monitor's own pass, reading profiles from the supplied sequence.
def _drive_monitor(im_module, monkeypatch, profiles):
    import threading

    stop = threading.Event()
    calls = []
    alerts = []
    bot = Mock()
    bot.context.is_logged_in = False

    # Supplies consecutive profiles and stops after the final profile has been processed.
    def profile(bot, username):
        followers, following, bio = profiles[min(len(calls), len(profiles) - 1)]
        calls.append(username)
        if len(calls) >= len(profiles):
            stop.set()
        return SimpleNamespace(username="target", userid=77, followers=followers, followees=following, biography=bio,
                               is_private=False, followed_by_viewer=False, mediacount=20,
                               profile_pic_url_no_iphone="https://example.com/avatar.jpg")

    for name, value in (("INSTA_CHECK_INTERVAL", 1), ("RANDOM_SLEEP_DIFF_LOW", 0), ("RANDOM_SLEEP_DIFF_HIGH", 0),
                        ("NEXT_OPERATION_DELAY", 0), ("DETECT_CHANGED_PROFILE_PIC", False), ("WEB_DASHBOARD_ENABLED", False), ("SESSION_USERNAME", ""),
                        ("SKIP_SESSION", True), ("SKIP_FOLLOWERS", True), ("SKIP_FOLLOWINGS", True),
                        ("SKIP_GETTING_STORY_DETAILS", True), ("SKIP_GETTING_POSTS_DETAILS", True),
                        ("GET_MORE_POST_DETAILS", False), ("DETECT_COLLAB_POSTS", False), ("FOLLOWERS_CHURN_DETECTION", False),
                        ("OUTPUT_DIR", "")):
        monkeypatch.setattr(im_module, name, value)
    monkeypatch.setattr(im_module, "instaloader_client", lambda **kwargs: bot)
    monkeypatch.setattr(im_module, "profile_from_username_resilient", profile)
    monkeypatch.setattr(im_module, "interruptible_sleep", lambda seconds, event=None: stop.is_set())
    monkeypatch.setattr(im_module, "send_notification_channels", lambda *args, **kwargs: alerts.append(args))
    monkeypatch.setattr(im_module, "notify_monitoring_error", lambda *args, **kwargs: pytest.fail("monitor raised an error"))
    im_module._run_instagram_monitor_pass("target", "", True, True, True, True, True, False, stop_event=stop)
    assert len(calls) == len(profiles)
    return alerts


# Runs startup and subsequent checks, comparing restored fields with the last known values.
@pytest.mark.parametrize("values", [[(None, None), (None, None)], [(None, None), (0, "")], [(5, "Original"), (None, None), (5, "Original")], [(5, "Original"), (None, None), (6, "Restored")]])
def test_monitor_pass_tolerates_unavailable_fields(im_module, monkeypatch, tmp_path, values):
    monkeypatch.chdir(tmp_path)
    alerts = _drive_monitor(im_module, monkeypatch, [(12, following, bio) for following, bio in values])
    if values[0][0] is None or values[-1] == values[0]:
        assert not alerts
    else:
        assert len(alerts) == 2
        assert "5 -> 6" in alerts[0][1]
        assert "bio has changed" in alerts[1][1]


# A count saved by an earlier run stays the comparison value while the current one is unknown at startup.
def test_saved_count_survives_an_unknown_startup_count(im_module, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "instagram_target_followers.json").write_text(json.dumps([12, ["fan"]]), encoding="utf-8")
    alerts = _drive_monitor(im_module, monkeypatch, [(None, 5, "Bio"), (15, 5, "Bio")])
    assert len(alerts) == 1
    assert "12 -> 15" in alerts[0][1]
