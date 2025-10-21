# This test is special because it exercises the request_reset, verify_reset, and reset_password views at once.
from .test_constants import username, password, false, FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from ..views import request_reset, verify_reset, reset_password, get_user_with_username

other_username = f'other_{username}'


class ResetPasswordTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user_setup(false)

    def test_user_does_not_exist_request_reset_returns_bad_response(self):
        request = self.factory.post("/user_system/request_reset")
        response = request_reset(request, other_username)
        self.assertEqual(response.status_code, FAIL)

    def test_user_does_not_exist_verify_reset_returns_bad_response(self):
        request = self.factory.post("/user_system/verify_reset")
        response = verify_reset(request, other_username, -1)
        self.assertEqual(response.status_code, FAIL)

    def test_user_does_not_exist_reset_password_returns_bad_response(self):
        new_password = f'new_{password}'
        request = self.factory.post("/user_system/reset_password")
        response = reset_password(request, other_username, self.local_email, new_password)
        self.assertEqual(response.status_code, FAIL)

    def test_reset_id_does_not_match_returns_bad_response(self):
        request = self.factory.post("/user_system/request_reset")
        response = request_reset(request, self.local_username)
        self.assertEqual(response.status_code, SUCCESS)

        # Get the reset id so we can send it over
        user = get_user_with_username(self.local_username)
        reset_id = user.reset_id

        request = self.factory.post("/user_system/verify_reset")
        response = verify_reset(request, self.local_username, reset_id + 1)
        self.assertEqual(response.status_code, FAIL)

    def test_password_reset_changes_user_password(self):
        request = self.factory.post("/user_system/request_reset")
        response = request_reset(request, self.local_username)
        self.assertEqual(response.status_code, SUCCESS)

        # Get the reset id so we can send it over
        user = get_user_with_username(self.local_username)
        reset_id = user.reset_id

        request = self.factory.post("/user_system/verify_reset")
        response = verify_reset(request, self.local_username, reset_id)
        self.assertEqual(response.status_code, SUCCESS)

        new_password = f'new_{password}'
        request = self.factory.post("/user_system/reset_password")
        response = reset_password(request, self.local_username, self.local_email, new_password)
        self.assertEqual(response.status_code, SUCCESS)
