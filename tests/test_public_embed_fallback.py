"""Synthetic public embed fixtures; no account data or network requests."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


# Builds a small public profile with a pinned older post and a newer carousel.
def _payload():
    owner = {"id": "77", "username": "target", "is_private": False}
    posts = []
    for shortcode, timestamp in (("PINNED", 1700000000), ("NEWEST", 1700000300)):
        posts.append({"shortcode_media": {
            "id": str(timestamp), "shortcode": shortcode, "taken_at_timestamp": timestamp,
            "owner": dict(owner), "display_url": "https://example.com/photo.jpg", "is_video": False,
            "edge_media_to_caption": {"edges": [{"node": {"text": "Example caption"}}]},
            "edge_sidecar_to_children": {"edges": [{"node": {"display_url": "https://example.com/child.jpg"}}]},
        }})
    return {"username": "target", "owner_id": "77", "full_name": "Example", "followers_count": 12,
            "posts_count": 20, "profile_pic_url": "https://example.com/avatar.jpg", "graphql_media": posts}


# Wraps JSON in the nested string used by Instagram's ServerJS payload without executable evaluation.
def _html(payload):
    data = {"require": [["Example", {"contextJSON": json.dumps({"context": payload})}]]}
    return '<html><script>requireLazy([],function(){s.handle(' + json.dumps(data) + ');});</script></html>'


# Creates an anonymous context whose mobile request fails with the reported deleted schema.
def _bot(im_module, monkeypatch, payload=None):
    response = Mock(status_code=200, text=_html(payload or _payload()))
    session = Mock()
    session.get.return_value = response
    context = SimpleNamespace(is_logged_in=False, request_timeout=20, _session=session,
                              do_sleep=Mock(), _rate_controller=Mock(), get_iphone_json=Mock(),
                              get_page_data=Mock(return_value=[]), get_anonymous_session=Mock(return_value=session))
    context.get_iphone_json.side_effect = im_module.instaloader.exceptions.QueryReturnedBadRequestException(
        "400 Bad Request: Asset asset://laser.provider/ig_business_category_subvertical has been deleted. You cannot use this schema")
    monkeypatch.setattr(im_module, "ensure_instagram_session_wrapped", lambda session: None)
    return SimpleNamespace(context=context), response


# The real entry points must recover together and share the snapshot rather than repeat the failed endpoint.
def test_schema_failure_recovers_profile_and_latest_post(im_module, monkeypatch):
    bot, response = _bot(im_module, monkeypatch)
    profile = im_module.profile_from_username_resilient(bot, "target")
    post, kind = im_module.latest_post_mobile("target", bot)
    assert (profile.userid, profile.username, profile.followers, profile.mediacount) == (77, "target", 12, 20)
    assert profile.followees is None
    assert profile.biography is None
    assert profile.profile_pic_url_no_iphone == "https://example.com/avatar.jpg"
    assert profile.is_private is False
    assert (post.shortcode, post.caption, kind) == ("NEWEST", "Example caption", "post")
    assert bot.context.get_iphone_json.call_count == 1
    assert bot.context._session.get.call_count == 1
    response.close.assert_called_once()


# Authentication and throttling failures never spend another request on the embed endpoint.
@pytest.mark.parametrize("error", ["401 Unauthorized", "429 Too Many Requests", "400 feedback_required", "400 other schema error"])
def test_other_failures_do_not_fall_back(im_module, monkeypatch, error):
    bot, _ = _bot(im_module, monkeypatch)
    bot.context.get_iphone_json.side_effect = im_module.instaloader.exceptions.ConnectionException(error)
    with pytest.raises(im_module.instaloader.exceptions.ConnectionException):
        im_module.profile_from_username_resilient(bot, "target")
    bot.context._session.get.assert_not_called()


# Healthy mobile responses and logged-in callers keep their existing source.
def test_healthy_response_is_unchanged(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    original = {"data": {"user": {"id": "77", "username": "target"}}}
    bot.context.get_iphone_json.side_effect = None
    bot.context.get_iphone_json.return_value = original
    assert im_module._anonymous_profile_info(bot, "target") is original
    bot.context._session.get.assert_not_called()


# Even the same schema exception cannot switch a signed-in session onto an anonymous source.
def test_logged_in_schema_failure_does_not_fall_back(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    bot.context.is_logged_in = True
    with pytest.raises(im_module.instaloader.exceptions.QueryReturnedBadRequestException):
        im_module._anonymous_profile_info(bot, "target")
    bot.context._session.get.assert_not_called()


# A successful route survives snapshot expiry; every later poll fetches fresh embed data.
def test_route_is_cached_but_snapshot_expires(im_module, monkeypatch):
    bot, response = _bot(im_module, monkeypatch)
    clock = [10.0]
    monkeypatch.setattr(im_module.time, "monotonic", lambda: clock[0])
    im_module._anonymous_profile_info(bot, "target")
    clock[0] += 6
    changed = _payload()
    changed["followers_count"] = 13
    response.text = _html(changed)
    assert im_module._anonymous_profile_info(bot, "target")["data"]["user"]["edge_followed_by"]["count"] == 13
    assert bot.context.get_iphone_json.call_count == 1
    assert bot.context._session.get.call_count == 2


# Private, mismatched, malformed and unexpectedly empty payloads must not look like successful empty profiles.
@pytest.mark.parametrize("case", ["username", "owner", "private", "id", "timestamp", "empty", "count", "not_json", "oversize"])
def test_invalid_embed_is_rejected(im_module, case):
    payload = _payload()
    if case == "username":
        payload["username"] = "different"
    elif case == "owner":
        payload["graphql_media"][0]["shortcode_media"]["owner"]["username"] = "different"
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
    html = "<script>location.href='/accounts/login/';</script>" if case == "not_json" else _html(payload)
    if case == "oversize":
        html = " " * (4 * 1024 * 1024 + 1)
    with pytest.raises(RuntimeError, match="public embed"):
        im_module._parse_public_embed("target", html)


# Parsing preserves carousel children and supports direct JSON script blocks as well as nested ServerJS strings.
def test_direct_json_preserves_carousel(im_module):
    payload = _payload()
    result = im_module._parse_public_embed("target", '<script type="application/json">' + json.dumps(payload) + '</script>')
    edges = result["edge_owner_to_timeline_media"]["edges"]
    assert edges[1]["node"]["edge_sidecar_to_children"]["edges"][0]["node"]["display_url"].endswith("child.jpg")


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


# Failed recovery closes its response and does not commit the route, so a later healthy API response can recover.
@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_failed_embed_is_not_cached(im_module, monkeypatch, status):
    bot, response = _bot(im_module, monkeypatch)
    response.status_code = status
    with pytest.raises(RuntimeError, match="public embed"):
        im_module._anonymous_profile_info(bot, "target")
    response.close.assert_called_once()
    original = {"data": {"user": {"id": "77"}}}
    bot.context.get_iphone_json.side_effect = None
    bot.context.get_iphone_json.return_value = original
    assert im_module._anonymous_profile_info(bot, "target") is original


# Runs startup and subsequent checks, comparing restored fields with the last known values.
@pytest.mark.parametrize("values", [[(None, None), (None, None)], [(None, None), (0, "")], [(5, "Original"), (None, None), (5, "Original")], [(5, "Original"), (None, None), (6, "Restored")]])
def test_monitor_pass_tolerates_unavailable_fields(im_module, monkeypatch, values):
    import threading

    stop = threading.Event()
    calls = []
    alerts = []
    bot = Mock()
    bot.context.is_logged_in = False

    # Supplies consecutive profiles and stops after the final profile has been processed.
    def profile(bot, username):
        following, bio = values[min(len(calls), len(values) - 1)]
        calls.append(username)
        if len(calls) >= len(values):
            stop.set()
        return SimpleNamespace(username="target", userid=77, followers=12, followees=following, biography=bio,
                               is_private=False, followed_by_viewer=False, mediacount=20,
                               profile_pic_url_no_iphone="https://example.com/avatar.jpg")

    for name, value in (("INSTA_CHECK_INTERVAL", 1), ("RANDOM_SLEEP_DIFF_LOW", 0), ("RANDOM_SLEEP_DIFF_HIGH", 0),
                        ("NEXT_OPERATION_DELAY", 0), ("DETECT_CHANGED_PROFILE_PIC", False), ("WEB_DASHBOARD_ENABLED", False), ("SESSION_USERNAME", ""),
                        ("SKIP_SESSION", True), ("SKIP_FOLLOWERS", True), ("SKIP_FOLLOWINGS", True),
                        ("SKIP_GETTING_STORY_DETAILS", True), ("SKIP_GETTING_POSTS_DETAILS", True),
                        ("GET_MORE_POST_DETAILS", False), ("DETECT_COLLAB_POSTS", False), ("FOLLOWERS_CHURN_DETECTION", False)):
        monkeypatch.setattr(im_module, name, value)
    monkeypatch.setattr(im_module, "instaloader_client", lambda **kwargs: bot)
    monkeypatch.setattr(im_module, "profile_from_username_resilient", profile)
    monkeypatch.setattr(im_module, "interruptible_sleep", lambda seconds, event=None: stop.is_set())
    monkeypatch.setattr(im_module, "send_notification_channels", lambda *args, **kwargs: alerts.append(args))
    monkeypatch.setattr(im_module, "notify_monitoring_error", lambda *args, **kwargs: pytest.fail("monitor raised an error"))
    im_module._run_instagram_monitor_pass("target", "", True, True, True, True, True, False, stop_event=stop)
    assert len(calls) == len(values)
    if values[0][0] is None or values[-1] == values[0]:
        assert not alerts
    else:
        assert len(alerts) == 2
        assert "5 -> 6" in alerts[0][1]
        assert "bio has changed" in alerts[1][1]


# Represents the two profile queries and the iPhone-shaped timeline returned by the normal public page.
def _page():
    nodes = []
    for shortcode, timestamp in (("PINNED", 1700000000), ("REEL", 1700000300)):
        nodes.append({"node": {"pk": str(timestamp), "code": shortcode, "taken_at": timestamp,
                              "media_type": 2, "product_type": "clips", "caption": {"text": "Page caption"},
                              "image_versions2": {"candidates": [{"url": "https://example.com/preview.jpg"}]},
                              "video_versions": [{"url": "https://example.com/video.mp4"}],
                              "user": {"pk": "77", "username": "target", "is_private": False},
                              "coauthor_producers": [{"username": "collaborator"}]}})
    return [{"xig_user_by_username": {"pk": "77", "id": "opaque-query-id", "username": "target",
                                      "is_private": False, "all_media_count": 20, "follower_count": 12,
                                      "following_count": 5, "biography": "Page biography",
                                      "profile_pic_url": "https://example.com/avatar.jpg"}},
            {"xig_user_by_username": {"polaris_ordered_timeline_connection": {"edges": nodes}}}]


# The normal page precedes the embed, normalizes its real account id and supplies every anonymous consumer.
def test_normal_page_is_preferred_and_shared(im_module, monkeypatch):
    bot, response = _bot(im_module, monkeypatch)
    bot.context.get_page_data.return_value = _page()
    profile = im_module.profile_from_username_resilient(bot, "target")
    assert (profile.userid, profile.mediacount, profile.followees, profile.biography) == (77, 20, 5, "Page biography")
    assert profile.is_business_account is None
    post, _ = im_module.latest_post_mobile("target", bot)
    assert (post.shortcode, post.caption, post.video_url) == ("REEL", "Page caption", "https://example.com/video.mp4")
    assert im_module.get_real_reel_code(bot, "target") == "REEL"
    collabs = im_module.fetch_leaked_collab_posts("target", bot)
    assert collabs[-1]["collaborators"] == ["collaborator"]
    assert bot.context.get_iphone_json.call_count == 1
    bot.context.get_page_data.assert_called_once_with("target/")
    bot.context._session.get.assert_not_called()
    response.close.assert_not_called()


# Instagram can reword its HTTP 400 error without disabling the anonymous fallback.
def test_any_anonymous_bad_request_tries_page(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    bot.context.get_iphone_json.side_effect = im_module.instaloader.exceptions.QueryReturnedBadRequestException("400 changed wording")
    bot.context.get_page_data.return_value = _page()
    assert im_module.profile_from_username_resilient(bot, "target").userid == 77


# A limit on the page stops recovery, rather than spending a further embed request against the same IP.
@pytest.mark.parametrize("status", [401, 429])
def test_page_limits_do_not_trigger_embed(im_module, monkeypatch, status):
    bot, _ = _bot(im_module, monkeypatch)
    bot.context.get_page_data.side_effect = im_module.instaloader.exceptions.ConnectionException(f"{status} error")
    with pytest.raises(im_module.instaloader.exceptions.ConnectionException):
        im_module.profile_from_username_resilient(bot, "target")
    bot.context._session.get.assert_not_called()


# A login redirect exposes no page data and still permits the last-resort public embed.
def test_page_redirect_uses_embed(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    bot.context.get_page_data.side_effect = im_module.instaloader.exceptions.ConnectionException("302 Found when accessing profile")
    assert im_module.profile_from_username_resilient(bot, "target").userid == 77
    assert bot.context._session.get.call_count == 1


# A remembered page route is refreshed, and can transition to embed if the page stops embedding metadata.
def test_page_route_survives_and_can_fall_back_later(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    clock = [10.0]
    monkeypatch.setattr(im_module.time, "monotonic", lambda: clock[0])
    bot.context.get_page_data.return_value = _page()
    im_module._anonymous_profile_info(bot, "target")
    clock[0] += 6
    bot.context.get_page_data.return_value = []
    im_module._anonymous_profile_info(bot, "target")
    clock[0] += 6
    im_module._anonymous_profile_info(bot, "target")
    assert bot.context.get_iphone_json.call_count == 1
    assert bot.context.get_page_data.call_count == 2
    assert bot.context._session.get.call_count == 2


# An embed never invents a dedicated Reel or retries the broken endpoint for other anonymous consumers.
def test_embed_consumers_share_data_without_inventing_reels(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    im_module.profile_from_username_resilient(bot, "target")
    assert im_module.get_real_reel_code(bot, "target") is None
    assert len(im_module.fetch_leaked_collab_posts("target", bot)) == 2
    assert bot.context.get_iphone_json.call_count == 1
    assert bot.context._session.get.call_count == 1


# The page session must retain proxy and TLS settings without mutating the original context's factory.
def test_page_session_respects_network_settings(im_module, monkeypatch):
    context = im_module.instaloader.InstaloaderContext(sleep=False, quiet=True)
    seen = []
    original_factory = context.get_anonymous_session

    # Exercises the factory on the copied context that get_page_data runs on.
    def get_page_data(ctx, path):
        with ctx.get_anonymous_session() as session:
            seen.append((dict(session.proxies), session.verify, session._instagram_monitor_wrapped))
        return _page()

    monkeypatch.setattr(im_module.instaloader.InstaloaderContext, "get_page_data", get_page_data)
    monkeypatch.setattr(im_module, "get_proxies", lambda: {"https": "http://proxy.example:8080"})
    monkeypatch.setattr(im_module, "get_proxies_ssl", lambda: "/example/ca.pem")
    try:
        result = im_module._fetch_public_profile_page(SimpleNamespace(context=context), "target")
        assert result["data"]["user"]["id"] == "77"
        assert seen == [({"https": "http://proxy.example:8080"}, "/example/ca.pem", True)]
        assert context.get_anonymous_session == original_factory
    finally:
        context.close()


# A page with missing optional fields remains a valid snapshot without producing zero counts or extra requests.
def test_unknown_page_fields_do_not_load_lazily(im_module, monkeypatch):
    bot, _ = _bot(im_module, monkeypatch)
    page = _page()
    for key in ("biography", "follower_count", "following_count", "profile_pic_url"):
        page[0]["xig_user_by_username"].pop(key)
    bot.context.get_page_data.return_value = page
    profile = im_module.profile_from_username_resilient(bot, "target")
    assert profile.followers is None
    assert profile.followees is None
    assert profile.biography is None
    assert profile.is_business_account is None
    assert profile.profile_pic_url_no_iphone is None
    assert profile.mediacount == 20
    assert bot.context.get_iphone_json.call_count == 1
    bot.context._session.get.assert_not_called()


# Wrong, private, incomplete and invalid page snapshots must not bypass embed validation.
@pytest.mark.parametrize("field,value", [("username", "other"), ("is_private", True), ("pk", "opaque"), ("all_media_count", None)])
def test_invalid_profile_page_uses_validated_embed(im_module, monkeypatch, field, value):
    bot, _ = _bot(im_module, monkeypatch)
    page = _page()
    page[0]["xig_user_by_username"][field] = value
    bot.context.get_page_data.return_value = page
    profile = im_module.profile_from_username_resilient(bot, "target")
    assert profile._node["_public_web"] == "embed"
    assert profile.userid == 77
