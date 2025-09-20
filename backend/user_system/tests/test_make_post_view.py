from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT
from ..views import make_post, get_user_with_username
from .test_constants import false, FAIL, SUCCESS
from ..classifiers import image_classifier_fake, text_classifier_fake

invalid_session_management_token = '?'
invalid_image_url = '?'
invalid_caption = 'DROP TABLE x;'

class MakePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user(false)

        # Create an instance of a POST request.
        self.make_post_request = self.factory.post("/user_system/make_post")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.make_post_request.user = self.user

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view make_post
        response = make_post(self.make_post_request, invalid_session_management_token, self.image_url, self.caption)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_image_url_returns_bad_response(self):
        # Test view make_post
        response = make_post(self.make_post_request, self.session_management_token, invalid_image_url, self.caption)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_caption_returns_bad_response(self):
        # Test view make_post
        response = make_post(self.make_post_request, self.session_management_token, self.image_url, invalid_caption)
        self.assertEqual(response.status_code, FAIL)

    def test_make_post_returns_good_response_and_adds_post_to_user(self):
        # Test view make_post
        response = make_post(self.make_post_request, self.session_management_token, POSITIVE_IMAGE_URL, POSITIVE_TEXT, image_classifier_fake, text_classifier_fake)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        posts = user.post_set.all()
        self.assertEqual(len(posts), 1)