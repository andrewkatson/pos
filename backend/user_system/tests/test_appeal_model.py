from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    HIDDEN_REASON_NONE, HIDDEN_REASON_REPORTS, HIDDEN_REASON_CLASSIFIER,
    APPEAL_STATUS_PENDING, APPEAL_STATUS_APPROVED,
)
from ..models import Appeal, Comment, Post, UserBan
from ..views import get_user_with_username


class HiddenReasonFieldTests(PositiveOnlySocialTestCase):
    """The hidden_reason groundwork on Post and Comment."""

    def setUp(self):
        super().setUp()
        self.make_post_with_users(num=1)
        self.user = get_user_with_username(self.local_username)

    def test_post_hidden_reason_defaults_to_none(self):
        self.assertFalse(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_NONE)

    def test_post_hidden_reason_can_be_set(self):
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()
        self.post.refresh_from_db()
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)

    def test_comment_hidden_reason_defaults_to_none(self):
        thread = self.post.commentthread_set.create()
        comment = thread.comment_set.create(author=self.user, body="hi")
        self.assertFalse(comment.hidden)
        self.assertEqual(comment.hidden_reason, HIDDEN_REASON_NONE)


class AppealModelTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        self.make_post_with_users(num=1)
        self.user = get_user_with_username(self.local_username)
        self.thread = self.post.commentthread_set.create()
        self.comment = self.thread.comment_set.create(author=self.user, body="hi")
        self.ban = UserBan.objects.create(user=self.user)

    def test_post_appeal_target_is_the_post(self):
        appeal = Appeal.objects.create(appellant=self.user, post=self.post, reason="please")
        self.assertEqual(appeal.target, self.post)
        self.assertEqual(appeal.status, APPEAL_STATUS_PENDING)

    def test_comment_appeal_target_is_the_comment(self):
        appeal = Appeal.objects.create(appellant=self.user, comment=self.comment)
        self.assertEqual(appeal.target, self.comment)

    def test_ban_appeal_target_is_the_ban(self):
        appeal = Appeal.objects.create(appellant=self.user, ban=self.ban)
        self.assertEqual(appeal.target, self.ban)

    def test_pending_manager_only_returns_pending(self):
        pending = Appeal.objects.create(appellant=self.user, post=self.post)
        resolved = Appeal.objects.create(appellant=self.user, comment=self.comment,
                                         status=APPEAL_STATUS_APPROVED)

        pending_ids = set(Appeal.objects.pending().values_list('appeal_identifier', flat=True))
        self.assertIn(pending.appeal_identifier, pending_ids)
        self.assertNotIn(resolved.appeal_identifier, pending_ids)

    def test_appeal_requires_a_target(self):
        """Zero targets is rejected by clean() (the DB allows it post-deletion)."""
        with self.assertRaises(ValidationError):
            Appeal(appellant=self.user).clean()

    def test_appeal_rejects_two_targets_via_clean(self):
        with self.assertRaises(ValidationError):
            Appeal(appellant=self.user, post=self.post, comment=self.comment).clean()

    def test_appeal_rejects_two_targets_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Appeal.objects.create(appellant=self.user, post=self.post, comment=self.comment)

    def test_deleting_post_keeps_appeal_record(self):
        """SET_NULL means denying-and-deleting a post leaves the audit trail."""
        appeal = Appeal.objects.create(appellant=self.user, post=self.post,
                                       content_snapshot=self.post.caption)
        self.post.delete()
        appeal.refresh_from_db()
        self.assertIsNone(appeal.post)
        self.assertIsNotNone(appeal.content_snapshot)
