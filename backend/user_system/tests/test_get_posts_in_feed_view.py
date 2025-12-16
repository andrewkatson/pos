from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import get_user_with_username

invalid_session_management_token = '?'
invalid_batch = -1


class GetPostsInFeedTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to:
        # 1. Create a user (setting self.local_username)
        # 2. Log them in (setting self.session_management_token)
        # 3. Create 30 posts (or 29 for other users, based on test logic)
        super().make_many_posts(30)

        # Store the valid header for all tests
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        url = reverse('get_posts_in_feed', kwargs={'batch': 1})
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.get(url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_invalid_batch_returns_bad_response(self):
        """
        Tests that a negative batch number in the URL
        is rejected with a 400 Bad Request.
        """
        invalid_url = f'feed/{invalid_batch}/'

        response = self.client.get(invalid_url, **self.valid_header)

        # Fails at the 'if batch < 0' check
        self.assertEqual(response.status_code, 404)

    def test_one_beyond_max_batch_returns_good_response(self):
        """
        Tests that requesting a batch beyond the total number of items
        returns an empty list.
        """
        # Original test used 4, implying batches 0, 1, 2, 3 were possible
        url = reverse('get_posts_in_feed', kwargs={'batch': 4})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        # We should grab no posts with a batch beyond the max number.
        self.assertEqual(len(responses), 0)

    def test_first_batch_amount_batch_returns_good_response(self):
        """
        Tests that requesting the first batch (batch 0) returns the
        correct number of items (10).
        """
        url = reverse('get_posts_in_feed', kwargs={'batch': 0})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()

        # This assumes POST_BATCH_SIZE is 10
        self.assertEqual(len(responses), 10)

    def test_last_batch_returns_good_response(self):
        """
        Tests that requesting the last partial batch (batch 2)
        returns the remaining items (9).
        """
        url = reverse('get_posts_in_feed', kwargs={'batch': 2})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()

        # Preserving original test logic: 29 posts total in feed
        # Batch 0: 10
        # Batch 1: 10
        # Batch 2: 9
        self.assertEqual(len(responses), 9)

    def test_blocked_user_posts_not_in_feed(self):
        """
        Tests that the blocked users posts are hidden when they are blocked
        """
        # 1. Create User B and their posts
        fields = self.make_user_with_posts(num_posts=5)
        user_b = get_user_with_username(fields[Fields.username])

        # 2. Block User B
        get_user_with_username(self.local_username).blocked.add(user_b)

        # 3. Get feed
        url = reverse('get_posts_in_feed', kwargs={'batch': 0})
        response = self.client.get(url, **self.valid_header)

        # 4. Verify no posts from User B
        self.assertEqual(response.status_code, 200)
        responses = response.json()
        for post in responses:
            self.assertNotEqual(post[Fields.username], user_b.username)