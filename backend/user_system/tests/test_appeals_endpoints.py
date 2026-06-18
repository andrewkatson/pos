from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    Fields,
    HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_REPORTS,
    APPEAL_STATUS_PENDING, APPEAL_STATUS_DENIED,
    MAX_APPEAL_REASON_LENGTH,
)
from ..models import Appeal, CommentThread
from ..views import get_user_with_username


class AppealsEndpointsTestCase(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def _hidden_post(self, reason=HIDDEN_REASON_CLASSIFIER):
        return self.user.post_set.create(
            image_url=f'https://b.s3.amazonaws.com/{self.user.id}/x.jpeg',
            caption='a caption', hidden=True, hidden_reason=reason)

    def _hidden_comment(self, reason=HIDDEN_REASON_CLASSIFIER):
        post = self.user.post_set.create(
            image_url=f'https://b.s3.amazonaws.com/{self.user.id}/y.jpeg', caption='c')
        thread = CommentThread.objects.create(post=post)
        return thread.comment_set.create(author=self.user, body='a comment',
                                         hidden=True, hidden_reason=reason)

    def _submit(self, target_type, target_identifier, reason='please reconsider'):
        return self.client.post(
            reverse('submit_appeal'),
            data={Fields.target_type: target_type,
                  Fields.target_identifier: str(target_identifier),
                  Fields.reason: reason},
            content_type='application/json', **self.header)


class HiddenContentListingTests(AppealsEndpointsTestCase):

    def test_requires_auth(self):
        response = self.client.get(reverse('get_hidden_posts', kwargs={'batch': 0}))
        self.assertEqual(response.status_code, 401)

    def test_lists_only_own_hidden_posts(self):
        hidden = self._hidden_post(reason=HIDDEN_REASON_REPORTS)
        self.user.post_set.create(image_url='u', caption='visible', hidden=False)  # excluded

        response = self.client.get(reverse('get_hidden_posts', kwargs={'batch': 0}), **self.header)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0][Fields.post_identifier], str(hidden.post_identifier))
        self.assertEqual(body[0][Fields.hidden_reason], HIDDEN_REASON_REPORTS)
        self.assertFalse(body[0][Fields.has_appeal])

    def test_another_users_hidden_post_not_listed(self):
        other = self.make_user_with_prefix()
        other_user = get_user_with_username(other['username'])
        other_user.post_set.create(image_url='u', caption='x', hidden=True)

        response = self.client.get(reverse('get_hidden_posts', kwargs={'batch': 0}), **self.header)
        self.assertEqual(response.json(), [])

    def test_has_appeal_flag_true_after_appeal(self):
        post = self._hidden_post()
        Appeal.objects.create(appellant=self.user, post=post, reason='x')

        response = self.client.get(reverse('get_hidden_posts', kwargs={'batch': 0}), **self.header)
        self.assertTrue(response.json()[0][Fields.has_appeal])

    def test_lists_only_own_hidden_comments(self):
        comment = self._hidden_comment()
        response = self.client.get(reverse('get_hidden_comments', kwargs={'batch': 0}), **self.header)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0][Fields.comment_identifier], str(comment.comment_identifier))


class MyAppealsListingTests(AppealsEndpointsTestCase):

    def test_lists_my_appeals_with_status(self):
        post = self._hidden_post()
        Appeal.objects.create(appellant=self.user, post=post, reason='r',
                              content_snapshot=post.caption, status=APPEAL_STATUS_DENIED,
                              resolution_note='no')

        response = self.client.get(reverse('get_my_appeals', kwargs={'batch': 0}), **self.header)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0][Fields.status], APPEAL_STATUS_DENIED)
        self.assertEqual(body[0][Fields.target_type], 'post')
        self.assertEqual(body[0][Fields.resolution_note], 'no')


class SubmitAppealTests(AppealsEndpointsTestCase):

    def test_appeal_hidden_post(self):
        post = self._hidden_post()
        response = self._submit('post', post.post_identifier)
        self.assertEqual(response.status_code, 201)
        appeal = Appeal.objects.get(appeal_identifier=response.json()[Fields.appeal_identifier])
        self.assertEqual(appeal.post_id, post.post_identifier)
        self.assertEqual(appeal.status, APPEAL_STATUS_PENDING)
        self.assertEqual(appeal.content_snapshot, post.caption)

    def test_appeal_hidden_comment(self):
        comment = self._hidden_comment()
        response = self._submit('comment', comment.comment_identifier)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Appeal.objects.filter(comment=comment).exists())

    def test_ban_target_type_rejected_in_app(self):
        """Ban appeals go through email, not this endpoint."""
        response = self._submit('ban', 1)
        self.assertEqual(response.status_code, 400)
        self.assertIn('target_type', response.json().get('error', ''))

    def test_invalid_target_type_rejected(self):
        response = self._submit('banana', 'x')
        self.assertEqual(response.status_code, 400)
        self.assertIn('target_type', response.json().get('error', ''))

    def test_missing_reason_rejected(self):
        post = self._hidden_post()
        response = self._submit('post', post.post_identifier, reason='')
        self.assertEqual(response.status_code, 400)

    def test_reason_too_long_rejected(self):
        post = self._hidden_post()
        response = self._submit('post', post.post_identifier, reason='a' * (MAX_APPEAL_REASON_LENGTH + 1))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Appeal.objects.count(), 0)

    def test_cannot_appeal_visible_post(self):
        post = self.user.post_set.create(image_url='u', caption='v', hidden=False)
        response = self._submit('post', post.post_identifier)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Appeal.objects.count(), 0)

    def test_cannot_appeal_another_users_post(self):
        other = self.make_user_with_prefix()
        other_user = get_user_with_username(other['username'])
        post = other_user.post_set.create(image_url='u', caption='x', hidden=True)
        response = self._submit('post', post.post_identifier)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Appeal.objects.count(), 0)

    def test_duplicate_appeal_rejected(self):
        post = self._hidden_post()
        self.assertEqual(self._submit('post', post.post_identifier).status_code, 201)
        second = self._submit('post', post.post_identifier)
        self.assertEqual(second.status_code, 400)
        self.assertIn('already been appealed', second.json().get('error', ''))
        self.assertEqual(Appeal.objects.filter(post=post).count(), 1)

    def test_denied_item_cannot_be_reappealed(self):
        comment = self._hidden_comment()
        Appeal.objects.create(appellant=self.user, comment=comment, reason='r',
                              status=APPEAL_STATUS_DENIED)
        response = self._submit('comment', comment.comment_identifier)
        self.assertEqual(response.status_code, 400)
