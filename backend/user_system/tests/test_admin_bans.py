from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import ResolverMatch
from django.utils import timezone

from ..admin import PositiveOnlySocialUserAdmin, UserBanAdmin
from ..constants import BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW
from ..models import LoginCookie, PositiveOnlySocialUser, Session, UserBan


class AdminBanActionTests(TestCase):
    """
    Tests the ban/unban admin actions and ban-status display directly on the
    ModelAdmin classes, bypassing the admin views (and the IP allowlist
    middleware in front of them).
    """

    def setUp(self):
        super().setUp()

        self.factory = RequestFactory()
        self.site = AdminSite()
        self.user_admin = PositiveOnlySocialUserAdmin(PositiveOnlySocialUser, self.site)
        self.ban_admin = UserBanAdmin(UserBan, self.site)

        self.admin_user = PositiveOnlySocialUser.objects.create_superuser(
            username='adminuser', email='admin@email.com', password='AdminPassword123!')
        self.target = PositiveOnlySocialUser.objects.create_user(
            username='targetuser', email='target@email.com', password='TargetPassword123!')

    def _request(self, user):
        request = self.factory.post('/')
        request.user = user
        # The actions report results via the messages framework, which needs
        # a real session and message storage attached to the request.
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        return request

    def _target_queryset(self, *users):
        pks = [user.pk for user in users or (self.target,)]
        return PositiveOnlySocialUser.objects.filter(pk__in=pks)

    # =========================================================================
    # APPLYING BANS
    # =========================================================================

    def test_apply_outright_ban_action(self):
        self.user_admin.apply_outright_ban(self._request(self.admin_user), self._target_queryset())

        ban = UserBan.objects.active().get(user=self.target)
        self.assertEqual(ban.ban_type, BAN_TYPE_OUTRIGHT)
        self.assertEqual(ban.banned_by, self.admin_user)

    def test_apply_shadow_ban_action(self):
        self.user_admin.apply_shadow_ban(self._request(self.admin_user), self._target_queryset())

        ban = UserBan.objects.active().get(user=self.target)
        self.assertEqual(ban.ban_type, BAN_TYPE_SHADOW)

    def test_outright_ban_action_tears_down_sessions(self):
        Session.objects.create(management_user=self.target, management_token='token', ip='1.2.3.4')

        self.user_admin.apply_outright_ban(self._request(self.admin_user), self._target_queryset())

        self.assertEqual(Session.objects.filter(management_user=self.target).count(), 0)

    def test_outright_ban_action_bulk_bans_and_tears_down_all_sessions(self):
        """
        Banning several users at once must create every ban and tear down the
        sessions and login cookies for all of them (bulk_create bypasses
        UserBan.save(), so the action does this teardown itself).
        """
        other = PositiveOnlySocialUser.objects.create_user(
            username='targetuser2', email='target2@email.com', password='TargetPassword123!')
        Session.objects.create(management_user=self.target, management_token='t1', ip='1.2.3.4')
        Session.objects.create(management_user=other, management_token='t2', ip='1.2.3.4')
        LoginCookie.objects.create(cookie_user=other, token='c2')

        self.user_admin.apply_outright_ban(
            self._request(self.admin_user), self._target_queryset(self.target, other))

        self.assertEqual(UserBan.objects.active().filter(ban_type=BAN_TYPE_OUTRIGHT).count(), 2)
        self.assertEqual(Session.objects.filter(management_user__in=[self.target, other]).count(), 0)
        self.assertEqual(LoginCookie.objects.filter(cookie_user=other).count(), 0)

    def test_shadow_ban_action_keeps_sessions(self):
        Session.objects.create(management_user=self.target, management_token='token', ip='1.2.3.4')

        self.user_admin.apply_shadow_ban(self._request(self.admin_user), self._target_queryset())

        self.assertEqual(Session.objects.filter(management_user=self.target).count(), 1)

    def test_apply_ban_skips_already_banned_user(self):
        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_OUTRIGHT)

        self.user_admin.apply_outright_ban(self._request(self.admin_user), self._target_queryset())

        self.assertEqual(UserBan.objects.filter(user=self.target).count(), 1)

    def test_apply_ban_allows_second_type(self):
        """An active shadow ban must not block applying an outright ban."""
        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_SHADOW)

        self.user_admin.apply_outright_ban(self._request(self.admin_user), self._target_queryset())

        self.assertEqual(UserBan.objects.filter(user=self.target).count(), 2)

    def test_admin_cannot_ban_self(self):
        self.user_admin.apply_outright_ban(
            self._request(self.admin_user), self._target_queryset(self.admin_user))

        self.assertEqual(UserBan.objects.filter(user=self.admin_user).count(), 0)

    def test_staff_without_permission_cannot_ban(self):
        staff = PositiveOnlySocialUser.objects.create_user(
            username='staffuser', email='staff@email.com', password='StaffPassword123!',
            is_staff=True)

        self.user_admin.apply_outright_ban(self._request(staff), self._target_queryset())

        self.assertEqual(UserBan.objects.filter(user=self.target).count(), 0)

    # =========================================================================
    # LIFTING BANS
    # =========================================================================

    def test_lift_active_bans_expires_but_keeps_records(self):
        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_OUTRIGHT)
        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_SHADOW)

        self.user_admin.lift_active_bans(self._request(self.admin_user), self._target_queryset())

        self.assertEqual(UserBan.objects.active().filter(user=self.target).count(), 0)
        # The records survive as an audit trail.
        self.assertEqual(UserBan.objects.filter(user=self.target).count(), 2)

    def test_staff_without_permission_cannot_lift_bans(self):
        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_OUTRIGHT)
        staff = PositiveOnlySocialUser.objects.create_user(
            username='staffuser2', email='staff2@email.com', password='StaffPassword123!',
            is_staff=True)

        self.user_admin.lift_active_bans(self._request(staff), self._target_queryset())

        self.assertEqual(UserBan.objects.active().filter(user=self.target).count(), 1)

    # =========================================================================
    # DISPLAY & FORM BEHAVIOR
    # =========================================================================

    def test_ban_status_shows_active_ban_types(self):
        self.assertEqual(self.user_admin.ban_status(self.target), "—")

        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_SHADOW)
        self.assertEqual(self.user_admin.ban_status(self.target), BAN_TYPE_SHADOW)

        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_OUTRIGHT)
        self.assertEqual(self.user_admin.ban_status(self.target),
                         f"{BAN_TYPE_OUTRIGHT}, {BAN_TYPE_SHADOW}")

    def test_ban_status_ignores_expired_bans(self):
        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_OUTRIGHT,
                               expires=timezone.now() - timedelta(days=1))

        self.assertEqual(self.user_admin.ban_status(self.target), "—")

    def test_save_model_sets_banned_by(self):
        ban = UserBan(user=self.target, ban_type=BAN_TYPE_OUTRIGHT)

        self.ban_admin.save_model(self._request(self.admin_user), ban, form=None, change=False)

        self.assertEqual(ban.banned_by, self.admin_user)

    def test_in_effect_display(self):
        active = UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_SHADOW)
        expired = UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_OUTRIGHT,
                                         expires=timezone.now() - timedelta(days=1))

        self.assertTrue(self.ban_admin.in_effect(active))
        self.assertFalse(self.ban_admin.in_effect(expired))

    def test_changelist_ban_status_uses_prefetched_bans(self):
        """
        The changelist queryset prefetches active bans, so rendering
        ban_status for each row must not issue any further queries.
        """
        UserBan.objects.create(user=self.target, ban_type=BAN_TYPE_SHADOW)

        users = list(self.user_admin.get_queryset(self._request(self.admin_user)))
        statuses = {}
        with self.assertNumQueries(0):
            for user in users:
                statuses[user.username] = self.user_admin.ban_status(user)

        self.assertEqual(statuses['targetuser'], BAN_TYPE_SHADOW)
        self.assertEqual(statuses['adminuser'], "—")

    def test_autocomplete_request_skips_ban_prefetch(self):
        """
        The user autocomplete endpoint reuses get_queryset but never renders
        ban_status, so it must not carry the active-bans prefetch.
        """
        request = self._request(self.admin_user)
        request.resolver_match = ResolverMatch(
            func=lambda r: None, args=(), kwargs={}, url_name='autocomplete')

        qs = self.user_admin.get_queryset(request)

        self.assertEqual(qs._prefetch_related_lookups, ())
