from django.contrib.sessions.middleware import SessionMiddleware

from ..views import delete_user, get_user_with_username
from .test_constants import false, FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase

invalid_session_management_token = '?'

class LogoutUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user(false)

        # Create an instance of a DELETE request.
        self.delete_user_request = self.make_delete_request_obj('delete_user', self.local_username)
        
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
