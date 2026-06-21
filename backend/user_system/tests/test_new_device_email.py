from django.core import mail
from django.urls import reverse
from .test_constants import false, true
from .test_parent_case import PositiveOnlySocialTestCase
from ..models import KnownDevice, PositiveOnlySocialUser

# The Django test client sends REMOTE_ADDR '127.0.0.1' by default, so that is
# the IP recorded at registration. A login from any *other* IP is therefore a
# new device.
REGISTRATION_IP = '127.0.0.1'
NEW_IP = '203.0.113.7'
ANOTHER_NEW_IP = '198.51.100.9'


class NewDeviceEmailTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.login_url = reverse('login_user')
        self.registration_email= list(mail.outbox)
        mail.outbox.clear()
    def _login(self, remote_addr, remember_me=false):
        data = {
            'username_or_email': self.local_username,
            'password': self.local_password,
            'remember_me': remember_me,
        }
        response = self.client.post(self.login_url, data=data,
                                    content_type='application/json',
                                    REMOTE_ADDR=remote_addr)
        self.assertEqual(response.status_code, 200)
        return response.json()

    # --- registration ---

    def test_registration_records_device_without_emailing(self):
        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.assertTrue(KnownDevice.objects.filter(user=user, ip=REGISTRATION_IP).exists())
        self.assertEqual(len(self.registration_email), 1)
        self.assertEqual(self.registration_email[0].subject,"Welcome to Good Vibes Only")


    # --- login from a new device ---

    def test_login_from_new_ip_sends_email_and_records_device(self):
        self._login(NEW_IP)

        user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.assertTrue(KnownDevice.objects.filter(user=user, ip=NEW_IP).exists())
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn(self.local_email, message.to)
        self.assertIn(NEW_IP, message.body)

    def test_login_from_known_ip_does_not_send_email(self):
        # Same IP that registration recorded -> not a new device.
        self._login(REGISTRATION_IP)
        self.assertEqual(len(mail.outbox), 0)

    def test_repeated_login_from_same_new_ip_emails_only_once(self):
        self._login(NEW_IP)
        self._login(NEW_IP)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            KnownDevice.objects.filter(user__username=self.local_username, ip=NEW_IP).count(), 1)

    def test_each_distinct_new_ip_emails(self):
        self._login(NEW_IP)
        self._login(ANOTHER_NEW_IP)
        self.assertEqual(len(mail.outbox), 2)

    # --- remember-me login ---

    def test_remember_me_login_from_new_ip_sends_email(self):
        # Establish a remember-me cookie from the (already known) registration IP.
        login_data = self._login(REGISTRATION_IP, remember_me=true)
        self.assertEqual(len(mail.outbox), 0)

        url = reverse('login_user_with_remember_me')
        data = {
            'session_management_token': login_data['session_management_token'],
            'series_identifier': login_data['series_identifier'],
            'login_cookie_token': login_data['login_cookie_token'],
        }
        response = self.client.post(url, data=data, content_type='application/json',
                                    REMOTE_ADDR=NEW_IP)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(NEW_IP, mail.outbox[0].body)
        self.assertTrue(
            KnownDevice.objects.filter(user__username=self.local_username, ip=NEW_IP).exists())
