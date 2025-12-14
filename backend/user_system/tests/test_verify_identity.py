from django.urls import reverse
from django.contrib.auth import get_user_model
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields

class VerifyIdentityTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('verify_identity')
        
        # Create a user to test with
        self.user = get_user_model().objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='password'
        )
        self.user.save()
        
        # Log in the user (if required by decorator, but verify_identity is @api_login_required)
        # Wait, verify_identity IS @api_login_required. So we need a token.
        # Let's create a session for the user.
        self.session = self.user.session_set.create(management_token='validtoken123', ip='127.0.0.1')
        self.token = self.session.management_token

    def test_verify_identity_adult(self):
        data = {'date_of_birth': '2000-01-01'}
        response = self.client.post(
            self.url, 
            data=data, 
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}'
        )
        self.assertEqual(response.status_code, 200)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.identity_is_verified)
        self.assertTrue(self.user.is_adult)

    def test_verify_identity_minor(self):
        data = {'date_of_birth': '2020-01-01'}
        response = self.client.post(
            self.url, 
            data=data, 
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}'
        )
        self.assertEqual(response.status_code, 200)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.identity_is_verified)
        self.assertFalse(self.user.is_adult)

    def test_verify_identity_invalid_date(self):
        data = {'date_of_birth': 'invalid-date'}
        response = self.client.post(
            self.url, 
            data=data, 
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}'
        )
        self.assertEqual(response.status_code, 400)
        
    def test_verify_identity_missing_date(self):
        data = {}
        response = self.client.post(
            self.url, 
            data=data, 
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}'
        )
        self.assertEqual(response.status_code, 400)
