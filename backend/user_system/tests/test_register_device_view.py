from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    DEVICE_PLATFORM_IOS, DEVICE_PLATFORM_ANDROID, MAX_DEVICE_TOKEN_LENGTH,
)
from ..models import DeviceToken, PositiveOnlySocialUser


class RegisterDeviceViewTests(PositiveOnlySocialTestCase):
    """POST /devices/register/ — authenticated upsert of a push token (#342)."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.token = self.session_management_token
        self.url = reverse('register_device')

    def _post(self, body, token=None):
        header = {'HTTP_AUTHORIZATION': f'Bearer {token or self.token}'}
        return self.client.post(self.url, data=body, content_type='application/json', **header)

    def test_registers_a_new_token(self):
        response = self._post({'platform': DEVICE_PLATFORM_IOS, 'token': 'abc123'})
        self.assertEqual(response.status_code, 200)
        rows = DeviceToken.objects.filter(token='abc123')
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.platform, DEVICE_PLATFORM_IOS)
        self.assertEqual(row.user.username, self.local_username)

    def test_reregistering_same_token_is_idempotent(self):
        self._post({'platform': DEVICE_PLATFORM_IOS, 'token': 'dupe'})
        self._post({'platform': DEVICE_PLATFORM_IOS, 'token': 'dupe'})
        self.assertEqual(DeviceToken.objects.filter(token='dupe').count(), 1)

    def test_reregistering_bumps_updated_at(self):
        """Re-registering refreshes updated_at so "last seen" stays meaningful
        for pruning/monitoring. Backdate the row, then re-register and assert the
        timestamp advanced (update_or_create re-adds auto_now fields to
        update_fields, so the upsert does bump it)."""
        self._post({'platform': DEVICE_PLATFORM_IOS, 'token': 'refresh'})
        row = DeviceToken.objects.get(token='refresh')
        past = timezone.now() - timedelta(hours=1)
        DeviceToken.objects.filter(pk=row.pk).update(updated_at=past)

        self._post({'platform': DEVICE_PLATFORM_IOS, 'token': 'refresh'})

        row.refresh_from_db()
        self.assertGreater(row.updated_at, past)

    def test_reregistering_token_repoints_it_to_the_new_user(self):
        """A device that changes accounts moves rather than duplicating: the
        (platform, token) row is repointed at whoever registers it last."""
        self._post({'platform': DEVICE_PLATFORM_IOS, 'token': 'moving'})

        other = self.make_user_with_prefix(prefix='second')
        response = self._post(
            {'platform': DEVICE_PLATFORM_IOS, 'token': 'moving'},
            token=other['session_management_token'])
        self.assertEqual(response.status_code, 200)

        rows = DeviceToken.objects.filter(token='moving')
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().user.username, other['username'])

    def test_same_token_on_two_platforms_are_distinct_rows(self):
        """Uniqueness is on (platform, token), so the identical string under a
        different platform is a separate device."""
        self._post({'platform': DEVICE_PLATFORM_IOS, 'token': 'shared'})
        self._post({'platform': DEVICE_PLATFORM_ANDROID, 'token': 'shared'})
        self.assertEqual(DeviceToken.objects.filter(token='shared').count(), 2)

    def test_token_is_stripped(self):
        self._post({'platform': DEVICE_PLATFORM_IOS, 'token': '  spaced  '})
        self.assertTrue(DeviceToken.objects.filter(token='spaced').exists())

    def test_rejects_unknown_platform(self):
        response = self._post({'platform': 'windows', 'token': 'abc'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DeviceToken.objects.exists())

    def test_rejects_missing_token(self):
        response = self._post({'platform': DEVICE_PLATFORM_IOS})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DeviceToken.objects.exists())

    def test_rejects_blank_token(self):
        response = self._post({'platform': DEVICE_PLATFORM_IOS, 'token': '   '})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DeviceToken.objects.exists())

    def test_rejects_oversized_token(self):
        response = self._post(
            {'platform': DEVICE_PLATFORM_IOS, 'token': 'x' * (MAX_DEVICE_TOKEN_LENGTH + 1)})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DeviceToken.objects.exists())

    def test_rejects_invalid_json(self):
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        response = self.client.post(self.url, data='not json', content_type='application/json', **header)
        self.assertEqual(response.status_code, 400)

    def test_requires_authentication(self):
        response = self.client.post(
            self.url, data={'platform': DEVICE_PLATFORM_IOS, 'token': 'abc'},
            content_type='application/json')
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(DeviceToken.objects.exists())

    def test_rejects_get(self):
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        response = self.client.get(self.url, **header)
        self.assertEqual(response.status_code, 405)
