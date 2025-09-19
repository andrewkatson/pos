from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware

from ..views import register, login_user
from ..constants import Fields, Patterns
from ..input_validator import is_valid_pattern
from .test_constants import username, email, password, ip, invalid_username, invalid_password, \
    invalid_email, invalid_ip, invalid_bool, false, true, FAIL, SUCCESS
from .test_utils import get_response_fields
from .test_parent_case import PositiveOnlySocialTestCase

class LoginUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        # Every test needs access to the request factory.
        self.factory = RequestFactory()
        prefix = self._testMethodName
        self.local_username = f'{username}_{prefix}'
        self.local_password = f'{password}_{prefix}'
        self.local_email = f'{email}_{prefix}@email.com'
        self.user = AnonymousUser()

        # For this one we want to register a user with the info needed 
        # to login later. All tests start with remember_me turned off on purpose.
        request = self.factory.post("/user_system/register")
        response = register(request, self.local_username, self.local_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Create an instance of a POST request.
        self.request = self.factory.post("/user_system/login_user")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.request.user = self.user

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.request)
        self.request.session.save()

    def test_invalid_username_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.request, invalid_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_email_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.request, invalid_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_password_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.request, self.local_username, invalid_password, false, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_remember_me_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.request, self.local_username, self.local_password, invalid_bool, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_ip_returns_bad_response(self):
        # Test view login_user
        response = login_user(self.request, self.local_username, self.local_password, false, invalid_ip)
        self.assertEqual(response.status_code, FAIL)

    def test_user_does_exist_with_remember_me_and_username_returns_good_response(self):
        # Test view login_user
        response = login_user(self.request, self.local_username, self.local_password, true, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_does_exist_without_remember_me_and_with_username_returns_good_response(self):
        # Test view login_user
        response = login_user(self.request, self.local_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)

    def test_user_does_exist_with_remember_me_and_email_returns_good_response(self):
        # Test view login_user
        response = login_user(self.request, self.local_email, self.local_password, true, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.series_identifier], Patterns.uuid4))
        self.assertTrue(is_valid_pattern(fields[Fields.login_cookie_token], Patterns.alphanumeric))
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))

    def test_user_does_exist_without_remember_me_and_with_email_returns_good_response(self):
        # Test view login_user
        response = login_user(self.request, self.local_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Check that there are login cookie, series identifier, and management token added
        fields = get_response_fields(response)

        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertNotIn(Fields.login_cookie_token, fields)
        self.assertNotIn(Fields.series_identifier, fields)
