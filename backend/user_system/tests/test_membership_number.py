"""Membership-number feature (issue #198): sequential join numbers assigned at
registration, backfilled for pre-existing accounts, and exposed publicly on the
profile endpoint."""
import importlib
import os
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields


# The data migration's module name starts with a digit, so it can't be imported
# with normal `from ... import` syntax.
backfill_migration = importlib.import_module(
    'user_system.migrations.0022_backfill_membership_number'
)


class MembershipNumberTests(PositiveOnlySocialTestCase):

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_registration_assigns_consecutive_numbers(self):
        """Each new member gets the next number, one past the previous member."""
        first = self.make_user('memberalpha')
        second = self.make_user('memberbravo')
        third = self.make_user('membercharlie')

        self.assertIsNotNone(first[Fields.membership_number])
        self.assertEqual(second[Fields.membership_number], first[Fields.membership_number] + 1)
        self.assertEqual(third[Fields.membership_number], second[Fields.membership_number] + 1)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_registration_persists_number_on_the_user(self):
        response = self.make_user('memberdelta')
        user = get_user_model().objects.get(username='memberdelta')
        self.assertEqual(user.membership_number, response[Fields.membership_number])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_profile_details_exposes_own_number(self):
        self.register_user_and_setup_local_fields()
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        user = get_user_model().objects.get(username=self.local_username)

        url = reverse('get_profile_details', kwargs={'username': self.local_username})
        response = self.client.get(url, **header)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(user.membership_number)
        self.assertEqual(response.json()[Fields.membership_number], user.membership_number)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_other_users_number_is_publicly_visible(self):
        """The join number shows on anyone's profile, not just your own (#198)."""
        self.register_user_and_setup_local_fields()
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.make_user('someoneelse123')
        other = get_user_model().objects.get(username='someoneelse123')

        url = reverse('get_profile_details', kwargs={'username': 'someoneelse123'})
        response = self.client.get(url, **header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.membership_number], other.membership_number)

    def test_backfill_numbers_existing_users_in_join_order(self):
        """The data migration numbers pre-existing (null-numbered) accounts by
        creation_time, with null creation_time sorting first."""
        UserModel = get_user_model()
        # create_user does not assign a number — these mimic accounts created
        # before the field existed.
        u_old = UserModel.objects.create_user(username='oldest_member', email='o@e.com')
        u_mid = UserModel.objects.create_user(username='middle_member', email='m@e.com')
        u_new = UserModel.objects.create_user(username='newest_member', email='n@e.com')
        u_null = UserModel.objects.create_user(username='grandfathered_member', email='g@e.com')

        now = timezone.now()
        UserModel.objects.filter(pk=u_old.pk).update(
            creation_time=now - timedelta(days=3), membership_number=None)
        UserModel.objects.filter(pk=u_mid.pk).update(
            creation_time=now - timedelta(days=2), membership_number=None)
        UserModel.objects.filter(pk=u_new.pk).update(
            creation_time=now - timedelta(days=1), membership_number=None)
        UserModel.objects.filter(pk=u_null.pk).update(
            creation_time=None, membership_number=None)

        backfill_migration.backfill_membership_numbers(django_apps, None)

        for u in (u_old, u_mid, u_new, u_null):
            u.refresh_from_db()

        # Order: null creation_time first, then ascending creation_time — and the
        # numbers are consecutive (robust to any users pre-existing in the DB).
        self.assertEqual(u_old.membership_number, u_null.membership_number + 1)
        self.assertEqual(u_mid.membership_number, u_old.membership_number + 1)
        self.assertEqual(u_new.membership_number, u_mid.membership_number + 1)

    def test_backfill_leaves_already_numbered_users_untouched(self):
        """Re-running the backfill must not renumber members who already have one."""
        UserModel = get_user_model()
        numbered = UserModel.objects.create_user(username='already_numbered', email='a@e.com')
        UserModel.objects.filter(pk=numbered.pk).update(membership_number=500)

        backfill_migration.backfill_membership_numbers(django_apps, None)

        numbered.refresh_from_db()
        self.assertEqual(numbered.membership_number, 500)
