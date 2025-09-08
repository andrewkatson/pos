import uuid

from django.test import RequestFactory, TestCase
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from ..views import register, login_user_with_remember_me
from ..constants import Fields
from .test_constants import username, email, password, ip, invalid_ip, true, false, FAIL, SUCCESS
from .test_utils import get_response_fields
from ..utils import generate_login_cookie_token

invalid_session_management_token = '?'
invalid_series_identifier = '?'
invalid_login_cookie_token = '?'


class LoginUserRememberMETests(TestCase):

    def setUp(self):
        # Every test needs access to the request factory.
        self.factory = RequestFactory()
        prefix = self._testMethodName
        self.local_username = f'{username}_{prefix}'
        self.local_password = f'{password}_{prefix}'
        self.local_email = f'{email}_{prefix}@email.com'
        self.user = AnonymousUser()

        # For this one we want to register a user with the info needed 
        # to login later. All tests start with remember_me turned on here on purpose.
        request = self.factory.post("/user_system/register")
        response = register(request, self.local_username, self.local_email, self.local_password, true, ip)
        self.assertEqual(response.status_code, SUCCESS)

        fields = get_response_fields(response)

        # Store the info needed to call remember me later
        self.session_management_token = fields[Fields.session_management_token]
        self.series_identifier = fields[Fields.series_identifier]
        self.login_cookie_token = fields[Fields.login_cookie_token]

        # Create an instance of a POST request.
        self.request = self.factory.post("/user_system/login_user_with_remember_me_with_remember_me")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.request.user = self.user

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.request)
        self.request.session.save()

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.request, invalid_session_management_token, self.series_identifier,
                                               self.login_cookie_token, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_series_identifier_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.request, self.session_management_token, invalid_series_identifier,
                                               self.login_cookie_token,
                                               ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_login_cookie_token_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.request, self.session_management_token, self.series_identifier,
                                               invalid_login_cookie_token, ip)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_ip_returns_bad_response(self):
        # Test view login_user_with_remember_me
        response = login_user_with_remember_me(self.request, self.session_management_token, self.series_identifier,
                                               self.login_cookie_token, invalid_ip)
        self.assertEqual(response.status_code, FAIL)

    def test_matching_login_cookie_token_returns_good_response_with_new_login_cookie_token(self):
        response = login_user_with_remember_me(self.request, self.session_management_token, self.series_identifier,
                                               self.login_cookie_token, ip)
        self.assertEqual(response.status_code, SUCCESS)

        fields = get_response_fields(response)
        self.assertNotEqual(fields[Fields.login_cookie_token], self.login_cookie_token)

    def test_not_matching_login_cookie_token_returns_bad_response(self):
        # Test view login_user_with_remember_me with the valid but non-existent series_identifier.
        not_matching_login_cookie_token = generate_login_cookie_token()
        response = login_user_with_remember_me(self.request, self.session_management_token, self.series_identifier,
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
        response = login_user_with_remember_me(self.request, self.session_management_token,
                                               non_existent_series_identifier,
                                               self.login_cookie_token, ip)
        self.assertEqual(response.status_code, FAIL)
