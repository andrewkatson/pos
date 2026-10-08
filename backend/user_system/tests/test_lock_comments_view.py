from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..models import Post

invalid_session_management_token = '?'
invalid_post_identifier = '?'


class LockCommentsTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        self.post, self.post_identifier = super().make_post_and_login_user()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.lock_url = reverse('lock_comments', kwargs={'post_identifier': str(self.post_identifier)})
        self.unlock_url = reverse('unlock_comments', kwargs={'post_identifier': str(self.post_identifier)})

    def test_invalid_session_management_token_returns_bad_response(self):
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.lock_url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        invalid_url = f'/posts/{invalid_post_identifier}/comments/lock/'

        response = self.client.post(invalid_url, **self.valid_header)

        self.assertEqual(response.status_code, 404)

    def test_cannot_lock_another_users_post_comments(self):
        other_user_data = self.make_user_with_prefix()
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other_user_data[Fields.session_management_token]}'}

        response = self.client.post(self.lock_url, **other_header)

        self.assertEqual(response.status_code, 400)
        self.post.refresh_from_db()
        self.assertFalse(self.post.comments_disabled)

    def test_cannot_unlock_another_users_post_comments(self):
        self.post.comments_disabled = True
        self.post.save(update_fields=['comments_disabled'])

        other_user_data = self.make_user_with_prefix()
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other_user_data[Fields.session_management_token]}'}

        response = self.client.post(self.unlock_url, **other_header)

        self.assertEqual(response.status_code, 400)
        self.post.refresh_from_db()
        self.assertTrue(self.post.comments_disabled)

    def test_lock_comments_returns_good_response_and_disables_comments(self):
        response = self.client.post(self.lock_url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {Fields.comments_disabled: True})

        self.post.refresh_from_db()
        self.assertTrue(self.post.comments_disabled)

    def test_unlock_comments_returns_good_response_and_reenables_comments(self):
        self.post.comments_disabled = True
        self.post.save(update_fields=['comments_disabled'])

        response = self.client.post(self.unlock_url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {Fields.comments_disabled: False})

        self.post.refresh_from_db()
        self.assertFalse(self.post.comments_disabled)
