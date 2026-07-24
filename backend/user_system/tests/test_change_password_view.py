from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..models import LoginCookie, Session
from ..utils import generate_login_cookie_token, generate_management_token


class ChangePasswordTests(PositiveOnlySocialTestCase):
    """POST /password/change/ changes the signed-in account's password after
    confirming the current one (issue #197)."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.new_password = 'BrandNewPass123-'
        self.url = reverse('change_password')

    def _user(self):
        return get_user_model().objects.get(username=self.local_username)

    def test_successful_change_updates_hash(self):
        response = self.client.post(
            self.url,
            data={'password': self.local_password, 'new_password': self.new_password},
            content_type='application/json',
            **self.valid_header,
        )
        self.assertEqual(response.status_code, 200)
        user = self._user()
        self.assertTrue(check_password(self.new_password, user.password))
        self.assertFalse(check_password(self.local_password, user.password))

    def test_wrong_current_password_is_rejected(self):
        response = self.client.post(
            self.url,
            data={'password': 'WrongPassword123-', 'new_password': self.new_password},
            content_type='application/json',
            **self.valid_header,
        )
        self.assertEqual(response.status_code, 400)
        # The stored password is unchanged.
        self.assertTrue(check_password(self.local_password, self._user().password))

    def test_weak_new_password_is_rejected(self):
        response = self.client.post(
            self.url,
            data={'password': self.local_password, 'new_password': 'weak'},
            content_type='application/json',
            **self.valid_header,
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(check_password(self.local_password, self._user().password))

    def test_new_password_must_differ_from_current(self):
        response = self.client.post(
            self.url,
            data={'password': self.local_password, 'new_password': self.local_password},
            content_type='application/json',
            **self.valid_header,
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_token_is_rejected(self):
        response = self.client.post(
            self.url,
            data={'password': self.local_password, 'new_password': self.new_password},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_current_session_preserved_other_sessions_and_cookies_evicted(self):
        user = self._user()
        # A second device: another session plus a remember-me cookie.
        other_session = user.session_set.create(management_token=generate_management_token(), ip='1.2.3.4')
        LoginCookie.objects.create(cookie_user=user, token=generate_login_cookie_token())

        response = self.client.post(
            self.url,
            data={'password': self.local_password, 'new_password': self.new_password},
            content_type='application/json',
            **self.valid_header,
        )
        self.assertEqual(response.status_code, 200)

        # The current session survives; the other device's session and every
        # remember-me cookie are gone.
        self.assertTrue(
            Session.objects.filter(management_token=self.session_management_token).exists()
        )
        self.assertFalse(Session.objects.filter(pk=other_session.pk).exists())
        self.assertEqual(LoginCookie.objects.filter(cookie_user=user).count(), 0)
