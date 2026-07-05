import hashlib
import re
from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from .test_constants import true
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import EMAIL_NOT_VERIFIED
from ..models import PositiveOnlySocialUser

# Matches the link built by views._email_verification_link
TOKEN_LINK_RE = re.compile(r"/verify-email\?token=([A-Za-z0-9_-]{43})")


class EmailVerificationTests(PositiveOnlySocialTestCase):
    """Covers the email-verification flow added for issue #237: registration
    stores a hashed token and emails a verification link, and login plus every
    authenticated endpoint refuse the account until the link is used."""

    def setUp(self):
        super().setUp()
        self.verify_url = reverse('verify_email')
        self.resend_url = reverse('resend_verification_email')

    def _register_unverified(self, remember_me=None):
        username = self._get_unique_username('unverified')
        password = f'Password_{self.prefix}123-'
        email = f'{username}@email.com'
        if remember_me is None:
            response_data = self._register_user(username, email, password, verify_email=False)
        else:
            response_data = self._register_user(username, email, password, remember_me,
                                                verify_email=False)
        return username, email, password, response_data

    def _token_from_last_email(self):
        self.assertGreater(len(mail.outbox), 0)
        match = TOKEN_LINK_RE.search(mail.outbox[-1].body)
        self.assertIsNotNone(match, "No verification link found in email body")
        return match.group(1)

    def _verify(self, token):
        return self.client.post(self.verify_url, data={'verification_token': token},
                                content_type='application/json')

    def _resend(self, username_or_email):
        return self.client.post(self.resend_url, data={'username_or_email': username_or_email},
                                content_type='application/json')

    def _login(self, username, password):
        url = reverse('login_user')
        data = {'username_or_email': username, 'password': password, 'remember_me': 'false'}
        return self.client.post(url, data=data, content_type='application/json')

    # --- registration ---

    def test_register_stores_hashed_token_and_emails_link(self):
        username, email, _, _ = self._register_unverified()
        user = PositiveOnlySocialUser.objects.get(username=username)

        self.assertFalse(user.email_verified)
        self.assertIsNotNone(user.email_verification_token)
        self.assertIsNotNone(user.email_verification_token_expires)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Welcome to Good Vibes Only")
        self.assertIn(email, message.to)

        raw_token = self._token_from_last_email()
        self.assertEqual(hashlib.sha256(raw_token.encode()).hexdigest(),
                         user.email_verification_token)
        # The raw token must never be stored.
        self.assertNotEqual(raw_token, user.email_verification_token)

    # --- gating while unverified ---

    def test_login_rejected_until_verified(self):
        username, _, password, _ = self._register_unverified()
        response = self._login(username, password)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], EMAIL_NOT_VERIFIED)

    def test_authed_endpoint_rejected_until_verified(self):
        _, _, _, register_data = self._register_unverified()
        token = register_data['session_management_token']
        response = self.client.post(reverse('logout_user'), content_type='application/json',
                                    HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], EMAIL_NOT_VERIFIED)

    def test_remember_me_login_rejected_until_verified(self):
        _, _, _, register_data = self._register_unverified(remember_me=true)
        url = reverse('login_user_with_remember_me')
        data = {
            'session_management_token': register_data['session_management_token'],
            'series_identifier': register_data['series_identifier'],
            'login_cookie_token': register_data['login_cookie_token'],
        }
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], EMAIL_NOT_VERIFIED)

    # --- verifying ---

    def test_verify_email_marks_user_verified_and_unblocks_login(self):
        username, _, password, _ = self._register_unverified()
        raw_token = self._token_from_last_email()

        response = self._verify(raw_token)
        self.assertEqual(response.status_code, 200)

        user = PositiveOnlySocialUser.objects.get(username=username)
        self.assertTrue(user.email_verified)
        self.assertIsNone(user.email_verification_token)
        self.assertIsNone(user.email_verification_token_expires)

        self.assertEqual(self._login(username, password).status_code, 200)

    def test_verify_email_token_cannot_be_reused(self):
        self._register_unverified()
        raw_token = self._token_from_last_email()
        self.assertEqual(self._verify(raw_token).status_code, 200)
        self.assertEqual(self._verify(raw_token).status_code, 400)

    def test_verify_email_rejects_malformed_token(self):
        self._register_unverified()
        for bad in ['', 'short', 'x' * 43 + '!', 'a' * 44]:
            response = self._verify(bad)
            self.assertEqual(response.status_code, 400)

    def test_verify_email_rejects_unknown_token(self):
        self._register_unverified()
        response = self._verify('A' * 43)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid or expired', response.json()['error'])

    def test_verify_email_rejects_expired_token(self):
        username, _, _, _ = self._register_unverified()
        raw_token = self._token_from_last_email()

        user = PositiveOnlySocialUser.objects.get(username=username)
        user.email_verification_token_expires = timezone.now() - timedelta(hours=1)
        user.save()

        self.assertEqual(self._verify(raw_token).status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    # --- resending ---

    def test_resend_issues_new_token_and_invalidates_old(self):
        username, _, _, _ = self._register_unverified()
        old_token = self._token_from_last_email()

        response = self._resend(username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

        new_token = self._token_from_last_email()
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(self._verify(old_token).status_code, 400)
        self.assertEqual(self._verify(new_token).status_code, 200)

    def test_resend_by_email_address(self):
        _, email, _, _ = self._register_unverified()
        self.assertEqual(self._resend(email).status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

    def test_resend_rejected_for_verified_user(self):
        self.register_user_and_setup_local_fields()
        response = self._resend(self.local_username)
        self.assertEqual(response.status_code, 400)
        self.assertIn('already verified', response.json()['error'])

    def test_resend_rejected_for_unknown_user(self):
        response = self._resend('nosuchuser12345')
        self.assertEqual(response.status_code, 400)

    # --- grandfathered users (helper-verified) are unaffected ---

    def test_verified_user_flow_unchanged(self):
        self.register_user_and_setup_local_fields()
        response = self._login(self.local_username, self.local_password)
        self.assertEqual(response.status_code, 200)
