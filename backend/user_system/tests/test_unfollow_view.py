from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import PositiveOnlySocialUser

# --- Constants ---
invalid_session_management_token = '?'
non_existent_username = 'iamnotauser'


class UnfollowUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Set up User A (the follower)
        # This helper creates a user and sets self.local_username/self.session_management_token
        self.register_user_and_setup_local_fields()
        self.user_a_username = self.local_username
        self.user_a_token = self.session_management_token
        self.user_a_header = {'HTTP_AUTHORIZATION': f'Bearer {self.user_a_token}'}
        self.user_a = PositiveOnlySocialUser.objects.get(username=self.user_a_username)

        # 2. Set up User B (the one to be followed)
        self.user_b_username = "OtherUser23"
        self.make_user(self.user_b_username)  # This just creates them in the DB
        self.user_b = PositiveOnlySocialUser.objects.get(username=self.user_b_username)

        # 3. User A must follow User B. Call the 'follow_user' endpoint.
        follow_url = reverse('follow_user', kwargs={'username_to_follow': self.user_b_username})
        response = self.client.post(follow_url, **self.user_a_header)

        # Verify the follow was successful before testing unfollow
        self.assertEqual(response.status_code, 200)
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 1)
        self.assertEqual(self.user_a.following.first(), self.user_b)

        # 4. Define the URL for the unfollow action
        self.unfollow_url = reverse('unfollow_user', kwargs={'username_to_unfollow': self.user_b_username})

    def test_unfollow_user_success(self):
        """
        Tests that a valid, authenticated POST request successfully unfollows a user.
        """
        # Verify they are following before the test
        self.assertEqual(self.user_a.following.count(), 1)

        # Now, unfollow them.
        response = self.client.post(self.unfollow_url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'User unfollowed'})

        # The following count should be back to 0.
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 0)

    def test_unfollow_user_invalid_token_fails(self):
        """
        Tests that the @api_login_required decorator rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.unfollow_url, **invalid_header)

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_unfollow_non_existent_user_fails(self):
        """
        Tests that attempting to unfollow a user that does not exist fails.
        """
        invalid_url = reverse('unfollow_user', kwargs={'username_to_unfollow': non_existent_username})

        response = self.client.post(invalid_url, **self.user_a_header)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'User does not exist'})

    def test_unfollow_user_not_following_fails(self):
        """
        Tests that attempting to unfollow a user you are not
        already following fails.
        """
        # 1. First, unfollow them (this should succeed)
        response = self.client.post(self.unfollow_url, **self.user_a_header)
        self.assertEqual(response.status_code, 200)

        # 2. Verify the user is not following anyone.
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 0)

        # 3. Attempt to unfollow the other user *again*.
        response = self.client.post(self.unfollow_url, **self.user_a_header)

        # 4. This should fail with a 400
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'Not following user'})

        # 5. The following count should still be 0.
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 0)