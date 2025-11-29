from unittest.mock import patch
import os
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT, NEGATIVE_TEXT, NEGATIVE_IMAGE_URL
from ..constants import Fields
from ..views import get_user_with_username

# --- Constants ---
invalid_session_management_token = '?'
invalid_image_url = '?'
invalid_caption = 'DROP TABLE x;'

class MakePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to create/login a user and set
        # self.local_username and self.session_management_token
        self.register_user_and_setup_local_fields()

        # Store the user object, valid header, and URL for all tests
        self.user = get_user_with_username(self.local_username)
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('make_post')

        # A valid data payload for the "happy path"
        self.valid_data = {
            'image_url': POSITIVE_IMAGE_URL,
            'caption': POSITIVE_TEXT
        }

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(
            self.url,
            data=self.valid_data,
            content_type='application/json',
            **invalid_header
        )

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_invalid_image_url_returns_bad_response(self):
        """
        Tests that a malformed image_url is rejected.
        """
        data = self.valid_data.copy()
        data['image_url'] = invalid_image_url

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_caption_returns_bad_response(self):
        """
        Tests that a malformed caption is rejected.
        """
        data = self.valid_data.copy()
        data['caption'] = invalid_caption

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_negative_image_returns_bad_response(self):
        """
        Tests that a negative image (as per the fake classifier) is rejected.
        """
        data = {'image_url': NEGATIVE_IMAGE_URL, 'caption': POSITIVE_TEXT}

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Image is not positive", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_negative_caption_returns_bad_response(self):
        """
        Tests that a negative caption (as per the fake classifier) is rejected.
        """
        data = {'image_url': POSITIVE_IMAGE_URL, 'caption': NEGATIVE_TEXT}

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Text is not positive", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_make_post_returns_good_response_and_adds_post_to_user(self):
        """
        Tests the "happy path" for creating a post.
        """
        # 1. Check DB before
        self.assertEqual(self.user.post_set.count(), 0)

        # 2. Make the request
        response = self.client.post(
            self.url,
            data=self.valid_data,
            content_type='application/json',
            **self.valid_header
        )

        # 3. Check response
        self.assertEqual(response.status_code, 201)  # 201 Created
        fields = response.json()
        self.assertIn(Fields.post_identifier, fields)

        # 4. Check DB after
        self.user.refresh_from_db()
        self.assertEqual(self.user.post_set.count(), 1)

        # 5. Verify the created post
        post = self.user.post_set.first()
        self.assertEqual(fields[Fields.post_identifier], str(post.post_identifier))
        self.assertEqual(post.caption, POSITIVE_TEXT)
        self.assertEqual(post.image_url, POSITIVE_IMAGE_URL)