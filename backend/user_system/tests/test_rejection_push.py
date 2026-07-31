from unittest.mock import patch

from django.test import TestCase

from .. import tasks
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import (
    HIDDEN_REASON_PENDING_CLASSIFICATION, DEVICE_PLATFORM_IOS, PUSH_TYPE_POST_REJECTED,
)
from ..models import DeviceToken, PositiveOnlySocialUser

ALLOWED = ClassificationResult(allowed=True)
APPEALABLE = ClassificationResult(allowed=False, appealable=True)
FINAL_REJECT = ClassificationResult(allowed=False, appealable=False)

TEXT = 'user_system.tasks.text_classifier_class.is_text_positive'
IMAGE = 'user_system.tasks.image_classifier_class.is_image_positive'
SEND_PUSH = 'user_system.tasks.push.send_push'


class RejectionPushWiringTests(TestCase):
    """classify_post fires a best-effort push alongside the rejection email (#342)."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='push_author', email='push_author@test.com', password='x')
        self.post = self.user.post_set.create(
            caption='a caption', hidden=True,
            hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION)
        DeviceToken.objects.create(user=self.user, platform=DEVICE_PLATFORM_IOS, token='dev-1')

    def _run(self):
        tasks.classify_post(str(self.post.post_identifier))
        self.post.refresh_from_db()

    @patch(SEND_PUSH)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_rejection_sends_push(self, _text, _image, send_push):
        self._run()
        send_push.assert_called_once()
        user_arg, payload = send_push.call_args.args
        self.assertEqual(user_arg, self.user)
        self.assertEqual(payload['data']['type'], PUSH_TYPE_POST_REJECTED)
        self.assertTrue(payload['data']['appealable'])

    @patch(SEND_PUSH)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_rejection_sends_non_appealable_push(self, _text, _image, send_push):
        self._run()
        send_push.assert_called_once()
        _user, payload = send_push.call_args.args
        self.assertFalse(payload['data']['appealable'])

    @patch(SEND_PUSH)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_approval_sends_no_push(self, _text, _image, send_push):
        self._run()
        send_push.assert_not_called()

    @patch(SEND_PUSH, side_effect=RuntimeError('push blew up'))
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_push_failure_does_not_break_classification(self, _text, _image, _send_push):
        """A push failure is swallowed — the rejection outcome is still recorded."""
        self._run()  # must not raise
        self.assertTrue(self.post.hidden)
