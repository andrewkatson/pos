from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Prefetch
from django.utils import timezone

from . import moderation
from .constants import BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW, APPEAL_STATUS_PENDING
from .models import Appeal, LoginCookie, ModerationReview, PositiveOnlySocialUser, Session, UserBan, \
    notify_user_of_outright_ban

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
        qs = super().get_queryset(request)
        # ban_status (in list_display) needs each user's active bans, so
        # prefetch them in one query for the changelist. Skip the prefetch for
        # the admin autocomplete endpoint, which reuses this get_queryset (via
        # UserBanAdmin.autocomplete_fields) but never renders ban_status — the
        # prefetch would just add an unneeded query per lookup.
        resolver_match = getattr(request, 'resolver_match', None)
        if resolver_match and resolver_match.url_name == 'autocomplete':
            return qs
        return qs.prefetch_related(
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

        # Materialize the selection once so total_selected does not need a
        # separate count() query.
        selected = list(queryset)

        # One query up front instead of an exists() check per selected user.
        already_banned_ids = set(
            UserBan.objects.active()
            .filter(user__in=selected, ban_type=ban_type)
            .values_list('user_id', flat=True)
        )

        # An admin must not ban themselves: an outright ban would tear down
        # their own sessions mid-action. Skip them and anyone already banned
        # with this type.
        valid_users = [
            user for user in selected
            if user != request.user and user.pk not in already_banned_ids
        ]
        banned = len(valid_users)
        skipped = len(selected) - banned

        if valid_users:
            new_bans = [
                UserBan(user=user, ban_type=ban_type, banned_by=request.user,
                        reason="Issued via admin action")
                for user in valid_users
            ]
            UserBan.objects.bulk_create(new_bans)
            # bulk_create bypasses UserBan.save(), so the session/login-cookie
            # teardown and ban-notification email that an outright ban normally
            # triggers must be done here. These freshly created bans have no
            # expiry, so they are in effect.
            if ban_type == BAN_TYPE_OUTRIGHT:
                Session.objects.filter(management_user__in=valid_users).delete()
                LoginCookie.objects.filter(cookie_user__in=valid_users).delete()
                for ban in new_bans:
                    notify_user_of_outright_ban(ban)

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


class AppealAdmin(admin.ModelAdmin):
    list_display = ("appellant", "target_kind", "status", "created", "resolved_time", "resolved_by")
    list_filter = ("status",)
    search_fields = ("appellant__username",)
    # Appeals are user-submitted and resolved via the approve/deny actions, so
    # every field is read-only in the form — admins act, they don't hand-edit.
    readonly_fields = ("appeal_identifier", "appellant", "post", "comment", "ban",
                       "reason", "content_snapshot", "status", "created",
                       "resolved_time", "resolved_by", "resolution_note")
    actions = ("approve_appeals", "deny_appeals")

    @admin.display(description="Target")
    def target_kind(self, appeal):
        return appeal.target_kind or "—"

    def _resolve(self, request, queryset, approve):
        if not request.user.has_perm('user_system.change_appeal'):
            self.message_user(request, "You do not have permission to resolve appeals.", messages.ERROR)
            return

        # Only pending appeals can be resolved; resolving is irreversible (a
        # denied post is deleted, an approved one un-hidden), so skip the rest.
        selected = list(queryset)
        pending = [appeal for appeal in selected if appeal.status == APPEAL_STATUS_PENDING]
        for appeal in pending:
            if approve:
                appeal.approve(resolved_by=request.user)
            else:
                appeal.deny(resolved_by=request.user)

        resolved = len(pending)
        skipped = len(selected) - resolved
        verb = "Approved" if approve else "Denied"
        message = f"{verb} {resolved} appeal(s)."
        if skipped:
            message += f" Skipped {skipped} already-resolved."
        self.message_user(request, message)

    @admin.action(description="Approve selected appeals (reverse the moderation action)")
    def approve_appeals(self, request, queryset):
        self._resolve(request, queryset, approve=True)

    @admin.action(description="Deny selected appeals")
    def deny_appeals(self, request, queryset):
        self._resolve(request, queryset, approve=False)


class ModerationReviewAdmin(admin.ModelAdmin):
    """The human end of user moderation (issue #467).

    Reports hide nothing on their own, so this queue is where content that kept
    drawing reports after the automated re-review cleared it actually gets
    decided. Filter to "Escalated to a moderator" for the work queue; the other
    statuses are the audit trail of what reports led to.
    """

    list_display = ("target_kind", "target_summary", "author", "status",
                    "report_count", "created", "resolved_time", "resolved_by")
    list_filter = ("status",)
    search_fields = ("post__caption", "comment__body", "post__author__username",
                     "comment__author__username")
    # Reviews are written by the report pipeline and resolved via the actions
    # below, so nothing here is hand-edited — admins act, they don't type.
    readonly_fields = ("review_identifier", "post", "comment", "status", "author",
                       "target_summary", "reported_reasons", "report_count",
                       "reports_at_last_review", "review_attempts", "created",
                       "updated", "reviewed_time", "resolved_time", "resolved_by",
                       "resolution_note")
    actions = ("hide_content", "dismiss_reports")

    def get_queryset(self, request):
        # target/author/report rendering walks to the post or comment and its
        # author for every row, so fetch them in the changelist query, and count
        # the reports in it too — report_count is in list_display, so counting
        # per row would be one extra COUNT per queue entry.
        #
        # Exactly one of the two joins is non-null per row (the check
        # constraint), so the sum is that side's count and the other is 0. Both
        # aggregates need distinct=True: two multi-valued joins in one query
        # multiply each other's rows, and only DISTINCT collapses that fan-out
        # back to the real counts.
        return super().get_queryset(request).select_related(
            'post', 'post__author', 'comment', 'comment__author', 'resolved_by',
        ).annotate(
            _report_count=(Count('post__postreport', distinct=True)
                           + Count('comment__commentreport', distinct=True)),
        )

    @admin.display(description="Target")
    def target_kind(self, review):
        return review.target_kind

    @admin.display(description="Content")
    def target_summary(self, review):
        """The reported text, truncated. Returned as a plain string so the admin
        escapes it — never mark_safe on user-authored content."""
        target = review.target
        text = (target.caption if review.post_id else target.body) or ''
        if review.post_id and target.image_url and not text:
            return "(image only)"
        return (text[:80] + '…') if len(text) > 80 else (text or '—')

    @admin.display(description="Author")
    def author(self, review):
        return review.target.author

    @admin.display(description="Reports", ordering='_report_count')
    def report_count(self, review):
        # Annotated by get_queryset for every admin view. The fallback keeps the
        # column correct for a row that reached it from some other queryset
        # (a caller outside the admin, a test) rather than silently blanking.
        count = getattr(review, '_report_count', None)
        return review.report_count() if count is None else count

    @admin.display(description="Reported reasons")
    def reported_reasons(self, review):
        """What the reporters actually said. Shown to a human here and nowhere
        else: this text is deliberately never fed to the automated review, so a
        crafted report cannot steer a classifier verdict."""
        reasons = [report.reason or '(no reason given)' for report in review.reports()]
        return "\n".join(f"• {reason}" for reason in reasons) or '—'

    def _resolve(self, request, queryset, hide):
        if not request.user.has_perm('user_system.change_moderationreview'):
            self.message_user(request, "You do not have permission to resolve reports.", messages.ERROR)
            return

        # An already-decided review is deliberately NOT skipped: the immunity a
        # terminal status confers is against *reports* (record_report will not
        # reopen it), not against moderators. A moderator correcting their own
        # hide — or overruling a colleague — is a legitimate, fully audited
        # operation (resolved_by/resolved_time/resolution_note record who
        # decided what, when).
        reviews = list(queryset)
        reversed_count = sum(1 for review in reviews if review.is_terminal)
        for review in reviews:
            if hide:
                moderation.hide_reviewed_content(review, moderator=request.user)
            else:
                moderation.dismiss_reports(review, moderator=request.user)

        verb = "Hid the content of" if hide else "Dismissed the reports on"
        message = f"{verb} {len(reviews)} review(s)."
        if reversed_count:
            message += f" {reversed_count} of those reversed an earlier decision."
        self.message_user(request, message)

    @admin.action(description="Hide the reported content")
    def hide_content(self, request, queryset):
        self._resolve(request, queryset, hide=True)

    @admin.action(description="Dismiss the reports (content stays up, and is immune to further automated review)")
    def dismiss_reports(self, request, queryset):
        self._resolve(request, queryset, hide=False)


admin.site.register(PositiveOnlySocialUser, PositiveOnlySocialUserAdmin)
admin.site.register(UserBan, UserBanAdmin)
admin.site.register(Appeal, AppealAdmin)
admin.site.register(ModerationReview, ModerationReviewAdmin)
