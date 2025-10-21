import uuid

from .test_constants import username, email, password, ip, invalid_ip, true, false, FAIL, SUCCESS, \
    LOGIN_USER_WITH_REMEMBER_ME
from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_fields
from ..constants import Fields
from ..utils import generate_login_cookie_token
from ..views import register, login_user_with_remember_me

invalid_session_management_token = '?'
invalid_series_identifier = '?'
invalid_login_cookie_token = '?'


class LoginUserRememberMETests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user_setup(true, LOGIN_USER_WITH_REMEMBER_ME)

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.login_user_request, invalid_session_management_token,
                                               self.series_identifier,
                                               self.login_cookie_token, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_series_identifier_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.login_user_request, self.session_management_token,
                                               invalid_series_identifier,
                                               self.login_cookie_token,
                                               ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_login_cookie_token_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.login_user_request, self.session_management_token,
                                               self.series_identifier,
                                               invalid_login_cookie_token, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_ip_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.login_user_request, self.session_management_token,
                                               self.series_identifier,
                                               self.login_cookie_token, invalid_ip)
        self.assertEqual(response.status_code, FAIL)

    def test_matching_login_cookie_token_returns_good_response_with_new_login_cookie_token(self):
        response = login_user_with_remember_me(self.login_user_request, self.session_management_token,
                                               self.series_identifier,
                                               self.login_cookie_token, ip)
        self.assertEqual(response.status_code, SUCCESS)

        fields = get_response_fields(response)
        self.assertNotEqual(fields[Fields.login_cookie_token], self.login_cookie_token)
        self.assertNotEqual(fields[Fields.session_management_token], self.session_management_token)

    def test_not_matching_login_cookie_token_returns_bad_response(self):
        # Test view login_user_with_remember_me with the valid but non-existent series_identifier.
        not_matching_login_cookie_token = generate_login_cookie_token()
        response = login_user_with_remember_me(self.login_user_request, self.session_management_token,
                                               self.series_identifier,
                                               not_matching_login_cookie_token, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_missing_series_identifier_returns_bad_response(self):
        prefix = self._testMethodName
        other_username = f'other_{username}_{prefix}'
        other_password = f'other_{password}_{prefix}'
        other_email = f'other_{email}_{prefix}@email.com'

        # For this one we want to register a user with the info needed
        # to login later. This test has no remember me so there should be no series identifier..
        request = self.factory.post("/user_system/register")
        response = register(request, other_username, other_email, other_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Test view login_user_with_remember_me with the valid but non-existent series_identifier.
        non_existent_series_identifier = str(uuid.uuid4())
        response = login_user_with_remember_me(self.login_user_request, self.session_management_token,
                                               non_existent_series_identifier,
                                               self.login_cookie_token, ip)
        self.assertEqual(response.status_code, FAIL)
