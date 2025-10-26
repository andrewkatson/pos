import uuid
from django.urls import reverse

from .test_constants import ip, invalid_ip, true, false, LOGIN_USER_WITH_REMEMBER_ME
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..utils import generate_login_cookie_token

# --- Constants ---
invalid_session_management_token = '?'
invalid_series_identifier = '?'
invalid_login_cookie_token = '?'


class LoginUserRememberMETests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to:
        # 1. Create a user
        # 2. Log them in WITH remember_me=True
        # 3. Set self.session_management_token, self.series_identifier,
        #    and self.login_cookie_token
        super().register_user_and_setup_local_fields(remember_me=true)

        # The URL for the view
        self.url = reverse('login_user_with_remember_me')

        # Valid data payload for the "happy path"
        self.valid_data = {
            Fields.session_management_token: self.session_management_token,
            'series_identifier': self.series_identifier,
            'login_cookie_token': self.login_cookie_token,
            'ip': ip
        }

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that a malformed session token is rejected.
        """
        data = self.valid_data.copy()
        data[Fields.session_management_token] = invalid_session_management_token

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)  # 400 Bad Request

    def test_invalid_series_identifier_returns_bad_response(self):
        """
        Tests that a malformed series identifier is rejected.
        """
        data = self.valid_data.copy()
        data['series_identifier'] = invalid_series_identifier

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_invalid_login_cookie_token_returns_bad_response(self):
        """
        Tests that a malformed login cookie token is rejected.
        """
        data = self.valid_data.copy()
        data['login_cookie_token'] = invalid_login_cookie_token

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

    def test_matching_login_cookie_token_returns_good_response_with_new_tokens(self):
        """
        Tests the "happy path" - valid tokens should succeed and return
        new, rotated tokens.
        """
        response = self.client.post(self.url, data=self.valid_data, content_type='application/json')

        self.assertEqual(response.status_code, 200)

        fields = response.json()

        # Check that both tokens were successfully rotated
        self.assertIn(Fields.login_cookie_token, fields)
        self.assertIn(Fields.session_management_token, fields)
        self.assertNotEqual(fields[Fields.login_cookie_token], self.login_cookie_token)
        self.assertNotEqual(fields[Fields.session_management_token], self.session_management_token)

    def test_not_matching_login_cookie_token_returns_bad_response(self):
        """
        Tests that a valid series identifier but an incorrect token fails.
        """
        not_matching_login_cookie_token = generate_login_cookie_token()

        data = self.valid_data.copy()
        data['login_cookie_token'] = not_matching_login_cookie_token

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_non_existent_series_identifier_returns_bad_response(self):
        """
        Tests that a validly formatted but non-existent series identifier fails.
        """
        non_existent_series_identifier = str(uuid.uuid4())

        data = self.valid_data.copy()
        data['series_identifier'] = non_existent_series_identifier

        response = self.client.post(self.url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 404)