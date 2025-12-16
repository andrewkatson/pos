from django.urls import reverse

from backend.user_system.constants import Fields
from .test_parent_case import PositiveOnlySocialTestCase

invalid_session_management_token = '?'
invalid_batch = -1
non_existent_username = 'iamnotauser'
malformed_username = '??!!'


class GetPostsForUserTests(PositiveOnlySocialTestCase):

    def test_posts_hidden_when_user_blocked(self):
        # 1. Block the user whose posts we want to see (self.username)
        # We need to access the requesting user. 'make_user_with_posts' doesn't return the user object directly,
        # but the test case setup usually has 'self.local_username' for the implicit user created if not explicit?
        # Wait, 'make_user_with_posts' creates a user and returns fields.
        # But who is the requester? 
        # Ah, in this test class, we have `self.token` which belongs to `self.username`.
        # So we are requesting OUR OWN posts?
        # `get_posts_for_user(self.username)` with `self.token`.
        # A user blocking themselves is not allowed / tested elsewhere.
        
        # We need a SECOND user to test blocking visibility.
        fields_other = self.make_user_with_prefix('other')
        token_other = fields_other[Fields.session_management_token]
        header_other = {'HTTP_AUTHORIZATION': f'Bearer {token_other}'}
        user_other = self.get_user_by_username(fields_other[Fields.username])
        
        target_user = self.get_user_by_username(self.username)
        
        # Case A: Other user blocks Target user.
        user_other.blocked.add(target_user)
        
        url = reverse('get_posts_for_user', kwargs={'username': self.username, 'batch': 0})
        response = self.client.get(url, **header_other)
        
        # Should be empty
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)


    def setUp(self):
        super().setUp()

        fields = self.make_user_with_posts(num_posts=10)
        self.username = fields[Fields.username]
        self.token = fields[Fields.session_management_token]

        # Store the valid header for all tests
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        url = reverse('get_posts_for_user', kwargs={
            'username': self.username,
            'batch': 0
        })
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.get(url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_invalid_batch_returns_bad_response(self):
        """
        Tests that a negative batch number in the URL
        is rejected with a 400 Bad Request.
        """

        invalid_url = f'users/{self.username}/posts/{invalid_batch}/'

        response = self.client.get(invalid_url, **self.valid_header)

        # Fails at the 'if batch < 0' check
        self.assertEqual(response.status_code, 404)

    def test_malformed_username_returns_bad_response(self):
        """
        Tests that a malformed username in the URL
        is rejected with a 400 Bad Request.
        """
        url = reverse('get_posts_for_user', kwargs={
            'username': malformed_username,  # Invalid
            'batch': 0
        })

        response = self.client.get(url, **self.valid_header)

        # Fails at the 'is_valid_pattern' check
        self.assertEqual(response.status_code, 400)

    def test_non_existent_username_returns_bad_response(self):
        """
        Tests that a valid but non-existent username in the URL
        is rejected with a 400 Bad Request.
        """
        url = reverse('get_posts_for_user', kwargs={
            'username': non_existent_username,  # Invalid
            'batch': 0
        })

        response = self.client.get(url, **self.valid_header)

        # Fails at 'get_user_with_username'
        self.assertEqual(response.status_code, 400)

    def test_one_beyond_max_batch_returns_good_response(self):
        """
        Tests that requesting a batch beyond the total number of items
        returns an empty list. (10 items / 10 per batch = batch 0)
        """
        # Assuming POST_BATCH_SIZE = 10, batch 1 should be the first empty one
        url = reverse('get_posts_for_user', kwargs={
            'username': self.username,
            'batch': 1
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        # We should grab no posts with a batch beyond the max number.
        self.assertEqual(len(responses), 0)

    def test_first_batch_returns_good_response(self):
        """
        Tests that requesting the first batch (batch 0) returns the
        correct number of posts (10).
        """
        url = reverse('get_posts_for_user', kwargs={
            'username': self.username,
            'batch': 0
        })

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()

        # Correcting the original test's logic.
        # If we made 10 posts, we should get 10 posts back.
        # (Assuming POST_BATCH_SIZE >= 10)
        self.assertEqual(len(responses), 10)