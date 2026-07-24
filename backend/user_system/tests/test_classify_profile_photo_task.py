from unittest.mock import patch

from django.test import TestCase

from .. import tasks
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import (
    PROFILE_IMAGE_STATUS_APPROVED, PROFILE_IMAGE_STATUS_NONE,
    PROFILE_IMAGE_STATUS_PENDING, PROFILE_IMAGE_STATUS_REJECTED,
    CLASSIFICATION_MAX_ATTEMPTS,
)
from ..models import PositiveOnlySocialUser

ALLOWED = ClassificationResult(allowed=True)
REJECTED = ClassificationResult(allowed=False, reason_code='nudity')
PROVIDER_FAILURE = ClassificationResult(allowed=False, provider_failure=True)

IMAGE = 'user_system.tasks.image_classifier_class.is_image_positive'

PENDING_URL = 'https://test-bucket.s3.amazonaws.com/user/pending.jpeg'
OLD_LIVE_URL = 'https://test-bucket.s3.amazonaws.com/user/old.jpeg'


class ClassifyProfilePhotoTaskTests(TestCase):
    """The async profile-photo classification worker (issue #7), driven directly."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='avatar_worker_user', email='avatar@test.com', password='x')
        self.user.pending_profile_image_url = PENDING_URL
        self.user.profile_image_status = PROFILE_IMAGE_STATUS_PENDING
        self.user.save()

    def _run(self):
        tasks.classify_profile_photo(str(self.user.id))
        self.user.refresh_from_db()

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=ALLOWED)
    def test_approval_promotes_pending_to_live(self, _image, mock_delete):
        self._run()
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_APPROVED)
        self.assertEqual(self.user.profile_image_url, PENDING_URL)
        self.assertIsNone(self.user.pending_profile_image_url)
        self.assertIsNone(self.user.profile_image_reason_code)
        self.assertEqual(self.user.profile_image_classification_attempts, 1)
        # No prior photo, so nothing to clean up.
        mock_delete.assert_not_called()

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=ALLOWED)
    def test_approval_deletes_previous_live_photo(self, _image, mock_delete):
        PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
            profile_image_url=OLD_LIVE_URL)
        self._run()
        self.assertEqual(self.user.profile_image_url, PENDING_URL)
        mock_delete.assert_called_once_with(OLD_LIVE_URL)

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=REJECTED)
    def test_rejection_drops_pending_and_records_reason(self, _image, mock_delete):
        self._run()
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_REJECTED)
        self.assertIsNone(self.user.pending_profile_image_url)
        self.assertEqual(self.user.profile_image_reason_code, 'nudity')
        # The rejected upload's S3 object is cleaned up.
        mock_delete.assert_called_once_with(PENDING_URL)

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=REJECTED)
    def test_rejection_keeps_previously_approved_photo(self, _image, mock_delete):
        """A bad new upload must not wipe out a user's current good avatar."""
        PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
            profile_image_url=OLD_LIVE_URL)
        self._run()
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_REJECTED)
        self.assertEqual(self.user.profile_image_url, OLD_LIVE_URL)
        mock_delete.assert_called_once_with(PENDING_URL)

    @patch(IMAGE, return_value=PROVIDER_FAILURE)
    def test_provider_failure_raises_and_leaves_pending(self, _image):
        with self.assertRaises(tasks.ClassificationProviderError):
            tasks.classify_profile_photo(str(self.user.id))
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_PENDING)
        self.assertEqual(self.user.pending_profile_image_url, PENDING_URL)
        # The attempt was still counted before the fallible provider call.
        self.assertEqual(self.user.profile_image_classification_attempts, 1)

    @patch(IMAGE, return_value=ALLOWED)
    def test_no_pending_photo_is_a_noop(self, mock_image):
        PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
            profile_image_status=PROFILE_IMAGE_STATUS_NONE,
            pending_profile_image_url=None)
        self._run()
        mock_image.assert_not_called()
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_NONE)

    @patch(IMAGE, return_value=ALLOWED)
    def test_exhausted_attempts_drops_job_without_classifying(self, mock_image):
        PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
            profile_image_classification_attempts=CLASSIFICATION_MAX_ATTEMPTS)
        self._run()
        mock_image.assert_not_called()
        # Stays pending (fail closed) — never approved without classification.
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_PENDING)

    def test_missing_user_is_a_noop(self):
        # A user deleted while the job was queued must not raise.
        tasks.classify_profile_photo('00000000-0000-0000-0000-000000000000')

    @patch('user_system.tasks.delete_image')
    def test_pending_photo_replaced_mid_job_is_not_transitioned(self, mock_delete):
        """If the user uploads a new pending photo while a job is classifying the
        old one, the stale verdict must not be applied to the new upload."""
        new_url = 'https://test-bucket.s3.amazonaws.com/user/new.jpeg'

        def swap_then_reject(url):
            # Simulate the user replacing their pending photo during the (slow)
            # classifier call — a concurrent set_profile_photo.
            PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
                pending_profile_image_url=new_url)
            return REJECTED

        with patch(IMAGE, side_effect=swap_then_reject):
            self._run()

        # The job's rejection verdict (for the OLD upload) was not applied to the
        # new pending upload: it stays pending and intact.
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_PENDING)
        self.assertEqual(self.user.pending_profile_image_url, new_url)
        mock_delete.assert_not_called()
