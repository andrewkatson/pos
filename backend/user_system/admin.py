from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PositiveOnlySocialUser

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


admin.site.register(PositiveOnlySocialUser, PositiveOnlySocialUserAdmin)
