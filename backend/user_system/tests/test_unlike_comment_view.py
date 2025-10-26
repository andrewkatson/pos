from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import Comment

# --- Constants ---
invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'

class UnlikeCommentTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. This helper creates User 0 (poster), User 1 (commenter),
        #    and User 2 (liker). It also sets up self.post_identifier,
        #    self.comment_..._identifier, and self.commenter_..._token.
        self.comment_on_post_with_users()

        # 2. Get the "liker's" info (User 2)
        self.liker_token = self.users[UserFields.TOKEN][2]
        self.liker_header = {'HTTP_AUTHORIZATION': f'Bearer {self.liker_token}'}
        self.commenter_header = {'HTTP_AUTHORIZATION': f'Bearer {self.commenter_session_management_token}'}

        # 3. Call the 'like_comment' endpoint to set up the DB state
        like_url = reverse('like_comment', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': str(self.comment_identifier)
        })
        response = self.client.post(like_url, **self.liker_header)
        self.assertEqual(response.status_code, 200)  # Ensure setup worked

        # 4. Get the comment object and verify the like
        self.comment = Comment.objects.get(comment_identifier=self.comment_identifier)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.commentlike_set.count(), 1)

        # 5. Define the URL for all 'unlike' tests
        self.url = reverse('unlike_comment', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': str(self.comment_identifier)
        })

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
        invalid_url = f'posts/{invalid_post_identifier}/threads/{self.comment_thread_identifier}/comments/{self.comment_identifier}/unlike/'

        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_thread_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{self.post_identifier}/threads/{invalid_comment_thread_identifier}/comments/{self.comment_identifier}/unlike/'

        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{self.post_identifier}/threads/{self.comment_thread_identifier}/comments/{invalid_comment_identifier}/unlike/'

        response = self.client.post(invalid_url, **self.liker_header)

        self.assertEqual(response.status_code, 404)

    def test_unlike_own_comment_returns_bad_response(self):
        """
        Tests that a user cannot unlike a comment they authored
        (even if someone else liked it).
        """
        # Use the *commenter's* header (User 1)
        response = self.client.post(self.url, **self.commenter_header)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'Cannot unlike own comment'})

    def test_unlike_comment_twice_returns_bad_response(self):
        """
        Tests that unliking the same comment twice fails on the second attempt.
        """
        # 1. First unlike (should succeed)
        response1 = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response1.status_code, 200)

        # 2. Check database
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.commentlike_set.count(), 0)

        # 3. Second unlike (should fail)
        response2 = self.client.post(self.url, **self.liker_header)
        self.assertEqual(response2.status_code, 404)
        self.assertEqual(response2.json(), {'error': 'Comment not liked yet'})

    def test_unlike_comment_returns_good_response_and_unlikes_comment(self):
        """
        Tests the "happy path" for unliking a comment.
        """
        # 1. Check DB before (like exists from setUp)
        self.assertEqual(self.comment.commentlike_set.count(), 1)

        # 2. Make the request
        response = self.client.post(self.url, **self.liker_header)

        # 3. Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Comment unliked'})

        # 4. Check DB after
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.commentlike_set.count(), 0)