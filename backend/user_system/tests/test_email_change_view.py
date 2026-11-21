import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import EMAIL_IN_USE, Fields, GOOGLE_SIGN_IN_UNAVAILABLE, REAUTHENTICATION_REQUIRED
from .. import views
from ..google_auth import GoogleTokenError
from ..models import Session

CHANGE_LINK_RE = re.compile(r"/verify-email-change\?token=([A-Za-z0-9_-]{43})")
VERIFY_PATH = 'user_system.views.verify_google_id_token'
FAKE_ID_TOKEN = 'aaaaheader.bbbbpayloadbbbb.ccccsignature'


class EmailChangeTests(PositiveOnlySocialTestCase):
    """Changing the registered email (issue #594): POST /me/email/ stores the
    new address as pending and mails it a link; POST /verify-email-change/
    swaps it in; POST /me/email/cancel/ withdraws it."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.user = get_user_model().objects.get(username=self.local_username)
        self.new_email = 'brand.new.address@example.com'
        mail.outbox.clear()

    def _request(self, body, header=None):
        return self.client.post(reverse('request_email_change'), data=body, content_type='application/json',
                                **(header if header is not None else self.header))

    def _request_with_password(self, email=None):
        return self._request({Fields.email: email or self.new_email, Fields.password: self.local_password})

    def _token_from_outbox(self):
        match = CHANGE_LINK_RE.search(mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _confirm(self, token):
        return self.client.post(reverse('confirm_email_change'), data={Fields.verification_token: token},
                                content_type='application/json')

    # -- requesting ------------------------------------------------------------

    def test_request_stores_pending_and_mails_the_new_address(self):
        response = self._request_with_password()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.pending_email], self.new_email)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, self.local_email)
        self.assertEqual(self.user.pending_email, self.new_email)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.new_email])
        # Only the token's hash is stored.
        self.assertNotEqual(self.user.pending_email_token, self._token_from_outbox())

    def test_me_reports_pending_email_and_has_password(self):
        me = self.client.get(reverse('get_current_user'), **self.header).json()
        self.assertIsNone(me[Fields.pending_email])
        self.assertTrue(me[Fields.has_password])
        self._request_with_password()
        me = self.client.get(reverse('get_current_user'), **self.header).json()
        self.assertEqual(me[Fields.pending_email], self.new_email)
        self.assertEqual(me[Fields.email], self.local_email)

    def test_missing_password_is_refused(self):
        response = self._request({Fields.email: self.new_email})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], REAUTHENTICATION_REQUIRED)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.pending_email)
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_password_is_refused(self):
        response = self._request({Fields.email: self.new_email, Fields.password: 'WrongPassword123-'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], REAUTHENTICATION_REQUIRED)

    def test_invalid_email_is_refused(self):
        for bad in ['not-an-email', '', 42, None, ('a' * 250) + '@example.com']:
            with self.subTest(bad=bad):
                response = self._request({Fields.email: bad, Fields.password: self.local_password})
                self.assertEqual(response.status_code, 400)

    def test_same_email_is_refused_ignoring_case(self):
        response = self._request_with_password(self.local_email.upper())
        self.assertEqual(response.status_code, 400)

    def test_address_of_another_account_is_refused_ignoring_case(self):
        other = self._get_unique_username('otheremailer')
        self.make_user(other)
        other_email = get_user_model().objects.get(username=other).email
        response = self._request_with_password(other_email.upper())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], EMAIL_IN_USE)

    def test_requires_session(self):
        response = self._request({Fields.email: self.new_email, Fields.password: self.local_password}, header={})
        self.assertEqual(response.status_code, 401)

    def test_second_request_replaces_the_first(self):
        self._request_with_password()
        first_token = self._token_from_outbox()
        self._request_with_password('second.choice@example.com')
        self.assertEqual(self._confirm(first_token).status_code, 400)
        self.assertEqual(self._confirm(self._token_from_outbox()).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'second.choice@example.com')

    # -- confirming ------------------------------------------------------------

    def test_confirm_swaps_the_address_and_notifies_the_old_one(self):
        self._request_with_password()
        token = self._token_from_outbox()
        mail.outbox.clear()
        response = self._confirm(token)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, self.new_email)
        self.assertIsNone(self.user.pending_email)
        self.assertIsNone(self.user.pending_email_token)
        self.assertTrue(self.user.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.local_email])

    def test_confirm_needs_no_session(self):
        self._request_with_password()
        token = self._token_from_outbox()
        self.client.logout()
        self.assertEqual(self._confirm(token).status_code, 200)

    def test_token_is_single_use(self):
        self._request_with_password()
        token = self._token_from_outbox()
        self.assertEqual(self._confirm(token).status_code, 200)
        self.assertEqual(self._confirm(token).status_code, 400)

    def test_expired_token_is_refused(self):
        self._request_with_password()
        token = self._token_from_outbox()
        get_user_model().objects.filter(pk=self.user.pk).update(
            pending_email_token_expires=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self._confirm(token).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, self.local_email)

    def test_malformed_token_is_refused(self):
        for bad in ['short', 'x' * 43 + '!', None, 7]:
            with self.subTest(bad=bad):
                self.assertEqual(self._confirm(bad).status_code, 400)

    def test_address_taken_since_the_request_is_refused_and_cleared(self):
        self._request_with_password()
        token = self._token_from_outbox()
        other = self._get_unique_username('quickerperson')
        self.make_user(other)
        get_user_model().objects.filter(username=other).update(email=self.new_email.upper())
        response = self._confirm(token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], EMAIL_IN_USE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, self.local_email)
        self.assertIsNone(self.user.pending_email)

    def test_confirm_voids_an_outstanding_password_reset(self):
        get_user_model().objects.filter(pk=self.user.pk).update(
            reset_token='a' * 64, reset_token_expires=timezone.now() + timedelta(hours=1))
        self._request_with_password()
        self._confirm(self._token_from_outbox())
        self.user.refresh_from_db()
        self.assertIsNone(self.user.reset_token)

    def test_login_with_the_new_address(self):
        self._request_with_password()
        self._confirm(self._token_from_outbox())
        response = self.client.post(reverse('login_user'), data={
            Fields.username_or_email: self.new_email, Fields.password: self.local_password,
            Fields.remember_me: 'false'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)

    # -- cancelling ------------------------------------------------------------

    def test_cancel_clears_pending_and_kills_the_link(self):
        self._request_with_password()
        token = self._token_from_outbox()
        response = self.client.post(reverse('cancel_email_change'), **self.header)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.pending_email)
        self.assertEqual(self._confirm(token).status_code, 400)

    def test_cancel_requires_session(self):
        self.assertEqual(self.client.post(reverse('cancel_email_change')).status_code, 401)


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=['test-client-id.apps.googleusercontent.com'])
class GoogleOnlyEmailChangeTests(PositiveOnlySocialTestCase):
    """A Google-only account has no password to re-enter, so it proves itself
    with a fresh Google ID token for the Google account already linked to it."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        user = get_user_model().objects.get(username=self.local_username)
        user.set_unusable_password()
        user.google_sub = 'linked-sub'
        user.save()
        self.body = {Fields.email: 'google.change@example.com', Fields.id_token: FAKE_ID_TOKEN}

    def _claims(self, sub):
        return {'sub': sub, 'email': 'whatever@example.com', 'email_verified': True}

    def _request(self, body):
        return self.client.post(reverse('request_email_change'), data=body, content_type='application/json',
                                **self.header)

    def test_me_reports_no_password(self):
        me = self.client.get(reverse('get_current_user'), **self.header).json()
        self.assertFalse(me[Fields.has_password])

    def test_token_for_the_linked_google_account_is_accepted(self):
        with patch(VERIFY_PATH, return_value=self._claims('linked-sub')):
            response = self._request(self.body)
        self.assertEqual(response.status_code, 200)

    def test_token_for_another_google_account_is_refused(self):
        with patch(VERIFY_PATH, return_value=self._claims('someone-else')):
            response = self._request(self.body)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], REAUTHENTICATION_REQUIRED)

    def test_unverifiable_token_is_refused(self):
        with patch(VERIFY_PATH, side_effect=GoogleTokenError('bad')):
            response = self._request(self.body)
        self.assertEqual(response.json()['error'], REAUTHENTICATION_REQUIRED)

    def test_missing_token_is_refused(self):
        response = self._request({Fields.email: 'google.change@example.com'})
        self.assertEqual(response.json()['error'], REAUTHENTICATION_REQUIRED)

    def test_a_password_is_no_substitute(self):
        response = self._request({Fields.email: 'google.change@example.com', Fields.password: 'Anything123-'})
        self.assertEqual(response.json()['error'], REAUTHENTICATION_REQUIRED)

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=[])
    def test_unconfigured_google_is_reported(self):
        response = self._request(self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error'], GOOGLE_SIGN_IN_UNAVAILABLE)


class EmailChangeReviewFixTests(PositiveOnlySocialTestCase):
    """Follow-ups from review of issue #594: the proof is judged against the
    locked row, a revoked session can't finish a request, and confirming voids
    both stages of a password reset."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.user = get_user_model().objects.get(username=self.local_username)
        mail.outbox.clear()

    def _request(self):
        return self.client.post(reverse('request_email_change'), data={
            Fields.email: 'fresh@example.com', Fields.password: self.local_password},
            content_type='application/json', **self.header)

    def _mid_request(self, action):
        """Run `action` after authentication but before the row lock, by riding
        on the token generation that sits between them."""
        real = views.secrets.token_urlsafe

        def side_effect(n):
            action()
            return real(n)
        return patch.object(views.secrets, 'token_urlsafe', side_effect=side_effect)

    def test_password_changed_mid_request_invalidates_the_old_one(self):
        def change_password():
            user = get_user_model().objects.get(pk=self.user.pk)
            user.set_password('SomethingElse123-')
            user.save(update_fields=['password'])
        with self._mid_request(change_password):
            response = self._request()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], REAUTHENTICATION_REQUIRED)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.pending_email)

    def test_session_revoked_mid_request_is_refused(self):
        with self._mid_request(lambda: Session.objects.filter(management_user=self.user).delete()):
            response = self._request()
        self.assertEqual(response.status_code, 401)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.pending_email)
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_voids_the_emailed_reset_code_too(self):
        get_user_model().objects.filter(pk=self.user.pk).update(
            verification_token='b' * 64, verification_token_expires=timezone.now() + timedelta(hours=1))
        self._request()
        token = CHANGE_LINK_RE.search(mail.outbox[-1].body).group(1)
        self.client.post(reverse('confirm_email_change'), data={Fields.verification_token: token},
                         content_type='application/json')
        self.user.refresh_from_db()
        self.assertIsNone(self.user.verification_token)
        self.assertIsNone(self.user.verification_token_expires)
