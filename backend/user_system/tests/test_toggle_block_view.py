from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import get_user_with_username

class ToggleBlockViewTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        
        # Create User A (logs them in)
        fields_a = self.register_and_login_user(prefix='user_a')
        self.user_a_username = fields_a['username']
        self.user_a = get_user_with_username(self.user_a_username)
        # make_user_with_prefix returns a helper dict with 'token' key
        self.user_a_header = {'HTTP_AUTHORIZATION': f"Bearer {fields_a['token']}"}

        # Create User B (another user to block)
        fields_b = self.make_user_with_prefix(prefix='user_b')
        self.user_b_username = fields_b['username']
        self.user_b = get_user_with_username(self.user_b_username)

    def test_block_user(self):
        """
        Tests that a user can successfully block another valid user.
        """
        url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.user_b_username})
        response = self.client.post(url, **self.user_a_header)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'User blocked'})
        
        self.assertTrue(self.user_a.blocked.filter(pk=self.user_b.pk).exists())
        self.assertTrue(self.user_b.blocked_by.filter(pk=self.user_a.pk).exists())

    def test_unblock_user(self):
        """
        Tests that a user can successfully unblock a previously blocked user.
        """
        # Block first manually
        self.user_a.blocked.add(self.user_b)
        
        url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.user_b_username})
        response = self.client.post(url, **self.user_a_header)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'User unblocked'})
        
        self.assertFalse(self.user_a.blocked.filter(pk=self.user_b.pk).exists())

    def test_block_user_removes_follow(self):
        """
        Tests that blocking a user automatically removes the follow relationship
        where the blocker follows the blocked user.
        """
        self.user_a.following.add(self.user_b)
        self.assertTrue(self.user_a.following.filter(pk=self.user_b.pk).exists())
        
        url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.user_b_username})
        response = self.client.post(url, **self.user_a_header)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user_a.following.filter(pk=self.user_b.pk).exists())

    def test_block_user_removes_mutual_follow(self):
        """
        Tests that blocking a user automatically removes the follow relationship
        where the blocked user follows the blocker.
        """
        self.user_b.following.add(self.user_a)
        self.assertTrue(self.user_b.following.filter(pk=self.user_a.pk).exists())
        
        url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.user_b_username})
        response = self.client.post(url, **self.user_a_header)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user_b.following.filter(pk=self.user_a.pk).exists())

    def test_block_self(self):
        """
        Tests that a user cannot block themselves and receives an error.
        """
        url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.user_a_username})
        response = self.client.post(url, **self.user_a_header)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Cannot block self'})

    def test_block_nonexistent_user(self):
        """
        Tests that attempting to block a user that does not exist returns an error.
        """
        url = reverse('toggle_block', kwargs={'username_to_toggle_block': 'nonexistent_user'})
        response = self.client.post(url, **self.user_a_header)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'User does not exist'})
