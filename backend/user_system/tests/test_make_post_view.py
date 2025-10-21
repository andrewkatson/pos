from .test_constants import false, FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_fields
from ..classifiers import image_classifier_fake, text_classifier_fake
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT, NEGATIVE_TEXT, NEGATIVE_IMAGE_URL
from ..constants import Fields
from ..views import make_post, get_user_with_username

invalid_session_management_token = '?'
invalid_image_url = '?'
invalid_caption = 'DROP TABLE x;'


class MakePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user(false)

        # Create an instance of a POST request.
        self.make_post_request = self.make_post_request_obj('make_post', self.local_username)

        # Store some basic info used in these tests
        self.image_url = f'{self.prefix}.png'
        self.caption = f'This is my caption :P'

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

    def test_negative_image_returns_bad_response(self):
        # Test view make_post
        response = make_post(self.make_post_request, self.session_management_token, NEGATIVE_IMAGE_URL, POSITIVE_TEXT)
        self.assertEqual(response.status_code, FAIL)

    def test_negative_caption_returns_bad_response(self):
        # Test view make_post
        response = make_post(self.make_post_request, self.session_management_token, self.image_url, NEGATIVE_TEXT)
        self.assertEqual(response.status_code, FAIL)

    def test_make_post_returns_good_response_and_adds_post_to_user(self):
        # Test view make_post
        response = make_post(self.make_post_request, self.session_management_token, POSITIVE_IMAGE_URL, POSITIVE_TEXT,
                             image_classifier_fake, text_classifier_fake)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        posts = user.post_set.all()
        self.assertEqual(len(posts), 1)

        fields = get_response_fields(response)
        self.assertTrue(fields[Fields.post_identifier])
