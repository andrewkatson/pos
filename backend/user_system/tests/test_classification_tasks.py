import uuid
from concurrent.futures import Future
from unittest.mock import patch

from django.core import mail
from django.test import TestCase

from .. import tasks
from ..classifiers.classifier_utils import (
    API_CLAUDE, API_GEMINI, API_GEMMA, API_OPENAI, CASCADE_ORDER, ClassificationResult,
)
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
BLURHASH = 'user_system.tasks.compute_blurhash'

IMAGE_URL = 'https://test-bucket.s3.amazonaws.com/user/img.jpeg'
FAKE_BLURHASH = 'LEHV6nWB2yk8pyo0adR*.7kCMdnj'


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

    @patch(BLURHASH, return_value=FAKE_BLURHASH)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_approval_stores_blurhash(self, _text, _image, mock_blur):
        """On approval the worker records the computed BlurHash (issue #387) so
        clients can render a blurred placeholder while the image loads."""
        self._run()
        self.assertFalse(self.post.hidden)
        mock_blur.assert_called_once_with(IMAGE_URL)
        self.assertEqual(self.post.image_blurhash, FAKE_BLURHASH)

    @patch(BLURHASH, return_value=None)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_approval_tolerates_blurhash_failure(self, _text, _image, _blur):
        """BlurHash is decorative: an encode failure (None) never blocks the
        approval — the post still becomes visible, just without a placeholder."""
        self._run()
        self.assertFalse(self.post.hidden)
        self.assertIsNone(self.post.image_blurhash)

    @patch(BLURHASH, return_value=FAKE_BLURHASH)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_rejection_still_stores_blurhash(self, _text, _image, _blur):
        """A hidden-but-appealable post keeps its BlurHash so a later successful
        appeal can show the placeholder without re-running classification."""
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)
        self.assertEqual(self.post.image_blurhash, FAKE_BLURHASH)

    @patch(BLURHASH, return_value=FAKE_BLURHASH)
    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_rejection_skips_blurhash(self, _text, _image, _delete, mock_blur):
        """A final rejection deletes the image, so the worker neither computes
        nor stores a BlurHash for it."""
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER_FINAL)
        mock_blur.assert_not_called()
        self.assertIsNone(self.post.image_blurhash)

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


# The cascade the worker rotates through (issue #511). Patched in because the
# test environment has no OPENROUTER_API_KEY, so the real lookup is empty.
AVAILABLE = 'user_system.tasks.get_available_apis'
ALL_TIERS = list(CASCADE_ORDER)


def _judged(consulted, decided_by, allowed=True, appealable=False, provider_failure=False):
    return ClassificationResult(allowed=allowed, appealable=appealable, provider_failure=provider_failure,
                                consulted=list(consulted), decided_by=decided_by)


class _InlineExecutor:
    """Runs submitted cascades on the calling thread, so a test's fake cascade
    can touch the (per-thread) test database mid-job."""

    def submit(self, fn, *args, **kwargs):
        future = Future()
        future.set_result(fn(*args, **kwargs))
        return future


