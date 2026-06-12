from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .test_constants import true
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import ACCOUNT_BANNED, BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW, Fields
from ..models import LoginCookie, Session, UserBan
from ..utils import generate_login_cookie_token, generate_management_token
from ..views import get_user_with_username


class UserBanTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Registers a user with remember_me so we have a session token,
        # a series identifier, and a login cookie token to test against.
        super().register_user_and_setup_local_fields(remember_me=true)

        self.user = get_user_with_username(self.local_username)

        self.login_url = reverse('login_user')
        self.remember_me_url = reverse('login_user_with_remember_me')

        self.login_data = {
            'username_or_email': self.local_username,
            'password': self.local_password,
            'remember_me': False,
        }

    def _ban_user(self, ban_type=BAN_TYPE_OUTRIGHT, expires=None):
        return UserBan.objects.create(user=self.user, ban_type=ban_type, expires=expires)

    # =========================================================================
    # BAN APPLICATION
    # =========================================================================

    def test_outright_ban_deletes_sessions_and_login_cookies(self):
        """
        Applying an outright ban must delete the user's Session and
        LoginCookie rows so live sessions die immediately.
        """
        self.assertEqual(Session.objects.filter(management_user=self.user).count(), 1)
        self.assertEqual(LoginCookie.objects.filter(cookie_user=self.user).count(), 1)

        self._ban_user()

        self.assertEqual(Session.objects.filter(management_user=self.user).count(), 0)
        self.assertEqual(LoginCookie.objects.filter(cookie_user=self.user).count(), 0)

    def test_shadow_ban_keeps_sessions_and_login_cookies(self):
        """
        A shadow ban must leave the user's sessions alone so they stay unaware.
        """
        self._ban_user(ban_type=BAN_TYPE_SHADOW)

        self.assertEqual(Session.objects.filter(management_user=self.user).count(), 1)
        self.assertEqual(LoginCookie.objects.filter(cookie_user=self.user).count(), 1)

    # =========================================================================
    # LOGIN GATE
    # =========================================================================

    def test_outright_ban_blocks_login(self):
        """
        An outright-banned user gets the distinct account_banned error
        instead of a session.
        """
        self._ban_user()

        response = self.client.post(self.login_url, data=self.login_data, content_type='application/json')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('error'), ACCOUNT_BANNED)

    def test_outright_ban_with_future_expiry_blocks_login(self):
        """
        A temporary ban that has not yet expired still blocks login.
        """
        self._ban_user(expires=timezone.now() + timedelta(days=1))

        response = self.client.post(self.login_url, data=self.login_data, content_type='application/json')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('error'), ACCOUNT_BANNED)

    def test_expired_outright_ban_allows_login(self):
        """
        A ban whose expiry has passed no longer blocks login.
        """
        self._ban_user(expires=timezone.now() - timedelta(days=1))

        response = self.client.post(self.login_url, data=self.login_data, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn(Fields.session_management_token, response.json())

    def test_shadow_ban_does_not_block_login(self):
        """
        A shadow-banned user can still log in normally.
        """
        self._ban_user(ban_type=BAN_TYPE_SHADOW)

        response = self.client.post(self.login_url, data=self.login_data, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn(Fields.session_management_token, response.json())

    def test_login_with_wrong_password_does_not_reveal_ban(self):
        """
        Without valid credentials the response stays the generic login
        failure, not account_banned.
        """
        self._ban_user()

        data = self.login_data.copy()
        data['password'] = "CorrectFormatButWrongPassword123$"

        response = self.client.post(self.login_url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('error'), "Invalid username or password")

    # =========================================================================
    # REMEMBER-ME GATE
    # =========================================================================

    def test_outright_ban_blocks_remember_me_login(self):
        """
        Even if a login cookie and session somehow exist after the ban,
        the remember-me gate rejects the user with account_banned.
        """
        self._ban_user()

        # Recreate credentials post-ban to exercise the gate itself
        # (applying the ban deletes the originals).
        login_cookie = LoginCookie.objects.create(cookie_user=self.user, token=generate_login_cookie_token())
        session = Session.objects.create(management_user=self.user, management_token=generate_management_token())

        data = {
            Fields.session_management_token: session.management_token,
            'series_identifier': str(login_cookie.series_identifier),
            'login_cookie_token': login_cookie.token,
        }

        response = self.client.post(self.remember_me_url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('error'), ACCOUNT_BANNED)

    def test_outright_ban_invalidates_existing_remember_me_credentials(self):
        """
        The credentials issued before the ban stop working because the ban
        deleted them.
        """
        data = {
            Fields.session_management_token: self.session_management_token,
            'series_identifier': self.series_identifier,
            'login_cookie_token': self.login_cookie_token,
        }

        self._ban_user()

        response = self.client.post(self.remember_me_url, data=data, content_type='application/json')

        self.assertEqual(response.status_code, 400)

    # =========================================================================
    # API SESSION GATE
    # =========================================================================

    def test_outright_ban_kills_existing_session_token(self):
        """
        A session token issued before the ban is rejected because the ban
        deleted the session.
        """
        url = reverse('get_profile_details', kwargs={'username': self.local_username})
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        # Sanity check: the token works before the ban
        response = self.client.get(url, **header)
        self.assertEqual(response.status_code, 200)

        self._ban_user()

        response = self.client.get(url, **header)
        self.assertEqual(response.status_code, 401)

    def test_api_request_with_active_ban_returns_account_banned(self):
        """
        Even if a session somehow exists while the user is banned, the
        api_login_required gate rejects it with account_banned.
        """
        self._ban_user()

        # Recreate a session post-ban to exercise the gate itself.
        session = Session.objects.create(management_user=self.user, management_token=generate_management_token())

        url = reverse('get_profile_details', kwargs={'username': self.local_username})
        header = {'HTTP_AUTHORIZATION': f'Bearer {session.management_token}'}

        response = self.client.get(url, **header)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('error'), ACCOUNT_BANNED)

    def test_shadow_ban_does_not_block_api_requests(self):
        """
        A shadow-banned user's existing session keeps working.
        """
        self._ban_user(ban_type=BAN_TYPE_SHADOW)

        url = reverse('get_profile_details', kwargs={'username': self.local_username})
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        response = self.client.get(url, **header)

        self.assertEqual(response.status_code, 200)
