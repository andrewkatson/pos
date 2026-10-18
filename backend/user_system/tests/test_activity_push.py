from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .. import notifications, push, tasks
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import (
    BAN_TYPE_SHADOW, FOLLOW_CATEGORY_FAMILY, FOLLOW_CATEGORY_FOLLOWING, FOLLOW_CATEGORY_FRIEND,
    HIDDEN_REASON_PENDING_CLASSIFICATION, POST_AUDIENCE_FAMILY, POST_AUDIENCE_FRIENDS,
    PUSH_TYPE_ALL, PUSH_TYPE_NEW_COMMENT, PUSH_TYPE_NEW_LIKE, PUSH_TYPE_NEW_POST,
    PUSH_TYPE_POST_REJECTED,
)
from ..models import (
    CommentLike, NotificationPreference, PositiveOnlySocialUser, PostLike, UserBan, UserBlock,
    UserFollow,
)
from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase

SEND_PUSH = 'user_system.push.send_push'
ALLOWED = ClassificationResult(allowed=True)


def _sent(send_push):
    """{(username, notification_type): payload} for every send_push call."""
    return {(call.args[0].username, call.args[2]): call.args[1] for call in send_push.call_args_list}


class ActivityPushTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.author = self._user('author')
        self.post = self.author.post_set.create(caption='A lovely sunny day')

    def _user(self, name, **extra):
        return PositiveOnlySocialUser.objects.create_user(
            username=name, email=f'{name}@test.com', password='x', **extra)

    def _follow(self, follower, followee, category=FOLLOW_CATEGORY_FOLLOWING):
        UserFollow.objects.create(user_from=follower, user_to=followee, category=category)

    def _comment(self, author, thread=None, body='So nice!', **extra):
        thread = thread or self.post.commentthread_set.create()
        return thread.comment_set.create(author=author, body=body, **extra)


class AndroidChannelTests(TestCase):
    """FCM names the channel so background messages land on it (issue #444)."""

    def test_activity_kinds_use_the_activity_channel(self):
        for kind in (PUSH_TYPE_NEW_POST, PUSH_TYPE_NEW_COMMENT, PUSH_TYPE_NEW_LIKE):
            self.assertEqual(push.android_channel_for({'type': kind}), push.ANDROID_CHANNEL_ACTIVITY)

    def test_rejections_and_unknown_kinds_use_post_moderation(self):
        for data in ({'type': PUSH_TYPE_POST_REJECTED}, {'type': 'future_kind'}, {}):
            self.assertEqual(push.android_channel_for(data), push.ANDROID_CHANNEL_POST_MODERATION)


class PreferenceTreeTests(ActivityPushTestCase):
    """is_push_type_enabled honors every ancestor of a type (issue #444)."""

    def _off(self, notification_type):
        NotificationPreference.objects.create(
            user=self.author, notification_type=notification_type, enabled=False)

    def test_everything_defaults_on(self):
        self.assertTrue(push.is_push_type_enabled(self.author, 'new_post_friend'))

    def test_leaf_off(self):
        self._off('new_post_friend')
        self.assertFalse(push.is_push_type_enabled(self.author, 'new_post_friend'))
        self.assertTrue(push.is_push_type_enabled(self.author, 'new_post_family'))

    def test_kind_off_silences_its_sources_only(self):
        self._off(PUSH_TYPE_NEW_POST)
        self.assertFalse(push.is_push_type_enabled(self.author, 'new_post_family'))
        self.assertTrue(push.is_push_type_enabled(self.author, 'new_like_family'))

    def test_master_off_silences_everything(self):
        self._off(PUSH_TYPE_ALL)
        for notification_type in (PUSH_TYPE_POST_REJECTED, 'new_post_family', 'new_comment_other',
                                  'new_like_friend'):
            self.assertFalse(push.is_push_type_enabled(self.author, notification_type))

    def test_child_setting_survives_parent_round_trip(self):
        self._off('new_like_other')
        NotificationPreference.objects.create(
            user=self.author, notification_type=PUSH_TYPE_NEW_LIKE, enabled=False)
        NotificationPreference.objects.filter(notification_type=PUSH_TYPE_NEW_LIKE).update(enabled=True)
        self.assertFalse(push.is_push_type_enabled(self.author, 'new_like_other'))
        self.assertTrue(push.is_push_type_enabled(self.author, 'new_like_friend'))

    @patch('user_system.push._send_fcm', return_value=[])
    @patch('user_system.push._send_apns', return_value=[])
    def test_send_push_skips_when_an_ancestor_is_off(self, apns, _fcm):
        self.author.device_tokens.create(platform='ios', token='t-1')
        self._off(PUSH_TYPE_ALL)
        push.send_push(self.author, {'title': 't', 'body': 'b', 'data': {}}, PUSH_TYPE_POST_REJECTED)
        apns.assert_not_called()


