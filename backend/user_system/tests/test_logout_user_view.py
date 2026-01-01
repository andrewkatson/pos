from django.urls import reverse

from ..constants import Fields
from .test_parent_case import PositiveOnlySocialTestCase

invalid_session_management_token = '?'


class LogoutUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to create/login a user and set
        # self.local_username and self.session_management_token
        fields = self.register_and_login_user()
        self.username = fields[Fields.username]
        self.token = fields[Fields.session_management_token]

        # Store the valid header and URL for all tests
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        self.url = reverse('logout_user')

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that the @api_login_required decorator rejects an
        invalid token with a 401 Unauthorized.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        # Use self.client.post to make a real HTTP request
        response = self.client.post(self.url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_logged_in_user_logs_out_and_invalidates_token(self):
        """
        Tests that a valid logout request succeeds and the token
        can no longer be used.
        """
        # 1. Call the logout endpoint
        response = self.client.post(self.url, **self.valid_header)

        # 2. Check that the logout was successful
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Logout successful'})

        # 3. VERIFICATION: Try to use the same token (which should
        #    now be invalid) to access another protected endpoint.
        protected_url = reverse('get_posts_in_feed', kwargs={'batch': 0})
        response_after_logout = self.client.get(protected_url, **self.valid_header)

        # 4. This request should now fail with 401 Unauthorized
        self.assertEqual(response_after_logout.status_code, 401)