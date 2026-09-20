"""Offline regression tests for endpoint-specific authenticated profile recovery."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests


FEEDBACK = '400 Bad Request - "fail" status, message "feedback_required" when accessing https://www.instagram.com/api/v1/users/web_profile_info/?username=owner'


# Supplies a real Instaloader Profile with only the network calls replaced
@pytest.fixture
def profile_context(im_module):
    session = requests.Session()
    session.cookies.set('ds_user_id', '101')
    user = {'pk': '101', 'username': 'owner', 'full_name': 'Example', 'biography': 'Example bio',
            'follower_count': 12, 'following_count': 7, 'media_count': 3,
            'is_private': False, 'is_verified': False, 'profile_pic_url_hd': 'https://example.org/avatar.jpg'}
    ctx = SimpleNamespace(is_logged_in=True, username='owner', _session=session,
                          get_json=Mock(side_effect=im_module.instaloader.exceptions.AbortDownloadException(FEEDBACK)),
                          doc_id_graphql_query=Mock(return_value={'data': {'user': user}, 'status': 'ok'}))
    return SimpleNamespace(context=ctx), user


def test_feedback_recovers_full_metadata_and_refreshes_counts(im_module, profile_context):
    bot, user = profile_context
    first = im_module.profile_from_username_resilient(bot, 'owner')
    assert (first.userid, first.followers, first.followees, first.mediacount) == (101, 12, 7, 3)
    assert first.biography == 'Example bio'
    assert first.profile_pic_url_no_iphone == 'https://example.org/avatar.jpg'
    assert first._has_full_metadata
    user['follower_count'] = 13
    second = im_module.profile_from_username_resilient(bot, 'owner')
    assert first.followers == 12
    assert second.followers == 13
    assert first is not second
    assert bot.context.get_json.call_count == 1
    assert bot.context.doc_id_graphql_query.call_count == 2


def test_healthy_profile_path_is_unchanged(im_module, profile_context):
    bot, user = profile_context
    bot.context.get_json.side_effect = None
    bot.context.get_json.return_value = {'data': {'user': dict(user)}}
    assert im_module.profile_from_username_resilient(bot, 'owner').username == 'owner'
    bot.context.doc_id_graphql_query.assert_not_called()
    assert not bot.context._monitor_profile_graphql['enabled']


@pytest.mark.parametrize('message', [
    FEEDBACK.replace('feedback_required', 'checkpoint_required'),
    FEEDBACK.replace('feedback_required', 'challenge_required'),
    FEEDBACK.replace('feedback_required', 'login_required'),
    FEEDBACK.replace('400 Bad Request', '429 Too Many Requests'),
    FEEDBACK.replace('/api/v1/users/web_profile_info/', '/graphql/query'),
    FEEDBACK.replace('www.instagram.com', 'i.instagram.com'),
    FEEDBACK.replace('www.instagram.com', 'www.instagram.com.example.org'),
    FEEDBACK.replace('www.instagram.com', '['),
    FEEDBACK.replace('/web_profile_info/', '/web_profile_info/other'),
    'feedback_required web_profile_info',
])
def test_unrelated_aborts_do_not_fall_back(im_module, profile_context, message):
    bot, _ = profile_context
    error = im_module.instaloader.exceptions.AbortDownloadException(message)
    bot.context.get_json.side_effect = error
    with pytest.raises(type(error)) as caught:
        im_module.profile_from_username_resilient(bot, 'owner')
    assert caught.value is error
    bot.context.doc_id_graphql_query.assert_not_called()


def test_rate_limit_and_network_errors_do_not_fall_back(im_module, profile_context):
    bot, _ = profile_context
    for error_type in (im_module.instaloader.exceptions.TooManyRequestsException, im_module.instaloader.exceptions.ConnectionException):
        error = error_type('request failed')
        bot.context.get_json.side_effect = error
        with pytest.raises(error_type) as caught:
            im_module.profile_from_username_resilient(bot, 'owner')
        assert caught.value is error
    bot.context.doc_id_graphql_query.assert_not_called()


@pytest.mark.parametrize('mobile_succeeds', [True, False])
def test_anonymous_behavior_is_unchanged(im_module, monkeypatch, profile_context, mobile_succeeds):
    bot, _ = profile_context
    bot.context.is_logged_in = False
    mobile = object() if mobile_succeeds else None
    monkeypatch.setattr(im_module, '_profile_from_web_profile_info', lambda *_: mobile)
    if mobile_succeeds:
        assert im_module.profile_from_username_resilient(bot, 'owner') is mobile
        bot.context.get_json.assert_not_called()
    else:
        with pytest.raises(im_module.instaloader.exceptions.AbortDownloadException):
            im_module.profile_from_username_resilient(bot, 'owner')
    bot.context.doc_id_graphql_query.assert_not_called()
    assert not hasattr(bot.context, '_monitor_profile_graphql')


def test_exact_name_search_caches_only_the_matching_id(im_module, monkeypatch, profile_context):
    bot, user = profile_context
    user.update(pk='202', username='target')
    search = Mock(return_value=SimpleNamespace(get_profiles=lambda: iter([
        SimpleNamespace(username='target_similar', userid=999), SimpleNamespace(username='target', userid=202)])))
    monkeypatch.setattr(im_module.instaloader, 'TopSearchResults', search)
    assert im_module.profile_from_username_resilient(bot, 'TARGET').userid == 202
    assert im_module.profile_from_username_resilient(bot, 'target').userid == 202
    search.assert_called_once_with(bot.context, 'target')
    assert bot.context._monitor_profile_graphql['ids'] == {'target': '202'}


def test_missing_exact_name_is_not_reported_as_a_nonexistent_account(im_module, monkeypatch, profile_context):
    bot, _ = profile_context
    monkeypatch.setattr(im_module.instaloader, 'TopSearchResults', lambda *_: SimpleNamespace(get_profiles=lambda: []))
    with pytest.raises(im_module.instaloader.exceptions.ConnectionException, match='exact profile ID'):
        im_module.profile_from_username_resilient(bot, 'target')
    bot.context.doc_id_graphql_query.assert_not_called()
    assert not bot.context._monitor_profile_graphql['enabled']


@pytest.mark.parametrize('field,value', [('pk', '999'), ('username', 'someone_else')])
def test_mismatched_identity_never_enables_route(im_module, profile_context, field, value):
    bot, user = profile_context
    user[field] = value
    with pytest.raises(im_module.instaloader.exceptions.ConnectionException, match='different profile'):
        im_module.profile_from_username_resilient(bot, 'owner')
    assert not bot.context._monitor_profile_graphql['enabled']
    assert bot.context._monitor_profile_graphql['ids'] == {}


@pytest.mark.parametrize('marker', ['checkpoint_required', 'challenge_required', 'feedback_required'])
def test_graphql_failure_propagates_without_enabling_route(im_module, profile_context, marker):
    bot, _ = profile_context
    error = im_module.instaloader.exceptions.AbortDownloadException(marker)
    bot.context.doc_id_graphql_query.side_effect = error
    with pytest.raises(type(error)) as caught:
        im_module.profile_from_username_resilient(bot, 'owner')
    assert caught.value is error
    assert not bot.context._monitor_profile_graphql['enabled']


@pytest.mark.parametrize('replace_session', [True, False])
def test_session_changes_reset_successful_route(im_module, profile_context, replace_session):
    bot, _ = profile_context
    im_module.profile_from_username_resilient(bot, 'owner')
    old_state = bot.context._monitor_profile_graphql
    if replace_session:
        bot.context._session = requests.Session()
    else:
        bot.context.username = 'new_login'
    bot.context.get_json.side_effect = im_module.instaloader.exceptions.AbortDownloadException('checkpoint_required')
    with pytest.raises(im_module.instaloader.exceptions.AbortDownloadException):
        im_module.profile_from_username_resilient(bot, 'owner')
    assert bot.context.get_json.call_count == 2
    assert bot.context._monitor_profile_graphql is not old_state
    assert not bot.context._monitor_profile_graphql['enabled']
    assert bot.context._monitor_profile_graphql['ids'] == {}


def test_cached_id_is_invalidated_on_identity_mismatch(im_module, profile_context):
    bot, user = profile_context
    im_module.profile_from_username_resilient(bot, 'owner')
    user['username'] = 'renamed_account'
    with pytest.raises(im_module.instaloader.exceptions.ConnectionException, match='different profile'):
        im_module.profile_from_username_resilient(bot, 'owner')
    assert 'owner' not in bot.context._monitor_profile_graphql['ids']


def test_downstream_iterators_do_not_repeat_profile_fetch(im_module, monkeypatch, profile_context):
    bot, _ = profile_context
    profile = im_module.profile_from_username_resilient(bot, 'owner')
    iterator = Mock()
    monkeypatch.setattr(im_module.instaloader.structures, 'NodeIterator', iterator)
    profile.get_posts()
    assert iterator.call_args.kwargs['query_variables']['username'] == 'owner'
    profile.get_followers()
    assert iterator.call_args.args[4] == {'id': '101'}
    assert bot.context.doc_id_graphql_query.call_count == 1
    assert bot.context.get_json.call_count == 1
