from unittest.mock import patch

from django.test import TestCase

from .. import push
from ..constants import (
    DEVICE_PLATFORM_IOS, DEVICE_PLATFORM_ANDROID, DEVICE_PLATFORM_WEB,
    PUSH_TYPE_POST_REJECTED,
)
from ..models import DeviceToken, NotificationPreference, PositiveOnlySocialUser

APNS = 'user_system.push._send_apns'
FCM = 'user_system.push._send_fcm'

PAYLOAD = {'title': 't', 'body': 'b', 'data': {'type': PUSH_TYPE_POST_REJECTED}}


class _FakeResponse:
    """Minimal stand-in for the provider HTTP responses the dead-token helpers
    inspect (status_code + json())."""
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class DeadTokenDetectionTests(TestCase):
    """Only an unambiguous "token no longer exists" signal prunes a row; a
    config/payload/topic error must never delete a live token (#342)."""

    def test_apns_dead_only_on_410(self):
        self.assertTrue(push._apns_token_is_dead(_FakeResponse(410, {})))

    def test_apns_not_dead_on_400_or_config_errors(self):
        # BadDeviceToken / DeviceTokenNotForTopic can be an env/topic misconfig
        # (sandbox vs prod), not a dead token, so a 400 must never prune.
        self.assertFalse(push._apns_token_is_dead(_FakeResponse(400, {'reason': 'BadDeviceToken'})))
        self.assertFalse(push._apns_token_is_dead(_FakeResponse(400, {'reason': 'DeviceTokenNotForTopic'})))
        self.assertFalse(push._apns_token_is_dead(_FakeResponse(403, {'reason': 'ExpiredProviderToken'})))

    def test_fcm_dead_only_on_explicit_unregistered(self):
        # FCM's real unregistered response carries both NOT_FOUND and the
        # UNREGISTERED detail; the detail is what we key on.
        self.assertTrue(push._fcm_token_is_dead(_FakeResponse(
            404, {'error': {'status': 'NOT_FOUND', 'details': [{'errorCode': 'UNREGISTERED'}]}})))

    def test_fcm_not_dead_without_unregistered_detail(self):
        # A bare 404, or a NOT_FOUND status with no UNREGISTERED detail (a wrong
        # project_id/URL), or INVALID_ARGUMENT must never prune — else a config
        # mistake would wipe every token.
        self.assertFalse(push._fcm_token_is_dead(_FakeResponse(404, {})))
        self.assertFalse(push._fcm_token_is_dead(_FakeResponse(404, {'error': {'status': 'NOT_FOUND'}})))
        self.assertFalse(push._fcm_token_is_dead(_FakeResponse(
            400, {'error': {'status': 'INVALID_ARGUMENT'}})))


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

        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)

        apns.assert_called_once()
        self.assertEqual(sorted(apns.call_args.args[0]), ['ios-1'])
        fcm.assert_called_once()
        self.assertEqual(sorted(fcm.call_args.args[0]), ['android-1', 'web-1'])

    @patch(FCM)
    @patch(APNS)
    def test_no_tokens_calls_no_provider(self, apns, fcm):
        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)
        apns.assert_not_called()
        fcm.assert_not_called()

    @patch(FCM, return_value=[])
    @patch(APNS, return_value=[])
    def test_only_calls_provider_for_platforms_present(self, apns, fcm):
        self._add(DEVICE_PLATFORM_IOS, 'ios-only')
        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)
        apns.assert_called_once()
        fcm.assert_not_called()

    @patch(FCM)
    @patch(APNS)
    def test_disabled_type_is_not_sent(self, apns, fcm):
        """A type the user has toggled off in Settings is skipped entirely — no
        provider is even contacted."""
        self._add(DEVICE_PLATFORM_IOS, 'ios-1')
        NotificationPreference.objects.create(
            user=self.user, notification_type=PUSH_TYPE_POST_REJECTED, enabled=False)

        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)

        apns.assert_not_called()
        fcm.assert_not_called()

    @patch(FCM, return_value=[])
    @patch(APNS, return_value=[])
    def test_reenabled_type_is_sent(self, apns, fcm):
        self._add(DEVICE_PLATFORM_IOS, 'ios-1')
        NotificationPreference.objects.create(
            user=self.user, notification_type=PUSH_TYPE_POST_REJECTED, enabled=True)

        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)

        apns.assert_called_once()

    @patch(FCM, return_value=['android-dead'])
    @patch(APNS, return_value=['ios-dead'])
    def test_prunes_dead_tokens_reported_by_providers(self, apns, fcm):
        self._add(DEVICE_PLATFORM_IOS, 'ios-dead')
        self._add(DEVICE_PLATFORM_IOS, 'ios-live')
        self._add(DEVICE_PLATFORM_ANDROID, 'android-dead')
        self._add(DEVICE_PLATFORM_ANDROID, 'android-live')

        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)

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

        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)

        self.assertFalse(DeviceToken.objects.filter(token='ios-dead').exists())
        self.assertTrue(DeviceToken.objects.filter(token='other-live').exists())

    @patch(FCM, return_value=['android-dead'])
    @patch(APNS, side_effect=RuntimeError('apns down'))
    def test_one_provider_failing_does_not_block_the_other(self, apns, fcm):
        """APNs raising is swallowed; FCM still runs and its dead token is
        still pruned. Push is best-effort — a provider outage never propagates."""
        self._add(DEVICE_PLATFORM_IOS, 'ios-live')
        self._add(DEVICE_PLATFORM_ANDROID, 'android-dead')

        push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)  # must not raise

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
            push.send_push(self.user, PAYLOAD, PUSH_TYPE_POST_REJECTED)
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
