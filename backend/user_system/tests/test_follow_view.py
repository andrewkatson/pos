from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..models import PositiveOnlySocialUser  # Import model for assertions

invalid_session_management_token = '?'
non_existent_username = 'iamnotauser'


class FollowUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Set up the primary user (User A) who will do the following.
        super().register_user_and_setup_local_fields()
        self.user_a_token = self.session_management_token
        self.user_a_username = self.local_username
        self.user_a_header = {'HTTP_AUTHORIZATION': f'Bearer {self.user_a_token}'}
        self.user_a = PositiveOnlySocialUser.objects.get(username=self.user_a_username)

        # 2. Create a second user (User B) to be the target of the follow action.
        self.user_b_username = "OtherUser11"
        self.make_user(self.user_b_username)
        self.user_b = PositiveOnlySocialUser.objects.get(username=self.user_b_username)

        # 3. Define the URL for User A to follow User B
        self.follow_url = reverse('follow_user', kwargs={'username_to_follow': self.user_b_username})

    def test_follow_user_success(self):
        """
        Tests that a valid, authenticated POST request successfully follows a user.
        """
        response = self.client.post(self.follow_url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        self.assertIn('User followed', response.content.decode('utf8'))

        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 1)
        self.assertEqual(self.user_a.following.first(), self.user_b)

    def test_follow_user_invalid_token_fails(self):
        """
        Tests that the @api_login_required decorator rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.follow_url, **invalid_header)

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_follow_non_existent_user_fails(self):
        """
        Tests that attempting to follow a user that does not exist fails.
        """
        invalid_url = reverse('follow_user', kwargs={'username_to_follow': non_existent_username})

        response = self.client.post(invalid_url, **self.user_a_header)

        self.assertEqual(response.status_code, 400)  # 400 Bad Request
        self.assertIn('Target user does not exist', response.content.decode('utf8'))

    def test_follow_self_fails(self):
        """
        Tests that a user cannot follow themselves.
        """
        follow_self_url = reverse('follow_user', kwargs={'username_to_follow': self.user_a_username})

        response = self.client.post(follow_self_url, **self.user_a_header)

        self.assertEqual(response.status_code, 400)  # 400 Bad Request
        self.assertIn('You cannot follow yourself', response.content.decode())

        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 0)

    def test_follow_already_following_fails(self):
        """
        Tests that attempting to follow the same user twice fails
        on the second attempt and does not create a duplicate relationship.
        """
        # 1. First, follow the user successfully.
        response = self.client.post(self.follow_url, **self.user_a_header)
        self.assertEqual(response.status_code, 200)

        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 1)
        self.assertEqual(self.user_a.following.first(), self.user_b)

        # 2. Try to follow them again.
        response = self.client.post(self.follow_url, **self.user_a_header)

        # 3. This should fail.
        self.assertEqual(response.status_code, 400)  # 400 Bad Request
        self.assertEqual('Already following this user', response.content.decode())

        # 4. The following count should remain 1.
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.following.count(), 1)