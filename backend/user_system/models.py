import logging
import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from .constants import (
    NEVER_RUN, BAN_TYPE_OUTRIGHT, BAN_TYPE_SHADOW,
    HIDDEN_REASON_NONE, HIDDEN_REASON_REPORTS, HIDDEN_REASON_CLASSIFIER,
    APPEAL_STATUS_PENDING, APPEAL_STATUS_APPROVED, APPEAL_STATUS_DENIED,
    APPEAL_TARGET_POST, APPEAL_TARGET_COMMENT, APPEAL_TARGET_BAN,
)

logger = logging.getLogger(__name__)


def notify_user_of_outright_ban(ban):
    """Email a user that their account has been suspended.

    Only outright bans are announced — shadow bans are intentionally silent so
    the user stays unaware. A mail failure must never block the ban, so it is
    logged and swallowed (matching the new-device login email behaviour).
    """
    if ban.ban_type != BAN_TYPE_OUTRIGHT or not ban.is_in_effect():
        return
    if not ban.user.email:
        return

    if ban.expires:
        duration = f"until {ban.expires:%Y-%m-%d %H:%M UTC}"
    else:
        duration = "permanently"
    reason = (ban.reason or "").strip()
    reason_line = f"\n\nReason: {reason}" if reason else ""

    body = (
        "Your account has been suspended for violating our community "
        f"guidelines. The suspension is in effect {duration}.{reason_line}\n\n"
        "If you believe this was a mistake, you can reply to this email to "
        "appeal."
    )
    try:
        send_mail(
            "Your account has been suspended",
            body,
            settings.EMAIL_HOST_USER,
            [ban.user.email],
        )
    except Exception:
        logger.exception(f"Failed to send ban notification email for user_id {ban.user_id}")


def notify_user_of_appeal_resolution(appeal, outcome_label):
    """Email the appellant that their appeal was approved or denied.

    Best-effort, like the ban email: a mail failure is logged and swallowed so
    it never blocks resolving the appeal.
    """
    user = appeal.appellant
    if not user.email:
        return
    note = (appeal.resolution_note or "").strip()
    note_line = f"\n\nNote from the moderation team: {note}" if note else ""
    body = (
        f"Your appeal has been reviewed and was {outcome_label}.{note_line}"
    )
    try:
        send_mail(
            "Update on your appeal",
            body,
            settings.EMAIL_HOST_USER,
            [user.email],
        )
    except Exception:
        logger.exception(f"Failed to send appeal resolution email for appeal_id {appeal.appeal_identifier}")


# The model to explicitly define the "follow" relationship
class UserFollow(models.Model):
    user_from = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='following_set', on_delete=models.CASCADE)
    user_to = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='followers_set', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'user_system'
        constraints = [
            models.UniqueConstraint(fields=['user_from', 'user_to'], name='unique_followers')
        ]


# The model to explicitly define the "block" relationship
class UserBlock(models.Model):
    user_blocker = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='blocking_set', on_delete=models.CASCADE)
    user_blocked = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='blocked_by_set', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'user_system'
        constraints = [
            models.UniqueConstraint(fields=['user_blocker', 'user_blocked'], name='unique_blocks')
        ]


# The non-admin user class (no changes needed here)
class PositiveOnlySocialUser(AbstractUser):
    verification_token = models.TextField(null=True, blank=True, default=None)
    verification_token_expires = models.DateTimeField(null=True, blank=True, default=None)
    reset_token = models.TextField(null=True, blank=True, default=None)
    reset_token_expires = models.DateTimeField(null=True, blank=True, default=None)
    report_id = models.TextField(null=True)
    verification_report_status = models.TextField(default=NEVER_RUN)
    identity_is_verified = models.BooleanField(default=False)
    is_adult = models.BooleanField(default=False)
    verification_failed_attempts = models.IntegerField(default=0)
    verification_lockout_until = models.DateTimeField(null=True, blank=True, default=None)

    # Email-address verification. Distinct from identity_is_verified (age/identity)
    # and from verification_token above (password reset). Login and all
    # authenticated endpoints are refused until the address is verified.
    #
    # The default is True (grandfathered-safe): any account created by a path
    # other than registration — a superuser, a fixture, or old app code still
    # running mid rolling-deploy — is usable rather than permanently locked out
    # with no token to verify. Registration is the only path that gates: it
    # issues a verification token, which explicitly flips this to False (see
    # _issue_email_verification_token in views).
    email_verified = models.BooleanField(default=True)
    email_verification_token = models.TextField(null=True, blank=True, default=None)
    email_verification_token_expires = models.DateTimeField(null=True, blank=True, default=None)

    creation_time = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    following = models.ManyToManyField('self', through=UserFollow, through_fields=('user_from', 'user_to'),
                                       symmetrical=False, related_name='followers')
    blocked = models.ManyToManyField('self', through=UserBlock, through_fields=('user_blocker', 'user_blocked'),
                                       symmetrical=False, related_name='blocked_by')

    def __str__(self):
        return self.username