@patch(AVAILABLE, return_value=ALL_TIERS)
class ClassifyPostModelChainTests(TestCase):
    """The worker leads each round with a tier that has not judged the post
    yet, and records which tiers did (issue #511)."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='chain_test_user', email='chain@test.com', password='x')
        self.post = self.user.post_set.create(
            image_url=IMAGE_URL, caption='a caption', hidden=True,
            hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION)

    def _run(self, raises=False):
        if raises:
            with self.assertRaises(tasks.ClassificationProviderError):
                tasks.classify_post(str(self.post.post_identifier))
        else:
            tasks.classify_post(str(self.post.post_identifier))
        self.post.refresh_from_db()

    @patch(IMAGE, return_value=_judged([API_GEMMA, API_GEMINI], API_GEMINI))
    @patch(TEXT, return_value=_judged([API_GEMMA], API_GEMMA))
    def test_first_round_uses_the_normal_order_for_both_cascades(self, mock_text, mock_image, _avail):
        self._run()
        self.assertFalse(self.post.hidden)
        self.assertEqual(mock_text.call_args.kwargs['available_apis'], ALL_TIERS)
        self.assertEqual(mock_image.call_args.kwargs['available_apis'], ALL_TIERS)
        # Every tier consulted by either cascade, and both deciders, are on record.
        self.assertEqual(self.post.classification_models_tried, [API_GEMMA, API_GEMINI])
        self.assertEqual(self.post.classification_model_chain, [API_GEMMA, API_GEMINI])

    @patch('user_system.tasks.delete_image')
    @patch(IMAGE, return_value=_judged([API_GEMMA], API_GEMMA, allowed=False))
    @patch(TEXT, return_value=_judged([API_GEMMA], API_GEMMA))
    def test_a_rejection_records_its_decider_too(self, _text, _image, _delete, _avail):
        self._run()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER_FINAL)
        self.assertEqual(self.post.classification_model_chain, [API_GEMMA])

    @patch(IMAGE, return_value=_judged([API_GEMMA], API_GEMMA))
    @patch(TEXT, return_value=_judged([API_GEMMA], API_GEMMA))
    def test_a_retry_leads_with_a_tier_the_failed_attempt_did_not(self, mock_text, mock_image, _avail):
        """A round that reached no verdict still consulted tiers; the retry
        must not replay the same order, or a wedged first tier would eat every
        attempt in the budget."""
        mock_text.return_value = _judged(ALL_TIERS, None, allowed=False, provider_failure=True)
        self._run(raises=True)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_PENDING_CLASSIFICATION)
        # The failed text cascade consulted everything; the image cascade,
        # which did reach a verdict, is on record as well.
        self.assertEqual(self.post.classification_models_tried, ALL_TIERS)
        self.assertEqual(self.post.classification_model_chain, [API_GEMMA])

        mock_text.return_value = _judged([API_GEMINI], API_GEMINI)
        mock_image.return_value = _judged([API_GEMINI], API_GEMINI)
        self._run()
        self.assertFalse(self.post.hidden)
        expected = [API_GEMINI, API_OPENAI, API_CLAUDE, API_GEMMA]
        self.assertEqual(mock_text.call_args.kwargs['available_apis'], expected)
        self.assertEqual(mock_image.call_args.kwargs['available_apis'], expected)
        self.assertEqual(self.post.classification_model_chain, [API_GEMMA, API_GEMINI])

    @patch(IMAGE, return_value=_judged([API_OPENAI], API_OPENAI))
    @patch(TEXT, return_value=_judged([API_OPENAI], API_OPENAI))
    def test_a_complete_chain_starts_a_new_cycle(self, mock_text, _image, _avail):
        Post.objects.filter(pk=self.post.pk).update(
            classification_models_tried=ALL_TIERS, classification_model_chain=ALL_TIERS)
        with patch('user_system.classifiers.model_chain.random.randrange', return_value=2):
            self._run()
        self.assertEqual(mock_text.call_args.kwargs['available_apis'],
                         [API_OPENAI, API_CLAUDE, API_GEMMA, API_GEMINI])
        # The old cycle's lists are gone; only this round is on record.
        self.assertEqual(self.post.classification_models_tried, [API_OPENAI])
        self.assertEqual(self.post.classification_model_chain, [API_OPENAI])

    @patch(IMAGE, return_value=_judged([API_GEMMA], API_GEMMA))
    @patch(TEXT, return_value=_judged([API_GEMMA], API_GEMMA))
    def test_the_fold_merges_with_bookkeeping_recorded_during_the_cascade(self, mock_text, _image, _avail):
        """A duplicate delivery (or a re-review) can record its own round while
        this job's cascades are out. What it wrote must survive: the fold works
        on the row as it is at commit time, not on the pre-cascade read."""
        def cascade_then_record(*_args, **_kwargs):
            Post.objects.filter(pk=self.post.pk).update(
                classification_models_tried=[API_CLAUDE], classification_model_chain=[API_CLAUDE])
            return _judged([API_GEMMA], API_GEMMA)

        mock_text.side_effect = cascade_then_record
        with patch('user_system.tasks._CLASSIFICATION_EXECUTOR', _InlineExecutor()):
            self._run()
        self.assertFalse(self.post.hidden)
        self.assertEqual(self.post.classification_models_tried, [API_CLAUDE, API_GEMMA])
        self.assertEqual(self.post.classification_model_chain, [API_CLAUDE, API_GEMMA])

    @patch(IMAGE, return_value=_judged([API_GEMMA], API_GEMMA))
    @patch(TEXT, return_value=_judged(ALL_TIERS, None, allowed=False, provider_failure=True))
    def test_an_outage_record_merges_with_bookkeeping_recorded_during_the_cascade(self, _text, mock_image, _avail):
        def cascade_then_record(*_args, **_kwargs):
            Post.objects.filter(pk=self.post.pk).update(
                classification_models_tried=[API_CLAUDE], classification_model_chain=[API_CLAUDE])
            return _judged([API_GEMMA], API_GEMMA)

        mock_image.side_effect = cascade_then_record
        with patch('user_system.tasks._CLASSIFICATION_EXECUTOR', _InlineExecutor()):
            self._run(raises=True)
        self.assertEqual(self.post.classification_models_tried, [API_CLAUDE, API_GEMMA, API_GEMINI, API_OPENAI])
        self.assertEqual(self.post.classification_model_chain, [API_CLAUDE, API_GEMMA])

    @patch(IMAGE, return_value=FINAL_REJECT)
    @patch(TEXT, return_value=_judged([API_GEMMA], API_GEMMA))
    def test_a_text_only_post_records_only_the_text_cascade(self, _text, mock_image, _avail):
        self.post.image_url = None
        self.post.save(update_fields=['image_url'])
        self._run()
        mock_image.assert_not_called()
        self.assertEqual(self.post.classification_models_tried, [API_GEMMA])
        self.assertEqual(self.post.classification_model_chain, [API_GEMMA])

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_results_that_name_no_tier_leave_the_lists_empty(self, _text, _image, _avail):
        """Testing-mode verdicts (and the local pre-filters) involve no tier."""
        self._run()
        self.assertFalse(self.post.hidden)
        self.assertEqual(self.post.classification_models_tried, [])
        self.assertEqual(self.post.classification_model_chain, [])
