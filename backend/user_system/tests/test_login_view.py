from django.urls import reverse

from .test_constants import (
    ip, invalid_username, invalid_password,
    invalid_email, invalid_ip, invalid_bool, false, true
)
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, Patterns
from ..input_validator import is_valid_pattern


class LoginUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to create a user in the DB and set:
        # self.local_username, self.local_email, self.local_password
        super().register_user_and_setup_local_fields(false)

        # The URL for the view
        self.url = reverse('login_user')

        # A valid data payload that we can modify in each test
        self.valid_data = {
            'username_or_email': self.local_username,
            'password': self.local_password,
            'remember_me': false,
            'ip': ip
        }

    def test_invalid_username_or_email_returns_bad_response(self):
        """
        Tests that a malformed username (or email) is rejected.
        """
        data = self.valid_data.copy()
        data['username_or_email'] = invalid_username  # Using invalid_username as malformed

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_invalid_password_returns_bad_response(self):
        """
        Tests that a malformed password is rejected by the pattern validator.
        """
        data = self.valid_data.copy()
        data['password'] = invalid_password

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_incorrect_password_returns_bad_response(self):
        """
        Tests that a correctly formatted but incorrect password fails.
        """
        data = self.valid_data.copy()
        data['password'] = "CorrectFormatButWrongPassword123!"

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_invalid_remember_me_returns_bad_response(self):
        """
        Tests that a non-boolean 'remember_me' value is rejected.
        """
        data = self.valid_data.copy()
        data['remember_me'] = invalid_bool

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_invalid_ip_returns_bad_response(self):
        """
        Tests that a malformed IP address is rejected.
        """
        data = self.valid_data.copy()
        data['ip'] = invalid_ip

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_user_with_remember_me_and_username_returns_good_response(self):
        """
        Tests "happy path": login with username and remember_me=true.
        """
        data = self.valid_data.copy()
        data['remember_me'] = true

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 200)

        fields = response.json()
        self.assertIn(Fields.series_identifier, fields)
        self.assertIn(Fields.login_cookie_token, fields)
        self.assertIn(Fields.session_management_token, fields)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_without_remember_me_and_with_username_returns_good_response(self):
        """
        Tests "happy path": login with username and remember_me=false.
        """
        # self.valid_data already has remember_me=false
        response = self.client.post(self.url, data=self.valid_data, content_type='application/json')

        self.assertEqual(response.status_code, 200)

        fields = response.json()
        self.assertIn(Fields.session_management_token, fields)
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

        # Should not include "remember me" fields
        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)

    def test_user_with_remember_me_and_email_returns_good_response(self):
        """
        Tests "happy path": login with email and remember_me=true.
        """
        data = self.valid_data.copy()
        data['username_or_email'] = self.local_email
        data['remember_me'] = true

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 200)

        fields = response.json()
        self.assertIn(Fields.series_identifier, fields)
        self.assertIn(Fields.login_cookie_token, fields)
        self.assertIn(Fields.session_management_token, fields)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_without_remember_me_and_with_email_returns_good_response(self):
        """
        Tests "happy path": login with email and remember_me=false.
        """
        data = self.valid_data.copy()
        data['username_or_email'] = self.local_email

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 200)

        fields = response.json()
        self.assertIn(Fields.session_management_token, fields)
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)