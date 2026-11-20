"""Push notifications for follow requests and new followers (issue #604)."""
import json
from unittest.mock import patch

from django.test import override_settings

from .. import notifications, push
from ..constants import (
    BAN_TYPE_SHADOW, FOLLOW_CATEGORY_FAMILY, FOLLOW_CATEGORY_FRIEND, MAX_USERNAME_LENGTH, PUSH_TYPE_ALL,
    PUSH_TYPE_FOLLOW_ACCEPTED, PUSH_TYPE_FOLLOW_REQUEST, PUSH_TYPE_NEW_FOLLOWER, PUSH_TYPE_PARENTS,
    PUSH_TYPE_TREE, Patterns,
)
from ..input_validator import is_valid_pattern
from ..models import FollowRequest, NotificationPreference, UserBan, UserBlock, UserFollow
from .test_activity_push import SEND_PUSH, ActivityPushTestCase, _sent
from .test_private_accounts import PrivateAccountTestBase


class FollowPayloadSizeTests(ActivityPushTestCase):
    """The longest valid username keeps every follow payload inside APNs' limit."""

    def test_longest_astral_username_fits_apns(self):
        # 150 Deseret letters: valid \w characters, 4 bytes each in UTF-8 and
        # 12 as JSON \u escapes.
        name = '\U00010400' * MAX_USERNAME_LENGTH
        self.assertTrue(is_valid_pattern(name, Patterns.username))
        actor = self._user('placeholder')
        actor.username = name
        for kind, title in ((PUSH_TYPE_FOLLOW_REQUEST, f'{name} asked to follow you'),
                            (PUSH_TYPE_NEW_FOLLOWER, f'{name} started following you'),
                            (PUSH_TYPE_FOLLOW_ACCEPTED, f'{name} accepted your follow request')):
            body = push._apns_body(push.build_follow_payload(kind, actor, title, 'Tap to see.'))
            self.assertLessEqual(len(body), push.APNS_MAX_PAYLOAD_BYTES, kind)
            self.assertEqual(json.loads(body)['data']['username'], name)


class FollowPushTypeTests(ActivityPushTestCase):
    """The new kinds slot into the preference tree and the Activity channel."""

    def test_follow_kinds_have_every_source(self):
        for kind in (PUSH_TYPE_FOLLOW_REQUEST, PUSH_TYPE_NEW_FOLLOWER):
            self.assertEqual(PUSH_TYPE_PARENTS[kind], PUSH_TYPE_ALL)
            children = {value for value, _, parent in PUSH_TYPE_TREE if parent == kind}
            self.assertEqual(children, {f'{kind}_{source}' for source in
                                        ('following', 'friend', 'family', 'other')})

    def test_accepted_requests_have_only_follow_sources(self):
        # The requester always follows the owner once accepted: no "other".
        self.assertEqual(PUSH_TYPE_PARENTS[PUSH_TYPE_FOLLOW_ACCEPTED], PUSH_TYPE_ALL)
        children = {value for value, _, parent in PUSH_TYPE_TREE if parent == PUSH_TYPE_FOLLOW_ACCEPTED}
        self.assertEqual(children, {f'follow_accepted_{source}' for source in ('following', 'friend', 'family')})

    def test_every_type_fits_the_preference_column(self):
        max_length = NotificationPreference._meta.get_field('notification_type').max_length
        for value, _, _ in PUSH_TYPE_TREE:
            self.assertLessEqual(len(value), max_length, value)

    def test_follow_kinds_use_the_activity_channel(self):
        for kind in (PUSH_TYPE_FOLLOW_REQUEST, PUSH_TYPE_NEW_FOLLOWER, PUSH_TYPE_FOLLOW_ACCEPTED):
            self.assertEqual(push.android_channel_for({'type': kind}), push.ANDROID_CHANNEL_ACTIVITY)

    def test_kind_off_silences_its_sources_only(self):
        NotificationPreference.objects.create(
            user=self.author, notification_type=PUSH_TYPE_NEW_FOLLOWER, enabled=False)
        self.assertFalse(push.is_push_type_enabled(self.author, 'new_follower_other'))
        self.assertTrue(push.is_push_type_enabled(self.author, 'follow_request_other'))


