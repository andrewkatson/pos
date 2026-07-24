from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import (
    Fields,
    PROFILE_IMAGE_STATUS_APPROVED, PROFILE_IMAGE_STATUS_NONE,
    PROFILE_IMAGE_STATUS_PENDING, PROFILE_IMAGE_STATUS_REJECTED,
)
from ..models import PositiveOnlySocialUser
from ..views import get_user_with_username

ALLOWED = ClassificationResult(allowed=True)
REJECTED = ClassificationResult(allowed=False, reason_code='nudity')

IMAGE = 'user_system.tasks.image_classifier_class.is_image_positive'

invalid_session_management_token = '?'

# The endpoint accepts only URLs in the configured source bucket; the tests
# build 'test-bucket' URLs, so point the setting at that bucket.
SOURCE_BUCKET = 'test-bucket'


@override_settings(AWS_STORAGE_BUCKET_NAME=SOURCE_BUCKET)
class ProfilePhotoViewTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.set_url = reverse('set_profile_photo')
        self.remove_url = reverse('remove_profile_photo')
        self.scoped_url = f'https://{SOURCE_BUCKET}.s3.amazonaws.com/{self.user.id}/photo.jpeg'

    def _set(self, image_url):
        return self.client.post(
            self.set_url, data={Fields.image_url: image_url},
            content_type='application/json', **self.valid_header)

    def _reload(self):
        self.user.refresh_from_db()
        return self.user

    # --- Auth / validation ---

    def test_invalid_token_rejected(self):
        header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}
        response = self.client.post(
            self.set_url, data={Fields.image_url: self.scoped_url},
            content_type='application/json', **header)
        self.assertEqual(response.status_code, 401)

    def test_missing_image_url_rejected(self):
        response = self.client.post(
            self.set_url, data={}, content_type='application/json', **self.valid_header)
        self.assertEqual(response.status_code, 400)

    def test_image_url_scoped_to_other_user_rejected(self):
        other = self.make_user_with_prefix(prefix='other')
        other_user = get_user_with_username(other['username'])
        foreign_url = f'https://{SOURCE_BUCKET}.s3.amazonaws.com/{other_user.id}/photo.jpeg'
        response = self._set(foreign_url)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self._reload().pending_profile_image_url)

    def test_image_url_in_foreign_bucket_rejected(self):
        # A URL with this user's key prefix but in another (attacker-controlled)
        # bucket must be rejected, so the classifier never fetches arbitrary
        # remote content and we never mint CloudFront URLs for foreign objects.
        foreign_bucket_url = f'https://attacker-bucket.s3.amazonaws.com/{self.user.id}/photo.jpeg'
        response = self._set(foreign_bucket_url)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self._reload().pending_profile_image_url)

    # --- Set flow (eager classification runs inline in tests) ---

    @patch(IMAGE, return_value=ALLOWED)
    def test_set_then_approved_promotes_to_live(self, _image):
        response = self._set(self.scoped_url)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()[Fields.profile_image_status], PROFILE_IMAGE_STATUS_PENDING)
        # Eager classification has already approved it.
        user = self._reload()
        self.assertEqual(user.profile_image_status, PROFILE_IMAGE_STATUS_APPROVED)
        self.assertEqual(user.profile_image_url, self.scoped_url)
        self.assertIsNone(user.pending_profile_image_url)

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=REJECTED)
    def test_set_then_rejected_drops_photo(self, _image, mock_delete):
        response = self._set(self.scoped_url)
        self.assertEqual(response.status_code, 202)
        user = self._reload()
        self.assertEqual(user.profile_image_status, PROFILE_IMAGE_STATUS_REJECTED)
        self.assertIsNone(user.profile_image_url)
        self.assertIsNone(user.pending_profile_image_url)
        self.assertEqual(user.profile_image_reason_code, 'nudity')
        mock_delete.assert_called_once_with(self.scoped_url)

    @patch('user_system.views.delete_image')
    @patch('user_system.tasks.enqueue_profile_photo_classification')
    def test_replacing_pending_upload_cleans_up_superseded(self, _enqueue, mock_delete):
        # First upload stays pending because we stubbed out classification.
        first_url = f'https://test-bucket.s3.amazonaws.com/{self.user.id}/first.jpeg'
        PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
            pending_profile_image_url=first_url,
            profile_image_status=PROFILE_IMAGE_STATUS_PENDING)
        response = self._set(self.scoped_url)
        self.assertEqual(response.status_code, 202)
        user = self._reload()
        self.assertEqual(user.pending_profile_image_url, self.scoped_url)
        # The superseded, never-approved first upload is cleaned from S3.
        mock_delete.assert_called_once_with(first_url)

    # --- Remove flow ---

    @patch('user_system.views.delete_image')
    def test_remove_clears_and_deletes(self, mock_delete):
        live_url = f'https://test-bucket.s3.amazonaws.com/{self.user.id}/live.jpeg'
        pending_url = f'https://test-bucket.s3.amazonaws.com/{self.user.id}/pending.jpeg'
        PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
            profile_image_url=live_url, pending_profile_image_url=pending_url,
            profile_image_status=PROFILE_IMAGE_STATUS_PENDING)

        response = self.client.post(self.remove_url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        user = self._reload()
        self.assertIsNone(user.profile_image_url)
        self.assertIsNone(user.pending_profile_image_url)
        self.assertEqual(user.profile_image_status, PROFILE_IMAGE_STATUS_NONE)
        deleted = {c.args[0] for c in mock_delete.call_args_list}
        self.assertEqual(deleted, {live_url, pending_url})


class ProfilePhotoInProfileDetailsTests(PositiveOnlySocialTestCase):
    """The profile-details endpoint exposes the approved photo to everyone but
    the pending/rejected moderation state only to the owner."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.viewer = get_user_with_username(self.local_username)
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        self.other = self.make_user_with_prefix(prefix='subject')
        self.subject = get_user_with_username(self.other['username'])

    def test_owner_sees_pending_status(self):
        pending_url = f'https://test-bucket.s3.amazonaws.com/{self.viewer.id}/p.jpeg'
        PositiveOnlySocialUser.objects.filter(pk=self.viewer.pk).update(
            pending_profile_image_url=pending_url,
            profile_image_status=PROFILE_IMAGE_STATUS_PENDING)

        url = reverse('get_profile_details', kwargs={'username': self.local_username})
        data = self.client.get(url, **self.valid_header).json()

        self.assertEqual(data[Fields.profile_image_status], PROFILE_IMAGE_STATUS_PENDING)
        self.assertIsNotNone(data[Fields.pending_profile_image_url])

    def test_other_user_sees_approved_photo_but_not_status(self):
        live_url = f'https://test-bucket.s3.amazonaws.com/{self.subject.id}/live.jpeg'
        PositiveOnlySocialUser.objects.filter(pk=self.subject.pk).update(
            profile_image_url=live_url, profile_image_status=PROFILE_IMAGE_STATUS_APPROVED)

        url = reverse('get_profile_details', kwargs={'username': self.other['username']})
        data = self.client.get(url, **self.valid_header).json()

        self.assertEqual(data[Fields.profile_image_original_url], live_url)
        # The owner-only moderation fields are not exposed for other users.
        self.assertNotIn(Fields.profile_image_status, data)
        self.assertNotIn(Fields.pending_profile_image_url, data)
