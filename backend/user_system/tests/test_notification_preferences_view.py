from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import PUSH_TYPE_POST_REJECTED
from ..models import NotificationPreference


class NotificationPreferencesViewTests(PositiveOnlySocialTestCase):
    """GET/POST /notifications/preferences/ — the Settings toggles (#342/#343)."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.token = self.session_management_token
        self.url = reverse('notification_preferences')

    def _auth(self):
        return {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}

    def _get(self):
        return self.client.get(self.url, **self._auth())

    def _post(self, body):
        return self.client.post(self.url, data=body, content_type='application/json', **self._auth())

    def test_get_lists_known_types_enabled_by_default(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        prefs = response.json()['preferences']
        # Every known type is present, defaulting to enabled.
        types = {p['type']: p for p in prefs}
        self.assertIn(PUSH_TYPE_POST_REJECTED, types)
        row = types[PUSH_TYPE_POST_REJECTED]
        self.assertTrue(row['enabled'])
        self.assertTrue(row['label'])  # a human-facing label for the toggle

    def test_post_disables_a_type_and_get_reflects_it(self):
        response = self._post({'type': PUSH_TYPE_POST_REJECTED, 'enabled': False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['enabled'])

        row = NotificationPreference.objects.get(notification_type=PUSH_TYPE_POST_REJECTED)
        self.assertFalse(row.enabled)

        prefs = {p['type']: p['enabled'] for p in self._get().json()['preferences']}
        self.assertFalse(prefs[PUSH_TYPE_POST_REJECTED])

    def test_post_is_idempotent_upsert(self):
        self._post({'type': PUSH_TYPE_POST_REJECTED, 'enabled': False})
        self._post({'type': PUSH_TYPE_POST_REJECTED, 'enabled': True})
        self.assertEqual(
            NotificationPreference.objects.filter(notification_type=PUSH_TYPE_POST_REJECTED).count(), 1)
        self.assertTrue(
            NotificationPreference.objects.get(notification_type=PUSH_TYPE_POST_REJECTED).enabled)

    def test_post_rejects_unknown_type(self):
        response = self._post({'type': 'not_a_real_type', 'enabled': False})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(NotificationPreference.objects.exists())

    def test_post_non_string_type_is_400_not_500(self):
        # A non-string (unhashable) type must not blow the set-membership check
        # into a 500.
        response = self._post({'type': ['x'], 'enabled': True})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(NotificationPreference.objects.exists())

    def test_post_rejects_non_boolean_enabled(self):
        response = self._post({'type': PUSH_TYPE_POST_REJECTED, 'enabled': 'yes'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(NotificationPreference.objects.exists())

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))
