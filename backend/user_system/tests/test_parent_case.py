from django.test import TestCase
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware

from .test_utils import get_response_fields
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT
from ..constants import Fields
from ..views import register, login_user, make_post, get_user_with_username
from .test_constants import username, email, password, SUCCESS, ip, LOGIN_USER, false, UserFields
from ..classifiers import image_classifier_fake, text_classifier_fake


class PositiveOnlySocialTestCase(TestCase):
    def setUp(self):
        super().setUp()

        # Every test needs access to the request factory.
        self.factory = RequestFactory()
        self.prefix = self._testMethodName
        self.user = AnonymousUser()

        # Create an instance of a POST request.
        self.register_request = self.factory.post("/user_system/register")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.register_request.user = self.user

        self.users = {
            UserFields.USERNAME: [],
            UserFields.EMAIL: [],
            UserFields.PASSWORD: [],
            UserFields.SESSION_MANAGEMENT_TOKEN: [],
            UserFields.SERIES_IDENTIFIER: [],
            UserFields.LOGIN_COOKIE_TOKEN: [],
        }

    def tearDown(self):
        super().tearDown()

    def register_other_user(self, remember_me, num_user, user_dict):
        local_username = f'{num_user}_{username}_{self.prefix}'
        local_password = f'{num_user}_{password}_{self.prefix}'
        local_email = (f'{num_user}_{email}_{self.prefix}@email.com')

        # For this one we want to register a user with the info needed
        # to login later. All tests start with remember_me turned off on purpose.
        request = self.factory.post("/user_system/register")
        response = register(request, local_username, local_email, local_password, remember_me, ip)
        self.assertEqual(response.status_code, SUCCESS)

        fields = get_response_fields(response)

        # Store the info needed to call remember me later
        session_management_token = fields[Fields.session_management_token]
        if remember_me:
            series_identifier = fields[Fields.series_identifier]
            login_cookie_token = fields[Fields.login_cookie_token]

            series_identifiers = user_dict.get(UserFields.SERIES_IDENTIFIER, [])
            series_identifiers.append(series_identifier)

            login_cookies = user_dict.get(UserFields.LOGIN_COOKIE_TOKEN, [])
            login_cookies.append(login_cookie_token)

        usernames = user_dict.get(UserFields.USERNAME, [])
        usernames.append(local_username)

        emails = user_dict.get(UserFields.EMAIL, [])
        emails.append(local_email)

        passwords = user_dict.get(UserFields.PASSWORD, [])
        passwords.append(local_password)

        session_management_tokens = user_dict.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])
        session_management_tokens.append(session_management_token)

    def login_user_setup(self, remember_me, type_of_login=LOGIN_USER):
        self.register_other_user(remember_me, 0, self.users)

        # Create an instance of a POST request.
        self.login_user_request = self.factory.post(f"/user_system/{type_of_login}")

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.login_user_request)
        self.login_user_request.session.save()

    def login_user(self, remember_me):
        self.login_user_setup(remember_me)

        self.local_username = self.users.get(UserFields.USERNAME, [])[0]
        self.local_password = self.users.get(UserFields.PASSWORD, [])[0]
        self.local_email = self.users.get(UserFields.EMAIL, [])[0]
        self.session_management_token = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])[0]

        if remember_me:
            self.series_identifier = self.users.get(UserFields.SERIES_IDENTIFIER, [])[0]
            self.login_cookie_token = self.users.get(UserFields.LOGIN_COOKIE_TOKEN, [])[0]

        # Need to log the user in
        response = login_user(self.login_user_request, self.local_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

    def make_post(self):
        self.login_user(false)

        # Create an instance of a POST request.
        self.make_post_request = self.factory.post("/user_system/make_post")

        # Need to make a post
        response = make_post(self.make_post_request, self.session_management_token, POSITIVE_IMAGE_URL, POSITIVE_TEXT,
                             image_classifier_fake, text_classifier_fake)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        self.post = user.post_set.first()
        self.post_identifier = self.post.post_identifier

    def make_post_with_users(self, num=1):
        self.make_post()

        for i in range(num):
            self.register_other_user(false, i, self.users)

        # Store some basic info used in these tests
        self.image_url = f'{self.prefix}.png'
        self.caption = f'This is my caption :P'