# The session information (no changes needed here)
class Session(models.Model):
    management_token = models.TextField(null=True)
    management_user = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE)
    ip = models.TextField(null=True)


# The login cookie information (no changes needed here)
class LoginCookie(models.Model):
    series_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    token = models.TextField(null=True)
    cookie_user = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE)


# A device (identified by its IP) a user has logged in from. The first time a
# user logs in from an IP we have not recorded before we email them so they are
# alerted to the new login. Kept as its own record rather than relying on
# Session rows because those are deleted on logout/ban, which would make the
# same device look "new" again.
class KnownDevice(models.Model):
    user = models.ForeignKey(PositiveOnlySocialUser, related_name='known_devices', on_delete=models.CASCADE)
    ip = models.TextField()
    user_agent = models.TextField(default='', blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'user_system'
        constraints = [
            models.UniqueConstraint(fields=['user', 'ip','user_agent'], name='unique_user_device_ip_user_agent')
        ]

    def __str__(self):
        return f"{self.user} @ {self.ip}/{self.user_agent[:80]}"


class UserBanManager(models.Manager):
    def active(self):
        """Bans that are currently in effect (no expiry, or expiry in the future)."""
        return self.filter(models.Q(expires__isnull=True) | models.Q(expires__gt=timezone.now()))


# A ban applied to a user. Kept as a separate record rather than a flag on the
# user so there is an audit trail and a future appeals system can reference
# the specific ban.
class UserBan(models.Model):
    BAN_TYPE_CHOICES = [
        (BAN_TYPE_OUTRIGHT, 'Outright'),
        (BAN_TYPE_SHADOW, 'Shadow'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='bans', on_delete=models.CASCADE)
    ban_type = models.TextField(choices=BAN_TYPE_CHOICES, default=BAN_TYPE_OUTRIGHT)
    reason = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField(null=True, blank=True, default=None)
    banned_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='bans_issued', null=True, blank=True,
                                  on_delete=models.SET_NULL)

    objects = UserBanManager()

    class Meta:
        app_label = 'user_system'

    def is_in_effect(self):
        return self.expires is None or self.expires > timezone.now()

    def save(self, *args, **kwargs):
        # Whether this record was already an in-effect outright ban before the
        # save, so we can email only when it *transitions into* that state
        # (newly issued, shadow→outright, or expiry extended past now) and not
        # on ordinary edits like a reason change.
        was_active_outright = False
        if not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).only('ban_type', 'expires').first()
            if previous is not None:
                was_active_outright = (previous.ban_type == BAN_TYPE_OUTRIGHT
                                       and previous.is_in_effect())

        super().save(*args, **kwargs)

        # An outright ban must terminate the user's live sessions immediately.
        # Shadow bans leave sessions alone so the user stays unaware, and
        # already-expired bans (e.g. recording a historical ban) must not log
        # the user out.
        if self.ban_type == BAN_TYPE_OUTRIGHT and self.is_in_effect():
            Session.objects.filter(management_user=self.user).delete()
            LoginCookie.objects.filter(cookie_user=self.user).delete()
            if not was_active_outright:
                notify_user_of_outright_ban(self)

    def __str__(self):
        return f"{self.ban_type} ban on {self.user}"


# Why a post or comment is hidden, shared by Post and Comment. An empty reason
# means no cause is recorded — usually paired with hidden=False, but also with
# already-hidden rows that predate this field. A non-empty reason records what
# hid it so the appeal system can tell the author and decide what is appealable.
HIDDEN_REASON_CHOICES = [
    (HIDDEN_REASON_NONE, 'Unspecified'),
    (HIDDEN_REASON_REPORTS, 'Reports'),
    (HIDDEN_REASON_CLASSIFIER, 'Classifier'),
]


