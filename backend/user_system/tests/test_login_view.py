from ..views import login_user
from ..constants import Fields, Patterns
from ..input_validator import is_valid_pattern
from .test_constants import ip, invalid_username, invalid_password, \
    invalid_email, invalid_ip, invalid_bool, false, true, FAIL, SUCCESS
from .test_utils import get_response_fields
from .test_parent_case import PositiveOnlySocialTestCase

class LoginUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user_setup(false)

    def test_invalid_username_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, invalid_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_email_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, invalid_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_password_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, self.local_username, invalid_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_remember_me_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, self.local_username, self.local_password, invalid_bool, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_ip_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, self.local_username, self.local_password, false, invalid_ip)
        self.assertEqual(response.status_code, FAIL)

    def test_user_does_exist_with_remember_me_and_username_returns_good_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, self.local_username, self.local_password, true, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_does_exist_without_remember_me_and_with_username_returns_good_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, self.local_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)

    def test_user_does_exist_with_remember_me_and_email_returns_good_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, self.local_email, self.local_password, true, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_does_exist_without_remember_me_and_with_email_returns_good_response(self):
        # Test view login_user
        response = login_user(self.login_user_request, self.local_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)
