from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import Prefetch
from django.utils import timezone

from .constants import BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW
from .models import LoginCookie, PositiveOnlySocialUser, Session, UserBan

_SUPERUSER_ONLY_FIELDS = frozenset(("is_staff", "is_superuser", "groups", "user_permissions"))
_ALWAYS_READONLY_FIELDS = ("verification_token", "verification_token_expires",
                           "reset_token", "reset_token_expires")


class PositiveOnlySocialUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Profile", {"fields": (
            "identity_is_verified", "is_adult",
            "report_id", "verification_report_status",
            "verification_token", "verification_token_expires",
            "reset_token", "reset_token_expires",
        )}),
    )

    list_display = UserAdmin.list_display + ("ban_status",)
    actions = ("apply_outright_ban", "apply_shadow_ban", "lift_active_bans")

    def get_readonly_fields(self, request, obj=None):
        readonly = set(super().get_readonly_fields(request, obj))
        readonly.update(_ALWAYS_READONLY_FIELDS)
        if not request.user.is_superuser:
            readonly.update(_SUPERUSER_ONLY_FIELDS)
        return tuple(readonly)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets
        return [
            (name, {**opts, "fields": tuple(
                f for f in opts["fields"] if f not in _SUPERUSER_ONLY_FIELDS
            )})
            for name, opts in fieldsets
        ]

    def get_queryset(self, request):
        # Prefetch active bans in one query so ban_status does not run a
        # query per row on the changelist.
        return super().get_queryset(request).prefetch_related(
            Prefetch('bans', queryset=UserBan.objects.active(), to_attr='active_bans'))

    @admin.display(description="Ban status")
    def ban_status(self, user):
        active_bans = getattr(user, 'active_bans', None)
        if active_bans is None:
            active_bans = user.bans.active()
        active_types = sorted({ban.ban_type for ban in active_bans})
        return ", ".join(active_types) if active_types else "—"

    def _apply_ban(self, request, queryset, ban_type):
        if not request.user.has_perm('user_system.add_userban'):
            self.message_user(request, "You do not have permission to issue bans.", messages.ERROR)
            return

        # One query up front instead of an exists() check per selected user.
        already_banned_ids = set(
            UserBan.objects.active()
            .filter(user__in=queryset, ban_type=ban_type)
            .values_list('user_id', flat=True)
        )

        # An admin must not ban themselves: an outright ban would tear down
        # their own sessions mid-action. Skip them and anyone already banned
        # with this type.
        valid_users = [
            user for user in queryset
            if user != request.user and user.pk not in already_banned_ids
        ]
        total_selected = queryset.count() if hasattr(queryset, 'count') else len(queryset)
        banned = len(valid_users)
        skipped = total_selected - banned

        if valid_users:
            UserBan.objects.bulk_create([
                UserBan(user=user, ban_type=ban_type, banned_by=request.user,
                        reason="Issued via admin action")
                for user in valid_users
            ])
            # bulk_create bypasses UserBan.save(), so the session/login-cookie
            # teardown that an outright ban normally triggers must be done here.
            # These freshly created bans have no expiry, so they are in effect.
            if ban_type == BAN_TYPE_OUTRIGHT:
                Session.objects.filter(management_user__in=valid_users).delete()
                LoginCookie.objects.filter(cookie_user__in=valid_users).delete()

        message = f"Applied {ban_type} ban to {banned} user(s)."
        if skipped:
            message += f" Skipped {skipped} (already banned or self)."
        self.message_user(request, message)

    @admin.action(description="Apply outright ban to selected users")
    def apply_outright_ban(self, request, queryset):
        self._apply_ban(request, queryset, BAN_TYPE_OUTRIGHT)

    @admin.action(description="Apply shadow ban to selected users")
    def apply_shadow_ban(self, request, queryset):
        self._apply_ban(request, queryset, BAN_TYPE_SHADOW)

    @admin.action(description="Lift all active bans on selected users")
    def lift_active_bans(self, request, queryset):
        if not request.user.has_perm('user_system.change_userban'):
            self.message_user(request, "You do not have permission to lift bans.", messages.ERROR)
            return

        # Expire the bans instead of deleting them so the audit trail (and a
        # future appeals system) keeps the record.
        count = UserBan.objects.active().filter(user__in=queryset).update(expires=timezone.now())
        self.message_user(request, f"Lifted {count} ban(s).")


class UserBanAdmin(admin.ModelAdmin):
    list_display = ("user", "ban_type", "reason", "created", "expires", "banned_by", "in_effect")
    list_filter = ("ban_type",)
    search_fields = ("user__username",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created", "banned_by")

    @admin.display(boolean=True, description="In effect")
    def in_effect(self, ban):
        return ban.is_in_effect()

    def save_model(self, request, obj, form, change):
        if not change and obj.banned_by is None:
            obj.banned_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(PositiveOnlySocialUser, PositiveOnlySocialUserAdmin)
admin.site.register(UserBan, UserBanAdmin)
