from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..constants import (
    CLASSIFICATION_MAX_ATTEMPTS,
    HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_CLASSIFIER_FINAL,
    HIDDEN_REASON_PENDING_CLASSIFICATION,
    PROFILE_IMAGE_STATUS_PENDING,
)
from ..models import PositiveOnlySocialUser, Post


def _backdate(post, **delta):
    """Move a post's timestamps into the past via a queryset update (they are
    auto_now/auto_now_add fields, which ignore direct assignment). Both are
    moved: the stuck sweep keys on updated_time (last classification
    activity), the tombstone purge on creation_time."""
    then = timezone.now() - timedelta(**delta)
    Post.objects.filter(pk=post.pk).update(creation_time=then, updated_time=then)


class SweepClassificationsTests(TestCase):
    """The reconciliation sweep (issue #282): re-enqueue stuck pending posts,
    alert on exhausted ones, and purge old final-rejection tombstones."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='sweep_test_user', email='sweep@test.com', password='x')

    def _run(self, *args):
        out = StringIO()
        call_command('sweep_classifications', *args, stdout=out)
        return out.getvalue()

    def _pending_post(self, attempts=0):
        return self.user.post_set.create(
            caption='a caption', hidden=True,
            hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION,
            classification_attempts=attempts)

    def _tombstone(self):
        return self.user.post_set.create(
            caption='a caption', hidden=True,
            hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL, image_url=None)

    @patch('user_system.tasks.enqueue_classification')
    def test_stuck_pending_post_is_reenqueued(self, mock_enqueue):
        post = self._pending_post()
        _backdate(post, minutes=30)
        out = self._run()
        mock_enqueue.assert_called_once_with(post.post_identifier)
        self.assertIn('Re-enqueued 1', out)

    @patch('user_system.tasks.enqueue_classification')
    def test_recent_pending_post_is_left_alone(self, mock_enqueue):
        self._pending_post()  # just created — within the stuck threshold
        self._run()
        mock_enqueue.assert_not_called()

    @patch('user_system.tasks.enqueue_classification')
    def test_recently_attempted_post_is_not_reenqueued(self, mock_enqueue):
        """An old post whose worker attempt just bumped updated_time is not
        stuck: back-to-back sweep runs must not pile duplicate jobs onto it."""
        post = self._pending_post(attempts=1)
        _backdate(post, minutes=30)
        # Simulate the worker's attempt bookkeeping touching updated_time now.
        Post.objects.filter(pk=post.pk).update(updated_time=timezone.now())
        self._run()
        mock_enqueue.assert_not_called()

    @patch('user_system.tasks.enqueue_classification')
    def test_exhausted_pending_post_alerts_instead_of_reenqueueing(self, mock_enqueue):
        post = self._pending_post(attempts=CLASSIFICATION_MAX_ATTEMPTS)
        _backdate(post, minutes=30)
        with self.assertLogs('user_system.management.commands.sweep_classifications', level='ERROR'):
            out = self._run()
        mock_enqueue.assert_not_called()
        self.assertIn('1 exhausted', out)
        self.assertIn('1 newly alerted', out)
        # Fail closed: the post stays hidden-pending, never published — and the
        # alert is recorded as fired.
        post.refresh_from_db()
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_PENDING_CLASSIFICATION)
        self.assertTrue(post.hidden)
        self.assertTrue(post.classification_alerted)

    @patch('user_system.tasks.enqueue_classification')
    def test_exhausted_post_alerts_exactly_once_across_runs(self, mock_enqueue):
        """The operator alert must not flood: a second sweep run over the same
        exhausted post still counts it but emits no new error log."""
        post = self._pending_post(attempts=CLASSIFICATION_MAX_ATTEMPTS)
        _backdate(post, minutes=30)
        self._run()

        _backdate(post, minutes=30)  # the first run bumped nothing, but be explicit
        with self.assertNoLogs('user_system.management.commands.sweep_classifications', level='ERROR'):
            out = self._run()
        self.assertIn('1 exhausted', out)
        self.assertIn('0 newly alerted', out)

    def test_old_tombstone_is_purged(self):
        post = self._tombstone()
        _backdate(post, days=8)
        out = self._run()
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())
        self.assertIn('purged 1 tombstone', out)

    def test_recent_tombstone_is_kept_for_client_reconciliation(self):
        post = self._tombstone()
        _backdate(post, days=1)
        self._run()
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())

    def test_other_hidden_posts_are_never_purged(self):
        post = self.user.post_set.create(
            caption='a caption', hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)
        _backdate(post, days=30)
        self._run()
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())

    @patch('user_system.tasks.enqueue_classification')
    def test_dry_run_changes_nothing(self, mock_enqueue):
        stuck = self._pending_post()
        _backdate(stuck, minutes=30)
        tombstone = self._tombstone()
        _backdate(tombstone, days=8)

        out = self._run('--dry-run')

        mock_enqueue.assert_not_called()
        self.assertTrue(Post.objects.filter(pk=tombstone.pk).exists())
        self.assertIn('would purge 1', out)

    def test_negative_thresholds_are_rejected(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self._run('--stuck-minutes=-1')

    # --- Profile photos (issue #7) ---

    def _pending_photo(self, attempts=0, minutes_ago=30):
        """A user with a profile photo stuck in pending classification for the
        given number of minutes."""
        PositiveOnlySocialUser.objects.filter(pk=self.user.pk).update(
            profile_image_status=PROFILE_IMAGE_STATUS_PENDING,
            pending_profile_image_url='https://b.s3.amazonaws.com/x/p.jpeg',
            profile_image_classification_attempts=attempts,
            profile_image_classification_time=timezone.now() - timedelta(minutes=minutes_ago))

    @patch('user_system.tasks.enqueue_profile_photo_classification')
    def test_stuck_pending_photo_is_reenqueued(self, mock_enqueue):
        self._pending_photo()
        out = self._run()
        mock_enqueue.assert_called_once_with(self.user.id)
        self.assertIn('1 stuck pending profile photo', out)

    @patch('user_system.tasks.enqueue_profile_photo_classification')
    def test_recent_pending_photo_is_left_alone(self, mock_enqueue):
        self._pending_photo(minutes_ago=1)
        self._run()
        mock_enqueue.assert_not_called()

    @patch('user_system.tasks.enqueue_profile_photo_classification')
    def test_exhausted_pending_photo_alerts_instead_of_reenqueueing(self, mock_enqueue):
        self._pending_photo(attempts=CLASSIFICATION_MAX_ATTEMPTS)
        with self.assertLogs('user_system.management.commands.sweep_classifications', level='ERROR'):
            out = self._run()
        mock_enqueue.assert_not_called()
        self.assertIn('1 photo(s) exhausted', out)
        self.user.refresh_from_db()
        # Fail closed: the photo stays pending, never shown, alert recorded.
        self.assertEqual(self.user.profile_image_status, PROFILE_IMAGE_STATUS_PENDING)
        self.assertTrue(self.user.profile_image_classification_alerted)
