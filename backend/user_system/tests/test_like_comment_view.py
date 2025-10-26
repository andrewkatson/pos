from django.urls import reverse

from backend.user_system.constants import Fields
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import Comment  # Import the Comment model for assertions

invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'


class LikeCommentTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to:
        # 1. Create a post (setting self.post_identifier)
        # 2. Create a comment (setting self.comment_identifier, self.comment_thread_identifier)
        # 3. Create a commenter (setting self.commenter_session_management_token)
        # 4. Create other users, including a "liker" (populating self.users)
        super().comment_on_post_with_users()

        # Get the token for the "liker" user (assumed to be the 3rd user, index 2)
        other_session_management_tokens = self.users.get(Fields.session_management_token, [])
        self.liker_session_management_token = other_session_management_tokens[2]

        # Create the auth headers for our two key users
        self.liker_header = {'HTTP_AUTHORIZATION': f'Bearer {self.liker_session_management_token}'}
        self.commenter_header = {'HTTP_AUTHORIZATION': f'Bearer {self.commenter_session_management_token}'}

        # Define the URL for all tests
        self.url = reverse('like_comment', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': str(self.comment_identifier)
        })

        # Get the comment object for database assertions
        self.comment = Comment.objects.get(comment_identifier=self.comment_identifier)

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

        invalid_url = f'posts/{invalid_post_identifier}/threads/{self.comment_thread_identifier}/comments/{self.comment_identifier}/like/'

        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_thread_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{self.post_identifier}/threads/{invalid_comment_thread_identifier}/comments/{self.comment_identifier}/like/'


        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{self.post_identifier}/threads/{self.comment_thread_identifier}/comments/{invalid_comment_identifier}/like/'

        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_like_own_comment_returns_bad_response(self):
        """
        Tests that a user cannot like their own comment.
        """
        # Use the *commenter's* header to make the request
        response = self.client.post(self.url, **self.commenter_header)

        self.assertEqual(response.status_code, 400)

    def test_like_comment_twice_returns_bad_response(self):
        """
        Tests that liking the same comment twice fails on the second attempt.
        """
        # 1. First like (should succeed)
        response = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response.status_code, 200)

        # 2. Check database
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.commentlike_set.count(), 1)

        # 3. Second like (should fail)
        response = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response.status_code, 400)

        # 4. Verify database count hasn't changed
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.commentlike_set.count(), 1)

    def test_like_comment_returns_good_response_and_likes_comment(self):
        """
        Tests the "happy path" for liking a comment.
        """
        # 1. Check DB before
        self.assertEqual(self.comment.commentlike_set.count(), 0)

        # 2. Make the request
        response = self.client.post(self.url, **self.liker_header)

        # 3. Check response
        self.assertEqual(response.status_code, 200)

        # 4. Check DB after
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.commentlike_set.count(), 1)