# A post on the website
class Post(models.Model):
    post_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    image_url = models.TextField(null=True)
    caption = models.TextField(null=True)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    author = models.ForeignKey(PositiveOnlySocialUser, on_delete=models.CASCADE)
    hidden = models.BooleanField(default=False)
    hidden_reason = models.TextField(choices=HIDDEN_REASON_CHOICES, default=HIDDEN_REASON_NONE, blank=True)


# A report on a post
class PostReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    reason = models.TextField(null=True)


# A like on a post
class PostLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_post_like')
        ]


# A thread of comments on a post
class CommentThread(models.Model):
    comment_thread_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)


# A comment on a post
class Comment(models.Model):
    comment_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    comment_thread = models.ForeignKey(CommentThread, on_delete=models.CASCADE)
    body = models.TextField(null=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    updated_time = models.DateTimeField(auto_now=True, null=True, blank=True)
    hidden = models.BooleanField(default=False)
    hidden_reason = models.TextField(choices=HIDDEN_REASON_CHOICES, default=HIDDEN_REASON_NONE, blank=True)


# A report on a comment
class CommentReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    creation_time = models.DateTimeField(auto_now_add=True, null=True,
                                         blank=True)
    reason = models.TextField(null=True)


# A like on a comment
class CommentLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'comment'], name='unique_comment_like')
        ]


class AppealManager(models.Manager):
    def pending(self):
        """Appeals awaiting an admin decision."""
        return self.filter(status=APPEAL_STATUS_PENDING)