@patch(SEND_PUSH)
class NewPostPushTests(ActivityPushTestCase):

    def test_followers_get_the_type_for_their_category(self, send_push):
        plain, friend, family = self._user('plain'), self._user('friend'), self._user('family')
        self._follow(plain, self.author, FOLLOW_CATEGORY_FOLLOWING)
        self._follow(friend, self.author, FOLLOW_CATEGORY_FRIEND)
        self._follow(family, self.author, FOLLOW_CATEGORY_FAMILY)
        notifications.push_new_post(str(self.post.post_identifier))
        sent = _sent(send_push)
        self.assertEqual(set(sent), {
            ('plain', 'new_post_following'), ('friend', 'new_post_friend'), ('family', 'new_post_family'),
        })
        payload = sent[('plain', 'new_post_following')]
        self.assertEqual(payload['data']['type'], PUSH_TYPE_NEW_POST)
        self.assertEqual(payload['data']['post_identifier'], str(self.post.post_identifier))
        self.assertIn('author', payload['title'])
        self.assertEqual(payload['body'], 'A lovely sunny day')

    def test_non_followers_and_the_author_are_not_told(self, send_push):
        self._user('stranger')
        # The author following someone does not make them a recipient.
        self._follow(self.author, self._user('followee'))
        notifications.push_new_post(str(self.post.post_identifier))
        send_push.assert_not_called()

    def test_audience_limits_recipients(self, send_push):
        # The author labels who may see a restricted post; the follower's own
        # label for the author picks the preference type.
        friend, family = self._user('friend'), self._user('family')
        self._follow(friend, self.author)
        self._follow(family, self.author)
        self._follow(self.author, friend, FOLLOW_CATEGORY_FRIEND)
        self._follow(self.author, family, FOLLOW_CATEGORY_FAMILY)
        self.post.audience = POST_AUDIENCE_FAMILY
        self.post.save()
        notifications.push_new_post(str(self.post.post_identifier))
        self.assertEqual(set(_sent(send_push)), {('family', 'new_post_following')})

        send_push.reset_mock()
        self.post.audience = POST_AUDIENCE_FRIENDS
        self.post.save()
        notifications.push_new_post(str(self.post.post_identifier))
        self.assertEqual({user for user, _ in _sent(send_push)}, {'friend', 'family'})

    def test_hidden_post_is_not_announced(self, send_push):
        self._follow(self._user('fan'), self.author)
        self.post.hidden = True
        self.post.save()
        notifications.push_new_post(str(self.post.post_identifier))
        send_push.assert_not_called()

    def test_shadow_banned_author_is_not_announced(self, send_push):
        self._follow(self._user('fan'), self.author)
        UserBan.objects.create(user=self.author, ban_type=BAN_TYPE_SHADOW, reason='x')
        notifications.push_new_post(str(self.post.post_identifier))
        send_push.assert_not_called()

    def test_cross_age_band_follower_is_skipped(self, send_push):
        minor = self._user('minor', identity_is_verified=True, is_adult=False)
        self._follow(minor, self.author)
        notifications.push_new_post(str(self.post.post_identifier))
        send_push.assert_not_called()

    def test_missing_post_is_a_no_op(self, send_push):
        post_id = str(self.post.post_identifier)
        self.post.delete()
        notifications.push_new_post(post_id)
        send_push.assert_not_called()

    def test_large_following_is_worked_through_in_batches(self, send_push):
        fans = [self._user(f'fan{i}') for i in range(5)]
        for fan in fans:
            self._follow(fan, self.author)
        with patch.object(notifications, 'NEW_POST_FANOUT_BATCH_SIZE', 2), \
                patch.object(notifications, '_enqueue', wraps=notifications._enqueue) as enqueue:
            notifications.push_new_post(str(self.post.post_identifier))
        self.assertEqual(sorted(call.args[0].username for call in send_push.call_args_list),
                         sorted(fan.username for fan in fans))
        # Two full batches each chain a continuation; the short third does not.
        self.assertEqual(enqueue.call_count, 2)

    def test_hidden_mid_fan_out_stops_remaining_batches(self, send_push):
        for i in range(3):
            self._follow(self._user(f'fan{i}'), self.author)
        first_edge = UserFollow.objects.filter(user_to=self.author).order_by('pk').first()
        self.post.hidden = True
        self.post.save()
        notifications.push_new_post(str(self.post.post_identifier), first_edge.pk)
        send_push.assert_not_called()

    def test_one_failing_send_does_not_stop_the_fan_out(self, send_push):
        self._follow(self._user('a_fan'), self.author)
        self._follow(self._user('b_fan'), self.author)
        send_push.side_effect = [RuntimeError('boom'), None]
        notifications.push_new_post(str(self.post.post_identifier))
        self.assertEqual(send_push.call_count, 2)


