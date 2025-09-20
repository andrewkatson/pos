from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client

from ..views import logout_user, get_user_with_username
from .test_constants import  false, FAIL, SUCCESS, FORBIDDEN
from .test_parent_case import PositiveOnlySocialTestCase

invalid_session_management_token = '?'

class LogoutUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user(false)

        # Create an instance of a POST request.
        self.logout_user_request = self.factory.post("/user_system/logout_user")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.logout_user_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.logout_user_request)
        self.logout_user_request.session.save()

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view logout_user
        response = logout_user(self.logout_user_request, invalid_session_management_token)
        self.assertEqual(response.status_code, FAIL)

    def test_logged_in_user_logs_out(self):
        # Test view logout_user
        response = logout_user(self.logout_user_request, self.session_management_token)
        self.assertEqual(response.status_code, SUCCESS)

        client = Client()
        response = client.post('/user_system/delete_user')
        self.assertEqual(response.status_code, FORBIDDEN)