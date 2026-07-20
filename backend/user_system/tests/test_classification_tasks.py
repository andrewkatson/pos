import uuid
from unittest.mock import patch

from django.core import mail
from django.test import TestCase

from .. import tasks
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import (
    HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_CLASSIFIER_FINAL,
    HIDDEN_REASON_NONE, HIDDEN_REASON_PENDING_CLASSIFICATION,
    HIDDEN_REASON_REPORTS,
)
from ..models import PositiveOnlySocialUser, Post

ALLOWED = ClassificationResult(allowed=True)
APPEALABLE = ClassificationResult(allowed=False, appealable=True)
FINAL_REJECT = ClassificationResult(allowed=False, appealable=False)
PROVIDER_FAILURE = ClassificationResult(allowed=False, provider_failure=True)
APPEALABLE_HATE = ClassificationResult(allowed=False, appealable=True, reason_code='hate_speech')
FINAL_REJECT_GORE = ClassificationResult(allowed=False, appealable=False, reason_code='gore')

TEXT = 'user_system.tasks.text_classifier_class.is_text_positive'
IMAGE = 'user_system.tasks.image_classifier_class.is_image_positive'

IMAGE_URL = 'https://test-bucket.s3.amazonaws.com/user/img.jpeg'


class ClassifyPostTaskTests(TestCase):
    """The async classification worker job (issue #282), driven directly."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='worker_test_user', email='worker@test.com', password='x')
        self.post = self.user.post_set.create(
            image_url=IMAGE_URL, caption='a caption', hidden=True,
            hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION)

    def _run(self):
        tasks.classify_post(str(self.post.post_identifier))
        self.post.refresh_from_db()

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_approval_makes_post_visible(self, _text, _image):
        self._run()
        self.assertFalse(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_NONE)
        self.assertEqual(self.post.classification_attempts, 1)
        self.assertEqual(len(mail.outbox), 0)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_approval_clears_a_stale_reason_code(self, _text, _image):
        """A leftover reason code (e.g. a manual admin edit) must not survive
        an approval and leak into the author-visible status payloads."""
        Post.objects.filter(pk=self.post.pk).update(classification_reason_code='gore')
        self._run()
        self.assertFalse(self.post.hidden)
        self.assertIsNone(self.post.classification_reason_code)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_rejection_hides_and_emails(self, _text, _image):
        self._run()
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)
        self.assertEqual(self.post.image_url, IMAGE_URL)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('appeal', mail.outbox[0].body.lower())

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_rejection_tombstones_and_strips_image(self, _text, _image, mock_delete):
        self._run()
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER_FINAL)
        self.assertIsNone(self.post.image_url)
        mock_delete.assert_called_once_with(IMAGE_URL)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('cannot be appealed', mail.outbox[0].body)

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=FINAL_REJECT_GORE)
    @patch(TEXT, return_value=APPEALABLE_HATE)
    def test_decisive_final_rejection_wins_the_recorded_reason(self, _text, _image, _delete):
        """An appealable caption with a final image rejection is final, and the
        recorded reason is the image's (the decisive rejection), matching the
        old synchronous behavior."""
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER_FINAL)
        self.assertEqual(self.post.classification_reason_code, 'gore')

    @patch(IMAGE, return_value=APPEALABLE_HATE)
    @patch(TEXT, return_value=APPEALABLE)
    def test_text_precedence_when_both_rejections_share_finality(self, _text, _image):
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)
        # Text cited no rule, so its generic code wins over the image's.
        self.assertEqual(self.post.classification_reason_code, 'guidelines')

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=PROVIDER_FAILURE)
    def test_provider_failure_raises_and_stays_pending(self, _text, _image):
        """Infrastructure failure is not a verdict: the job raises so the
        queue retries it, and the post fails closed (stays hidden-pending)."""
        with self.assertRaises(tasks.ClassificationProviderError):
            tasks.classify_post(str(self.post.post_identifier))
        self.post.refresh_from_db()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_PENDING_CLASSIFICATION)
        # The attempt still counts, so the sweep's alerting sees every try.
        self.assertEqual(self.post.classification_attempts, 1)
        self.assertEqual(len(mail.outbox), 0)

    @patch(IMAGE, return_value=PROVIDER_FAILURE)
    @patch(TEXT, return_value=ALLOWED)
    def test_image_provider_failure_also_raises(self, _text, _image):
        with self.assertRaises(tasks.ClassificationProviderError):
            tasks.classify_post(str(self.post.post_identifier))
        self.post.refresh_from_db()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_PENDING_CLASSIFICATION)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_redelivered_job_is_a_no_op(self, _text, _image):
        """At-least-once delivery: a duplicate run of an already-resolved job
        must not re-apply the transition or re-send the email."""
        self._run()
        self.assertEqual(len(mail.outbox), 1)
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)
        self.assertEqual(self.post.classification_attempts, 1)
        self.assertEqual(len(mail.outbox), 1)

    @patch(TEXT, return_value=ALLOWED)
    def test_exhausted_retry_budget_drops_the_job_without_classifying(self, mock_text):
        """Once the budget is spent the job returns successfully (so the queue
        stops retrying) without any provider calls; the post stays pending
        (fail closed) at exactly the budget, for the sweep to alert on."""
        from ..constants import CLASSIFICATION_MAX_ATTEMPTS
        Post.objects.filter(pk=self.post.pk).update(
            classification_attempts=CLASSIFICATION_MAX_ATTEMPTS)
        self._run()  # must not raise
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_PENDING_CLASSIFICATION)
        self.assertEqual(self.post.classification_attempts, CLASSIFICATION_MAX_ATTEMPTS)
        mock_text.assert_not_called()

    @patch(TEXT, return_value=ALLOWED)
    def test_non_pending_post_is_left_alone(self, mock_text):
        """The job only ever acts on pending posts — e.g. a report-hidden post
        redelivered by mistake must not be touched (or reclassified)."""
        self.post.hidden_reason = HIDDEN_REASON_REPORTS
        self.post.save(update_fields=['hidden_reason'])
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_REPORTS)
        mock_text.assert_not_called()

    @patch(TEXT, return_value=ALLOWED)
    def test_deleted_post_is_a_no_op(self, mock_text):
        missing = uuid.uuid4()
        tasks.classify_post(str(missing))  # must not raise
        mock_text.assert_not_called()

    @patch(IMAGE, return_value=FINAL_REJECT)
    @patch(TEXT, return_value=ALLOWED)
    def test_text_only_post_skips_image_classifier(self, _text, mock_image):
        self.post.image_url = None
        self.post.save(update_fields=['image_url'])
        self._run()
        self.assertFalse(self.post.hidden)
        mock_image.assert_not_called()

    @patch('user_system.tasks.send_mail', side_effect=Exception('smtp down'))
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_email_failure_does_not_undo_the_transition(self, _text, _image, _mail):
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)
