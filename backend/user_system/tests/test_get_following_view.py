from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import get_user_with_username

class GetFollowingViewTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Create User A (logs them in) — the requester whose following we list.
        fields_a = self.register_and_login_user(prefix='user_a')
        self.user_a_username = fields_a['username']
        self.user_a = get_user_with_username(self.user_a_username)
        self.user_a_header = {'HTTP_AUTHORIZATION': f"Bearer {fields_a[Fields.session_management_token]}"}

        # Create User B and User C (users A might follow).
        fields_b = self.make_user_with_prefix(prefix='user_b')
        self.user_b_username = fields_b['username']
        self.user_b = get_user_with_username(self.user_b_username)

        fields_c = self.make_user_with_prefix(prefix='user_c')
        self.user_c_username = fields_c['username']
        self.user_c = get_user_with_username(self.user_c_username)

        self.url = reverse('get_following')

    def test_not_following_anyone(self):
        """A user who follows nobody gets an empty list."""
        response = self.client.get(self.url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_following_returned_sorted_by_username(self):
        """All followed users are returned, ordered by username."""
        self.user_a.following.add(self.user_c)
        self.user_a.following.add(self.user_b)

        response = self.client.get(self.url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        usernames = [user[Fields.username] for user in response.json()]
        self.assertEqual(usernames, sorted([self.user_b_username, self.user_c_username]))
        for user in response.json():
            self.assertIn(Fields.identity_is_verified, user)

    def test_followers_are_not_returned_as_following(self):
        """Users who follow the requester do not appear in their following list."""
        self.user_b.following.add(self.user_a)

        response = self.client.get(self.url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_only_own_following_returned(self):
        """The list is scoped to the requester — B's following never leaks to A."""
        self.user_b.following.add(self.user_c)

        response = self.client.get(self.url, **self.user_a_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_unfollow_removes_from_list(self):
        """Unfollowing via the unfollow endpoint removes the user from the list."""
        self.user_a.following.add(self.user_b)

        unfollow_url = reverse('unfollow_user', kwargs={'username_to_unfollow': self.user_b_username})
        response = self.client.post(unfollow_url, **self.user_a_header)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(self.url, **self.user_a_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_requires_authentication(self):
        """The endpoint rejects unauthenticated requests."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
