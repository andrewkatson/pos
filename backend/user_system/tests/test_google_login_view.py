"""Tests for Google sign-in (issue #10).

`verify_google_id_token` is patched throughout: it is the only part of the flow
that talks to Google, and it has its own tests in test_google_auth.py. Patching
it here keeps every test about what the *endpoint* does with a set of claims.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from .test_constants import false, true
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    ACCOUNT_BANNED, BAN_TYPE_OUTRIGHT, Fields, GOOGLE_EMAIL_UNVERIFIED,
    GOOGLE_SIGN_IN_UNAVAILABLE, INVALID_GOOGLE_TOKEN, Patterns,
)
from ..google_auth import GoogleTokenError
from ..input_validator import is_valid_pattern
from ..models import UserBan

# A syntactically valid JWS compact serialization. The endpoint shape-checks the
# token before calling Google, so it has to look like a JWT even though the
# verification that would read it is patched out.
FAKE_ID_TOKEN = 'aaaaheader.bbbbpayloadbbbb.ccccsignature'

VERIFY_PATH = 'user_system.views.verify_google_id_token'
CLASSIFIER_PATH = 'user_system.views.text_classifier_class.is_text_positive'


def claims(sub='google-sub-1', email='hopefulperson@example.com', email_verified=True):
    return {'sub': sub, 'email': email, 'email_verified': email_verified}


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=['test-client-id.apps.googleusercontent.com'])
class GoogleLoginTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('login_user_google')

    def _sign_in(self, token_claims=None, remember_me=false, expect_status=200):
        """POST to login/google/ with `verify_google_id_token` stubbed to `token_claims`."""
        with patch(VERIFY_PATH, return_value=token_claims or claims()), \
                patch(CLASSIFIER_PATH) as classify:
            classify.return_value = True
            response = self.client.post(
                self.url,
                data={'id_token': FAKE_ID_TOKEN, 'remember_me': remember_me},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, expect_status, response.content)
        return response

    # =========================================================================
    # Creating an account
    # =========================================================================

    def test_first_sign_in_creates_an_account_and_a_session(self):
        response = self._sign_in()
        body = response.json()

        self.assertTrue(is_valid_pattern(body[Fields.session_management_token], Patterns.hex_token))
        self.assertTrue(body[Fields.created_account])
        self.assertIsNotNone(body[Fields.membership_number])

        user = get_user_model().objects.get(id=body[Fields.user_id])
        self.assertEqual(user.google_sub, 'google-sub-1')
        self.assertEqual(user.email, 'hopefulperson@example.com')
        # Google has already proven the address, so no verification email is
        # owed and the account is usable immediately.
        self.assertTrue(user.email_verified)
        self.assertIsNone(user.email_verification_token)

    def test_created_account_has_no_usable_password(self):
        """There is no password behind a Google account, so none can be guessed."""
        body = self._sign_in().json()
        user = get_user_model().objects.get(id=body[Fields.user_id])
        self.assertFalse(user.has_usable_password())

        # And the password login path agrees: it must not let anyone in.
        response = self.client.post(
            reverse('login_user'),
            data={'username_or_email': user.username, 'password': 'AnyPassword123', 'remember_me': false},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_created_account_matches_a_registration_with_no_date_of_birth(self):
        """No ID token carries a birthday, so the account is age-unverified."""
        body = self._sign_in().json()
        user = get_user_model().objects.get(id=body[Fields.user_id])
        self.assertFalse(user.identity_is_verified)
        self.assertFalse(user.is_adult)

    def test_username_is_generated_from_the_email_local_part(self):
        body = self._sign_in(claims(email='hopefulperson@example.com')).json()
        self.assertEqual(body[Fields.username], 'hopefulperson')

    def test_non_word_characters_are_stripped_from_the_generated_username(self):
        body = self._sign_in(claims(email='hopeful.person-42@example.com')).json()
        self.assertEqual(body[Fields.username], 'hopefulperson42')

    def test_short_local_part_is_padded_to_a_valid_username(self):
        """Usernames must be at least 10 word characters, so a short one grows."""
        body = self._sign_in(claims(email='amy@example.com')).json()
        username = body[Fields.username]
        self.assertTrue(username.startswith('amy'))
        self.assertTrue(is_valid_pattern(username, Patterns.alphanumeric))

    def test_taken_username_gets_a_suffix_instead_of_failing(self):
        taken = 'hopefulperson'
        self._register_user(taken, 'someoneelse@example.com', f'Password_{self.prefix}123-')

        body = self._sign_in(claims(email='hopefulperson@example.com')).json()
        self.assertNotEqual(body[Fields.username], taken)
        self.assertTrue(body[Fields.username].startswith(taken))

    def test_non_positive_local_part_falls_back_to_a_neutral_username(self):
        """A name the user never chose must not be what stops them signing up."""
        with patch(VERIFY_PATH, return_value=claims(email='negativeperson@example.com')), \
                patch(CLASSIFIER_PATH, return_value=False):
            response = self.client.post(
                self.url,
                data={'id_token': FAKE_ID_TOKEN, 'remember_me': false},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()[Fields.username].startswith('friend'))

    def test_classifier_failure_does_not_block_the_sign_in(self):
        with patch(VERIFY_PATH, return_value=claims()), \
                patch(CLASSIFIER_PATH, side_effect=RuntimeError('classifier is down')):
            response = self.client.post(
                self.url,
                data={'id_token': FAKE_ID_TOKEN, 'remember_me': false},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()[Fields.username].startswith('friend'))

    # =========================================================================
    # Signing back in
    # =========================================================================

    def test_second_sign_in_reuses_the_same_account(self):
        first = self._sign_in().json()
        second = self._sign_in().json()

        self.assertEqual(first[Fields.user_id], second[Fields.user_id])
        self.assertFalse(second[Fields.created_account])
        self.assertNotIn(Fields.membership_number, second)
        self.assertNotEqual(first[Fields.session_management_token], second[Fields.session_management_token])
        self.assertEqual(get_user_model().objects.filter(google_sub='google-sub-1').count(), 1)

    def test_a_changed_email_still_finds_the_account_by_its_google_sub(self):
        """`sub` is the join key precisely because an address can change."""
        first = self._sign_in().json()
        second = self._sign_in(claims(email='renamedmailbox@example.com')).json()
        self.assertEqual(first[Fields.user_id], second[Fields.user_id])

    def test_remember_me_returns_cookie_tokens(self):
        body = self._sign_in(remember_me=true).json()
        self.assertIn(Fields.series_identifier, body)
        self.assertIn(Fields.login_cookie_token, body)

    def test_session_response_is_not_cached(self):
        response = self._sign_in()
        self.assertEqual(response['Cache-Control'], 'no-store')

    # =========================================================================
    # Linking to an existing password account
    # =========================================================================

    def test_matching_verified_email_links_to_the_existing_account(self):
        registered = self._register_user(
            self._get_unique_username('linkme'), 'sharedaddress@example.com', f'Password_{self.prefix}123-'
        )

        body = self._sign_in(claims(email='sharedaddress@example.com')).json()

        self.assertEqual(body[Fields.user_id], registered[Fields.user_id])
        self.assertFalse(body[Fields.created_account])
        user = get_user_model().objects.get(id=registered[Fields.user_id])
        self.assertEqual(user.google_sub, 'google-sub-1')
        # Linking must not create a second account for the same person.
        self.assertEqual(get_user_model().objects.filter(email__iexact='sharedaddress@example.com').count(), 1)

    def test_linking_matches_the_email_case_insensitively(self):
        registered = self._register_user(
            self._get_unique_username('linkcase'), 'MixedCase@Example.com', f'Password_{self.prefix}123-'
        )

        body = self._sign_in(claims(email='mixedcase@example.com')).json()
        self.assertEqual(body[Fields.user_id], registered[Fields.user_id])

    def test_linking_verifies_an_account_still_waiting_on_its_email_link(self):
        registered = self._register_user(
            self._get_unique_username('unverified'), 'notyetclicked@example.com',
            f'Password_{self.prefix}123-', verify_email=False,
        )
        unverified = get_user_model().objects.get(id=registered[Fields.user_id])
        self.assertFalse(unverified.email_verified)

        self._sign_in(claims(email='notyetclicked@example.com'))

        unverified.refresh_from_db()
        self.assertTrue(unverified.email_verified)
        self.assertIsNone(unverified.email_verification_token)

    def test_password_still_works_after_linking(self):
        """Linking adds a way in; it never takes the original one away."""
        password = f'Password_{self.prefix}123-'
        username = self._get_unique_username('bothways')
        self._register_user(username, 'bothways@example.com', password)

        self._sign_in(claims(email='bothways@example.com'))

        self._login_user(username, password)

    def test_ambiguous_email_is_refused_rather_than_linked_arbitrarily(self):
        """Nothing enforces email uniqueness, so two rows can hold one address."""
        password = f'Password_{self.prefix}123-'
        self._register_user(self._get_unique_username('dupea'), 'duplicate@example.com', password)
        self._register_user(self._get_unique_username('dupeb'), 'Duplicate@example.com', password)

        self._sign_in(claims(email='duplicate@example.com'), expect_status=409)
        self.assertFalse(get_user_model().objects.filter(google_sub='google-sub-1').exists())

    # =========================================================================
    # Refusals
    # =========================================================================

    def test_banned_account_is_refused(self):
        body = self._sign_in().json()
        user = get_user_model().objects.get(id=body[Fields.user_id])
        UserBan.objects.create(user=user, ban_type=BAN_TYPE_OUTRIGHT, reason='Testing')

        response = self._sign_in(expect_status=403)
        self.assertEqual(response.json()['error'], ACCOUNT_BANNED)

    def test_two_factor_enrolled_account_gets_a_challenge_not_a_session(self):
        """Holding the Google account is a first factor, not a bypass of the second."""
        body = self._sign_in().json()
        get_user_model().objects.filter(id=body[Fields.user_id]).update(
            totp_enabled=True, totp_secret='ABCDEFGHIJKLMNOP',
        )

        second = self._sign_in().json()
        self.assertTrue(second[Fields.two_factor_required])
        self.assertNotIn(Fields.session_management_token, second)
        self.assertTrue(is_valid_pattern(second[Fields.challenge_token], Patterns.hex_token))

    def test_unverified_google_email_is_refused(self):
        response = self._sign_in(claims(email_verified=False), expect_status=403)
        self.assertEqual(response.json()['error'], GOOGLE_EMAIL_UNVERIFIED)
        self.assertFalse(get_user_model().objects.filter(google_sub='google-sub-1').exists())

    def test_unverifiable_token_is_refused(self):
        with patch(VERIFY_PATH, side_effect=GoogleTokenError('bad signature')):
            response = self.client.post(
                self.url,
                data={'id_token': FAKE_ID_TOKEN, 'remember_me': false},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], INVALID_GOOGLE_TOKEN)

    def test_malformed_token_is_rejected_before_google_is_asked(self):
        with patch(VERIFY_PATH) as verify:
            response = self.client.post(
                self.url,
                data={'id_token': 'not-a-jwt', 'remember_me': false},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 400)
        verify.assert_not_called()

    def test_missing_token_is_rejected(self):
        response = self.client.post(self.url, data={'remember_me': false}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_remember_me_is_rejected(self):
        response = self.client.post(
            self.url,
            data={'id_token': FAKE_ID_TOKEN, 'remember_me': 'perhaps'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_omitted_remember_me_defaults_to_not_remembering(self):
        with patch(VERIFY_PATH, return_value=claims()), patch(CLASSIFIER_PATH, return_value=True):
            response = self.client.post(
                self.url, data={'id_token': FAKE_ID_TOKEN}, content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(Fields.login_cookie_token, response.json())

    def test_invalid_json_is_rejected(self):
        response = self.client.post(self.url, data='{oops', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[])
class GoogleLoginNotConfiguredTests(PositiveOnlySocialTestCase):
    """With no OAuth client IDs there is no audience to trust, so the door is shut."""

    def test_endpoint_reports_that_google_sign_in_is_unavailable(self):
        with patch(VERIFY_PATH) as verify:
            response = self.client.post(
                reverse('login_user_google'),
                data={'id_token': FAKE_ID_TOKEN, 'remember_me': false},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error'], GOOGLE_SIGN_IN_UNAVAILABLE)
        verify.assert_not_called()
