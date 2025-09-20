from django.contrib.sessions.middleware import SessionMiddleware

from ..views import delete_user, get_user_with_username
from .test_constants import false, FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase

invalid_session_management_token = '?'

class LogoutUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user(false)

        # Create an instance of a POST request.
        self.delete_user_request = self.factory.post("/user_system/delete_user")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.delete_user_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.delete_user_request)
        self.delete_user_request.session.save()
        
    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view delete_user
        response = delete_user(self.delete_user_request, invalid_session_management_token)
        self.assertEqual(response.status_code, FAIL)

    def test_logged_in_user_is_deleted(self):
        # Test view delete_user
        response = delete_user(self.delete_user_request, self.session_management_token)
        self.assertEqual(response.status_code, SUCCESS)

        # Test that the user is gone
        self.assertIsNone(get_user_with_username(self.local_username))
