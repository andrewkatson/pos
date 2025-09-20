from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT
from ..views import register, login_user, make_post, delete_post, get_user_with_username
from ..constants import Fields
from .test_constants import username, email, password, ip, false, FAIL, SUCCESS
from .test_utils import get_response_fields
from ..classifiers import image_classifier_fake, text_classifier_fake

invalid_session_management_token = '?'
invalid_post_identifier = '?'

class DeletePostTests(PositiveOnlySocialTestCase):

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

        fields = get_response_fields(response)

        # Store the info needed to call remember me later
        self.session_management_token = fields[Fields.session_management_token]

        # Store some basic info used in these tests
        self.image_url = f'{prefix}.png'
        self.caption = f'This is my caption :P'

        # Create an instance of a POST request.
        self.request = self.factory.post("/user_system/login_user")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.request.user = self.user

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.request)
        self.request.session.save()

        # Need to log the user in
        response = login_user(self.request, self.local_username, self.local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Need to make a post
        response = make_post(self.request, self.session_management_token, POSITIVE_IMAGE_URL, POSITIVE_TEXT, image_classifier_fake, text_classifier_fake)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        self.post = user.post_set.first()
        self.post_identifier = self.post.post_identifier

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view delete_post
        response = delete_post(self.request, invalid_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view delete_post
        response = delete_post(self.request, self.session_management_token, invalid_post_identifier)
        self.assertEqual(response.status_code, FAIL)

    def test_delete_post_returns_good_response_and_removes_post_from_user(self):
        # Test view make_post
        response = delete_post(self.request, self.session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        posts = user.post_set.all()
        self.assertEqual(len(posts), 0)