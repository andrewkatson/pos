"""Account reports (issue #602): reviewing a reported account's username, bio
and profile photo.

The rules every test here protects are the post/comment ones (issue #467) —
no number of reports does anything by itself; only a verdict on the profile
itself, or a moderator, acts — plus what is particular to a profile: each part
is judged on its own, a failing bio or photo is removed (never "hidden"), a
failing username can only go to a human, and a decision about a profile stops
binding it once its owner replaces the bio or photo.
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from .. import moderation, tasks
from ..admin import ModerationReviewAdmin
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import (
    CLASSIFICATION_MAX_ATTEMPTS, MAX_REPORTS_PER_USER_PER_DAY,
    PROFILE_IMAGE_STATUS_APPROVED, PROFILE_IMAGE_STATUS_PENDING, PROFILE_IMAGE_STATUS_REJECTED,
    REPORTS_AFTER_CLEAR_BEFORE_ESCALATION, REVIEW_STATUS_CLEARED, REVIEW_STATUS_DISMISSED,
    REVIEW_STATUS_ESCALATED, REVIEW_STATUS_HIDDEN, REVIEW_STATUS_PENDING, REVIEW_TARGET_ACCOUNT,
)
from ..models import AccountReport, ModerationReview, PositiveOnlySocialUser

ALLOWED = ClassificationResult(allowed=True)
HATE = ClassificationResult(allowed=False, appealable=True, reason_code='hate_speech')
NUDITY = ClassificationResult(allowed=False, appealable=False, reason_code='nudity')
PROVIDER_FAILURE = ClassificationResult(allowed=False, provider_failure=True)

TEXT = 'user_system.tasks.text_classifier_class.is_text_positive'
IMAGE = 'user_system.tasks.image_classifier_class.is_image_positive'
TASK_DELETE = 'user_system.tasks.delete_image'
MODERATION_DELETE = 'user_system.moderation.delete_image'

PHOTO_URL = 'https://test-bucket.s3.amazonaws.com/user/avatar.jpeg'
PENDING_URL = 'https://test-bucket.s3.amazonaws.com/user/pending.jpeg'
USERNAME = 'reported_account'
BIO = 'I love long walks and sunsets'
BAD_BIO = 'a bio the classifier will not like'


def text_verdicts(**verdicts):
    """A text-classifier stand-in that rejects particular texts."""
    def classify(text, available_apis=None):
        return verdicts.get(text, ALLOWED)
    return classify


@override_settings(CLASSIFICATION_EAGER=True)
class AccountReviewTests(TestCase):
    def setUp(self):
        super().setUp()
        self.account = PositiveOnlySocialUser.objects.create(
            username=USERNAME, email='account@test.com', bio=BIO,
            profile_image_url=PHOTO_URL, profile_image_status=PROFILE_IMAGE_STATUS_APPROVED,
            profile_image_blurhash='LEHV6nWB2yk8pyo0adR*.7kCMdnj')
        self.reporters = [
            PositiveOnlySocialUser.objects.create(username=f'acct_reporter_{i}', email=f'ar{i}@test.com')
            for i in range(REPORTS_AFTER_CLEAR_BEFORE_ESCALATION + 3)
        ]

    def _report(self, reporter, reason='I do not like this account'):
        AccountReport.objects.create(user=reporter, reported_user=self.account, reason=reason)
        return moderation.record_report(account=self.account)

    def _refresh(self, review):
        review.refresh_from_db()
        self.account.refresh_from_db()
        return review

    # --- the automated re-review -----------------------------------------

    @patch(TASK_DELETE)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_a_clean_profile_is_cleared_and_left_alone(self, text, image, delete):
        review = self._refresh(self._report(self.reporters[0]))

        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)
        self.assertEqual(review.target_kind, REVIEW_TARGET_ACCOUNT)
        self.assertEqual(review.reports_at_last_review, 1)
        self.assertEqual(self.account.bio, BIO)
        self.assertEqual(self.account.profile_image_url, PHOTO_URL)
        delete.assert_not_called()
        self.assertEqual(mail.outbox, [])

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_only_the_profile_is_classified_never_the_reports(self, text, image):
        self._report(self.reporters[0], reason='REASON TEXT THAT MUST NOT REACH A MODEL')

        classified_texts = sorted(call.args[0] for call in text.call_args_list)
        self.assertEqual(classified_texts, sorted([USERNAME, BIO]))
        image.assert_called_once()
        self.assertEqual(image.call_args.args[0], PHOTO_URL)

    @patch(IMAGE)
    @patch(TEXT, return_value=ALLOWED)
    def test_parts_that_are_absent_are_not_classified(self, text, image):
        self.account.bio = ''
        self.account.profile_image_url = None
        self.account.save()

        review = self._refresh(self._report(self.reporters[0]))

        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)
        self.assertEqual([call.args[0] for call in text.call_args_list], [USERNAME])
        image.assert_not_called()

    @patch(TASK_DELETE)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, side_effect=text_verdicts(**{BIO: HATE}))
    def test_a_failing_bio_is_removed_and_the_owner_emailed(self, text, image, delete):
        review = self._refresh(self._report(self.reporters[0]))

        self.assertEqual(self.account.bio, '')
        self.assertEqual(self.account.profile_image_url, PHOTO_URL)
        # The profile as it now stands has passed, so the review is cleared and
        # further reports count toward a human look.
        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)
        self.assertIn('bio', review.resolution_note)
        delete.assert_not_called()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['account@test.com'])
        self.assertIn('bio', mail.outbox[0].body)
        # Nothing about who reported it, or how many did.
        self.assertNotIn(self.reporters[0].username, mail.outbox[0].body)

    @patch(TASK_DELETE)
    @patch(IMAGE, return_value=NUDITY)
    @patch(TEXT, return_value=ALLOWED)
    def test_a_failing_photo_is_removed_and_the_owner_told_why(self, text, image, delete):
        review = self._refresh(self._report(self.reporters[0]))

        self.assertIsNone(self.account.profile_image_url)
        self.assertIsNone(self.account.profile_image_blurhash)
        self.assertEqual(self.account.profile_image_status, PROFILE_IMAGE_STATUS_REJECTED)
        self.assertEqual(self.account.profile_image_reason_code, 'nudity')
        self.assertEqual(self.account.bio, BIO)
        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)
        delete.assert_called_once_with(PHOTO_URL)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('profile photo', mail.outbox[0].body)

    @patch(TASK_DELETE)
    @patch(IMAGE, return_value=NUDITY)
    @patch(TEXT, return_value=ALLOWED)
    def test_removing_the_live_photo_leaves_a_pending_upload_alone(self, text, image, delete):
        self.account.pending_profile_image_url = PENDING_URL
        self.account.profile_image_status = PROFILE_IMAGE_STATUS_PENDING
        self.account.save()

        self._refresh(self._report(self.reporters[0]))

        self.assertIsNone(self.account.profile_image_url)
        # The upload under review is a different picture with its own verdict
        # still to come; its pending status must survive.
        self.assertEqual(self.account.pending_profile_image_url, PENDING_URL)
        self.assertEqual(self.account.profile_image_status, PROFILE_IMAGE_STATUS_PENDING)
        delete.assert_called_once_with(PHOTO_URL)

    @patch(TASK_DELETE)
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, side_effect=text_verdicts(**{USERNAME: HATE}))
    def test_a_failing_username_escalates_to_a_moderator(self, text, image, delete):
        review = self._refresh(self._report(self.reporters[0]))

        # A username cannot be removed, so a human decides (and can ban).
        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)
        self.assertIn('Username', review.resolution_note)
        self.assertEqual(self.account.username, USERNAME)
        self.assertEqual(self.account.bio, BIO)
        self.assertEqual(self.account.profile_image_url, PHOTO_URL)
        self.assertEqual(mail.outbox, [])

    @patch(TASK_DELETE)
    @patch(IMAGE, return_value=NUDITY)
    @patch(TEXT, side_effect=text_verdicts(**{USERNAME: HATE, BIO: HATE}))
    def test_everything_failing_removes_what_it_can_and_escalates(self, text, image, delete):
        review = self._refresh(self._report(self.reporters[0]))

        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)
        self.assertEqual(self.account.bio, '')
        self.assertIsNone(self.account.profile_image_url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('bio and profile photo', mail.outbox[0].body)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=PROVIDER_FAILURE)
    def test_a_provider_outage_changes_nothing(self, text, image):
        AccountReport.objects.create(user=self.reporters[0], reported_user=self.account, reason='x')
        review = ModerationReview.objects.create(account=self.account)

        with self.assertRaises(tasks.ClassificationProviderError):
            tasks.review_reported_content(review.review_identifier)

        review = self._refresh(review)
        self.assertEqual(review.status, REVIEW_STATUS_PENDING)
        self.assertEqual(review.review_attempts, 1)
        self.assertEqual(self.account.bio, BIO)
        self.assertEqual(self.account.profile_image_url, PHOTO_URL)

    @patch(IMAGE)
    @patch(TEXT)
    def test_an_exhausted_retry_budget_escalates(self, text, image):
        review = ModerationReview.objects.create(
            account=self.account, review_attempts=CLASSIFICATION_MAX_ATTEMPTS)

        tasks.review_reported_content(review.review_identifier)

        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_ESCALATED)
        text.assert_not_called()
        image.assert_not_called()

    @patch(TASK_DELETE)
    def test_a_bio_replaced_while_the_cascade_ran_is_not_removed(self, delete):
        new_bio = 'a brand new bio, moderated on its own way in'

        def review_results(account, order):
            # The owner saves a new bio while the old one is being judged.
            PositiveOnlySocialUser.objects.filter(pk=account.pk).update(bio=new_bio)
            return ALLOWED, HATE, ALLOWED

        with patch.object(tasks, '_review_account_results', side_effect=review_results):
            self._report(self.reporters[0])

        self.account.refresh_from_db()
        self.assertEqual(self.account.bio, new_bio)
        self.assertEqual(mail.outbox, [])

    # --- escalation, retraction ------------------------------------------

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_reports_after_a_clear_escalate_to_a_human(self, text, image):
        review = self._report(self.reporters[0])
        for reporter in self.reporters[1:REPORTS_AFTER_CLEAR_BEFORE_ESCALATION]:
            self._report(reporter)
        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_CLEARED)

        self._report(self.reporters[REPORTS_AFTER_CLEAR_BEFORE_ESCALATION])

        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_ESCALATED)
        # Nothing was removed on the way: reports alone never act.
        self.assertEqual(self.account.bio, BIO)
        self.assertEqual(self.account.profile_image_url, PHOTO_URL)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, side_effect=text_verdicts(**{USERNAME: HATE}))
    def test_withdrawing_every_report_de_escalates(self, text, image):
        review = self._report(self.reporters[0])
        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_ESCALATED)

        self.account.account_reports.update(retracted_time='2026-01-01T00:00:00Z')
        moderation.withdraw_report(account=self.account)

        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_CLEARED)

    def test_account_reports_share_the_daily_budget(self):
        reporter = self.reporters[0]
        self.assertFalse(moderation.daily_report_limit_reached(reporter))
        for i in range(MAX_REPORTS_PER_USER_PER_DAY):
            target = PositiveOnlySocialUser.objects.create(username=f'budget_target_{i}', email=f'bt{i}@test.com')
            AccountReport.objects.create(user=reporter, reported_user=target, reason='x',
                                         retracted_time='2026-01-01T00:00:00Z' if i % 2 else None)
        # Retracted filings count too, exactly as for posts and comments.
        self.assertTrue(moderation.daily_report_limit_reached(reporter))

    # --- the moderator's decision ----------------------------------------

    def _escalated_review(self):
        return ModerationReview.objects.create(account=self.account, status=REVIEW_STATUS_ESCALATED)

    @patch(MODERATION_DELETE)
    def test_a_moderator_hide_removes_the_bio_and_photo(self, delete):
        AccountReport.objects.create(user=self.reporters[0], reported_user=self.account, reason='x')
        moderator = PositiveOnlySocialUser.objects.create(username='the_moderator', email='mod@test.com')
        review = self._escalated_review()

        moderation.hide_reviewed_content(review, moderator=moderator)

        review = self._refresh(review)
        self.assertEqual(review.status, REVIEW_STATUS_HIDDEN)
        self.assertEqual(review.resolved_by, moderator)
        self.assertEqual(self.account.bio, '')
        self.assertIsNone(self.account.profile_image_url)
        self.assertEqual(self.account.profile_image_status, PROFILE_IMAGE_STATUS_REJECTED)
        # The account itself is untouched: banning is the user admin's job.
        self.assertTrue(PositiveOnlySocialUser.objects.filter(pk=self.account.pk).exists())
        self.assertFalse(self.account.bans.exists())
        delete.assert_called_once_with(PHOTO_URL)
        self.assertEqual(len(mail.outbox), 1)

    @patch(MODERATION_DELETE)
    def test_a_moderator_dismissal_leaves_the_profile_alone(self, delete):
        review = self._escalated_review()

        moderation.dismiss_reports(review)

        review = self._refresh(review)
        self.assertEqual(review.status, REVIEW_STATUS_DISMISSED)
        self.assertEqual(self.account.bio, BIO)
        self.assertEqual(self.account.profile_image_url, PHOTO_URL)
        delete.assert_not_called()

    @patch(IMAGE)
    @patch(TEXT)
    def test_reports_after_a_dismissal_change_nothing(self, text, image):
        review = ModerationReview.objects.create(account=self.account, status=REVIEW_STATUS_DISMISSED)
        for reporter in self.reporters:
            self._report(reporter)

        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_DISMISSED)
        text.assert_not_called()

    # --- a changed profile is a new profile ------------------------------

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_a_profile_change_releases_a_dismissal(self, text, image):
        AccountReport.objects.create(user=self.reporters[0], reported_user=self.account, reason='x')
        review = ModerationReview.objects.create(account=self.account, status=REVIEW_STATUS_DISMISSED)

        moderation.profile_content_changed(self.account)

        review = self._refresh(review)
        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)
        # Reports filed about the old profile do not count toward the new one's
        # escalation; fresh ones do.
        self.assertEqual(review.reports_at_last_review, 1)
        for reporter in self.reporters[1:REPORTS_AFTER_CLEAR_BEFORE_ESCALATION + 1]:
            self._report(reporter)
        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_ESCALATED)

    def test_a_profile_change_leaves_pending_and_escalated_reviews_alone(self):
        for status in (REVIEW_STATUS_PENDING, REVIEW_STATUS_ESCALATED):
            with self.subTest(status=status):
                ModerationReview.objects.filter(account=self.account).delete()
                review = ModerationReview.objects.create(account=self.account, status=status)
                moderation.profile_content_changed(self.account)
                self.assertEqual(self._refresh(review).status, status)

    @patch('user_system.tasks.compute_blurhash', return_value=None)
    @patch(TASK_DELETE)
    @patch(IMAGE, return_value=ALLOWED)
    def test_an_approved_new_photo_releases_a_decision(self, image, delete, blurhash):
        review = ModerationReview.objects.create(account=self.account, status=REVIEW_STATUS_HIDDEN)
        self.account.pending_profile_image_url = PENDING_URL
        self.account.profile_image_status = PROFILE_IMAGE_STATUS_PENDING
        self.account.save()

        tasks.classify_profile_photo(str(self.account.pk))

        self.assertEqual(self._refresh(review).status, REVIEW_STATUS_CLEARED)

    # --- the admin queue -------------------------------------------------

    def test_the_admin_queue_describes_an_account_review(self):
        AccountReport.objects.create(user=self.reporters[0], reported_user=self.account,
                                     reason='their bio is mean')
        AccountReport.objects.create(user=self.reporters[1], reported_user=self.account,
                                     reason='withdrawn', retracted_time='2026-01-01T00:00:00Z')
        ModerationReview.objects.create(account=self.account, status=REVIEW_STATUS_ESCALATED)
        model_admin = ModerationReviewAdmin(ModerationReview, None)

        request = type('Request', (), {'resolver_match': None})()
        review = model_admin.get_queryset(request).get()

        self.assertEqual(model_admin.target_kind(review), REVIEW_TARGET_ACCOUNT)
        self.assertEqual(model_admin.author(review), self.account)
        self.assertEqual(model_admin.report_count(review), 1)
        self.assertIn(f'@{USERNAME}', model_admin.target_summary(review))
        self.assertIn(BIO, model_admin.target_summary(review))
        self.assertEqual(model_admin.reported_reasons(review), '• their bio is mean')
        self.assertEqual(model_admin.classifier_chain(review), '—')
