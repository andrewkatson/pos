from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import PositiveOnlySocialUser  # Import the model for checking

invalid_session_management_token = '?'


class DeleteUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This parent helper is assumed to create a user and log them in,
        # setting self.local_username and self.session_management_token.
        # The 'false' argument is removed as it's no longer relevant.
        super().register_user_and_setup_local_fields()

        # Store the valid header and URL for all tests
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('delete_user')

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        # Use self.client.post to make a real HTTP request
        response = self.client.post(self.url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_logged_in_user_is_deleted(self):
        """
        Tests that a valid request successfully deletes the user.
        """
        # 1. Verify the user exists in the database before the test
        self.assertTrue(
            PositiveOnlySocialUser.objects.filter(username=self.local_username).exists()
        )

        # 2. Make the authenticated request to delete the user
        response = self.client.post(self.url, **self.valid_header)

        # 3. Check for a successful response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'User deleted successfully'})

        # 4. Test that the user is truly gone from the database
        self.assertFalse(
            PositiveOnlySocialUser.objects.filter(username=self.local_username).exists()
        )