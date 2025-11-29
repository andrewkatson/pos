from unittest.mock import patch
import os
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_TEXT
from ..constants import Fields
from ..views import get_user_with_username

invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'


class DeleteCommentTests(PositiveOnlySocialTestCase):

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def setUp(self):
        super().setUp()

        # 1. Create a user, log them in, and create a post
        self.post, self.post_identifier = super().make_post_and_login_user()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.user = get_user_with_username(self.local_username)

        # 2. Make a comment on that post using the test client
        comment_url = reverse('comment_on_post', kwargs={'post_identifier': str(self.post_identifier)})
        comment_data = {'comment_text': POSITIVE_TEXT}

        response = self.client.post(
            comment_url,
            data=comment_data,
            content_type='application/json',
            **self.valid_header
        )
        self.assertEqual(response.status_code, 201)  # 201 Created

        # 3. Get the created comment's details for testing
        fields = response.json()
        self.comment_thread_identifier = fields[Fields.comment_thread_identifier]
        self.comment_identifier = fields[Fields.comment_identifier]

        # 4. Store the created post and thread for later assertions
        self.post = self.user.post_set.first()
        self.comment_thread = self.post.commentthread_set.get(
            comment_thread_identifier=self.comment_thread_identifier
        )

        # 5. Define the URL for the delete operation
        self.delete_url = reverse('delete_comment', kwargs={
            'post_identifier': self.post_identifier,
            'comment_thread_identifier': self.comment_thread_identifier,
            'comment_identifier': self.comment_identifier
        })

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.delete_url, **invalid_header)

        # @api_login_required should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL is rejected.
        """
        invalid_url = f"/user_index/posts/{invalid_post_identifier}/threads/{self.comment_thread_identifier}/comments/{self.comment_identifier}/delete/"

        response = self.client.post(invalid_url, **self.valid_header)

        # View's pattern matching should return 404 malformed url
        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_thread_identifier in the URL is rejected.
        """
        invalid_url = f"/user_index/posts/{self.post_identifier}/threads/{invalid_comment_thread_identifier}/comments/{self.comment_identifier}/delete/"

        response = self.client.post(invalid_url, **self.valid_header)

        # View's pattern matching should return 404 malformed url
        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_identifier in the URL is rejected.
        """
        invalid_url = f"/user_index/posts/{self.post_identifier}/threads/{self.comment_thread_identifier}/comments/{invalid_comment_identifier}/delete/"

        response = self.client.post(invalid_url, **self.valid_header)

        # View's pattern matching should return 404 malformed url
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_another_users_comment(self):
        """
        Tests that a user cannot delete a comment they do not own.
        """
        # 1. Create a second user and log them in
        other_user_data = self.make_user_with_prefix(prefix='Delete_another_user_comment')
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other_user_data["token"]}'}

        # 2. Try to delete the first user's comment
        response = self.client.post(self.delete_url, **other_header)

        # 3. Check for authorization failure
        self.assertEqual(response.status_code, 400)

        # 4. Verify the comment was NOT deleted
        self.comment_thread.refresh_from_db()
        self.assertEqual(self.comment_thread.comment_set.count(), 1)

    def test_delete_comment_returns_good_response_and_deletes_comment(self):
        """
        Tests that a valid request successfully deletes the comment.
        """
        # Verify comment exists before deletion
        self.assertEqual(self.comment_thread.comment_set.count(), 1)

        response = self.client.post(self.delete_url, **self.valid_header)

        # 1. Check for a successful response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Comment deleted'})

        # 2. Verify the comment is gone from the database
        self.comment_thread.refresh_from_db()
        self.assertEqual(self.comment_thread.comment_set.count(), 0)