@patch(SEND_PUSH)
class NewPostApprovalWiringTests(ActivityPushTestCase):
    """classify_post announces a post to followers only once it is approved."""

    def setUp(self):
        super().setUp()
        self.fan = self._user('fan')
        self._follow(self.fan, self.author)
        self.pending = self.author.post_set.create(
            caption='pending', hidden=True, hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION)

    @patch('user_system.tasks.image_classifier_class.is_image_positive', return_value=ALLOWED)
    @patch('user_system.tasks.text_classifier_class.is_text_positive', return_value=ALLOWED)
    def test_approval_notifies_followers(self, _text, _image, send_push):
        tasks.classify_post(str(self.pending.post_identifier))
        self.assertEqual(set(_sent(send_push)), {('fan', 'new_post_following')})

    @patch('user_system.tasks.image_classifier_class.is_image_positive', return_value=ALLOWED)
    @patch('user_system.tasks.text_classifier_class.is_text_positive',
           return_value=ClassificationResult(allowed=False, appealable=True))
    def test_rejection_does_not_notify_followers(self, _text, _image, send_push):
        tasks.classify_post(str(self.pending.post_identifier))
        self.assertEqual({user for user, _ in _sent(send_push)}, {'author'})


@patch(SEND_PUSH)
class NewCommentPushTests(ActivityPushTestCase):

    def test_top_level_comment_notifies_post_author_as_other(self, send_push):
        commenter = self._user('commenter')
        comment = self._comment(commenter, body='Beautiful!')
        notifications.push_new_comment(str(comment.comment_identifier))
        sent = _sent(send_push)
        self.assertEqual(set(sent), {('author', 'new_comment_other')})
        payload = sent[('author', 'new_comment_other')]
        self.assertEqual(payload['data']['type'], PUSH_TYPE_NEW_COMMENT)
        self.assertEqual(payload['body'], 'Beautiful!')
        self.assertIn('commented on your post', payload['title'])

    def test_source_is_the_recipients_label_for_the_commenter(self, send_push):
        commenter = self._user('commenter')
        self._follow(self.author, commenter, FOLLOW_CATEGORY_FAMILY)
        comment = self._comment(commenter)
        notifications.push_new_comment(str(comment.comment_identifier))
        self.assertEqual(set(_sent(send_push)), {('author', 'new_comment_family')})

    def test_reply_notifies_thread_starter_and_post_author(self, send_push):
        starter, replier = self._user('starter'), self._user('replier')
        first = self._comment(starter)
        reply = self._comment(replier, thread=first.comment_thread)
        notifications.push_new_comment(str(reply.comment_identifier))
        sent = _sent(send_push)
        self.assertEqual(set(sent), {('starter', 'new_comment_other'), ('author', 'new_comment_other')})
        self.assertIn('replied to your comment', sent[('starter', 'new_comment_other')]['title'])

    def test_reply_in_authors_own_thread_notifies_author_once(self, send_push):
        first = self._comment(self.author)
        reply = self._comment(self._user('replier'), thread=first.comment_thread)
        notifications.push_new_comment(str(reply.comment_identifier))
        self.assertEqual(send_push.call_count, 1)

    def test_own_comment_is_silent(self, send_push):
        comment = self._comment(self.author)
        notifications.push_new_comment(str(comment.comment_identifier))
        send_push.assert_not_called()

    def test_hidden_comment_is_silent(self, send_push):
        comment = self._comment(self._user('commenter'), hidden=True)
        notifications.push_new_comment(str(comment.comment_identifier))
        send_push.assert_not_called()

    def test_comment_audience_excluding_the_author_is_silent(self, send_push):
        # A family-only comment reaches only people its author labeled family.
        comment = self._comment(self._user('commenter'), audience=POST_AUDIENCE_FAMILY)
        notifications.push_new_comment(str(comment.comment_identifier))
        send_push.assert_not_called()

    def test_blocked_commenter_is_silent(self, send_push):
        commenter = self._user('commenter')
        UserBlock.objects.create(user_blocker=self.author, user_blocked=commenter)
        comment = self._comment(commenter)
        notifications.push_new_comment(str(comment.comment_identifier))
        send_push.assert_not_called()


