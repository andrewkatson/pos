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
)
from ..models import PositiveOnlySocialUser, Post


def _backdate(post, **delta):
    """creation_time is auto_now_add, so tests move it via a queryset update."""
    Post.objects.filter(pk=post.pk).update(
        creation_time=timezone.now() - timedelta(**delta))


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
    def test_exhausted_pending_post_alerts_instead_of_reenqueueing(self, mock_enqueue):
        post = self._pending_post(attempts=CLASSIFICATION_MAX_ATTEMPTS)
        _backdate(post, minutes=30)
        out = self._run()
        mock_enqueue.assert_not_called()
        self.assertIn('1 exhausted', out)
        # Fail closed: the post stays hidden-pending, never published.
        post.refresh_from_db()
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_PENDING_CLASSIFICATION)
        self.assertTrue(post.hidden)

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