# An appeal a user files against a moderation action: a hidden post, a hidden
# comment, or a ban. Exactly one of post/comment/ban is set. Kept as its own
# record (rather than a flag on the target) so admins have a queue and an audit
# trail of who appealed what, when, and how it was resolved. A post or comment
# may be deleted as part of denying its appeal, so content_snapshot preserves
# what was appealed for the trail.
class Appeal(models.Model):
    APPEAL_STATUS_CHOICES = [
        (APPEAL_STATUS_PENDING, 'Pending'),
        (APPEAL_STATUS_APPROVED, 'Approved'),
        (APPEAL_STATUS_DENIED, 'Denied'),
    ]

    appeal_identifier = models.UUIDField(default=uuid.uuid4, primary_key=True, unique=True, editable=False)
    appellant = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='appeals', on_delete=models.CASCADE)

    # Exactly one target is set. on_delete=SET_NULL so resolving (and deleting)
    # the target does not erase the appeal record.
    post = models.ForeignKey(Post, related_name='appeals', null=True, blank=True, on_delete=models.SET_NULL)
    comment = models.ForeignKey(Comment, related_name='appeals', null=True, blank=True, on_delete=models.SET_NULL)
    ban = models.ForeignKey(UserBan, related_name='appeals', null=True, blank=True, on_delete=models.SET_NULL)

    reason = models.TextField(null=True, blank=True)
    content_snapshot = models.TextField(null=True, blank=True)
    status = models.TextField(choices=APPEAL_STATUS_CHOICES, default=APPEAL_STATUS_PENDING)
    created = models.DateTimeField(auto_now_add=True)
    resolved_time = models.DateTimeField(null=True, blank=True, default=None)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='appeals_resolved', null=True, blank=True,
                                    on_delete=models.SET_NULL)
    resolution_note = models.TextField(null=True, blank=True)

    objects = AppealManager()

    class Meta:
        app_label = 'user_system'
        constraints = [
            # At most one target may be set. We cannot require *exactly* one at
            # the DB level because on_delete=SET_NULL clears the target when the
            # post/comment/ban is deleted (e.g. when denying an appeal removes
            # the offending post); the "exactly one at creation" rule is
            # enforced by clean() and the appeal endpoints instead.
            models.CheckConstraint(
                name='appeal_has_at_most_one_target',
                condition=~(
                    (Q(post__isnull=False) & Q(comment__isnull=False))
                    | (Q(post__isnull=False) & Q(ban__isnull=False))
                    | (Q(comment__isnull=False) & Q(ban__isnull=False))
                ),
            ),
            # One appeal per post/comment, enforced at the DB level so two
            # concurrent submissions cannot both pass the application-side
            # exists() check and create duplicates.
            models.UniqueConstraint(
                fields=['post'], condition=Q(post__isnull=False),
                name='unique_appeal_per_post',
            ),
            models.UniqueConstraint(
                fields=['comment'], condition=Q(comment__isnull=False),
                name='unique_appeal_per_comment',
            ),
        ]

    @property
    def target(self):
        """The post, comment, or ban this appeal is about (whichever is set)."""
        return self.post or self.comment or self.ban

    def clean(self):
        targets = [self.post, self.comment, self.ban]
        if sum(t is not None for t in targets) != 1:
            raise ValidationError("An appeal must reference exactly one of a post, comment, or ban.")

    def save(self, *args, **kwargs):
        # Django does not run clean() on save()/create(), and the DB constraint
        # only forbids *two* targets (it must allow zero so SET_NULL can clear a
        # target when its post/comment/ban is deleted). Enforce the exactly-one
        # rule on insert here so a zero-target appeal can never be created; once
        # persisted, a later target-clearing delete is allowed.
        if self._state.adding:
            self.clean()
        super().save(*args, **kwargs)

    @property
    def target_kind(self):
        """'post', 'comment', or 'ban' — or None if the target was removed when
        the appeal was resolved (e.g. a denied post)."""
        if self.post_id:
            return APPEAL_TARGET_POST
        if self.comment_id:
            return APPEAL_TARGET_COMMENT
        if self.ban_id:
            return APPEAL_TARGET_BAN
        return None

    def _mark_resolved(self, status, resolved_by, note):
        self.status = status
        self.resolved_time = timezone.now()
        self.resolved_by = resolved_by
        if note:
            self.resolution_note = note
        self.save(update_fields=['status', 'resolved_time', 'resolved_by', 'resolution_note'])

    def _claim_pending(self):
        """Lock this appeal's row and confirm it is still pending, so two admins
        resolving the same appeal concurrently cannot both apply side effects.
        Must be called inside transaction.atomic(); returns True if this caller
        won the claim (the loser blocks on the lock, then sees it resolved)."""
        return type(self).objects.select_for_update().filter(
            pk=self.pk, status=APPEAL_STATUS_PENDING).exists()

    def approve(self, resolved_by=None, note=''):
        """Reverse the moderation action and mark the appeal approved: un-hide
        the post/comment, or lift the ban. A no-op if the appeal is no longer
        pending (resolution is irreversible)."""
        with transaction.atomic():
            if not self._claim_pending():
                return
            if self.post is not None and self.post.hidden:
                self.post.hidden = False
                self.post.hidden_reason = HIDDEN_REASON_NONE
                self.post.save(update_fields=['hidden', 'hidden_reason'])
            if self.comment is not None and self.comment.hidden:
                self.comment.hidden = False
                self.comment.hidden_reason = HIDDEN_REASON_NONE
                self.comment.save(update_fields=['hidden', 'hidden_reason'])
            if self.ban is not None and self.ban.is_in_effect():
                # Expire rather than delete so the ban audit trail is kept.
                self.ban.expires = timezone.now()
                self.ban.save(update_fields=['expires'])
            self._mark_resolved(APPEAL_STATUS_APPROVED, resolved_by, note)
        # Outside the transaction: never hold the row lock during SMTP, and do
        # not email if the transaction rolled back.
        notify_user_of_appeal_resolution(self, "approved")

    def deny(self, resolved_by=None, note=''):
        """Mark the appeal denied. A denied post is removed (its image cleaned
        up from S3) since it stays hidden forever; the appeal keeps
        content_snapshot for the audit trail. Denied comments stay hidden and
        denied bans stay in effect. A no-op if the appeal is no longer pending."""
        image_url = None
        with transaction.atomic():
            if not self._claim_pending():
                return
            self._mark_resolved(APPEAL_STATUS_DENIED, resolved_by, note)
            if self.post is not None:
                image_url = self.post.image_url
                self.post.delete()  # SET_NULL clears self.post; content_snapshot remains
        # Outside the transaction: email and the S3 cleanup (network I/O) run
        # only after the denial has committed.
        notify_user_of_appeal_resolution(self, "denied")
        if image_url is not None:
            # Local import avoids importing the S3/boto3 module at model load.
            from .s3 import delete_image
            delete_image(image_url)

    def __str__(self):
        # target is None once a resolved target has been deleted (e.g. a denied
        # post), so fall back to a clear placeholder and always show the id.
        target = self.target if self.target is not None else "removed target"
        return f"{self.status} appeal {self.appeal_identifier} by {self.appellant} on {target}"