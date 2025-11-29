import os

from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_TEXT, NEGATIVE_TEXT
from ..constants import Fields
from ..views import get_user_with_username

invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_comment_text = 'DROP TABLE;'

class CommentOnPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper should set self.local_username and self.session_management_token
        self.post, self.post_identifier = super().make_post_and_login_user()

        # --- Reusable test components ---

        # 1. The URL we are testing (e.g., /posts/<uuid>/comments/)
        self.url = reverse('comment_on_post', kwargs={'post_identifier': self.post_identifier})

        # 2. Valid JSON data to send
        self.valid_data = {'comment_text': POSITIVE_TEXT}

        # 3. Valid authorization header
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        response = self.client.post(
            self.url,
            data=self.valid_data,
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {invalid_session_management_token}'  # Invalid header
        )
        # @api_login_required should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL
        is rejected with a 400 Bad Request.
        """
        invalid_data = {'post_identifier': invalid_post_identifier}

        response = self.client.post(
            self.url,
            data=invalid_data,
            content_type='application/json',
            **self.valid_header  # Valid header
        )
        # View's pattern matching should return 400 Bad Request
        self.assertEqual(response.status_code, 400)

    def test_invalid_text_returns_bad_response(self):
        """
        Tests that malformed comment_text (failing the regex pattern)
        is rejected with a 400 Bad Request.
        """
        invalid_data = {'comment_text': invalid_comment_text}

        response = self.client.post(
            self.url,
            data=invalid_data,
            content_type='application/json',
            **self.valid_header
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_text_returns_bad_response(self):
        """
        Tests that text classified as negative by the (fake) classifier
        is rejected with a 400 Bad Request.
        """
        negative_data = {'comment_text': NEGATIVE_TEXT}

        response = self.client.post(
            self.url,
            data=negative_data,
            content_type='application/json',
            **self.valid_header
        )
        # View logic should return 400 Bad Request
        self.assertEqual(response.status_code, 400)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_comment_on_post_returns_good_response_and_adds_thread_with_comment(self):
        """
        Tests that a valid request successfully creates a new comment
        and returns a 201 Created.
        """
        response = self.client.post(
            self.url,
            data=self.valid_data,
            content_type='application/json',
            **self.valid_header
        )
        # Successful creation should return 201 Created
        self.assertEqual(response.status_code, 201)

        # --- Verify database state ---
        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        self.assertEqual(post.commentthread_set.count(), 1)  # Check thread was created

        comment_thread = post.commentthread_set.first()
        self.assertEqual(comment_thread.comment_set.count(), 1)  # Check comment was added

        comment = comment_thread.comment_set.first()
        self.assertEqual(comment.author, user)
        self.assertEqual(comment.body, POSITIVE_TEXT)

        # --- Verify response content ---
        fields = response.json()
        self.assertIn(Fields.comment_thread_identifier, fields)
        self.assertIn(Fields.comment_identifier, fields)

        # Check that the returned IDs match the ones created in the DB
        self.assertEqual(fields[Fields.comment_thread_identifier], str(comment_thread.comment_thread_identifier))
        self.assertEqual(fields[Fields.comment_identifier], str(comment.comment_identifier))