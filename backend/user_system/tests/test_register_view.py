from django.urls import reverse

from .test_constants import (
    username, email, password, ip, invalid_username, invalid_password,
    invalid_email, invalid_ip, invalid_bool, false, true
)
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, Patterns
from ..input_validator import is_valid_pattern


# The view is no longer imported
# from ..views import register


class RegisterTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Define user details for this test
        self.local_username = f'{username}_{self.prefix}'
        self.local_password = f'{password}_{self.prefix}'
        self.local_email = f'{email}_{self.prefix}@email.com'

        # The URL for the register endpoint
        self.url = reverse('register')

        # A valid data payload that we can modify in each test
        self.valid_data = {
            'username': self.local_username,
            'email': self.local_email,
            'password': self.local_password,
            'remember_me': false,
            'ip': ip
        }

    def test_invalid_username_returns_bad_response(self):
        """
        Tests that a malformed username is rejected.
        """
        data = self.valid_data.copy()
        data['username'] = invalid_username

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_invalid_email_returns_bad_response(self):
        """
        Tests that a malformed email is rejected.
        """
        data = self.valid_data.copy()
        data['email'] = invalid_email

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_invalid_password_returns_bad_response(self):
        """
        Tests that a malformed password is rejected.
        """
        data = self.valid_data.copy()
        data['password'] = invalid_password

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_invalid_remember_me_returns_bad_response(self):
        """
        Tests that a malformed 'remember_me' value is rejected.
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

    def test_user_already_exists_returns_bad_response(self):
        """
        Tests that attempting to register with an existing username/email fails.
        """
        # First call: This one should succeed
        response1 = self.client.post(self.url, data=self.valid_data, content_type='application/json')
        self.assertEqual(response1.status_code, 201)  # 201 Created

        # Second call: This one should fail
        response2 = self.client.post(self.url, data=self.valid_data, content_type='application/json')
        self.assertEqual(response2.status_code, 404)
        self.assertIn("User already exists", response2.json().get('error', ''))

    def test_user_doesnt_exist_with_remember_me_returns_good_response(self):
        """
        Tests the "happy path" with remember_me=true.
        """
        data = self.valid_data.copy()
        data['remember_me'] = true

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 201)  # 201 Created

        fields = response.json()

        # Check that all three tokens are present and correctly formatted
        self.assertIn(Fields.series_identifier, fields)
        self.assertIn(Fields.login_cookie_token, fields)
        self.assertIn(Fields.session_management_token, fields)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_doesnt_exist_without_remember_me_returns_good_response(self):
        """
        Tests the "happy path" with remember_me=false.
        """
        # self.valid_data already has remember_me=false
        response = self.client.post(self.url, data=self.valid_data, content_type='application/json')

        self.assertEqual(response.status_code, 201)  # 201 Created

        fields = response.json()

        # Check that only the session token is returned
        self.assertIn(Fields.session_management_token, fields)
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)