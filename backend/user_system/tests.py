from django.test import RequestFactory, TestCase

from .views import register, login_user, login_user_with_remember_me, request_reset, reset_password, verify_reset, \
    logout_user, delete_user
from .models import PositiveOnlySocialUser

username = 'andrew'
email = 'andrew@email.com'
password = 'some password'


class RegisterTests(TestCase):
    def setUp(self):
        # Every test needs access to the request factory.
        self.factory = RequestFactory()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username=username, email=email, password=password
        )

    def test_invalid_username_returns_bad_response(self):
        # Create an instance of a POST request.
        request = self.factory.post("/users_system/register")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        request.user = self.user

        # Test my_view() as if it were deployed at /customer/details
        response = register(request)
        self.assertEqual(response.status_code, 200)
