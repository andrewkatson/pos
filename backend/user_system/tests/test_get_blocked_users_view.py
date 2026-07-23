from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import get_user_with_username

class GetBlockedUsersViewTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Create User A (logs them in)
        fields_a = self.register_and_login_user(prefix='user_a')
        self.user_a_username = fields_a['username']
        self.user_a = get_user_with_username(self.user_a_username)
        self.user_a_header = {'HTTP_AUTHORIZATION': f"Bearer {fields_a[Fields.session_management_token]}"}

        # Create User B and User C (users to block)
        fields_b = self.make_user_with_prefix(prefix='user_b')
        self.user_b_username = fields_b['username']
        self.user_b = get_user_with_username(self.user_b_username)

        fields_c = self.make_user_with_prefix(prefix='user_c')
        self.user_c_username = fields_c['username']
        self.user_c = get_user_with_username(self.user_c_username)

        self.url = reverse('get_blocked_users')

    def test_no_blocked_users(self):
        """
        Tests that a user with no blocks gets an empty list.
        """
        response = self.client.get(self.url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_blocked_users_returned_sorted_by_username(self):
        """
        Tests that all blocked users are returned, ordered by username.
        """
        self.user_a.blocked.add(self.user_c)
        self.user_a.blocked.add(self.user_b)

        response = self.client.get(self.url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        usernames = [user[Fields.username] for user in response.json()]
        self.assertEqual(usernames, sorted([self.user_b_username, self.user_c_username]))
        for user in response.json():
            self.assertIn(Fields.identity_is_verified, user)

    def test_only_own_blocks_returned(self):
        """
        Tests that users who blocked the requester do not appear in the list.
        """
        self.user_b.blocked.add(self.user_a)

        response = self.client.get(self.url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_unblocked_user_no_longer_listed(self):
        """
        Tests that unblocking via toggle_block removes the user from the list.
        """
        self.user_a.blocked.add(self.user_b)

        toggle_url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.user_b_username})
        response = self.client.post(toggle_url, **self.user_a_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'User unblocked'})

        response = self.client.get(self.url, **self.user_a_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_requires_authentication(self):
        """
        Tests that the endpoint rejects unauthenticated requests.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
