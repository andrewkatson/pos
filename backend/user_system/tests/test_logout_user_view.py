from django.test import Client

from .test_constants import false, FAIL, SUCCESS, FORBIDDEN
from .test_parent_case import PositiveOnlySocialTestCase
from ..views import logout_user

invalid_session_management_token = '?'


class LogoutUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user(false)

        # Create an instance of a POST request.
        self.logout_user_request = self.make_post_request_obj('logout_user', self.local_username)

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
