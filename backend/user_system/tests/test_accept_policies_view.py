import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, POLICY_VERSION


class AcceptPoliciesTests(PositiveOnlySocialTestCase):
    """POST /policies/accept/ records a signed-in member's acceptance of the
    privacy policy re-accept prompt (issue #620), and GET /me/ reads it back."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('accept_policies')

    def _user(self):
        return get_user_model().objects.get(username=self.local_username)

    def _accept(self, body, **headers):
        return self.client.post(self.url, json.dumps(body), content_type='application/json',
                                **(headers or self.valid_header))

    def test_records_the_version_and_time(self):
        before = timezone.now()
        response = self._accept({Fields.policy_version: POLICY_VERSION})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {Fields.policies_accepted_version: POLICY_VERSION})
        user = self._user()
        self.assertEqual(user.policies_accepted_version, POLICY_VERSION)
        self.assertIsNotNone(user.policies_accepted_time)
        self.assertGreaterEqual(user.policies_accepted_time, before)

    def test_existing_member_starts_with_nothing_on_record(self):
        # The gap this endpoint closes: accounts registered without the consent
        # fields (or before they existed) have both null until they accept.
        user = self._user()
        self.assertIsNone(user.policies_accepted_time)
        self.assertIsNone(user.policies_accepted_version)

    def test_records_the_clients_version_not_the_servers(self):
        # An app build from before a policy change bundles — and showed — the
        # older text, so that is what the member agreed to.
        response = self._accept({Fields.policy_version: '2026-01-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._user().policies_accepted_version, '2026-01-01')

    def test_accepting_again_overwrites_the_record(self):
        self._accept({Fields.policy_version: '2026-01-01'})
        user = self._user()
        user.policies_accepted_time = timezone.now() - timedelta(days=30)
        user.save(update_fields=['policies_accepted_time'])
        first_time = user.policies_accepted_time

        self._accept({Fields.policy_version: POLICY_VERSION})

        user = self._user()
        self.assertEqual(user.policies_accepted_version, POLICY_VERSION)
        self.assertGreater(user.policies_accepted_time, first_time)

    def test_missing_policy_version_is_a_validation_error(self):
        for body in ({}, {Fields.policy_version: None}):
            with self.subTest(body=body):
                response = self._accept(body)
                self.assertEqual(response.status_code, 400)
                self.assertIn('POLICY_VERSION', response.json()['error'])
        user = self._user()
        self.assertIsNone(user.policies_accepted_time)
        self.assertIsNone(user.policies_accepted_version)

    def test_malformed_policy_version_is_a_validation_error(self):
        # Same validation as register/ and login/google/.
        for bad in ('2026-11-2', '20261122', '2026-02-30', '0000-11-22', '2026-11-22\n', 20261122, True, ''):
            with self.subTest(policy_version=bad):
                response = self._accept({Fields.policy_version: bad})
                self.assertEqual(response.status_code, 400)
                self.assertIn('POLICY_VERSION', response.json()['error'])
        self.assertIsNone(self._user().policies_accepted_time)

    def test_invalid_json_is_rejected(self):
        for raw in ('not json', '[]', '"2026-11-22"'):
            with self.subTest(body=raw):
                response = self.client.post(self.url, raw, content_type='application/json', **self.valid_header)
                self.assertEqual(response.status_code, 400)
        self.assertIsNone(self._user().policies_accepted_time)

    def test_missing_token_is_rejected(self):
        response = self.client.post(self.url, json.dumps({Fields.policy_version: POLICY_VERSION}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_is_rejected(self):
        response = self._accept({Fields.policy_version: POLICY_VERSION}, HTTP_AUTHORIZATION='Bearer ?')
        self.assertEqual(response.status_code, 401)

    def test_only_post_is_allowed(self):
        response = self.client.get(self.url, **self.valid_header)
        self.assertEqual(response.status_code, 405)

    def test_banned_member_cannot_accept(self):
        with patch('user_system.views.has_active_outright_ban', return_value=True):
            response = self._accept({Fields.policy_version: POLICY_VERSION})
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self._user().policies_accepted_time)

    def test_me_reports_null_until_accepted_then_the_version(self):
        me = reverse('get_current_user')
        self.assertIsNone(self.client.get(me, **self.valid_header).json()[Fields.policies_accepted_version])

        self._accept({Fields.policy_version: POLICY_VERSION})

        self.assertEqual(self.client.get(me, **self.valid_header).json()[Fields.policies_accepted_version],
                         POLICY_VERSION)