@patch(SEND_PUSH)
class LikePushTests(ActivityPushTestCase):

    def setUp(self):
        super().setUp()
        self.liker = self._user('liker')

    def test_post_like_notifies_author(self, send_push):
        PostLike.objects.create(post=self.post, user=self.liker)
        self._follow(self.author, self.liker, FOLLOW_CATEGORY_FRIEND)
        notifications.push_post_like(str(self.post.post_identifier), self.liker.pk)
        sent = _sent(send_push)
        self.assertEqual(set(sent), {('author', 'new_like_friend')})
        self.assertEqual(sent[('author', 'new_like_friend')]['data']['type'], PUSH_TYPE_NEW_LIKE)

    def test_withdrawn_like_is_silent(self, send_push):
        notifications.push_post_like(str(self.post.post_identifier), self.liker.pk)
        send_push.assert_not_called()

    def test_relike_within_window_is_silent(self, send_push):
        PostLike.objects.create(post=self.post, user=self.liker)
        notifications.push_post_like(str(self.post.post_identifier), self.liker.pk)
        notifications.push_post_like(str(self.post.post_identifier), self.liker.pk)
        self.assertEqual(send_push.call_count, 1)

    def test_shadow_banned_liker_is_silent(self, send_push):
        PostLike.objects.create(post=self.post, user=self.liker)
        UserBan.objects.create(user=self.liker, ban_type=BAN_TYPE_SHADOW, reason='x')
        notifications.push_post_like(str(self.post.post_identifier), self.liker.pk)
        send_push.assert_not_called()

    def test_comment_like_notifies_comment_author(self, send_push):
        commenter = self._user('commenter')
        comment = self._comment(commenter, body='Love it')
        CommentLike.objects.create(comment=comment, user=self.liker)
        notifications.push_comment_like(str(comment.comment_identifier), self.liker.pk)
        sent = _sent(send_push)
        self.assertEqual(set(sent), {('commenter', 'new_like_other')})
        self.assertIn('liked your comment', sent[('commenter', 'new_like_other')]['title'])
        self.assertEqual(sent[('commenter', 'new_like_other')]['data']['post_identifier'],
                         str(self.post.post_identifier))

    def test_comment_like_skipped_when_commenter_lost_sight_of_post(self, send_push):
        commenter = self._user('commenter')
        comment = self._comment(commenter)
        CommentLike.objects.create(comment=comment, user=self.liker)
        self.author.is_private = True
        self.author.save()
        notifications.push_comment_like(str(comment.comment_identifier), self.liker.pk)
        send_push.assert_not_called()


@patch(SEND_PUSH)
class ViewWiringTests(PositiveOnlySocialTestCase):
    """The like and comment endpoints trigger the pushes (eager in tests)."""

    def setUp(self):
        super().setUp()
        with patch('user_system.tasks.text_classifier_class.is_text_positive', return_value=ALLOWED), \
                patch('user_system.tasks.image_classifier_class.is_image_positive', return_value=ALLOWED):
            self.make_post_with_users(2)
        self.other_header = {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][1]}'}

    def test_like_post_notifies_author(self, send_push):
        response = self.client.post(
            reverse('like_post', kwargs={'post_identifier': str(self.post_identifier)}), **self.other_header)
        self.assertEqual(response.status_code, 200)
        send_push.assert_called_once()
        self.assertEqual(send_push.call_args.args[0], self.post.author)
        self.assertEqual(send_push.call_args.args[2], 'new_like_other')

    @patch('user_system.views.text_classifier_class.is_text_positive', return_value=ALLOWED)
    def test_comment_notifies_author(self, _text, send_push):
        response = self.client.post(
            reverse('comment_on_post', kwargs={'post_identifier': str(self.post_identifier)}),
            data={'comment_text': 'What a great day'}, content_type='application/json', **self.other_header)
        self.assertEqual(response.status_code, 201)
        send_push.assert_called_once()
        self.assertEqual(send_push.call_args.args[2], 'new_comment_other')

    @patch('user_system.views.text_classifier_class.is_text_positive',
           return_value=ClassificationResult(allowed=False, appealable=True))
    def test_comment_hidden_pending_appeal_is_silent(self, _text, send_push):
        response = self.client.post(
            reverse('comment_on_post', kwargs={'post_identifier': str(self.post_identifier)}),
            data={'comment_text': 'What a great day'}, content_type='application/json', **self.other_header)
        self.assertEqual(response.status_code, 201)
        send_push.assert_not_called()
