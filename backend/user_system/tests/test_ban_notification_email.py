from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from ..constants import BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW
from ..models import PositiveOnlySocialUser, UserBan


class BanNotificationEmailTests(TestCase):
    """
    An outright ban emails the user that they have been suspended; shadow bans
    stay silent, and editing an existing ban does not re-notify.
    """

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='banneduser', email='banned@email.com', password='Password123!')

    def test_outright_ban_emails_the_user(self):
        UserBan.objects.create(user=self.user, ban_type=BAN_TYPE_OUTRIGHT)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('banned@email.com', message.to)
        self.assertIn('suspended', message.subject.lower())
        self.assertIn('permanently', message.body)

    def test_temporary_outright_ban_includes_expiry(self):
        expires = timezone.now() + timedelta(days=7)
        UserBan.objects.create(user=self.user, ban_type=BAN_TYPE_OUTRIGHT, expires=expires)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('until', mail.outbox[0].body)
        self.assertNotIn('permanently', mail.outbox[0].body)

    def test_ban_reason_included_when_present(self):
        UserBan.objects.create(user=self.user, ban_type=BAN_TYPE_OUTRIGHT,
                               reason='Repeated harassment')

        self.assertIn('Repeated harassment', mail.outbox[0].body)

    def test_shadow_ban_does_not_email(self):
        UserBan.objects.create(user=self.user, ban_type=BAN_TYPE_SHADOW)

        self.assertEqual(len(mail.outbox), 0)

    def test_expired_outright_ban_does_not_email(self):
        # Recording a historical ban must not notify the user.
        UserBan.objects.create(user=self.user, ban_type=BAN_TYPE_OUTRIGHT,
                               expires=timezone.now() - timedelta(days=1))

        self.assertEqual(len(mail.outbox), 0)

    def test_editing_existing_ban_does_not_resend(self):
        ban = UserBan.objects.create(user=self.user, ban_type=BAN_TYPE_OUTRIGHT)
        self.assertEqual(len(mail.outbox), 1)

        ban.reason = 'Updated reason'
        ban.save()

        # Still just the original email — no re-notification on edit.
        self.assertEqual(len(mail.outbox), 1)

    def test_user_without_email_is_skipped(self):
        self.user.email = ''
        self.user.save()

        UserBan.objects.create(user=self.user, ban_type=BAN_TYPE_OUTRIGHT)

        self.assertEqual(len(mail.outbox), 0)
