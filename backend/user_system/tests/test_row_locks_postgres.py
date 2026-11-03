"""Row-lock ordering between edits, reports and moderation, on PostgreSQL.

Caption/comment edits, reports and every review transition take the content
row lock first and the review row second (moderation.lock_reviewed_content,
issue #462). SQLite ignores select_for_update, so the SQLite suites can only
pin the order of the calls; these tests run each pair of operations on two
threads — two real database connections — and check that one really waits
for the other, that neither deadlocks, and that the one that waited re-checks
what the first committed. They are skipped unless the database is PostgreSQL
(the backend workflow's PostgreSQL job runs them).
"""
from unittest import skipUnless
from unittest.mock import patch
import os
import threading
import time

from django.db import connection, transaction
from django.test import Client
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTransactionTestCase
from .. import moderation, tasks
from ..constants import Fields, HIDDEN_REASON_REPORTS, REVIEW_STATUS_HIDDEN, REVIEW_STATUS_PENDING
from ..models import Comment, ModerationReview, Post

# Generous: a timeout here means a lock was never released, not a slow runner.
TIMEOUT = 15

POST_ROW_LOCK = ('FROM "user_system_post"', 'FOR NO KEY UPDATE')
COMMENT_ROW_LOCK = ('FROM "user_system_comment"', 'FOR NO KEY UPDATE')
POST_UPDATE = ('UPDATE "user_system_post"',)

edited_text = 'positive and edited #sunny'


