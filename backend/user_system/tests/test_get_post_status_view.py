from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    Fields,
    HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_CLASSIFIER_FINAL,
    HIDDEN_REASON_PENDING_CLASSIFICATION,
    POST_STATUS_APPROVED, POST_STATUS_PENDING, POST_STATUS_REJECTED,
    POST_STATUS_REJECTED_FINAL,
)
from ..views import get_user_with_username


class GetPostStatusTests(PositiveOnlySocialTestCase):
    """The author-only classification-status endpoint (issue #282), which
    clients poll to reconcile the async outcome of a pending post."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def _status(self, post, header=None):
        url = reverse('get_post_status', kwargs={'post_identifier': str(post.post_identifier)})
        return self.client.get(url, **(header or self.header))

    def _make_post(self, **kwargs):
        defaults = {'caption': 'a caption', 'hidden': False}
        defaults.update(kwargs)
        return self.user.post_set.create(**defaults)

    def test_pending_post_reports_pending(self):
        post = self._make_post(hidden=True, hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION)
        response = self._status(post)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[Fields.status], POST_STATUS_PENDING)
        self.assertFalse(body[Fields.appealable])
        self.assertIn('reviewed', body['message'])

    def test_approved_post_reports_approved_without_message(self):
        post = self._make_post()
        body = self._status(post).json()
        self.assertEqual(body[Fields.status], POST_STATUS_APPROVED)
        self.assertNotIn('message', body)

    def test_rejected_post_reports_reason_and_appealability(self):
        post = self._make_post(
            hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER,
            classification_reason_code='hate_speech')
        body = self._status(post).json()
        self.assertEqual(body[Fields.status], POST_STATUS_REJECTED)
        self.assertEqual(body[Fields.reason_code], 'hate_speech')
        self.assertTrue(body[Fields.appealable])
        self.assertIn('may contain hate speech', body['message'])
        self.assertIn('appeal', body['message'])

    def test_final_rejection_reports_terminal_state(self):
        post = self._make_post(
            hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL,
            classification_reason_code='gore', image_url=None)
        body = self._status(post).json()
        self.assertEqual(body[Fields.status], POST_STATUS_REJECTED_FINAL)
        self.assertFalse(body[Fields.appealable])
        self.assertIn('cannot be appealed', body['message'])

    def test_rejection_without_recorded_reason_uses_generic_phrase(self):
        post = self._make_post(hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)
        body = self._status(post).json()
        self.assertIn('did not meet our positivity guidelines', body['message'])

    def test_other_users_posts_look_missing(self):
        """The endpoint must not let anyone probe another user's moderation
        state: someone else's post is reported exactly like a missing one."""
        post = self._make_post(hidden=True, hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION)
        other = self.make_user_with_prefix(prefix='status_other')
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other[Fields.session_management_token]}'}
        response = self._status(post, header=other_header)
        self.assertEqual(response.status_code, 400)
        self.assertIn('No post with that identifier', response.json().get('error', ''))

    def test_invalid_identifier_is_rejected(self):
        url = reverse('get_post_status', kwargs={'post_identifier': '00000000-0000-4000-8000-000000000000'})
        # Valid uuid but no such post.
        response = self.client.get(url, **self.header)
        self.assertEqual(response.status_code, 400)

    def test_requires_authentication(self):
        post = self._make_post()
        url = reverse('get_post_status', kwargs={'post_identifier': str(post.post_identifier)})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)
