"""Tests for the Google ID-token verification helper (issue #10).

`google.oauth2.id_token.verify_oauth2_token` does the cryptography and is
Google's to test; what matters here is that we hand it the right audience, treat
everything it rejects as one failure, and normalize the claims we pass on.
"""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from ..google_auth import GoogleTokenError, is_google_sign_in_configured, verify_google_id_token

VERIFY_OAUTH2_PATH = 'google.oauth2.id_token.verify_oauth2_token'

CLIENT_IDS = ['web.apps.googleusercontent.com', 'ios.apps.googleusercontent.com']


def google_claims(**overrides):
    payload = {
        'iss': 'https://accounts.google.com',
        'sub': '1234567890',
        'email': 'Someone@Example.com',
        'email_verified': True,
        'aud': CLIENT_IDS[0],
    }
    payload.update(overrides)
    return payload


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=CLIENT_IDS)
class VerifyGoogleIdTokenTests(SimpleTestCase):

    def test_every_configured_client_id_is_offered_as_an_acceptable_audience(self):
        """Each platform has its own OAuth client, so all of them must be accepted."""
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims()) as verify:
            verify_google_id_token('a.b.c')

        self.assertEqual(verify.call_args.kwargs['audience'], CLIENT_IDS)

    def test_claims_are_normalized(self):
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims()):
            result = verify_google_id_token('a.b.c')

        self.assertEqual(result, {
            'sub': '1234567890',
            # Lower-cased so it matches consistently against stored addresses.
            'email': 'someone@example.com',
            'email_verified': True,
        })

    def test_bare_accounts_google_com_issuer_is_accepted(self):
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims(iss='accounts.google.com')):
            self.assertEqual(verify_google_id_token('a.b.c')['sub'], '1234567890')

    def test_a_string_email_verified_claim_is_honoured(self):
        """Documented as a boolean, but Google has also serialized it as a string."""
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims(email_verified='true')):
            self.assertTrue(verify_google_id_token('a.b.c')['email_verified'])

        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims(email_verified='false')):
            self.assertFalse(verify_google_id_token('a.b.c')['email_verified'])

    def test_a_missing_email_verified_claim_is_not_verification(self):
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims(email_verified=None)):
            self.assertFalse(verify_google_id_token('a.b.c')['email_verified'])

    def test_an_unexpected_issuer_is_rejected(self):
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims(iss='accounts.evil.example')):
            with self.assertRaises(GoogleTokenError):
                verify_google_id_token('a.b.c')

    def test_claims_without_a_subject_are_rejected(self):
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims(sub=None)):
            with self.assertRaises(GoogleTokenError):
                verify_google_id_token('a.b.c')

    def test_claims_without_an_email_are_rejected(self):
        with patch(VERIFY_OAUTH2_PATH, return_value=google_claims(email=None)):
            with self.assertRaises(GoogleTokenError):
                verify_google_id_token('a.b.c')

    def test_anything_google_auth_raises_becomes_a_google_token_error(self):
        """A bad signature, a wrong audience and an unreachable Google all read alike."""
        for failure in (ValueError('Token has wrong audience'), RuntimeError('cert fetch failed')):
            with self.subTest(failure=failure):
                with patch(VERIFY_OAUTH2_PATH, side_effect=failure):
                    with self.assertRaises(GoogleTokenError):
                        verify_google_id_token('a.b.c')


class GoogleSignInConfigurationTests(SimpleTestCase):

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=[])
    def test_no_client_ids_means_the_feature_is_off(self):
        self.assertFalse(is_google_sign_in_configured())

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=CLIENT_IDS)
    def test_client_ids_turn_the_feature_on(self):
        self.assertTrue(is_google_sign_in_configured())

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=[])
    def test_verification_refuses_outright_when_unconfigured(self):
        """Without an audience to check, no token could ever be meaningful."""
        with patch(VERIFY_OAUTH2_PATH) as verify:
            with self.assertRaises(GoogleTokenError):
                verify_google_id_token('a.b.c')
        verify.assert_not_called()
