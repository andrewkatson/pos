from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from ..views import  delete_post, get_user_with_username
from .test_constants import FAIL, SUCCESS

invalid_session_management_token = '?'
invalid_post_identifier = '?'

class DeletePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        self.post, self.post_identifier = super().make_post_and_login_user()

        # Create an instance of a DELETE request.
        self.delete_post_request = self.make_delete_request_obj('delete_post', self.local_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view delete_post
        response = delete_post(self.delete_post_request, invalid_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view delete_post
        response = delete_post(self.delete_post_request, self.session_management_token, invalid_post_identifier)
        self.assertEqual(response.status_code, FAIL)

    def test_delete_post_returns_good_response_and_removes_post_from_user(self):
        # Test view make_post
        response = delete_post(self.delete_post_request, self.session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        posts = user.post_set.all()
        self.assertEqual(len(posts), 0)