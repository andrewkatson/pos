import re
from datetime import timedelta

import pyotp
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .test_constants import false, true
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    Fields, Patterns, NUM_RECOVERY_CODES, TWO_FACTOR_MAX_ATTEMPTS,
    INVALID_TWO_FACTOR_CHALLENGE,
)
from ..input_validator import is_valid_pattern
from ..models import RecoveryCode, TwoFactorChallenge


class TwoFactorAuthTests(PositiveOnlySocialTestCase):
    """Tests for TOTP enrollment, the two-step login, recovery codes, and
    disabling two-factor authentication."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.setup_url = reverse('setup_totp')
        self.confirm_url = reverse('confirm_totp')
        self.disable_url = reverse('disable_totp')
        self.login_url = reverse('login_user')
        self.login_2fa_url = reverse('login_user_2fa')

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _user(self):
        return get_user_model().objects.get(username=self.local_username)

    def _reset_replay_guard(self):
        """Forget the last accepted TOTP time step.

        Tests run inside a single 30-second step, so consecutive verifications
        would otherwise be rejected as replays. Real logins are separated by
        minutes; the replay behaviour itself is covered explicitly below.
        """
        get_user_model().objects.filter(username=self.local_username).update(totp_last_used_step=None)

    def _setup_totp(self):
        response = self.client.post(self.setup_url, content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _enable_totp(self):
        """Runs setup + confirm. Returns (secret, recovery_codes)."""
        secret = self._setup_totp()[Fields.totp_secret]
        code = pyotp.TOTP(secret).now()
        response = self.client.post(self.confirm_url, data={Fields.totp_code: code},
                                    content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 200)
        self._reset_replay_guard()
        return secret, response.json()[Fields.recovery_codes]

    def _login_expect_challenge(self, remember_me=false):
        """Logs in with the password and asserts the 2FA challenge response."""
        data = {
            'username_or_email': self.local_username,
            'password': self.local_password,
            'remember_me': remember_me,
        }
        response = self.client.post(self.login_url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        fields = response.json()
        self.assertTrue(fields[Fields.two_factor_required])
        self.assertNotIn(Fields.session_management_token, fields)
        self.assertTrue(is_valid_pattern(fields[Fields.challenge_token], Patterns.hex_token))
        return fields[Fields.challenge_token]

    def _submit_2fa(self, challenge_token, totp_code=None, recovery_code=None):
        data = {Fields.challenge_token: challenge_token}
        if totp_code is not None:
            data[Fields.totp_code] = totp_code
        if recovery_code is not None:
            data[Fields.recovery_code] = recovery_code
        return self.client.post(self.login_2fa_url, data=data, content_type='application/json')

    # =========================================================================
    # ENROLLMENT
    # =========================================================================

    def test_setup_returns_secret_and_provisioning_uri(self):
        fields = self._setup_totp()

        self.assertTrue(re.fullmatch(r'[A-Z2-7]{32}', fields[Fields.totp_secret]))
        self.assertTrue(fields[Fields.otpauth_uri].startswith('otpauth://totp/'))

        user = self._user()
        self.assertEqual(user.totp_secret, fields[Fields.totp_secret])
        self.assertFalse(user.totp_enabled)

    def test_setup_requires_auth(self):
        response = self.client.post(self.setup_url, content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_setup_rejected_when_already_enabled(self):
        self._enable_totp()
        response = self.client.post(self.setup_url, content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 400)

    def test_confirm_with_valid_code_enables_and_returns_recovery_codes(self):
        secret, recovery_codes = self._enable_totp()

        user = self._user()
        self.assertTrue(user.totp_enabled)

        self.assertEqual(len(recovery_codes), NUM_RECOVERY_CODES)
        for code in recovery_codes:
            self.assertTrue(is_valid_pattern(code, Patterns.recovery_code))

        # Only hashes are stored, never the raw codes.
        stored = set(RecoveryCode.objects.filter(user=user).values_list('code_hash', flat=True))
        self.assertEqual(len(stored), NUM_RECOVERY_CODES)
        self.assertFalse(stored & set(recovery_codes))

    def test_confirm_with_wrong_code_does_not_enable(self):
        self._setup_totp()
        response = self.client.post(self.confirm_url, data={Fields.totp_code: '000000'},
                                    content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self._user().totp_enabled)

    def test_confirm_without_setup_returns_bad_response(self):
        response = self.client.post(self.confirm_url, data={Fields.totp_code: '123456'},
                                    content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 400)

    # =========================================================================
    # LOGIN CHALLENGE
    # =========================================================================

    def test_login_with_totp_enabled_returns_challenge_not_session(self):
        self._enable_totp()
        raw_challenge = self._login_expect_challenge()

        user = self._user()
        challenge = TwoFactorChallenge.objects.get(user=user)
        # Only the hash is stored.
        self.assertNotEqual(challenge.token_hash, raw_challenge)

    def test_login_without_totp_is_unchanged(self):
        # No enrollment: the classic single-step login response.
        data = {
            'username_or_email': self.local_username,
            'password': self.local_password,
            'remember_me': false,
        }
        response = self.client.post(self.login_url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        fields = response.json()
        self.assertIn(Fields.session_management_token, fields)
        self.assertNotIn(Fields.two_factor_required, fields)

    def test_login_2fa_with_valid_code_returns_session(self):
        secret, _ = self._enable_totp()
        challenge = self._login_expect_challenge()

        response = self._submit_2fa(challenge, totp_code=pyotp.TOTP(secret).now())

        self.assertEqual(response.status_code, 200)
        fields = response.json()
        self.assertTrue(is_valid_pattern(fields[Fields.session_management_token], Patterns.alphanumeric))
        self.assertEqual(fields[Fields.username], self.local_username)
        # The challenge is single-use.
        self.assertEqual(TwoFactorChallenge.objects.filter(user=self._user()).count(), 0)

    def test_login_2fa_with_remember_me_returns_cookie_fields(self):
        secret, _ = self._enable_totp()
        challenge = self._login_expect_challenge(remember_me=true)

        response = self._submit_2fa(challenge, totp_code=pyotp.TOTP(secret).now())

        self.assertEqual(response.status_code, 200)
        fields = response.json()
        self.assertIn(Fields.series_identifier, fields)
        self.assertIn(Fields.login_cookie_token, fields)

    def test_login_2fa_with_wrong_code_returns_bad_response(self):
        self._enable_totp()
        challenge = self._login_expect_challenge()

        response = self._submit_2fa(challenge, totp_code='000000')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(TwoFactorChallenge.objects.get(user=self._user()).failed_attempts, 1)

    def test_login_2fa_challenge_invalidated_after_max_attempts(self):
        secret, _ = self._enable_totp()
        challenge = self._login_expect_challenge()

        for attempt in range(TWO_FACTOR_MAX_ATTEMPTS - 1):
            self.assertEqual(self._submit_2fa(challenge, totp_code='000000').status_code, 400)
        self.assertEqual(self._submit_2fa(challenge, totp_code='000000').status_code, 429)

        # The challenge is gone: even the correct code is refused now.
        response = self._submit_2fa(challenge, totp_code=pyotp.TOTP(secret).now())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('error'), INVALID_TWO_FACTOR_CHALLENGE)

    def test_login_2fa_with_expired_challenge_returns_bad_response(self):
        secret, _ = self._enable_totp()
        challenge = self._login_expect_challenge()
        TwoFactorChallenge.objects.filter(user=self._user()).update(
            expires=timezone.now() - timedelta(minutes=1))

        response = self._submit_2fa(challenge, totp_code=pyotp.TOTP(secret).now())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('error'), INVALID_TWO_FACTOR_CHALLENGE)

    def test_login_2fa_rejects_code_replay(self):
        secret, _ = self._enable_totp()
        code = pyotp.TOTP(secret).now()

        challenge = self._login_expect_challenge()
        self.assertEqual(self._submit_2fa(challenge, totp_code=code).status_code, 200)

        # The same code within the same time step must not work twice.
        second_challenge = self._login_expect_challenge()
        self.assertEqual(self._submit_2fa(second_challenge, totp_code=code).status_code, 400)

    def test_login_2fa_with_unknown_challenge_returns_bad_response(self):
        self._enable_totp()
        response = self._submit_2fa('0' * 64, totp_code='123456')
        self.assertEqual(response.status_code, 400)

    def test_login_2fa_with_both_or_neither_code_kind_returns_bad_response(self):
        secret, recovery_codes = self._enable_totp()
        challenge = self._login_expect_challenge()

        both = self._submit_2fa(challenge, totp_code=pyotp.TOTP(secret).now(),
                                recovery_code=recovery_codes[0])
        self.assertEqual(both.status_code, 400)

        neither = self._submit_2fa(challenge)
        self.assertEqual(neither.status_code, 400)

    # =========================================================================
    # RECOVERY CODES
    # =========================================================================

    def test_login_2fa_with_recovery_code_is_single_use(self):
        _, recovery_codes = self._enable_totp()

        challenge = self._login_expect_challenge()
        self.assertEqual(self._submit_2fa(challenge, recovery_code=recovery_codes[0]).status_code, 200)

        used = RecoveryCode.objects.filter(user=self._user(), used_at__isnull=False)
        self.assertEqual(used.count(), 1)

        # A spent code is refused.
        second_challenge = self._login_expect_challenge()
        self.assertEqual(self._submit_2fa(second_challenge, recovery_code=recovery_codes[0]).status_code, 400)

        # An unspent one still works.
        self.assertEqual(self._submit_2fa(second_challenge, recovery_code=recovery_codes[1]).status_code, 200)

    # =========================================================================
    # TRUSTED DEVICES (REMEMBER ME)
    # =========================================================================

    def test_remember_me_login_skips_2fa(self):
        # A fresh user registered with remember_me so we hold a login cookie.
        username = self._get_unique_username('cookie_user')
        password = f'Password_{self.prefix}123-'
        register_fields = self._register_user(username, f'{username}@email.com', password, remember_me=true)
        header = {'HTTP_AUTHORIZATION': f'Bearer {register_fields[Fields.session_management_token]}'}

        # Enable TOTP for them.
        setup = self.client.post(self.setup_url, content_type='application/json', **header)
        secret = setup.json()[Fields.totp_secret]
        confirm = self.client.post(self.confirm_url, data={Fields.totp_code: pyotp.TOTP(secret).now()},
                                   content_type='application/json', **header)
        self.assertEqual(confirm.status_code, 200)

        # The remember-me flow exchanges the cookie for a new session with no
        # two-factor step: possession of the cookie is the trusted device.
        data = {
            Fields.session_management_token: register_fields[Fields.session_management_token],
            Fields.series_identifier: register_fields[Fields.series_identifier],
            Fields.login_cookie_token: register_fields[Fields.login_cookie_token],
        }
        response = self.client.post(reverse('login_user_with_remember_me'), data=data,
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        fields = response.json()
        self.assertIn(Fields.session_management_token, fields)
        self.assertNotIn(Fields.two_factor_required, fields)

    # =========================================================================
    # DISABLE
    # =========================================================================

    def test_disable_with_password_and_code_turns_2fa_off(self):
        secret, _ = self._enable_totp()

        data = {
            Fields.password: self.local_password,
            Fields.totp_code: pyotp.TOTP(secret).now(),
        }
        response = self.client.post(self.disable_url, data=data, content_type='application/json', **self.header)

        self.assertEqual(response.status_code, 200)
        user = self._user()
        self.assertFalse(user.totp_enabled)
        self.assertIsNone(user.totp_secret)
        self.assertEqual(RecoveryCode.objects.filter(user=user).count(), 0)

        # Login is single-step again.
        login_data = {
            'username_or_email': self.local_username,
            'password': self.local_password,
            'remember_me': false,
        }
        login_response = self.client.post(self.login_url, data=login_data, content_type='application/json')
        self.assertEqual(login_response.status_code, 200)
        self.assertIn(Fields.session_management_token, login_response.json())

    def test_disable_with_non_string_password_returns_bad_request(self):
        """A JSON number satisfies the coercing regex check, so without an
        explicit type check it would reach check_password and 500."""
        secret, _ = self._enable_totp()

        data = {
            Fields.password: 12345678,
            Fields.totp_code: pyotp.TOTP(secret).now(),
        }
        response = self.client.post(self.disable_url, data=data, content_type='application/json', **self.header)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self._user().totp_enabled)

    def test_disable_with_recovery_code_works(self):
        _, recovery_codes = self._enable_totp()

        data = {
            Fields.password: self.local_password,
            Fields.recovery_code: recovery_codes[0],
        }
        response = self.client.post(self.disable_url, data=data, content_type='application/json', **self.header)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._user().totp_enabled)

    def test_disable_with_wrong_password_is_refused(self):
        secret, _ = self._enable_totp()

        data = {
            Fields.password: 'WrongPassword123-',
            Fields.totp_code: pyotp.TOTP(secret).now(),
        }
        response = self.client.post(self.disable_url, data=data, content_type='application/json', **self.header)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self._user().totp_enabled)

    def test_disable_with_wrong_code_is_refused(self):
        self._enable_totp()

        data = {
            Fields.password: self.local_password,
            Fields.totp_code: '000000',
        }
        response = self.client.post(self.disable_url, data=data, content_type='application/json', **self.header)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self._user().totp_enabled)

    def test_disable_when_not_enabled_returns_bad_response(self):
        data = {
            Fields.password: self.local_password,
            Fields.totp_code: '123456',
        }
        response = self.client.post(self.disable_url, data=data, content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 400)
