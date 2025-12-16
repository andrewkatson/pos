from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import get_user_with_username  # Kept for assertion

invalid_session_management_token = '?'
invalid_batch = -1


class GetFollowedPostsTests(PositiveOnlySocialTestCase):

    def test_blocked_user_posts_not_in_followed_feed(self):
        # 1. Block User B (who we are already following from setUp)
        user_b = get_user_with_username(self.user_b_username)
        user_a = get_user_with_username(self.user_a_username)
        user_a.blocked.add(user_b)

        # 2. Get followed feed
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})
        response = self.client.get(url, **self.user_a_header)

        # 3. Verify empty (since we only follow User B and blocked them)
        self.assertEqual(response.status_code, 200)
        responses = response.json()
        self.assertEqual(len(responses), 0)


    def setUp(self):
        super().setUp()

        # 1. Create User B (the one with posts)
        fields = self.make_user_with_posts(num_posts=15)
        self.user_b_username = fields[Fields.username]
        self.user_b_token = fields[Fields.session_management_token]
        self.user_b_header = {'HTTP_AUTHORIZATION': f'Bearer {self.user_b_token}'}

        # 2. Create User A (the one who will follow)
        main_user_login_fields = self.make_user_with_prefix()
        self.user_a_token = main_user_login_fields[Fields.session_management_token]
        self.user_a_username = main_user_login_fields[Fields.username]
        self.user_a_header = {'HTTP_AUTHORIZATION': f'Bearer {self.user_a_token}'}

        # 3. Make User A follow User B using the test client
        follow_url = reverse('follow_user', kwargs={'username_to_follow': self.user_b_username})
        response = self.client.post(follow_url, **self.user_a_header)

        # We assume 200 OK for a successful follow
        self.assertEqual(response.status_code, 200)

        # 4. Verify the follow
        user = get_user_with_username(self.user_a_username)
        self.assertEqual(user.following.count(), 1)
        self.assertEqual(user.following.first().username, self.user_b_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.get(url, **invalid_header)

        # 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_invalid_batch_returns_bad_response(self):
        """
        Tests that a negative batch number is rejected.
        """
        invalid_url = f'feed/followed/{invalid_batch}/'

        response = self.client.get(invalid_url, **self.user_a_header)

        # 400 Bad Request
        self.assertEqual(response.status_code, 404)

    def test_no_followed_users_returns_empty_list(self):
        """
        Tests that a user who follows no one gets an empty feed.
        """
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})

        # Use User B's header, who is not following anyone
        response = self.client.get(url, **self.user_b_header)

        self.assertEqual(response.status_code, 200)
        responses = response.json()
        self.assertEqual(len(responses), 0)

    def test_first_batch_returns_correct_number_of_posts(self):
        """
        Tests that batch 0 returns the correct number of posts (10).
        """
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})

        # Use User A's header, who is following User B
        response = self.client.get(url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        responses = response.json()

        # Assumes POST_BATCH_SIZE is 10
        self.assertEqual(len(responses), 10)

    def test_last_batch_returns_correct_number_of_posts(self):
        """
        Tests that the last partial batch (batch 1) returns the
        remaining posts (5).
        """
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 1})

        response = self.client.get(url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        responses = response.json()

        # 15 total posts, batch 0 had 10, so batch 1 should have 5
        self.assertEqual(len(responses), 5)

    def test_batch_beyond_max_returns_empty_list(self):
        """
        Tests that requesting a batch beyond the total number
        of posts returns an empty list.
        """
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 2})

        response = self.client.get(url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        responses = response.json()

        # Batch 2 should be empty
        self.assertEqual(len(responses), 0)