"""Push notifications for follow requests and new followers (issue #604)."""
from unittest.mock import patch

from django.test import override_settings

from .. import notifications, push
from ..constants import (
    BAN_TYPE_SHADOW, FOLLOW_CATEGORY_FRIEND, PUSH_TYPE_ALL, PUSH_TYPE_FOLLOW_REQUEST,
    PUSH_TYPE_NEW_FOLLOWER, PUSH_TYPE_PARENTS, PUSH_TYPE_TREE,
)
from ..models import FollowRequest, NotificationPreference, UserBan, UserBlock, UserFollow
from .test_activity_push import SEND_PUSH, ActivityPushTestCase, _sent
from .test_private_accounts import PrivateAccountTestBase


class FollowPushTypeTests(ActivityPushTestCase):
    """The new kinds slot into the preference tree and the Activity channel."""

    def test_follow_kinds_have_every_source(self):
        for kind in (PUSH_TYPE_FOLLOW_REQUEST, PUSH_TYPE_NEW_FOLLOWER):
            self.assertEqual(PUSH_TYPE_PARENTS[kind], PUSH_TYPE_ALL)
            children = {value for value, _, parent in PUSH_TYPE_TREE if parent == kind}
            self.assertEqual(children, {f'{kind}_{source}' for source in
                                        ('following', 'friend', 'family', 'other')})

    def test_follow_kinds_use_the_activity_channel(self):
        for kind in (PUSH_TYPE_FOLLOW_REQUEST, PUSH_TYPE_NEW_FOLLOWER):
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
        FollowRequest.objects.create(user_from=self.requester, user_to=self.author)

    def _job(self):
        notifications.push_follow_request(self.requester.pk, self.author.pk)

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
        self._job()
        send_push.assert_not_called()

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

    def _job(self):
        notifications.push_new_follower(self.follower.pk, self.author.pk)

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
        self._job()
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


@patch(SEND_PUSH)
class FollowViewWiringTests(PrivateAccountTestBase):
    """The follow endpoints trigger the pushes (eager in tests): a request to a
    private account tells its owner, an outright follow tells the followee, and
    approving a request or an account going public tells nobody."""

    def _types_for(self, send_push, user):
        return [call.args[2] for call in send_push.call_args_list if call.args[0] == user]

    def test_follow_request_notifies_owner(self, send_push):
        response = self._follow(self.local_username, self.viewer_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._types_for(send_push, self.author), ['follow_request_other'])

    def test_approving_a_request_sends_nothing_more(self, send_push):
        self._follow(self.local_username, self.viewer_header)
        send_push.reset_mock()
        response = self._request_action('approve', self.viewer_username, self.author_header)
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
