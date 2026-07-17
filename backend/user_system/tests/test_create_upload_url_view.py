import os
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, Patterns
from ..input_validator import is_valid_pattern
from ..s3 import image_url_to_key
from ..views import get_user_with_username

# --- Constants ---
invalid_session_management_token = '?'

# Presigning is purely local (SigV4 over the request), so fake credentials are
# enough for the view to produce a URL — no AWS call is made.
fake_aws_env = {
    "TESTING": "True",
    "AWS_ACCESS_KEY_ID": "AKIAFAKEFAKEFAKEFAKE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret-key-for-signing-only",
    "AWS_REGION": "us-east-2",
}


class CreateUploadUrlTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('create_upload_url')

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    @patch.dict(os.environ, fake_aws_env, clear=True)
    def test_returns_presigned_url_scoped_to_user(self):
        """
        The upload URL must be a presigned PUT for a key under the
        authenticated user's `{user_id}/` prefix — key ownership is chosen by
        the backend, never the client.
        """
        response = self.client.post(self.url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        upload_url = data[Fields.upload_url]
        image_url = data[Fields.image_url]

        # The key is scoped to this user and is a JPEG.
        key = image_url_to_key(image_url)
        self.assertTrue(key.startswith(f"{self.user.id}/"))
        self.assertTrue(key.endswith(".jpeg"))

        # The upload URL is the same object with a SigV4 signature attached.
        parsed = urlparse(upload_url)
        query = parse_qs(parsed.query)
        self.assertIn('X-Amz-Signature', query)
        self.assertEqual(parsed._replace(query='', fragment='').geturl(), image_url)

    @patch.dict(os.environ, fake_aws_env, clear=True)
    def test_image_url_is_accepted_by_make_post_validation(self):
        """
        The returned image_url must pass the same validation make_post applies
        (pattern + user-prefix check), so the client can hand it straight back.
        """
        response = self.client.post(self.url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        image_url = response.json()[Fields.image_url]

        self.assertTrue(is_valid_pattern(image_url, Patterns.image_url))
        self.assertTrue(image_url_to_key(image_url).startswith(f"{self.user.id}/"))

    @patch.dict(os.environ, fake_aws_env, clear=True)
    def test_each_request_returns_a_fresh_key(self):
        """
        Every request must mint a new random key so an upload can never
        clobber a previously issued object.
        """
        first = self.client.post(self.url, **self.valid_header).json()
        second = self.client.post(self.url, **self.valid_header).json()

        self.assertNotEqual(first[Fields.image_url], second[Fields.image_url])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_missing_aws_credentials_returns_service_unavailable(self):
        """
        Without backend AWS credentials no presigned URL can be produced; the
        endpoint must fail loudly rather than return a broken URL.
        """
        response = self.client.post(self.url, **self.valid_header)

        self.assertEqual(response.status_code, 503)