@override_settings(FRONTEND_BASE_URL='https://smiling.social')
@patch(SEND_PUSH)
class FollowRequestPushTests(ActivityPushTestCase):

    def setUp(self):
        super().setUp()
        self.author.is_private = True
        self.author.save()
        self.requester = self._user('requester')

    def _request(self):
        return FollowRequest.objects.create(user_from=self.requester, user_to=self.author)

    def _job(self, follow_request_id=None):
        if follow_request_id is None:
            follow_request_id = FollowRequest.objects.get(user_from=self.requester, user_to=self.author).pk
        notifications.push_follow_request(follow_request_id)

    def test_owner_is_told_with_link_to_requests(self, send_push):
        self._request()
        self._job()
        sent = _sent(send_push)
        self.assertEqual(set(sent), {('author', 'follow_request_other')})
        payload = sent[('author', 'follow_request_other')]
        self.assertEqual(payload['title'], 'requester asked to follow you')
        self.assertEqual(payload['data'], {
            'type': PUSH_TYPE_FOLLOW_REQUEST,
            'username': 'requester',
            'deep_link': 'https://smiling.social/follow-requests',
        })
        self.assertNotIn('post_identifier', payload['data'])

    def test_source_is_the_owners_label_for_the_requester(self, send_push):
        self._request()
        UserFollow.objects.create(user_from=self.author, user_to=self.requester, category=FOLLOW_CATEGORY_FRIEND)
        self._job()
        self.assertEqual(set(_sent(send_push)), {('author', 'follow_request_friend')})

    def test_request_gone_before_job_is_silent(self, send_push):
        # Cancelled, denied, approved or converted: nothing to announce.
        follow_request = self._request()
        follow_request_id = follow_request.pk
        follow_request.delete()
        self._job(follow_request_id)
        send_push.assert_not_called()

    def test_owner_gone_public_is_silent(self, send_push):
        # The request may still be pending while the going-public backlog
        # converts, but there is nothing left to approve.
        self._request()
        self.author.is_private = False
        self.author.save()
        self._job()
        send_push.assert_not_called()

    def test_going_public_check_does_not_spend_the_dedupe(self, send_push):
        self._request()
        self.author.is_private = False
        self.author.save()
        self._job()
        self.author.is_private = True
        self.author.save()
        self._job()
        self.assertEqual(send_push.call_count, 1)

    def test_rerequest_within_window_is_silent(self, send_push):
        self._request()
        self._job()
        FollowRequest.objects.all().delete()
        self._request()
        self._job()
        self.assertEqual(send_push.call_count, 1)

    def test_shadow_banned_requester_is_silent(self, send_push):
        self._request()
        UserBan.objects.create(user=self.requester, ban_type=BAN_TYPE_SHADOW, reason='x')
        self._job()
        send_push.assert_not_called()

    def test_block_either_way_is_silent(self, send_push):
        self._request()
        for blocker, blocked in ((self.author, self.requester), (self.requester, self.author)):
            block = UserBlock.objects.create(user_blocker=blocker, user_blocked=blocked)
            self._job()
            block.delete()
        send_push.assert_not_called()

    def test_cross_age_band_is_silent(self, send_push):
        self._request()
        with patch('user_system.notifications.in_same_age_band', return_value=False):
            self._job()
        send_push.assert_not_called()


@override_settings(FRONTEND_BASE_URL='https://smiling.social')
@patch(SEND_PUSH)
class NewFollowerPushTests(ActivityPushTestCase):

    def setUp(self):
        super().setUp()
        self.follower = self._user('follower')

    def _job(self, follow_id=None):
        if follow_id is None:
            follow_id = UserFollow.objects.get(user_from=self.follower, user_to=self.author).pk
        notifications.push_new_follower(follow_id)

    def test_followee_is_told_with_link_to_follower(self, send_push):
        self._follow(self.follower, self.author)
        self._job()
        sent = _sent(send_push)
        self.assertEqual(set(sent), {('author', 'new_follower_other')})
        payload = sent[('author', 'new_follower_other')]
        self.assertEqual(payload['title'], 'follower started following you')
        self.assertEqual(payload['data'], {
            'type': PUSH_TYPE_NEW_FOLLOWER,
            'username': 'follower',
            'deep_link': 'https://smiling.social/profile/follower',
        })

    def test_follow_back_uses_the_followees_label(self, send_push):
        self._follow(self.follower, self.author)
        self._follow(self.author, self.follower, FOLLOW_CATEGORY_FRIEND)
        self._job()
        self.assertEqual(set(_sent(send_push)), {('author', 'new_follower_friend')})

    def test_unfollowed_before_job_is_silent(self, send_push):
        self._follow(self.follower, self.author)
        follow = UserFollow.objects.get(user_from=self.follower, user_to=self.author)
        follow_id = follow.pk
        follow.delete()
        self._job(follow_id)
        send_push.assert_not_called()

    def test_stale_job_ignores_a_later_follow_between_the_pair(self, send_push):
        # Follow, unfollow before the job runs, then follow again some other
        # way (say, an approved request): the first job must stay silent.
        self._follow(self.follower, self.author)
        first = UserFollow.objects.get(user_from=self.follower, user_to=self.author)
        first_id = first.pk
        first.delete()
        self._follow(self.follower, self.author)
        self._job(first_id)
        send_push.assert_not_called()

    def test_refollow_within_window_is_silent(self, send_push):
        self._follow(self.follower, self.author)
        self._job()
        UserFollow.objects.all().delete()
        self._follow(self.follower, self.author)
        self._job()
        self.assertEqual(send_push.call_count, 1)

    def test_shadow_banned_follower_is_silent(self, send_push):
        self._follow(self.follower, self.author)
        UserBan.objects.create(user=self.follower, ban_type=BAN_TYPE_SHADOW, reason='x')
        self._job()
        send_push.assert_not_called()

    def test_blocked_follower_is_silent(self, send_push):
        self._follow(self.follower, self.author)
        UserBlock.objects.create(user_blocker=self.author, user_blocked=self.follower)
        self._job()
        send_push.assert_not_called()

    def test_turned_off_type_is_not_delivered(self, _send_push):
        # Through the real send path: the kind's switch silences its sources.
        self._follow(self.follower, self.author)
        NotificationPreference.objects.create(
            user=self.author, notification_type=PUSH_TYPE_NEW_FOLLOWER, enabled=False)
        with patch('user_system.push._send_apns', return_value=[]) as apns, \
                patch('user_system.push._send_fcm', return_value=[]):
            push.send_push(self.author, {'title': 't', 'body': 'b', 'data': {}}, 'new_follower_other')
        apns.assert_not_called()


