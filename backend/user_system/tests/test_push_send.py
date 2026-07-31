from unittest.mock import patch

from django.test import TestCase

from .. import push
from ..constants import (
    DEVICE_PLATFORM_IOS, DEVICE_PLATFORM_ANDROID, DEVICE_PLATFORM_WEB,
    PUSH_TYPE_POST_REJECTED,
)
from ..models import DeviceToken, PositiveOnlySocialUser

APNS = 'user_system.push._send_apns'
FCM = 'user_system.push._send_fcm'

PAYLOAD = {'title': 't', 'body': 'b', 'data': {'type': PUSH_TYPE_POST_REJECTED}}


class SendPushFanOutTests(TestCase):
    """send_push routes tokens to the right provider and prunes dead ones (#342)."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='pusher', email='pusher@test.com', password='x')

    def _add(self, platform, token, user=None):
        return DeviceToken.objects.create(user=user or self.user, platform=platform, token=token)

    @patch(FCM, return_value=[])
    @patch(APNS, return_value=[])
    def test_fans_out_ios_to_apns_and_android_web_to_fcm(self, apns, fcm):
        self._add(DEVICE_PLATFORM_IOS, 'ios-1')
        self._add(DEVICE_PLATFORM_ANDROID, 'android-1')
        self._add(DEVICE_PLATFORM_WEB, 'web-1')

        push.send_push(self.user, PAYLOAD)

        apns.assert_called_once()
        self.assertEqual(sorted(apns.call_args.args[0]), ['ios-1'])
        fcm.assert_called_once()
        self.assertEqual(sorted(fcm.call_args.args[0]), ['android-1', 'web-1'])

    @patch(FCM)
    @patch(APNS)
    def test_no_tokens_calls_no_provider(self, apns, fcm):
        push.send_push(self.user, PAYLOAD)
        apns.assert_not_called()
        fcm.assert_not_called()

    @patch(FCM, return_value=[])
    @patch(APNS, return_value=[])
    def test_only_calls_provider_for_platforms_present(self, apns, fcm):
        self._add(DEVICE_PLATFORM_IOS, 'ios-only')
        push.send_push(self.user, PAYLOAD)
        apns.assert_called_once()
        fcm.assert_not_called()

    @patch(FCM, return_value=['android-dead'])
    @patch(APNS, return_value=['ios-dead'])
    def test_prunes_dead_tokens_reported_by_providers(self, apns, fcm):
        self._add(DEVICE_PLATFORM_IOS, 'ios-dead')
        self._add(DEVICE_PLATFORM_IOS, 'ios-live')
        self._add(DEVICE_PLATFORM_ANDROID, 'android-dead')
        self._add(DEVICE_PLATFORM_ANDROID, 'android-live')

        push.send_push(self.user, PAYLOAD)

        remaining = set(DeviceToken.objects.values_list('token', flat=True))
        self.assertEqual(remaining, {'ios-live', 'android-live'})

    @patch(FCM, return_value=[])
    @patch(APNS, return_value=['ios-dead'])
    def test_pruning_is_scoped_to_the_user(self, apns, fcm):
        """A dead token is only removed for the user we sent to; an identical
        string is never registered to two accounts, but the delete is scoped to
        be safe regardless."""
        other = PositiveOnlySocialUser.objects.create_user(
            username='bystander', email='by@test.com', password='x')
        self._add(DEVICE_PLATFORM_IOS, 'ios-dead')
        self._add(DEVICE_PLATFORM_ANDROID, 'other-live', user=other)

        push.send_push(self.user, PAYLOAD)

        self.assertFalse(DeviceToken.objects.filter(token='ios-dead').exists())
        self.assertTrue(DeviceToken.objects.filter(token='other-live').exists())

    @patch(FCM, return_value=['android-dead'])
    @patch(APNS, side_effect=RuntimeError('apns down'))
    def test_one_provider_failing_does_not_block_the_other(self, apns, fcm):
        """APNs raising is swallowed; FCM still runs and its dead token is
        still pruned. Push is best-effort — a provider outage never propagates."""
        self._add(DEVICE_PLATFORM_IOS, 'ios-live')
        self._add(DEVICE_PLATFORM_ANDROID, 'android-dead')

        push.send_push(self.user, PAYLOAD)  # must not raise

        fcm.assert_called_once()
        self.assertFalse(DeviceToken.objects.filter(token='android-dead').exists())
        self.assertTrue(DeviceToken.objects.filter(token='ios-live').exists())


class UnconfiguredProviderTests(TestCase):
    """With no credentials set, each provider send is a no-op that prunes
    nothing — the real (lazy-imported) provider code path, not a mock."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='noconf', email='noconf@test.com', password='x')

    def test_apns_unconfigured_returns_empty(self):
        with self.settings(APNS_AUTH_KEY='', APNS_AUTH_KEY_PATH='', APNS_KEY_ID='',
                           APNS_TEAM_ID='', APNS_TOPIC=''):
            self.assertEqual(push._send_apns(['tok'], PAYLOAD), [])

    def test_fcm_unconfigured_returns_empty(self):
        with self.settings(FCM_CREDENTIALS='', FCM_CREDENTIALS_PATH=''):
            self.assertEqual(push._send_fcm(['tok'], PAYLOAD), [])

    def test_send_push_with_unconfigured_providers_keeps_tokens(self):
        DeviceToken.objects.create(user=self.user, platform=DEVICE_PLATFORM_IOS, token='keep-me')
        with self.settings(APNS_AUTH_KEY='', APNS_AUTH_KEY_PATH='', APNS_KEY_ID='',
                           APNS_TEAM_ID='', APNS_TOPIC='', FCM_CREDENTIALS='', FCM_CREDENTIALS_PATH=''):
            push.send_push(self.user, PAYLOAD)
        self.assertTrue(DeviceToken.objects.filter(token='keep-me').exists())


class RejectionPayloadTests(TestCase):
    """build_rejection_payload carries the client deep-link contract (#343)."""

    def setUp(self):
        super().setUp()
        self.user = PositiveOnlySocialUser.objects.create_user(
            username='author', email='author@test.com', password='x')
        self.post = self.user.post_set.create(caption='hi')

    def test_appealable_payload(self):
        payload = push.build_rejection_payload(self.post, final=False)
        self.assertEqual(payload['data']['type'], PUSH_TYPE_POST_REJECTED)
        self.assertEqual(payload['data']['post_identifier'], str(self.post.post_identifier))
        # data values are strings (FCM constraint), so appealable is "true"/"false".
        self.assertEqual(payload['data']['appealable'], 'true')
        self.assertIn(f'/post/{self.post.post_identifier}', payload['data']['deep_link'])

    def test_final_payload_is_not_appealable(self):
        payload = push.build_rejection_payload(self.post, final=True)
        self.assertEqual(payload['data']['appealable'], 'false')

    def test_all_data_values_are_strings(self):
        """FCM's data map only carries strings; the contract is uniform so
        clients parse the same shape from both providers."""
        payload = push.build_rejection_payload(self.post, final=False)
        for key, value in payload['data'].items():
            self.assertIsInstance(value, str, f"{key} must be a string")
