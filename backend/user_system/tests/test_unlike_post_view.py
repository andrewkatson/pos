from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import MAX_BEFORE_HIDING_POST
from ..models import Post

# --- Constants ---
invalid_session_management_token = '?'
invalid_post_identifier = '?'

class UnlikePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Create User 0 (poster) and other users
        # The number of users is high but harmless, taken from original test
        self.make_post_with_users(MAX_BEFORE_HIDING_POST + 2)

        # 2. Get the "poster's" info (User 0)
        self.poster_token = self.session_management_token  # Set by parent helper
        self.poster_header = {'HTTP_AUTHORIZATION': f'Bearer {self.poster_token}'}

        # 3. Get the "liker's" info (User 1)
        self.liker_token = self.users[UserFields.TOKEN][1]
        self.liker_header = {'HTTP_AUTHORIZATION': f'Bearer {self.liker_token}'}

        # 4. Get the post object for DB assertions
        self.post = Post.objects.get(post_identifier=self.post_identifier)

        # 5. Call 'like_post' endpoint to set up the DB state
        like_url = reverse('like_post', kwargs={'post_identifier': str(self.post_identifier)})
        response = self.client.post(like_url, **self.liker_header)
        self.assertEqual(response.status_code, 200)  # Ensure setup worked

        # 6. Verify the like is in the DB
        self.post.refresh_from_db()
        self.assertEqual(self.post.postlike_set.count(), 1)

        # 7. Define the URL for all 'unlike' tests
        self.url = reverse('unlike_post', kwargs={'post_identifier': str(self.post_identifier)})

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.url, **invalid_header)

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{invalid_post_identifier}/unlike/'

        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_unlike_own_post_returns_bad_response(self):
        """
        Tests that a user cannot unlike their own post.
        """
        # Use the *poster's* header (User 0)
        response = self.client.post(self.url, **self.poster_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Cannot unlike own post'})

    def test_unlike_post_twice_returns_bad_response(self):
        """
        Tests that unliking the same post twice fails on the second attempt.
        """
        # 1. First unlike (should succeed)
        response1 = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response1.status_code, 200)

        # 2. Check database
        self.post.refresh_from_db()
        self.assertEqual(self.post.postlike_set.count(), 0)

        # 3. Second unlike (should fail)
        response2 = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response2.status_code, 400)
        self.assertEqual(response2.json(), {'error': 'Post not liked yet'})

    def test_unlike_post_returns_good_response_and_removes_like(self):
        """
        Tests the "happy path" for unliking a post.
        """
        # 1. Check DB before (like exists from setUp)
        self.assertEqual(self.post.postlike_set.count(), 1)

        # 2. Make the request
        response = self.client.post(self.url, **self.liker_header)

        # 3. Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Post unliked'})

        # 4. Check DB after
        self.post.refresh_from_db()
        self.assertEqual(self.post.postlike_set.count(), 0)