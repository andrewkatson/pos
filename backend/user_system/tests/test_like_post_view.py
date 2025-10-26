from django.urls import reverse

from backend.user_system.constants import Fields
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import Post  # Import the Post model for assertions

invalid_session_management_token = '?'
invalid_post_identifier = '?'


class LikePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to:
        # 1. Create a user (the "poster"), log them in, and set self.session_management_token
        # 2. Create a post for that user, setting self.post_identifier
        # 3. Create a second user (the "liker") and store their data in self.users
        super().make_post_with_users(2)

        # 1. Set up the Post Author ("poster")
        self.poster_token = self.session_management_token
        self.poster_header = {'HTTP_AUTHORIZATION': f'Bearer {self.poster_token}'}

        # 2. Set up the user who will do the liking ("liker")
        liker_tokens = self.users.get(Fields.session_management_token, [])
        self.liker_token = liker_tokens[1]
        self.liker_header = {'HTTP_AUTHORIZATION': f'Bearer {self.liker_token}'}

        # 3. Define the URL for all tests
        self.url = reverse('like_post', kwargs={'post_identifier': str(self.post_identifier)})

        # 4. Get the post object for database assertions
        self.post = Post.objects.get(post_identifier=self.post_identifier)

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
        invalid_url = f'posts/{invalid_post_identifier}/like/'

        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_like_own_post_returns_bad_response(self):
        """
        Tests that a user cannot like their own post.
        """
        # Use the *poster's* header to make the request
        response = self.client.post(self.url, **self.poster_header)

        self.assertEqual(response.status_code, 400)

    def test_like_post_twice_returns_bad_response(self):
        """
        Tests that liking the same post twice fails on the second attempt.
        """
        # 1. First like (should succeed)
        response = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response.status_code, 200)

        # 2. Check database
        self.post.refresh_from_db()
        self.assertEqual(self.post.postlike_set.count(), 1)

        # 3. Second like (should fail)
        response = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response.status_code, 400)

        # 4. Verify database count hasn't changed
        self.post.refresh_from_db()
        self.assertEqual(self.post.postlike_set.count(), 1)

    def test_like_post_returns_good_response_and_likes_post_from_user(self):
        """
        Tests the "happy path" for liking a post.
        """
        # 1. Check DB before
        self.assertEqual(self.post.postlike_set.count(), 0)

        # 2. Make the request
        response = self.client.post(self.url, **self.liker_header)

        # 3. Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Post liked'})

        # 4. Check DB after
        self.post.refresh_from_db()
        self.assertEqual(self.post.postlike_set.count(), 1)