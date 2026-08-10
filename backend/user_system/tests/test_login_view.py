from django.urls import reverse

from .test_constants import (
    invalid_username, invalid_password,
    invalid_email, invalid_bool, false, true
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
        }

    def test_invalid_username_or_email_returns_bad_response(self):
        """
        Tests that a malformed username (or email) is rejected.
        """
        data = self.valid_data.copy()
        data['username_or_email'] = invalid_username  # Using invalid_username as malformed

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_invalid_password_returns_bad_response(self):
        """
        Tests that a malformed password is rejected by the pattern validator.
        """
        data = self.valid_data.copy()
        data['password'] = invalid_password

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_incorrect_password_returns_bad_response(self):
        """
        Tests that a correctly formatted but incorrect password fails.
        """
        data = self.valid_data.copy()
        data['password'] = "CorrectFormatButWrongPassword123-"

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('error'), "Invalid username or password")

    def test_unknown_username_or_email_returns_generic_bad_response(self):
        """
        Tests that an unknown account does not reveal whether the username/email exists.
        """
        data = self.valid_data.copy()
        data['username_or_email'] = "UnknownUser123"

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('error'), "Invalid username or password")

    def test_invalid_remember_me_returns_bad_response(self):
        """
        Tests that a non-boolean 'remember_me' value is rejected.
        """
        data = self.valid_data.copy()
        data['remember_me'] = invalid_bool

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_non_string_remember_me_is_a_validation_error_not_a_crash(self):
        """
        A JSON number is neither a bool nor a parseable string. It used to reach
        `.lower()` and raise AttributeError, which no caller catches, so the
        request came back as a 500 instead of a validation error.
        """
        data = self.valid_data.copy()
        data['remember_me'] = 1

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_null_remember_me_is_treated_as_omitted(self):
        """
        An explicit JSON null means "no value", exactly like leaving the key out.
        This API does not distinguish the two anywhere — date_of_birth and the
        interest fields are read the same way — and a client that serializes an
        unset optional as null rather than dropping the key must not be rejected.
        """
        data = self.valid_data.copy()
        data['remember_me'] = None

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(Fields.login_cookie_token, response.json())

    def test_omitted_remember_me_logs_in_without_remembering(self):
        """
        'remember_me' is optional — the website's own LoginRequest type marks it
        so, and its API tests call login without it. Leaving it out must mean
        "don't remember me", not a 500 (which is what the AttributeError from
        `None.lower()` used to produce).
        """
        data = self.valid_data.copy()
        del data['remember_me']

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        fields = response.json()
        self.assertIn(Fields.session_management_token, fields)
        # No remembered device was asked for, so none is issued.
        self.assertNotIn(Fields.series_identifier, fields)
        self.assertNotIn(Fields.login_cookie_token, fields)

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
        self.assertIn(Fields.username, fields)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertEqual(fields[Fields.username], self.local_username)

    def test_user_without_remember_me_and_with_username_returns_good_response(self):
        """
        Tests "happy path": login with username and remember_me=false.
        """
        # self.valid_data already has remember_me=false
        response = self.client.post(self.url, data=self.valid_data, content_type='application/json')

        self.assertEqual(response.status_code, 200)

        fields = response.json()
        self.assertIn(Fields.session_management_token, fields)
        self.assertIn(Fields.username, fields)
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertEqual(fields[Fields.username], self.local_username)

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
        self.assertIn(Fields.username, fields)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertEqual(fields[Fields.username], self.local_username)

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
        self.assertIn(Fields.username, fields)
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertEqual(fields[Fields.username], self.local_username)

        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)