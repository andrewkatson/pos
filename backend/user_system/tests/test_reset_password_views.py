# This test is special because it exercises the request_reset, verify_reset, and reset_password views at once.
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from ..views import register, request_reset, verify_reset, reset_password, get_user_with_username
from .test_constants import username, email, password, ip, false, FAIL, SUCCESS

other_username = f'other_{username}'

class ResetPasswordTests(PositiveOnlySocialTestCase):

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

        request = self.factory.post("/user_system/verify_reset")
        response = verify_reset(request, self.local_username, -1)
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
