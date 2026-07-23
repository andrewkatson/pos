from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    Fields,
    HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_CLASSIFIER_FINAL,
    HIDDEN_REASON_PENDING_CLASSIFICATION,
    POST_STATUS_PENDING,
)
from ..models import Post
from ..views import get_user_with_username
from ..visibility import can_view_post, visible_posts


class PendingPostVisibilityTests(PositiveOnlySocialTestCase):
    """A post pending classification is hidden from all viewers except its
    author (issue #282 acceptance criterion); a final-rejection tombstone is
    visible to nobody, its author included."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.author = get_user_with_username(self.local_username)
        self.author_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        other = self.make_user_with_prefix(prefix='viewer')
        self.other_username = other['username']
        self.other_user = get_user_with_username(self.other_username)
        self.other_header = {'HTTP_AUTHORIZATION': f'Bearer {other[Fields.session_management_token]}'}

    def _make_post(self, hidden_reason, hidden=True):
        return self.author.post_set.create(
            caption='a caption', hidden=hidden, hidden_reason=hidden_reason)

    def _grid_ids(self, username, header):
        url = reverse('get_posts_for_user', kwargs={'username': username, 'batch': 0})
        response = self.client.get(url, **header)
        self.assertEqual(response.status_code, 200)
        return [p[Fields.post_identifier] for p in response.json()]

    def test_pending_post_visible_only_to_author(self):
        post = self._make_post(HIDDEN_REASON_PENDING_CLASSIFICATION)
        self.assertIn(str(post.post_identifier),
                      self._grid_ids(self.local_username, self.author_header))
        self.assertNotIn(str(post.post_identifier),
                         self._grid_ids(self.local_username, self.other_header))
        self.assertTrue(can_view_post(post, self.author))
        self.assertFalse(can_view_post(post, self.other_user))

    def test_author_grid_payload_carries_classification_fields(self):
        post = self._make_post(HIDDEN_REASON_PENDING_CLASSIFICATION)
        url = reverse('get_posts_for_user', kwargs={'username': self.local_username, 'batch': 0})
        payload = self.client.get(url, **self.author_header).json()
        entry = next(p for p in payload if p[Fields.post_identifier] == str(post.post_identifier))
        self.assertEqual(entry[Fields.status], POST_STATUS_PENDING)
        self.assertTrue(entry[Fields.hidden])
        self.assertEqual(entry[Fields.hidden_reason], HIDDEN_REASON_PENDING_CLASSIFICATION)
        self.assertFalse(entry[Fields.appealable])

    def test_other_viewers_payload_carries_no_classification_fields(self):
        self.author.post_set.create(caption='a caption', hidden=False)
        payload_entries = self.client.get(
            reverse('get_posts_for_user', kwargs={'username': self.local_username, 'batch': 0}),
            **self.other_header).json()
        self.assertTrue(payload_entries)
        for entry in payload_entries:
            self.assertNotIn(Fields.status, entry)
            self.assertNotIn(Fields.appealable, entry)

    def test_tombstone_invisible_to_everyone_including_author(self):
        post = self._make_post(HIDDEN_REASON_CLASSIFIER_FINAL)
        self.assertNotIn(str(post.post_identifier),
                         self._grid_ids(self.local_username, self.author_header))
        self.assertFalse(can_view_post(post, self.author))
        self.assertFalse(can_view_post(post, self.other_user))
        self.assertNotIn(post, visible_posts(Post.objects.all(), self.author))

    def test_appealable_hidden_post_still_visible_to_author(self):
        """The pre-existing author rule is unchanged for appealable hides."""
        post = self._make_post(HIDDEN_REASON_CLASSIFIER)
        self.assertIn(str(post.post_identifier),
                      self._grid_ids(self.local_username, self.author_header))
        self.assertNotIn(str(post.post_identifier),
                         self._grid_ids(self.local_username, self.other_header))


class ClassificationAppealEligibilityTests(PositiveOnlySocialTestCase):
    """Pending and final-rejected posts can never be appealed and never appear
    on the appeals screens (issue #282)."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def _make_post(self, hidden_reason):
        return self.user.post_set.create(
            caption='a caption', hidden=True, hidden_reason=hidden_reason)

    def _hidden_post_ids(self):
        url = reverse('get_hidden_posts', kwargs={'batch': 0})
        return [p[Fields.post_identifier] for p in self.client.get(url, **self.header).json()]

    def _submit_appeal(self, post):
        url = reverse('submit_appeal')
        data = {
            Fields.target_type: 'post',
            Fields.target_identifier: str(post.post_identifier),
            Fields.reason: 'please reconsider this decision',
        }
        return self.client.post(url, data=data, content_type='application/json', **self.header)

    def test_pending_post_not_listed_and_not_appealable(self):
        post = self._make_post(HIDDEN_REASON_PENDING_CLASSIFICATION)
        self.assertNotIn(str(post.post_identifier), self._hidden_post_ids())
        response = self._submit_appeal(post)
        self.assertEqual(response.status_code, 400)
        self.assertIn('No appealable item', response.json().get('error', ''))

    def test_tombstone_not_listed_and_not_appealable(self):
        post = self._make_post(HIDDEN_REASON_CLASSIFIER_FINAL)
        self.assertNotIn(str(post.post_identifier), self._hidden_post_ids())
        response = self._submit_appeal(post)
        self.assertEqual(response.status_code, 400)

    def test_classifier_hidden_post_still_listed_and_appealable(self):
        post = self._make_post(HIDDEN_REASON_CLASSIFIER)
        self.assertIn(str(post.post_identifier), self._hidden_post_ids())
        response = self._submit_appeal(post)
        self.assertEqual(response.status_code, 201)
