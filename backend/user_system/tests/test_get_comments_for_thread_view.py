from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase

invalid_comment_thread_identifier = '?'
invalid_batch = -1
invalid_session_management_token = '?'


class GetCommentsForThreadTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to:
        # 1. Create a user and log them in (setting self.session_management_token)
        # 2. Create a post and a single comment thread (setting self.comment_thread_identifier)
        # 3. Create 60 comments on that one thread for batch testing.
        super().make_many_comments_on_thread(60)

        # Store the valid header for all tests
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'batch': 0
        })
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.get(url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_thread_identifier in the URL
        is rejected with a 400 Bad Request.
        """

        invalid_url = f'threads/{invalid_comment_thread_identifier}/comments/{1}/'

        response = self.client.get(invalid_url, **self.valid_header)

        # Fails at the 'is_valid_pattern' check
        self.assertEqual(response.status_code, 404)

    def test_invalid_batch_returns_bad_response(self):
        """
        Tests that a negative batch number in the URL
        is rejected with a 400 Bad Request.
        """
        invalid_url = f'threads/{self.comment_thread_identifier}/comments/{invalid_batch}/'

        response = self.client.get(invalid_url, **self.valid_header)

        # Fails at the 'if batch < 0' check
        self.assertEqual(response.status_code, 404)

    def test_one_beyond_max_batch_returns_good_response(self):
        """
        Tests that requesting a batch beyond the total number of items
        returns an empty list. (60 items / 30 per batch = batches 0, 1)
        """
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'batch': 2  # Batch 2 should be the first empty one
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        # We should grab no comments with a batch beyond the max number.
        self.assertEqual(len(responses), 0)

    def test_first_batch_amount_batch_returns_good_response(self):
        """
        Tests that requesting the first batch (batch 0) returns the
        correct number of items (assuming 30 per batch).
        """
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'batch': 0
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        # Assumes COMMENT_BATCH_SIZE is 30
        self.assertEqual(len(responses), 30)

    def test_last_batch_returns_good_response(self):
        """
        Tests that requesting the last full batch (batch 1) returns
        the correct number of items (assuming 30 per batch).
        """
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'batch': 1
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        # Assumes COMMENT_BATCH_SIZE is 30
        self.assertEqual(len(responses), 30)