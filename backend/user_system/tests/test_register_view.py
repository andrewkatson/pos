from .test_constants import username, email, password, ip, invalid_username, invalid_password, \
    invalid_email, invalid_ip, invalid_bool, false, true, FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_fields
from ..constants import Fields, Patterns
from ..input_validator import is_valid_pattern
from ..views import register


class RegisterTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        self.local_username = f'{username}_{self.prefix}'
        self.local_password = f'{password}_{self.prefix}'
        self.local_email = (f'{email}_{self.prefix}@email.com')

    def test_invalid_username_returns_bad_response(self):
        # Test view register
        response = register(self.register_request, invalid_username, self.local_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_email_returns_bad_response(self):
        # Create an instance of a POST request.
        # Test view register
        response = register(self.register_request, self.local_username, invalid_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_password_returns_bad_response(self):
        # Test view register
        response = register(self.register_request, self.local_username, self.local_email, invalid_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_remember_me_returns_bad_response(self):
        # Test view register
        response = register(self.register_request, self.local_username, self.local_email, self.local_password,
                            invalid_bool, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_ip_returns_bad_response(self):
        # Test view register
        response = register(self.register_request, self.local_username, self.local_email, self.local_password, false,
                            invalid_ip)
        self.assertEqual(response.status_code, FAIL)

    def test_user_already_exists_returns_bad_response(self):
        # Test view register
        response = register(self.register_request, self.local_username, self.local_email, self.local_password, false,
                            ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Test view register again
        response = register(self.register_request, self.local_username, self.local_email, self.local_password, false,
                            ip)
        self.assertEqual(response.status_code, FAIL)

    def test_user_doesnt_exist_with_remember_me_returns_good_response(self):
        # Test view register
        response = register(self.register_request, self.local_username, self.local_email, self.local_password, true, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_doesnt_exist_without_remember_me_returns_good_response(self):
        # Test view register
        response = register(self.register_request, self.local_username, self.local_email, self.local_password, false,
                            ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)
