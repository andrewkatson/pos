from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .constants import BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW
from .models import PositiveOnlySocialUser, UserBan

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

    @admin.display(description="Ban status")
    def ban_status(self, user):
        active_types = sorted(set(user.bans.active().values_list('ban_type', flat=True)))
        return ", ".join(active_types) if active_types else "—"

    def _apply_ban(self, request, queryset, ban_type):
        if not request.user.has_perm('user_system.add_userban'):
            self.message_user(request, "You do not have permission to issue bans.", messages.ERROR)
            return

        banned = 0
        skipped = 0
        for user in queryset:
            # An admin must not ban themselves: an outright ban would tear
            # down their own sessions mid-action.
            if user == request.user:
                skipped += 1
                continue
            if UserBan.objects.active().filter(user=user, ban_type=ban_type).exists():
                skipped += 1
                continue
            UserBan.objects.create(user=user, ban_type=ban_type, banned_by=request.user,
                                   reason="Issued via admin action")
            banned += 1

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
