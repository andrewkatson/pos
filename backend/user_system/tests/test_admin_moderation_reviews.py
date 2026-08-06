"""The moderator queue behind user reports (issue #467).

Exercised on the ModelAdmin directly, like test_admin_bans, so the admin views
(and the IP allowlist middleware in front of them) are out of the picture.
"""
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import timezone

from ..admin import ModerationReviewAdmin
from ..constants import (
    HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_NONE, HIDDEN_REASON_REPORTS,
    REVIEW_STATUS_DISMISSED, REVIEW_STATUS_ESCALATED, REVIEW_STATUS_HIDDEN,
)
from ..models import Comment, CommentThread, ModerationReview, PositiveOnlySocialUser


class ModerationReviewAdminTests(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.admin = ModerationReviewAdmin(ModerationReview, AdminSite())

        self.moderator = PositiveOnlySocialUser.objects.create_superuser(
            username='moderator', email='mod@email.com', password='ModPassword123-')
        self.author = PositiveOnlySocialUser.objects.create(
            username='author', email='author@email.com')
        self.reporter = PositiveOnlySocialUser.objects.create(
            username='reporter', email='reporter@email.com')

        self.post = self.author.post_set.create(caption='a contested caption')
        self.post.postreport_set.create(user=self.reporter, reason='I think this is mean')
        self.review = ModerationReview.objects.create(
            post=self.post, status=REVIEW_STATUS_ESCALATED, reports_at_last_review=0)

    def _request(self, user):
        request = self.factory.post('/')
        request.user = user
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        return request

    def _queryset(self):
        return ModerationReview.objects.filter(pk=self.review.pk)

    def _refresh(self):
        self.review.refresh_from_db()
        self.post.refresh_from_db()

    def test_hide_action_hides_the_content_and_records_the_moderator(self):
        self.admin.hide_content(self._request(self.moderator), self._queryset())

        self._refresh()
        self.assertEqual(self.review.status, REVIEW_STATUS_HIDDEN)
        self.assertEqual(self.review.resolved_by, self.moderator)
        self.assertIsNotNone(self.review.resolved_time)
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_REPORTS)

    def test_dismiss_action_leaves_the_content_up(self):
        self.admin.dismiss_reports(self._request(self.moderator), self._queryset())

        self._refresh()
        self.assertEqual(self.review.status, REVIEW_STATUS_DISMISSED)
        self.assertFalse(self.post.hidden)

    def test_dismiss_action_restores_content_the_queue_hid(self):
        self.admin.hide_content(self._request(self.moderator), self._queryset())

        self.admin.dismiss_reports(self._request(self.moderator), self._queryset())

        self._refresh()
        self.assertEqual(self.review.status, REVIEW_STATUS_DISMISSED)
        self.assertFalse(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_NONE)

    def test_a_moderator_can_reverse_an_earlier_decision(self):
        """A terminal status makes content immune to *reports*, not to
        moderators: a decision can be corrected from the queue, and the audit
        trail records who decided last."""
        self.admin.dismiss_reports(self._request(self.moderator), self._queryset())

        self.admin.hide_content(self._request(self.moderator), self._queryset())

        self._refresh()
        self.assertEqual(self.review.status, REVIEW_STATUS_HIDDEN)
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_REPORTS)

    def test_actions_require_permission(self):
        staffer = PositiveOnlySocialUser.objects.create_user(
            username='staffer', email='staff@email.com', password='StaffPassword123-', is_staff=True)
        staffer.user_permissions.add(Permission.objects.get(codename='view_moderationreview'))

        self.admin.hide_content(self._request(staffer), self._queryset())

        self._refresh()
        self.assertEqual(self.review.status, REVIEW_STATUS_ESCALATED)
        self.assertFalse(self.post.hidden)

    def test_hide_action_keeps_an_existing_hide_reason(self):
        """Content the classifier already hid keeps that reason, so an appeal can
        still tell the author what actually happened to it."""
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()

        self.admin.hide_content(self._request(self.moderator), self._queryset())

        self._refresh()
        self.assertEqual(self.review.status, REVIEW_STATUS_HIDDEN)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)

    def test_changelist_counts_reports_without_a_query_per_row(self):
        """The queue's Reports column is annotated, not counted per row: a
        moderator opening a busy queue must not pay one COUNT per entry."""
        thread = CommentThread.objects.create(post=self.post)
        for i in range(4):
            post = self.author.post_set.create(caption=f'contested {i}')
            post.postreport_set.create(user=self.reporter, reason='no')
            post.postreport_set.create(user=self.moderator, reason='no')
            ModerationReview.objects.create(post=post, status=REVIEW_STATUS_ESCALATED)
            comment = Comment.objects.create(
                comment_thread=thread, author=self.author, body=f'contested comment {i}')
            comment.commentreport_set.create(user=self.reporter, reason='no')
            ModerationReview.objects.create(comment=comment, status=REVIEW_STATUS_ESCALATED)

        # A withdrawn report is kept as a filing record but must not inflate the
        # queue's tally — the column has to agree with report_count().
        withdrawn = self.post.postreport_set.create(user=self.moderator, reason='changed my mind')
        withdrawn.retracted_time = timezone.now()
        withdrawn.save(update_fields=['retracted_time'])

        request = self._request(self.moderator)
        # One query for the rows, whatever the row count — no per-row COUNT and
        # no per-row walk to the post/comment or its author.
        with self.assertNumQueries(1):
            counts = [self.admin.report_count(review)
                      for review in self.admin.get_queryset(request)]

        # 9 reviews: 4 posts with 2 reports, 4 comments with 1, and setUp's 1.
        self.assertEqual(sorted(counts), [1, 1, 1, 1, 1, 2, 2, 2, 2])

    def test_changelist_columns_render_the_reported_content(self):
        """The queue is only useful if a moderator can see what was reported and
        what the reporters said — and that text is shown here, never sent to a
        classifier."""
        self.assertEqual(self.admin.target_kind(self.review), 'post')
        self.assertEqual(self.admin.target_summary(self.review), 'a contested caption')
        self.assertEqual(self.admin.author(self.review), self.author)
        self.assertEqual(self.admin.report_count(self.review), 1)
        self.assertIn('I think this is mean', self.admin.reported_reasons(self.review))
