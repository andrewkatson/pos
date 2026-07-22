import os

from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_TEXT, NEGATIVE_TEXT
from ..constants import Fields, MAX_COMMENT_LENGTH
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

    def test_comment_over_max_length_returns_bad_response(self):
        """
        A comment longer than MAX_COMMENT_LENGTH characters must be rejected with a
        message that states the limit.
        """
        # Positive text (no "negative" substring) so only the length check can fail it.
        too_long_data = {'comment_text': 'a' * (MAX_COMMENT_LENGTH + 1)}

        response = self.client.post(
            self.url,
            data=too_long_data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(f"maximum length of {MAX_COMMENT_LENGTH}", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_unicode_comment_at_max_length_returns_good_response(self):
        """
        A non-ASCII comment at exactly MAX_COMMENT_LENGTH code points must be accepted,
        confirming the limit is unicode aware rather than byte/ASCII based.
        """
        # 'é' is multi-byte in UTF-8 but a single unicode code point; len() counts code points.
        body = 'é' * MAX_COMMENT_LENGTH
        response = self.client.post(
            self.url,
            data={'comment_text': body},
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        user = get_user_with_username(self.local_username)
        comment = user.post_set.first().commentthread_set.first().comment_set.first()
        self.assertEqual(comment.body, body)

    # The reason this test isn't "negative" in title is because the classifier looks for "negative" in tests
    # in the username and will fail this test
    def test_not_positive_text_returns_bad_response(self):
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
    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_non_string_comment_text_returns_bad_response(self):
        """
        A truthy non-string comment_text must be rejected with a 400 rather than raising
        a TypeError from the semicolon/length checks and surfacing as a 500.
        """
        for comment_text in (123, 1.5, True, ['a'], {'a': 'b'}):
            with self.subTest(comment_text=comment_text):
                data = self.valid_data.copy()
                data['comment_text'] = comment_text

                response = self.client.post(
                    self.url,
                    data=data,
                    content_type='application/json',
                    **self.valid_header
                )

                self.assertEqual(response.status_code, 400)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_non_string_reply_comment_text_returns_bad_response(self):
        """
        reply_to_comment_thread shares the same validation shape as comment_on_post,
        so a truthy non-string comment_text must also yield a 400 rather than a 500.
        """
        thread = self._comment_on_post(self.session_management_token, self.post_identifier)
        url = reverse('reply_to_comment_thread', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(thread[Fields.comment_thread_identifier]),
        })

        for comment_text in (123, 1.5, True, ['a'], {'a': 'b'}):
            with self.subTest(comment_text=comment_text):
                response = self.client.post(
                    url,
                    data={'comment_text': comment_text},
                    content_type='application/json',
                    **self.valid_header
                )

                self.assertEqual(response.status_code, 400)
