from django.core import mail
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from ..constants import Fields
from .test_constants import username, password, false, ip
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import PositiveOnlySocialUser

import os

# --- Constants ---
other_username = f'other_{username}'
non_existent_username = 'iamnotauser'


def _get_verification_token_from_email():
    """Extracts the raw verification token from the most recent outbox email."""
    body = mail.outbox[-1].body
    # Email body: "...token is:\n\n<TOKEN>\n\nEnter this..."
    return body.split('\n\n')[1].strip()


class ResetPasswordTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()

    # --- Helpers ---

    def _request_reset(self, username_or_email=None):
        url = reverse('request_reset')
        data = {'username_or_email': username_or_email or self.local_username}
        return self.client.post(url, data=data, content_type='application/json')

    def _verify_reset(self, verification_token, username_or_email=None):
        url = reverse('verify_reset')
        data = {
            'username_or_email': username_or_email or self.local_username,
            'verification_token': verification_token,
        }
        return self.client.post(url, data=data, content_type='application/json')

    def _do_full_verify(self):
        """Request reset, extract token from email, verify. Returns the step-3 reset_token."""
        self._request_reset()
        verification_token = _get_verification_token_from_email()
        response = self._verify_reset(verification_token)
        self.assertEqual(response.status_code, 200)
        return response.json().get('reset_token')

    # --- request_reset tests ---

    def test_user_does_not_exist_request_reset_returns_bad_response(self):
        url = reverse('request_reset')
        response = self.client.post(url, data={'username_or_email': non_existent_username}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("No user with that username or email", response.json().get('error', ''))

    def test_request_reset_stores_verification_token_hash(self):
        self._request_reset()
        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.assertIsNotNone(user.verification_token)
        self.assertIsNotNone(user.verification_token_expires)
        self.assertGreater(user.verification_token_expires, timezone.now())

    # --- verify_reset tests ---

    def test_user_does_not_exist_verify_reset_returns_bad_response(self):
        url = reverse('verify_reset')
        data = {'username_or_email': non_existent_username, 'verification_token': 'sometoken'}
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("No user with that username or email", response.json().get('error', ''))

    def test_invalid_verification_token_returns_bad_response(self):
        self._request_reset()
        response = self._verify_reset('definitely_wrong_token')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid or expired", response.json().get('error', ''))

    def test_verify_reset_response_has_no_store_cache_control(self):
        self._request_reset()
        verification_token = _get_verification_token_from_email()
        response = self._verify_reset(verification_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Cache-Control'), 'no-store')

    # --- reset_password tests ---

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_user_does_not_exist_reset_password_returns_bad_response(self):
        new_password = f'new_{password}'
        url = reverse('reset_password')
        data = {
            'username': non_existent_username,
            'email': self.local_email,
            'password': new_password,
            'reset_token': 'dummy_token'
        }
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("No user with that username or email", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_password_reset_flow_succeeds_and_changes_password(self):
        """Full happy-path: request → verify → reset → login with new password."""
        reset_token = self._do_full_verify()
        self.assertIsNotNone(reset_token)

        # Check verification_token was cleared after verify step
        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.assertIsNone(user.verification_token)

        # Reset password
        new_password = f'new_{password}_{self.prefix}!'
        reset_url = reverse('reset_password')
        response = self.client.post(reset_url, data={
            'username': self.local_username,
            'email': self.local_email,
            'password': new_password,
            'reset_token': reset_token,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Password reset successfully'})

        login_url = reverse('login_user')

        # Old password should fail
        response = self.client.post(login_url, data={
            'username_or_email': self.local_username,
            'password': self.local_password,
            'remember_me': false,
            'ip': ip,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

        # New password should succeed
        response = self.client.post(login_url, data={
            'username_or_email': self.local_username,
            'password': new_password,
            'remember_me': false,
            'ip': ip,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(Fields.session_management_token, response.json())

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_expired_verification_token_rejected(self):
        self._request_reset()
        verification_token = _get_verification_token_from_email()

        # Manually expire it
        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        user.verification_token_expires = timezone.now() - timedelta(minutes=1)
        user.save()

        response = self._verify_reset(verification_token)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid or expired", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_expired_reset_token_rejected(self):
        reset_token = self._do_full_verify()

        # Manually expire the step-3 token
        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        user.reset_token_expires = timezone.now() - timedelta(minutes=1)
        user.save()

        response = self.client.post(reverse('reset_password'), data={
            'username': self.local_username,
            'email': self.local_email,
            'password': f'new_{password}_{self.prefix}!',
            'reset_token': reset_token,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_token_is_single_use(self):
        reset_token = self._do_full_verify()
        new_password = f'new_{password}_{self.prefix}!'

        # First use succeeds
        response = self.client.post(reverse('reset_password'), data={
            'username': self.local_username,
            'email': self.local_email,
            'password': new_password,
            'reset_token': reset_token,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        # Second use with same token fails
        response = self.client.post(reverse('reset_password'), data={
            'username': self.local_username,
            'email': self.local_email,
            'password': f'second_{password}_{self.prefix}!',
            'reset_token': reset_token,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid reset token", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_password_without_verify_step_fails(self):
        url = reverse('reset_password')
        response = self.client.post(url, data={
            'username': self.local_username,
            'email': self.local_email,
            'password': f'new_{password}_{self.prefix}!',
            'reset_token': 'fake_token_without_verify',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid reset token", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_password_non_positive_username_fails(self):
        url = reverse('reset_password')
        response = self.client.post(url, data={
            'username': 'negative_user_reset',
            'email': self.local_email,
            'password': 'Positive_Password123!',
            'reset_token': 'dummy_token',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Username is not positive", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_password_non_positive_email_fails(self):
        url = reverse('reset_password')
        response = self.client.post(url, data={
            'username': self.local_username,
            'email': 'negative_email@email.com',
            'password': 'Positive_Password123!',
            'reset_token': 'dummy_token',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Email is not positive", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_password_non_positive_password_fails(self):
        url = reverse('reset_password')
        response = self.client.post(url, data={
            'username': self.local_username,
            'email': self.local_email,
            'password': 'Negative_Password_123!',
            'reset_token': 'dummy_token',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Password is not positive", response.json().get('error', ''))
