from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware

from ..views import register, login_user, logout_user, delete_user
from ..constants import Fields
from .test_constants import username, email, password, ip, false, FAIL, SUCCESS, NOT_FOUND_REDIRECT
from .test_utils import get_response_fields
from .test_parent_case import PositiveOnlySocialTestCase

invalid_session_management_token = '?'

class LogoutUserTests(PositiveOnlySocialTestCase):

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
        # to login later. All tests start with remember_me turned on on purpose.
        request = self.factory.post("/user_system/register")
        response = register(request, self.local_username, self.local_email, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        fields = get_response_fields(response)

        # Store the info needed to call remember me later
        self.session_management_token = fields[Fields.session_management_token]

        # Create an instance of a POST request.
        self.request = self.factory.post("/user_system/login_user")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.request.user = self.user

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.request)
        self.request.session.save()

        # Need to log the user in
        response = login_user(self.request, self.local_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view logout_user
        response = logout_user(self.request, invalid_session_management_token)
        self.assertEqual(response.status_code, FAIL)

    def test_logged_in_user_logs_out(self):
        # Test view logout_user
        response = logout_user(self.request, self.session_management_token)
        self.assertEqual(response.status_code, SUCCESS)

        # Test some endpoint that needs login to get a redirect
        response = delete_user(self.request, self.session_management_token)
        self.assertEqual(response.status_code, NOT_FOUND_REDIRECT)