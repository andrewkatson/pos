from django.contrib.auth import get_user_model
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields


class GetCurrentUserTests(PositiveOnlySocialTestCase):
    """GET /me/ returns the signed-in account's own username and email
    (issues #194/#197)."""

    def setUp(self):
        super().setUp()
        # Registers one user and populates self.local_username / _email / token.
        super().register_user_and_setup_local_fields()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def test_returns_own_username_and_email(self):
        url = reverse('get_current_user')
        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[Fields.username], self.local_username)
        self.assertEqual(data[Fields.email], self.local_email)

    def test_reports_the_accepted_policy_version(self):
        # Clients skip the privacy policy re-accept prompt (issue #620) when
        # this is not older than the version they bundle; null means nothing
        # is on record, so they ask.
        url = reverse('get_current_user')
        self.assertIsNone(self.client.get(url, **self.valid_header).json()[Fields.policies_accepted_version])

        user = get_user_model().objects.get(username=self.local_username)
        user.policies_accepted_version = '2026-11-22'
        user.save(update_fields=['policies_accepted_version'])

        data = self.client.get(url, **self.valid_header).json()
        self.assertEqual(data[Fields.policies_accepted_version], '2026-11-22')

    def test_response_is_not_cacheable(self):
        # The body carries the account's email, so it must not be cached by
        # intermediary proxies or browsers.
        url = reverse('get_current_user')
        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_missing_token_is_rejected(self):
        url = reverse('get_current_user')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_is_rejected(self):
        url = reverse('get_current_user')
        response = self.client.get(url, HTTP_AUTHORIZATION='Bearer ?')
        self.assertEqual(response.status_code, 401)

    def test_only_get_is_allowed(self):
        url = reverse('get_current_user')
        response = self.client.post(url, **self.valid_header)
        self.assertEqual(response.status_code, 405)
