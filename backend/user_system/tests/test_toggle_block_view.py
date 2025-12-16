from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from user_system.models import LoginCookie, Session, Post
from user_system.utils import generate_login_cookie_token, generate_series_identifier

class ToggleBlockViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = get_user_model().objects.create_user(username='user1', email='user1@example.com', password='password')
        self.user2 = get_user_model().objects.create_user(username='user2', email='user2@example.com', password='password')
        
        # User 1 login
        self.user1_session = self.user1.session_set.create(management_token='token123', ip='127.0.0.1')
        
        self.url = lambda username: reverse('toggle_block', kwargs={'username_to_toggle_block': username})

    def test_block_user(self):
        response = self.client.post(self.url('user2'), HTTP_AUTHORIZATION='Bearer token123')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'User blocked'})
        self.assertTrue(self.user1.blocked.filter(pk=self.user2.pk).exists())
        self.assertTrue(self.user2.blocked_by.filter(pk=self.user1.pk).exists())

    def test_unblock_user(self):
        self.user1.blocked.add(self.user2)
        response = self.client.post(self.url('user2'), HTTP_AUTHORIZATION='Bearer token123')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'User unblocked'})
        self.assertFalse(self.user1.blocked.filter(pk=self.user2.pk).exists())

    def test_block_user_removes_follow(self):
        self.user1.following.add(self.user2)
        self.assertTrue(self.user1.following.filter(pk=self.user2.pk).exists())
        
        response = self.client.post(self.url('user2'), HTTP_AUTHORIZATION='Bearer token123')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user1.following.filter(pk=self.user2.pk).exists())

    def test_block_user_removes_mutual_follow(self):
        self.user2.following.add(self.user1)
        self.assertTrue(self.user2.following.filter(pk=self.user1.pk).exists())

        response = self.client.post(self.url('user2'), HTTP_AUTHORIZATION='Bearer token123')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user2.following.filter(pk=self.user1.pk).exists())

    def test_block_self(self):
        response = self.client.post(self.url('user1'), HTTP_AUTHORIZATION='Bearer token123')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Cannot block self'})

    def test_block_nonexistent_user(self):
        response = self.client.post(self.url('nobody'), HTTP_AUTHORIZATION='Bearer token123')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'User does not exist'})
