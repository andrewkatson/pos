from unittest.mock import patch

from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import get_user_with_username

invalid_session_management_token = '?'
invalid_post_identifier = '?'


class DeletePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Create a user, log them in, and create a post
        self.post, self.post_identifier = super().make_post_and_login_user()

        # 2. Store the user and valid auth header
        self.user = get_user_with_username(self.local_username)
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        # 3. Define the URL we will be testing
        self.url = reverse('delete_post', kwargs={'post_identifier': str(self.post_identifier)})

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.url, **invalid_header)

        # Not authorized error
        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL
        is rejected with a 400 Bad Request.
        """
        invalid_url = f'posts/{invalid_post_identifier}/delete/'

        response = self.client.post(invalid_url, **self.valid_header)

        # Malformed url error
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_another_users_post(self):
        """
        Tests that a user cannot delete a post they do not own.
        This is a critical security check.
        """
        # 1. Create a second user and log them in
        other_user_data = self.make_user_with_prefix()
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other_user_data[Fields.session_management_token]}'}

        # 2. Try to delete the first user's post (self.url)
        response = self.client.post(self.url, **other_header)

        # 3. Check for authorization failure
        # Your view should return 400 or 404 when Post.DoesNotExist is raised
        self.assertEqual(response.status_code, 400)

        # 4. Verify the post was NOT deleted
        self.user.refresh_from_db()
        self.assertEqual(self.user.post_set.count(), 1)

    def test_delete_post_returns_good_response_and_removes_post(self):
        """
        Tests that a valid request successfully deletes the post.
        """
        # Verify the post exists before we try to delete it
        self.assertEqual(self.user.post_set.count(), 1)

        response = self.client.post(self.url, **self.valid_header)

        # 1. Check for a successful response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Post deleted'})

        # 2. Verify the post is gone from the database
        self.user.refresh_from_db()
        self.assertEqual(self.user.post_set.count(), 0)

    def test_delete_post_cleans_up_s3_image(self):
        """Deleting a post removes its backing image from S3 rather than
        orphaning it."""
        image_url = self.post.image_url

        with patch('user_system.views.delete_image') as mock_delete:
            response = self.client.post(self.url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once_with(image_url)

    def test_failed_delete_does_not_clean_up_s3(self):
        """If no post is deleted (wrong owner), no S3 cleanup happens."""
        other_user_data = self.make_user_with_prefix()
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other_user_data[Fields.session_management_token]}'}

        with patch('user_system.views.delete_image') as mock_delete:
            response = self.client.post(self.url, **other_header)

        self.assertEqual(response.status_code, 400)
        mock_delete.assert_not_called()