class Actor(threading.Thread):
    """Runs `work` on its own thread, and so on its own database connection.

    With `pause_after`, the thread stops right after the first SQL statement
    containing every one of those strings has run — still inside its
    transaction, so any row lock it took stays held — until release()."""

    def __init__(self, work, pause_after=None):
        super().__init__(daemon=True)
        self.work = work
        self.pause_after = pause_after
        self.paused = threading.Event()
        self._resume = threading.Event()
        self.result = None
        self.error = None

    def _pause_hook(self, execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        if self.pause_after and not self.paused.is_set() and all(s in sql for s in self.pause_after):
            self.paused.set()
            self._resume.wait(TIMEOUT)
        return result

    def run(self):
        try:
            with connection.execute_wrapper(self._pause_hook):
                self.result = self.work()
        except BaseException as e:  # surfaced by finish()
            self.error = e
        finally:
            self.paused.set()
            connection.close()

    def release(self):
        self._resume.set()

    def finish(self):
        self.release()
        self.join(TIMEOUT)
        if self.is_alive():
            raise AssertionError("actor never finished")
        if self.error is not None:
            raise self.error
        return self.result


@skipUnless(connection.vendor == 'postgresql', 'row locks are only real on PostgreSQL')
class RowLockOrderTests(PositiveOnlySocialTransactionTestCase):
    # Keeps the interest categories migration 0029 seeds across the flushes.
    serialized_rollback = True

    def setUp(self):
        # The classifiers run in TESTING mode for the whole test, on every
        # thread (so not a decorator, which would end with setUp), and opened
        # reviews stay pending: the automated re-review would otherwise race
        # the assertions from the reporting thread.
        for p in (patch.dict(os.environ, {"TESTING": "True"}, clear=True),
                  patch.object(tasks, 'enqueue_report_review')):
            p.start()
            self.addCleanup(p.stop)
        super().setUp()
        self.post, self.post_identifier = super().make_post_and_login_user()
        self.author_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        created = self._comment_on_post(self.session_management_token, self.post_identifier)
        self.thread_identifier = created[Fields.comment_thread_identifier]
        self.comment = Comment.objects.get(comment_identifier=created[Fields.comment_identifier])
        reporter = self.make_user_with_prefix(prefix='reporter')
        self.reporter_header = {'HTTP_AUTHORIZATION': f'Bearer {reporter[Fields.session_management_token]}'}
        self.post.refresh_from_db()
        self.assertFalse(self.post.hidden)

    # -- the operations, each on a fresh client --------------------------------

    def _edit_post(self, caption=edited_text):
        return Client().post(
            reverse('edit_post', kwargs={'post_identifier': str(self.post_identifier)}),
            data={Fields.caption: caption}, content_type='application/json', **self.author_header)

    def _report_post(self):
        return Client().post(
            reverse('report_post', kwargs={'post_identifier': str(self.post_identifier)}),
            data={'reason': 'not nice'}, content_type='application/json', **self.reporter_header)

    def _comment_kwargs(self):
        return {
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.thread_identifier),
            'comment_identifier': str(self.comment.comment_identifier),
        }

    def _edit_comment(self):
        return Client().post(
            reverse('edit_comment', kwargs=self._comment_kwargs()),
            data={Fields.comment_text: edited_text}, content_type='application/json', **self.author_header)

    def _report_comment(self):
        return Client().post(
            reverse('report_comment', kwargs=self._comment_kwargs()),
            data={'reason': 'not nice'}, content_type='application/json', **self.reporter_header)

    def _open_post_review(self):
        self.assertEqual(self._report_post().status_code, 200)
        return ModerationReview.objects.get(post=self.post, status=REVIEW_STATUS_PENDING)

    # -- orchestration ---------------------------------------------------------

    def _wait_until_blocked(self, actor):
        """Wait until some connection is waiting on a lock — `actor`'s, since
        it is the only other one working."""
        deadline = time.monotonic() + TIMEOUT
        with connection.cursor() as cursor:
            while time.monotonic() < deadline:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'")
                if cursor.fetchone()[0]:
                    return
                if not actor.is_alive():
                    actor.finish()
                    self.fail("the second operation finished without waiting for the first one's lock")
                time.sleep(0.02)
        self.fail("the second operation never waited on a row lock")

    def _run_second_while_first_holds_lock(self, first, pause_after, second):
        """Start `first`, hold it just after it takes the lock `pause_after`
        matches, run `second` until it is waiting on that lock, then let both
        finish. Returns both results; a deadlock surfaces as an error."""
        holder = Actor(first, pause_after)
        holder.start()
        self.assertTrue(holder.paused.wait(TIMEOUT), "first operation never took its lock")
        waiter = Actor(second)
        waiter.start()
        try:
            self._wait_until_blocked(waiter)
        finally:
            first_result = holder.finish()
        return first_result, waiter.finish()

    # -- edits vs reports ------------------------------------------------------

    def test_report_waits_for_an_edit_in_flight_then_reviews_the_new_caption(self):
        edited, reported = self._run_second_while_first_holds_lock(
            self._edit_post, POST_ROW_LOCK, self._report_post)

        self.assertEqual(edited.status_code, 200)
        self.assertEqual(reported.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, edited_text)
        self.assertTrue(ModerationReview.objects.filter(post=self.post, status=REVIEW_STATUS_PENDING).exists())

    def test_edit_waits_for_a_report_in_flight_then_is_refused(self):
        original = self.post.caption

        reported, edited = self._run_second_while_first_holds_lock(
            self._report_post, POST_ROW_LOCK, self._edit_post)

        self.assertEqual(reported.status_code, 200)
        self.assertEqual(edited.status_code, 409)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, original)
        self.assertIsNone(self.post.edited_time)

    def test_comment_edit_waits_for_a_report_in_flight_then_is_refused(self):
        original = self.comment.body

        reported, edited = self._run_second_while_first_holds_lock(
            self._report_comment, COMMENT_ROW_LOCK, self._edit_comment)

        self.assertEqual(reported.status_code, 200)
        self.assertEqual(edited.status_code, 409)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, original)
        self.assertTrue(ModerationReview.objects.filter(comment=self.comment, status=REVIEW_STATUS_PENDING).exists())

    def test_edit_waiting_on_a_hide_rechecks_the_committed_row(self):
        # Whatever hides the post holds its row until it commits; the edit's
        # locked `hidden=False` read then re-evaluates against the hidden row
        # and finds nothing, rather than writing over hidden content.
        def hide():
            with transaction.atomic():
                Post.objects.select_for_update(no_key=True).get(pk=self.post.pk)
                Post.objects.filter(pk=self.post.pk).update(hidden=True, hidden_reason=HIDDEN_REASON_REPORTS)

        _, edited = self._run_second_while_first_holds_lock(hide, POST_UPDATE, self._edit_post)

        self.assertEqual(edited.status_code, 409)
        self.post.refresh_from_db()
        self.assertTrue(self.post.hidden)
        self.assertNotEqual(self.post.caption, edited_text)

    def test_stale_categorization_waits_for_the_edit_then_discards_its_buckets(self):
        Post.objects.filter(pk=self.post.pk).update(caption='nature')

        # categorize_post reads 'nature' while the edit holds the row
        # uncommitted, then waits on its own locked `caption='nature'` read,
        # which matches nothing once the edit commits.
        edited, _ = self._run_second_while_first_holds_lock(
            lambda: self._edit_post('just some ordinary words'), POST_ROW_LOCK,
            lambda: tasks.categorize_post(str(self.post_identifier)))

        self.assertEqual(edited.status_code, 200)
        self.assertEqual(list(self.post.interest_categories.all()), [])

    # -- moderator decisions vs the automated re-review ------------------------

    def test_moderator_decision_waits_for_the_rereview_without_deadlocking(self):
        review = self._open_post_review()

        self._run_second_while_first_holds_lock(
            lambda: tasks.review_reported_content(str(review.review_identifier)), POST_ROW_LOCK,
            lambda: moderation.hide_reviewed_content(ModerationReview.objects.get(pk=review.pk)))

        review.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(review.status, REVIEW_STATUS_HIDDEN)
        self.assertTrue(self.post.hidden)

    def test_rereview_waits_for_the_moderator_decision_without_deadlocking(self):
        review = self._open_post_review()

        self._run_second_while_first_holds_lock(
            lambda: moderation.hide_reviewed_content(ModerationReview.objects.get(pk=review.pk)), POST_ROW_LOCK,
            lambda: tasks.review_reported_content(str(review.review_identifier)))

        # The re-review found the review already decided and left it alone.
        review.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(review.status, REVIEW_STATUS_HIDDEN)
        self.assertTrue(self.post.hidden)
