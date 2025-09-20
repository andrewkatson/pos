from ..views import logout_user, delete_user
from .test_constants import  false, FAIL, SUCCESS, NOT_FOUND_REDIRECT
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
        self.logout_user_request.user = self.user

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view logout_user
        response = logout_user(self.logout_user_request, invalid_session_management_token)
        self.assertEqual(response.status_code, FAIL)

    def test_logged_in_user_logs_out(self):
        # Test view logout_user
        response = logout_user(self.logout_user_request, self.session_management_token)
        self.assertEqual(response.status_code, SUCCESS)

        # Test some endpoint that needs login to get a redirect
        response = delete_user(self.login_user_request, self.session_management_token)
        self.assertEqual(response.status_code, NOT_FOUND_REDIRECT)