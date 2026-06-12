from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.utils import timezone

from ..admin import PositiveOnlySocialUserAdmin, UserBanAdmin
from ..constants import BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW
from ..models import PositiveOnlySocialUser, Session, UserBan


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
        # storage attached to the request.
        request.session = {}
        request._messages = FallbackStorage(request)
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
