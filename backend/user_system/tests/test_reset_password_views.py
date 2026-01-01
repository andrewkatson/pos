from django.urls import reverse
from unittest.mock import patch

from ..constants import Fields
from .test_constants import username, password, false, ip
from .test_parent_case import PositiveOnlySocialTestCase
# Import the user model to check the reset_id
from ..models import PositiveOnlySocialUser

import os

# --- Constants ---
other_username = f'other_{username}'
non_existent_username = 'iamnotauser'


class ResetPasswordTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to create a user and set:
        # self.local_username, self.local_email, self.local_password
        self.register_user_and_setup_local_fields()

    def test_user_does_not_exist_request_reset_returns_bad_response(self):
        """
        Tests that request_reset fails for a non-existent user.
        """
        url = reverse('request_reset')
        data = {'username_or_email': non_existent_username}

        response = self.client.post(url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn("No user with that username or email", response.json().get('error', ''))

    def test_user_does_not_exist_verify_reset_returns_bad_response(self):
        """
        Tests that verify_reset fails for a non-existent user.
        """
        url = reverse('verify_reset', kwargs={
            'username_or_email': non_existent_username,
            'reset_id': 12345
        })

        response = self.client.get(url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("No user with that username or email", response.json().get('error', ''))
        
    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_user_does_not_exist_reset_password_returns_bad_response(self):
        """
        Tests that reset_password fails for a non-existent user.
        """
        new_password = f'new_{password}'
        url = reverse('reset_password')
        data = {
            'username': non_existent_username,
            'email': self.local_email,
            'password': new_password
        }

        response = self.client.post(url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn("No user with that username or email", response.json().get('error', ''))

    def test_reset_id_does_not_match_returns_bad_response(self):
        """
        Tests the flow where the user provides an incorrect reset ID.
        """
        # 1. Request the reset
        url = reverse('request_reset')
        data = {'username_or_email': self.local_username}
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        # 2. Get the real reset id from the DB
        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        reset_id = user.reset_id
        self.assertGreater(reset_id, 0)  # Make sure it was set

        # 3. Attempt to verify with an incorrect ID
        verify_url = reverse('verify_reset', kwargs={
            'username_or_email': self.local_username,
            'reset_id': reset_id + 1  # Incorrect ID
        })
        response = self.client.get(verify_url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not match", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_password_reset_flow_succeeds_and_changes_password(self):
        """
        Tests the full, "happy path" end-to-end flow:
        1. Request reset
        2. Verify reset ID
        3. Set new password
        4. Verify old password fails and new password works
        """
        # --- 1. Request Reset ---
        request_url = reverse('request_reset')
        request_data = {'username_or_email': self.local_username}
        response = self.client.post(request_url, data=request_data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        # --- 2. Get Reset ID and Verify ---
        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        reset_id = user.reset_id
        self.assertGreater(reset_id, 0)

        verify_url = reverse('verify_reset', kwargs={
            'username_or_email': self.local_username,
            'reset_id': reset_id  # Correct ID
        })
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)

        # Check that the reset_id was invalidated
        user.refresh_from_db()
        self.assertEqual(user.reset_id, -1)

        # --- 3. Reset Password ---
        new_password = f'new_{password}_{self.prefix}!'
        reset_url = reverse('reset_password')
        reset_data = {
            'username': self.local_username,
            'email': self.local_email,
            'password': new_password
        }
        response = self.client.post(reset_url, data=reset_data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Password reset successfully'})

        # --- 4. VERIFY THE CHANGE ---
        login_url = reverse('login_user')

        # a) Try to log in with the OLD password (should fail)
        old_login_data = {
            'username_or_email': self.local_username,
            'password': self.local_password,  # The original password
            'remember_me': false,
            'ip': ip
        }
        response = self.client.post(login_url, data=old_login_data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Password was not correct", response.json().get('error', ''))

        # b) Try to log in with the NEW password (should succeed)
        new_login_data = {
            'username_or_email': self.local_username,
            'password': new_password,  # The new password
            'remember_me': false,
            'ip': ip
        }
        response = self.client.post(login_url, data=new_login_data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(Fields.session_management_token, response.json())

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_password_non_positive_username_fails(self):
        """
        Tests that a non-positive username is rejected during password reset.
        """
        url = reverse('reset_password')
        data = {
            'username': 'negative_user_reset',
            'email': self.local_email,
            'password': 'Positive_Password123!'
        }
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Username is not positive", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_password_non_positive_email_fails(self):
        """
        Tests that a non-positive email is rejected during password reset.
        """
        url = reverse('reset_password')
        data = {
            'username': self.local_username,
            'email': 'negative_email@email.com',
            'password': 'Positive_Password123!'
        }
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Email is not positive", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reset_password_non_positive_password_fails(self):
        """
        Tests that a non-positive password is rejected during password reset.
        """
        url = reverse('reset_password')
        data = {
            'username': self.local_username,
            'email': self.local_email,
            'password': 'Negative_Password_123!'
        }
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Password is not positive", response.json().get('error', ''))