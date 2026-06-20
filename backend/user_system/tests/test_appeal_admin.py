from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.test import RequestFactory, TestCase
from django.utils import timezone

from ..admin import AppealAdmin
from ..constants import (
    BAN_TYPE_OUTRIGHT, HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_NONE,
    APPEAL_STATUS_PENDING, APPEAL_STATUS_APPROVED, APPEAL_STATUS_DENIED,
)
from ..models import Appeal, Comment, CommentThread, Post, PositiveOnlySocialUser, UserBan


class AppealAdminActionTests(TestCase):

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.appeal_admin = AppealAdmin(Appeal, AdminSite())

        self.admin_user = PositiveOnlySocialUser.objects.create_superuser(
            username='adminuser', email='admin@email.com', password='AdminPassword123!')
        self.author = PositiveOnlySocialUser.objects.create_user(
            username='author', email='author@email.com', password='AuthorPassword123!')

    def _request(self, user):
        request = self.factory.post('/')
        request.user = user
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        return request

    def _hidden_post(self):
        return Post.objects.create(
            author=self.author, image_url='https://b.s3.amazonaws.com/k/x.jpeg',
            caption='my caption', hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)

    def _hidden_comment(self):
        post = Post.objects.create(author=self.author, image_url='u', caption='c')
        thread = CommentThread.objects.create(post=post)
        return thread.comment_set.create(author=self.author, body='my comment',
                                         hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)

    def _qs(self, *appeals):
        return Appeal.objects.filter(pk__in=[a.pk for a in appeals])

    # ----- approve -----------------------------------------------------------

    def test_approve_unhides_post(self):
        post = self._hidden_post()
        appeal = Appeal.objects.create(appellant=self.author, post=post, reason='r',
                                       content_snapshot=post.caption)

        self.appeal_admin.approve_appeals(self._request(self.admin_user), self._qs(appeal))

        post.refresh_from_db()
        self.assertFalse(post.hidden)
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_NONE)
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_APPROVED)
        self.assertEqual(appeal.resolved_by, self.admin_user)
        self.assertIsNotNone(appeal.resolved_time)

    def test_approve_unhides_comment(self):
        comment = self._hidden_comment()
        appeal = Appeal.objects.create(appellant=self.author, comment=comment, reason='r')

        self.appeal_admin.approve_appeals(self._request(self.admin_user), self._qs(appeal))

        comment.refresh_from_db()
        self.assertFalse(comment.hidden)
        self.assertEqual(comment.hidden_reason, HIDDEN_REASON_NONE)

    def test_approve_lifts_ban(self):
        ban = UserBan.objects.create(user=self.author, ban_type=BAN_TYPE_OUTRIGHT, reason='b')
        appeal = Appeal.objects.create(appellant=self.author, ban=ban, reason='r')

        self.appeal_admin.approve_appeals(self._request(self.admin_user), self._qs(appeal))

        ban.refresh_from_db()
        self.assertFalse(ban.is_in_effect())
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_APPROVED)

    def test_approve_emails_appellant(self):
        post = self._hidden_post()
        appeal = Appeal.objects.create(appellant=self.author, post=post, reason='r')

        mail.outbox.clear()
        self.appeal_admin.approve_appeals(self._request(self.admin_user), self._qs(appeal))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('approved', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['author@email.com'])

    # ----- deny --------------------------------------------------------------

    @patch('user_system.s3.delete_image')
    def test_deny_deletes_post_and_cleans_up_image(self, mock_delete):
        post = self._hidden_post()
        image_url = post.image_url
        appeal = Appeal.objects.create(appellant=self.author, post=post, reason='r',
                                       content_snapshot=post.caption)

        self.appeal_admin.deny_appeals(self._request(self.admin_user), self._qs(appeal))

        self.assertFalse(Post.objects.filter(pk=post.pk).exists())
        mock_delete.assert_called_once_with(image_url)
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_DENIED)
        self.assertIsNone(appeal.post)
        self.assertEqual(appeal.content_snapshot, 'my caption')  # audit trail kept

    def test_deny_keeps_comment_hidden(self):
        comment = self._hidden_comment()
        appeal = Appeal.objects.create(appellant=self.author, comment=comment, reason='r')

        self.appeal_admin.deny_appeals(self._request(self.admin_user), self._qs(appeal))

        comment.refresh_from_db()
        self.assertTrue(comment.hidden)
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_DENIED)

    @patch('user_system.s3.delete_image')
    def test_str_after_denied_post_deleted(self, _mock_delete):
        post = self._hidden_post()
        appeal = Appeal.objects.create(appellant=self.author, post=post, reason='r',
                                       content_snapshot=post.caption)
        appeal.deny(resolved_by=self.admin_user)

        appeal.refresh_from_db()
        rendered = str(appeal)
        self.assertIn('removed target', rendered)
        self.assertIn(str(appeal.appeal_identifier), rendered)

    def test_deny_emails_appellant(self):
        comment = self._hidden_comment()
        appeal = Appeal.objects.create(appellant=self.author, comment=comment, reason='r')

        mail.outbox.clear()
        self.appeal_admin.deny_appeals(self._request(self.admin_user), self._qs(appeal))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('denied', mail.outbox[0].body)

    # ----- guards ------------------------------------------------------------

    def test_already_resolved_appeal_is_skipped(self):
        post = self._hidden_post()
        appeal = Appeal.objects.create(appellant=self.author, post=post, reason='r',
                                       status=APPEAL_STATUS_DENIED)

        self.appeal_admin.approve_appeals(self._request(self.admin_user), self._qs(appeal))

        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_DENIED)  # unchanged
        post.refresh_from_db()
        self.assertTrue(post.hidden)  # not un-hidden

    def test_resolve_requires_permission(self):
        post = self._hidden_post()
        appeal = Appeal.objects.create(appellant=self.author, post=post, reason='r')
        powerless = PositiveOnlySocialUser.objects.create_user(
            username='powerless', email='p@email.com', password='PowerlessPass123!')

        self.appeal_admin.approve_appeals(self._request(powerless), self._qs(appeal))

        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_PENDING)
        post.refresh_from_db()
        self.assertTrue(post.hidden)

    def test_approve_is_noop_on_resolved_appeal(self):
        """Re-resolving must not overwrite the audit trail or re-send email."""
        comment = self._hidden_comment()
        appeal = Appeal.objects.create(appellant=self.author, comment=comment, reason='r')
        appeal.deny(resolved_by=self.admin_user)
        original_time = Appeal.objects.get(pk=appeal.pk).resolved_time

        mail.outbox.clear()
        appeal.approve(resolved_by=self.admin_user)  # should be a no-op

        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_DENIED)
        self.assertEqual(appeal.resolved_time, original_time)
        self.assertEqual(len(mail.outbox), 0)

    def test_deny_is_noop_on_resolved_appeal(self):
        post = self._hidden_post()
        appeal = Appeal.objects.create(appellant=self.author, post=post, reason='r')
        appeal.approve(resolved_by=self.admin_user)  # un-hides, marks approved

        with patch('user_system.s3.delete_image') as mock_delete:
            appeal.deny(resolved_by=self.admin_user)  # should be a no-op

        appeal.refresh_from_db()
        self.assertEqual(appeal.status, APPEAL_STATUS_APPROVED)
        mock_delete.assert_not_called()
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