@override_settings(FRONTEND_BASE_URL='https://smiling.social')
@patch(SEND_PUSH)
class FollowAcceptedPushTests(ActivityPushTestCase):

    def setUp(self):
        super().setUp()
        self.author.is_private = True
        self.author.save()
        self.requester = self._user('requester')

    def _job(self, follow_id=None):
        if follow_id is None:
            follow_id = UserFollow.objects.get(user_from=self.requester, user_to=self.author).pk
        notifications.push_follow_accepted(follow_id)

    def test_requester_is_told_with_link_to_owner(self, send_push):
        self._follow(self.requester, self.author, FOLLOW_CATEGORY_FAMILY)
        self._job()
        sent = _sent(send_push)
        self.assertEqual(set(sent), {('requester', 'follow_accepted_family')})
        payload = sent[('requester', 'follow_accepted_family')]
        self.assertEqual(payload['title'], 'author accepted your follow request')
        self.assertEqual(payload['data'], {
            'type': PUSH_TYPE_FOLLOW_ACCEPTED,
            'username': 'author',
            'deep_link': 'https://smiling.social/profile/author',
        })

    def test_unfollowed_before_job_is_silent(self, send_push):
        self._follow(self.requester, self.author)
        follow = UserFollow.objects.get(user_from=self.requester, user_to=self.author)
        follow_id = follow.pk
        follow.delete()
        self._job(follow_id)
        send_push.assert_not_called()

    def test_repeat_within_window_is_silent(self, send_push):
        self._follow(self.requester, self.author)
        self._job()
        self._job()
        self.assertEqual(send_push.call_count, 1)

    def test_shadow_banned_owner_is_silent(self, send_push):
        self._follow(self.requester, self.author)
        UserBan.objects.create(user=self.author, ban_type=BAN_TYPE_SHADOW, reason='x')
        self._job()
        send_push.assert_not_called()

    def test_block_is_silent(self, send_push):
        self._follow(self.requester, self.author)
        UserBlock.objects.create(user_blocker=self.requester, user_blocked=self.author)
        self._job()
        send_push.assert_not_called()


@patch(SEND_PUSH)
class FollowViewWiringTests(PrivateAccountTestBase):
    """The follow endpoints trigger the pushes (eager in tests): a request to a
    private account tells its owner, approving it tells the requester (and not
    the owner), an outright follow tells the followee, and an account going
    public tells nobody."""

    def _types_for(self, send_push, user):
        return [call.args[2] for call in send_push.call_args_list if call.args[0] == user]

    def test_follow_request_notifies_owner(self, send_push):
        response = self._follow(self.local_username, self.viewer_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._types_for(send_push, self.author), ['follow_request_other'])

    def test_approving_a_request_tells_the_requester_only(self, send_push):
        self._follow(self.local_username, self.viewer_header, FOLLOW_CATEGORY_FRIEND)
        send_push.reset_mock()
        response = self._request_action('approve', self.viewer_username, self.author_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._types_for(send_push, self.viewer), ['follow_accepted_friend'])
        self.assertEqual(self._types_for(send_push, self.author), [])

    def test_denying_a_request_tells_nobody(self, send_push):
        self._follow(self.local_username, self.viewer_header)
        send_push.reset_mock()
        response = self._request_action('deny', self.viewer_username, self.author_header)
        self.assertEqual(response.status_code, 200)
        send_push.assert_not_called()

    def test_going_public_converts_requests_silently(self, send_push):
        self._follow(self.local_username, self.viewer_header)
        send_push.reset_mock()
        response = self._set_private(False, self.author_header)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserFollow.objects.filter(user_from=self.viewer, user_to=self.author).exists())
        send_push.assert_not_called()

    def test_following_public_account_notifies_followee(self, send_push):
        self.author.is_private = False
        self.author.save(update_fields=['is_private'])
        response = self._follow(self.local_username, self.viewer_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._types_for(send_push, self.author), ['new_follower_other'])

    def test_refused_follow_sends_nothing(self, send_push):
        self.author.is_private = False
        self.author.save(update_fields=['is_private'])
        UserFollow.objects.create(user_from=self.viewer, user_to=self.author)
        response = self._follow(self.local_username, self.viewer_header)
        self.assertEqual(response.status_code, 400)
        send_push.assert_not_called()
