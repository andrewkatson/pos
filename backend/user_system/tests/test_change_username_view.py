import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from .. import views
from ..constants import (
    Fields, REVIEW_STATUS_CLEARED, REVIEW_STATUS_DISMISSED, REVIEW_STATUS_ESCALATED,
    USERNAME_CHANGE_COOLDOWN_DAYS, USERNAME_CHANGE_TOO_SOON, USERNAME_HOLD_DAYS, USERNAME_TAKEN,
)
from ..models import ModerationReview, UsernameHold, UserFollow


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class ChangeUsernameTests(PositiveOnlySocialTestCase):
    """POST /me/username/ renames the signed-in account (issue #594). The text
    classifier runs in TESTING mode, where any text containing "negative" is
    rejected, so positivity is driven through the requested name."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.url = reverse('change_username')
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.user = get_user_model().objects.get(username=self.local_username)
        self.new_name = 'sunnyrenamed_one'

    def _rename(self, username, header=None):
        return self.client.post(self.url, data={Fields.username: username}, content_type='application/json',
                                **(header if header is not None else self.header))

    def _other_user(self, base='otherperson'):
        name = self._get_unique_username(base)
        data = self.make_user(name)
        return get_user_model().objects.get(username=name), {
            'HTTP_AUTHORIZATION': f"Bearer {data[Fields.session_management_token]}"}

    # -- the rename itself -------------------------------------------------------

    def test_rename_changes_username_and_starts_cooldown(self):
        response = self._rename(self.new_name)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[Fields.username], self.new_name)
        self.assertIsNotNone(body[Fields.next_username_change_time])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, self.new_name)
        self.assertIsNotNone(self.user.username_changed_time)

    def test_session_keeps_working_after_rename(self):
        self._rename(self.new_name)
        response = self.client.get(reverse('get_current_user'), **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.username], self.new_name)

    def test_old_name_is_held_for_the_former_owner(self):
        self._rename(self.new_name)
        hold = UsernameHold.objects.get(username=self.local_username)
        self.assertEqual(hold.user, self.user)
        expected = timezone.now() + timedelta(days=USERNAME_HOLD_DAYS)
        self.assertLess(abs((hold.expires - expected).total_seconds()), 60)

    def test_login_with_old_name_fails_and_new_name_works(self):
        self._rename(self.new_name)
        old = self.client.post(reverse('login_user'), data={
            Fields.username_or_email: self.local_username, Fields.password: self.local_password,
            Fields.remember_me: 'false'}, content_type='application/json')
        self.assertEqual(old.status_code, 400)
        new = self.client.post(reverse('login_user'), data={
            Fields.username_or_email: self.new_name, Fields.password: self.local_password,
            Fields.remember_me: 'false'}, content_type='application/json')
        self.assertEqual(new.status_code, 200)

    # -- refusals --------------------------------------------------------------

    def test_same_name_is_refused(self):
        response = self._rename(self.local_username)
        self.assertEqual(response.status_code, 400)

    def test_invalid_pattern_is_refused(self):
        for bad in ['short', 'has spaces in it', 'semi;colon_name', 123, None]:
            with self.subTest(bad=bad):
                self.assertEqual(self._rename(bad).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, self.local_username)

    def test_name_in_use_is_refused(self):
        other, _ = self._other_user()
        response = self._rename(other.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], USERNAME_TAKEN)

    def test_unkind_name_is_refused_and_not_appealable(self):
        response = self._rename('negative_name_here')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()[Fields.appealable])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, self.local_username)
        self.assertIsNone(self.user.username_changed_time)

    def test_second_rename_within_cooldown_is_refused(self):
        self.assertEqual(self._rename(self.new_name).status_code, 200)
        response = self._rename('sunnyrenamed_two')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], USERNAME_CHANGE_TOO_SOON)
        self.assertIsNotNone(response.json()[Fields.next_username_change_time])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, self.new_name)

    def test_rename_allowed_again_after_cooldown(self):
        self._rename(self.new_name)
        get_user_model().objects.filter(pk=self.user.pk).update(
            username_changed_time=timezone.now() - timedelta(days=USERNAME_CHANGE_COOLDOWN_DAYS, minutes=1))
        self.assertEqual(self._rename('sunnyrenamed_two').status_code, 200)

    def test_requires_session(self):
        self.assertEqual(self._rename(self.new_name, header={}).status_code, 401)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url, **self.header).status_code, 405)

    # -- the hold ----------------------------------------------------------------

    def test_held_name_cannot_be_taken_by_rename(self):
        self._rename(self.new_name)
        _, other_header = self._other_user()
        response = self._rename(self.local_username, header=other_header)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], USERNAME_TAKEN)

    def test_held_name_cannot_be_registered(self):
        self._rename(self.new_name)
        response = self.client.post(reverse('register'), data={
            'username': self.local_username, 'email': 'someoneelse@example.com',
            'password': 'Password123-', 'remember_me': 'false'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_expired_hold_frees_the_name(self):
        self._rename(self.new_name)
        UsernameHold.objects.filter(username=self.local_username).update(expires=timezone.now() - timedelta(seconds=1))
        _, other_header = self._other_user()
        self.assertEqual(self._rename(self.local_username, header=other_header).status_code, 200)

    def test_owner_can_take_back_held_name(self):
        self._rename(self.new_name)
        get_user_model().objects.filter(pk=self.user.pk).update(
            username_changed_time=timezone.now() - timedelta(days=USERNAME_CHANGE_COOLDOWN_DAYS, minutes=1))
        self.assertEqual(self._rename(self.local_username).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, self.local_username)
        self.assertFalse(UsernameHold.objects.filter(username=self.local_username).exists())
        self.assertTrue(UsernameHold.objects.filter(username=self.new_name, user=self.user).exists())

    def test_rename_sweeps_expired_holds(self):
        stale = UsernameHold.objects.create(username='longgone_name', user=self.user,
                                            expires=timezone.now() - timedelta(days=1))
        self._rename(self.new_name)
        self.assertFalse(UsernameHold.objects.filter(pk=stale.pk).exists())

    def test_generated_google_username_skips_held_name(self):
        self._rename(self.new_name)
        base = self.local_username
        with patch.object(views, '_google_username_base', return_value=base), \
                patch('user_system.views.text_classifier_class.is_text_positive', return_value=True):
            user, created = views._create_user_for_google(
                None, {'sub': 'sub-for-hold-test', 'email': 'holdtest@example.com', 'email_verified': True},
                '127.0.0.1')
        self.assertTrue(created)
        self.assertNotEqual(user.username, base)

    # -- old names still address the account ----------------------------------

    def test_old_name_still_resolves_profile_routes(self):
        self._rename(self.new_name)
        other, other_header = self._other_user()

        profile = self.client.get(reverse('get_profile_details', args=[self.local_username]), **other_header)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()[Fields.username], self.new_name)

        follow = self.client.post(reverse('follow_user', args=[self.local_username]), **other_header)
        self.assertEqual(follow.status_code, 200)
        self.assertTrue(UserFollow.objects.filter(user_from=other, user_to=self.user).exists())

    def test_old_name_resolves_public_profile(self):
        self._rename(self.new_name)
        response = self.client.get(reverse('get_public_profile_details', args=[self.local_username]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.username], self.new_name)

    def test_old_name_stops_resolving_after_hold_expires(self):
        self._rename(self.new_name)
        UsernameHold.objects.filter(username=self.local_username).update(expires=timezone.now() - timedelta(seconds=1))
        _, other_header = self._other_user()
        profile = self.client.get(reverse('get_profile_details', args=[self.local_username]), **other_header)
        self.assertEqual(profile.status_code, 400)

    def test_current_name_wins_over_a_hold(self):
        # A hold only applies when nobody holds the name now — e.g. an expired
        # hold row that has not been swept yet must not shadow the new owner.
        self._rename(self.new_name)
        UsernameHold.objects.filter(username=self.local_username).update(expires=timezone.now() - timedelta(seconds=1))
        other, other_header = self._other_user()
        self._rename(self.local_username, header=other_header)
        self.assertEqual(views.get_user_by_handle(self.local_username), other)

    # -- report review -----------------------------------------------------------

    def test_rename_releases_a_decided_account_review(self):
        review = ModerationReview.objects.create(account=self.user, status=REVIEW_STATUS_DISMISSED)
        self._rename(self.new_name)
        review.refresh_from_db()
        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)

    def test_rename_leaves_an_escalated_review_alone(self):
        review = ModerationReview.objects.create(account=self.user, status=REVIEW_STATUS_ESCALATED)
        self._rename(self.new_name)
        review.refresh_from_db()
        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)

    # -- /me/ --------------------------------------------------------------------

    def test_me_reports_next_rename_time(self):
        me = self.client.get(reverse('get_current_user'), **self.header).json()
        self.assertIsNone(me[Fields.next_username_change_time])
        self._rename(self.new_name)
        me = self.client.get(reverse('get_current_user'), **self.header).json()
        self.assertIsNotNone(me[Fields.next_username_change_time])
