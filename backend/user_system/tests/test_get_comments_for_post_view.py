from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase

invalid_post_identifier = '?'
invalid_batch = -1
invalid_session_management_token = '?'


class GetCommentsForPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to:
        # 1. Create a user and log them in (setting self.session_management_token)
        # 2. Create a post (setting self.post_identifier)
        # 3. Create 30 comment threads on that post for batch testing.
        super().make_many_comments(30)

        # Store the valid header for all tests
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        url = reverse('get_comments_for_post', kwargs={
            'post_identifier': str(self.post_identifier),
            'batch': 0
        })
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.get(url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_token_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL
        is rejected with a 400 Bad Request.
        """

        invalid_url = f"posts/{invalid_post_identifier}/comments/{1}/"

        response = self.client.get(invalid_url, **self.valid_header)

        # Fails at the 'is_valid_pattern' check
        self.assertEqual(response.status_code, 404)

    def test_invalid_batch_returns_bad_response(self):
        """
        Tests that a negative batch number in the URL
        is rejected with a 400 Bad Request.
        """

        invalid_url = f"posts/{self.post_identifier}/comments/{invalid_batch}/"

        response = self.client.get(invalid_url, **self.valid_header)

        # Fails at the 'if batch < 0' check
        self.assertEqual(response.status_code, 404)

    def test_one_beyond_max_batch_returns_good_response(self):
        """
        Tests that requesting a batch beyond the total number of items
        returns an empty list. (30 items / 10 per batch = batches 0, 1, 2)
        """
        # Batch 3 should be the first empty one. The original test used 4.
        url = reverse('get_comments_for_post', kwargs={
            'post_identifier': str(self.post_identifier),
            'batch': 4
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        self.assertEqual(len(responses), 0)

    def test_first_batch_amount_batch_returns_good_response(self):
        """
        Tests that requesting the first batch (batch 0) returns the
        correct number of items (assuming 10 per batch).
        """
        url = reverse('get_comments_for_post', kwargs={
            'post_identifier': str(self.post_identifier),
            'batch': 0
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        # Assumes COMMENT_THREAD_BATCH_SIZE is 10
        self.assertEqual(len(responses), 10)

    def test_last_batch_returns_good_response(self):
        """
        Tests that requesting the last full batch (batch 2) returns
        the correct number of items (assuming 10 per batch).
        """
        url = reverse('get_comments_for_post', kwargs={
            'post_identifier': str(self.post_identifier),
            'batch': 2
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        # Assumes COMMENT_THREAD_BATCH_SIZE is 10
        self.assertEqual(len(responses), 10)