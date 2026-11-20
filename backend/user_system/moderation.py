"""What a user report does, now that a report count hides nothing (issue #467).

Reporting used to be a headcount: past MAX_BEFORE_HIDING_POST/COMMENT reports the
content was hidden automatically, and retracting reports back under the bar
un-hid it. Any coordinated group could therefore take down anything, and one
user could be spammed into invisibility, so that path is gone entirely.

A report now only opens (or advances) a ModerationReview — see the module-level
comment on the model, and the REVIEW_STATUS_* block in constants.py, for the
whole state machine. This module holds the two ends of it: what a report and a
retraction do to a review (`record_report` / `withdraw_report`), and what a
moderator's decision does to the content (`hide_reviewed_content` /
`dismiss_reports`, driven from the admin queue). The middle — the automated
content re-review that a first report queues — lives in tasks.py with the rest
of the classification jobs.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import tasks
from .classifiers.classifier_constants import GENERIC_REASON_CODE
from .constants import (
    HIDDEN_REASON_NONE, HIDDEN_REASON_REPORTS,
    MAX_REPORTS_PER_USER_PER_DAY, REPORTS_AFTER_CLEAR_BEFORE_ESCALATION,
    PROFILE_IMAGE_STATUS_REJECTED,
    REVIEW_STATUS_CLEARED, REVIEW_STATUS_DISMISSED, REVIEW_STATUS_ESCALATED,
    REVIEW_STATUS_HIDDEN, TERMINAL_REVIEW_STATUSES,
)
from .models import AccountReport, CommentReport, ModerationReview, PostReport

logger = logging.getLogger(__name__)


def reports_filed_in_last_day(user):
    """How many reports this account has FILED in the trailing 24 hours, posts,
    comments and accounts together.

    Deliberately counts retracted reports too. The budget is on filings, not on
    reports currently standing: a retraction that gave budget back would make
    the cap a formality, since report-then-retract cycling would let one account
    open unlimited reviews (and spend unlimited provider calls) while never
    holding more than a handful of live reports. Retraction therefore stamps the
    row rather than deleting it — see ReportQuerySet.active.
    """
    since = timezone.now() - timedelta(days=1)
    return (PostReport.objects.filter(user=user, creation_time__gte=since).count()
            + CommentReport.objects.filter(user=user, creation_time__gte=since).count()
            + AccountReport.objects.filter(user=user, creation_time__gte=since).count())


def daily_report_limit_reached(user):
    """Whether this account has spent its daily report budget.

    A second bound under the per-endpoint rate limits: those cap how *fast* one
    account can report, this caps how much it can report at all, so a single
    account cannot flood the moderation queue no matter how patiently it paces
    itself.
    """
    return reports_filed_in_last_day(user) >= MAX_REPORTS_PER_USER_PER_DAY


def _get_or_create_review(post, comment, account=None):
    """The review row for this content, creating it on the first report.

    The atomic block keeps a lost race on the unique constraint from poisoning
    the caller's transaction; the loser simply adopts the winner's row.
    """
    try:
        with transaction.atomic():
            return ModerationReview.objects.get_or_create(post=post, comment=comment, account=account)
    except IntegrityError:
        return ModerationReview.objects.get(post=post, comment=comment, account=account), False


def lock_reviewed_content(post=None, comment=None, account=None):
    """Row-lock the post or comment a review is (or would be) about.

    The shared locking protocol for review transitions and caption/comment
    edits (issue #462): whoever opens, escalates or resolves a review, and an
    edit's final check-and-write, first locks the CONTENT row and only then
    touches the review row — always in that order, so they serialize without
    deadlocking. The content row rather than the review row, because opening a
    review inserts one: there is no review row to lock yet. An edit holding the
    lock therefore sees every review state it is checking for, and no review
    can open or change state until the edit has committed (or vice versa).
    The lock is FOR NO KEY UPDATE: it still excludes every other locker of the
    row, but not the KEY SHARE locks Postgres takes for the foreign-key checks
    of likes, saves, comments and reports inserted against it — paths that
    lock the author first, so a full FOR UPDATE here could deadlock with them.
    For an account review (issue #602) the content row is the reported user's
    own row, which set_bio, the profile photo worker and the moderator actions
    lock before touching the profile fields under review.
    Call inside transaction.atomic(). Returns the locked row, or None if it is
    gone.
    """
    target = next(t for t in (post, comment, account) if t is not None)
    return type(target).objects.select_for_update(no_key=True).filter(pk=target.pk).first()


def advance_review(post=None, comment=None, account=None):
    """Advance the moderation review for content that was just reported.

    The first report opens a review. Later reports never hide anything by
    themselves: while a review is pending or already escalated they do nothing
    at all, once a moderator has decided (hidden or dismissed) they do nothing
    forever, and on content the automated re-review cleared they only count
    toward escalating it to a human.

    Must run inside transaction.atomic() with the content row already locked
    (lock_reviewed_content) — the same transaction that inserts the report, so
    the report and the review it opens commit together and no edit can land
    between them (issue #462). Returns (review, opened); pass both to
    queue_opened_review once the transaction has committed.
    """
    review, opened = _get_or_create_review(post, comment, account)
    if opened:
        return review, True
    if review.status != REVIEW_STATUS_CLEARED:
        # Pending (already queued), escalated (a human is on it), or terminal
        # (decided — piling on is exactly what must not work).
        logger.info("advance_review: review %s is %s; the report changes nothing.",
                    review.review_identifier, review.status)
        return review, False
    if review.reports_since_last_review() >= REPORTS_AFTER_CLEAR_BEFORE_ESCALATION:
        review.status = REVIEW_STATUS_ESCALATED
        review.save(update_fields=['status', 'updated'])
        logger.info("advance_review: review %s escalated to a moderator after %d further reports.",
                    review.review_identifier, review.reports_since_last_review())
    return review, False


def queue_opened_review(review, opened):
    """Queue the automated re-review of a review advance_review just opened.
    Call after the transaction that opened it has committed, so the (possibly
    minutes-long) cascade never runs while the content row lock is held."""
    if opened:
        logger.info("queue_opened_review: opened review %s for %s; queuing automated re-review.",
                    review.review_identifier, review.target_kind)
        tasks.enqueue_report_review(review.review_identifier)


def record_report(post=None, comment=None, account=None):
    """Advance the moderation review for content whose report is already saved:
    advance_review under the content row lock, then queue_opened_review. The
    report endpoints insert the report in that same locked transaction instead
    (see views.report_post / report_comment); this is the entry point for
    callers that have no report write of their own to fold in."""
    with transaction.atomic():
        lock_reviewed_content(post, comment, account)
        review, opened = advance_review(post, comment, account)
    queue_opened_review(review, opened)
    return review


def withdraw_report(post=None, comment=None, account=None):
    """Fold a retracted report back into the review.

    A retraction is not a moderation decision, so it never un-hides anything —
    that is the whole point of dropping the old un-hide-on-retraction rule, which
    made hiding a reversible group vote. The one thing it does is spare a
    moderator a pointless queue entry: an escalation whose reports have all been
    withdrawn has nothing left to look at, so it drops back to cleared.
    """
    with transaction.atomic():
        # Same lock order as record_report (content, then review).
        lock_reviewed_content(post, comment, account)
        review = ModerationReview.objects.filter(post=post, comment=comment, account=account).first()
        if review is None or review.status != REVIEW_STATUS_ESCALATED:
            return review
        if review.report_count() == 0:
            review.status = REVIEW_STATUS_CLEARED
            fields = review.restart_escalation_count()
            review.save(update_fields=['status', *fields, 'updated'])
            logger.info("withdraw_report: review %s de-escalated; every report was retracted.",
                        review.review_identifier)
    return review


def _lock_for_resolution(review):
    """Take the locks a moderator's decision needs, in the shared order
    (content row, then review row — see lock_reviewed_content), and re-read
    both under them. A decision landing between an edit's final check and its
    save would otherwise hand the new text the old text's ruling (issue #462).
    Call inside transaction.atomic(); returns the locked content, or None when
    it (and so the review) is gone. `review` is refreshed in place."""
    target = lock_reviewed_content(post=review.post if review.post_id else None,
                                   comment=review.comment if review.comment_id else None,
                                   account=review.account if review.account_id else None)
    if target is None or not ModerationReview.objects.select_for_update().filter(pk=review.pk).exists():
        return None
    review.refresh_from_db()
    return target


def hide_reviewed_content(review, moderator=None, note=''):
    """Apply a moderator's decision to hide the content a review is about.

    Hidden as HIDDEN_REASON_REPORTS — a human hid it after reading the reports —
    which is appealable, so the author still gets a route back. Content already
    hidden for another reason keeps that reason, so an appeal can still tell the
    author what actually happened to it.

    An account has nothing to hide as a whole (issue #602): "hiding" it removes
    its bio and approved profile photo, the parts of a profile its owner can
    replace. A username is fixed once chosen, so a moderator who finds the
    username itself unacceptable bans the account from the user admin instead.
    """
    if review.account_id:
        return _strip_reviewed_account(review, moderator, note)
    with transaction.atomic():
        target = _lock_for_resolution(review)
        if target is None:
            return review
        if not target.hidden:
            target.hidden = True
            target.hidden_reason = HIDDEN_REASON_REPORTS
            target.save(update_fields=['hidden', 'hidden_reason'])
            logger.info("hide_reviewed_content: %s hidden by moderator review %s.",
                        review.target_kind, review.review_identifier)
        review.resolve(REVIEW_STATUS_HIDDEN, moderator, note or 'Hidden by a moderator after user reports')
    return review


def dismiss_reports(review, moderator=None, note=''):
    """Apply a moderator's decision that the reports were unfounded.

    Terminal: the content is immune to further automated review, so a group that
    keeps reporting it cannot reopen the case. (For an account, only until its
    owner changes the bio or photo — see profile_content_changed. A dismissal
    cannot restore an account's bio or photo either: removing them deletes them.) Content this queue had previously
    hidden (HIDDEN_REASON_REPORTS) is restored, which is how a moderator undoes
    their own hide without making the author file an appeal; content hidden by
    the classifier is left alone, since dismissing *reports* says nothing about
    an automated rejection.
    """
    with transaction.atomic():
        target = _lock_for_resolution(review)
        if target is None:
            return review
        if review.account_id is None and target.hidden and target.hidden_reason == HIDDEN_REASON_REPORTS:
            target.hidden = False
            target.hidden_reason = HIDDEN_REASON_NONE
            target.save(update_fields=['hidden', 'hidden_reason'])
            logger.info("dismiss_reports: %s restored by moderator review %s.",
                        review.target_kind, review.review_identifier)
        review.resolve(REVIEW_STATUS_DISMISSED, moderator, note or 'Reports dismissed by a moderator')
    return review


# --- Account reports (issue #602) --------------------------------------------
#
# An account is reviewed as what it shows everyone: its username, its bio and its
# approved profile photo. Each was moderated when it was set, so a report asks
# the same question again, of the profile as it stands. What a failing verdict
# does differs by part: a bio or photo is simply removed (the owner can set
# another, exactly as when one is rejected on write), but a username is fixed
# once chosen, so a failing username goes to a moderator, who can ban.


def strip_profile_content(user, bio=False, photo=False, reason_code=GENERIC_REASON_CODE):
    """Clear the bio and/or the approved profile photo on a LOCKED user row.

    Saves the row. The removed photo's S3 object is deliberately NOT deleted
    here: an upload key is only scoped to its owner, so the same object can
    also back one of their posts or a pending avatar, and deleting it would
    break that. Once nothing references it, cleanup_orphan_images (which checks
    posts and both avatar fields) reclaims it after its grace window. A photo upload
    still under review is left alone — it is a different picture, and the
    worker classifies it on its own — so the rejected status (which tells the
    owner's client why their avatar disappeared) is only set when there is no
    pending upload whose own status it would overwrite.
    """
    fields = []
    if bio and user.bio:
        user.bio = ""
        fields.append('bio')
    if photo and user.profile_image_url:
        user.profile_image_url = None
        user.profile_image_blurhash = None
        fields += ['profile_image_url', 'profile_image_blurhash']
        if not user.pending_profile_image_url:
            user.profile_image_status = PROFILE_IMAGE_STATUS_REJECTED
            user.profile_image_reason_code = reason_code
            fields += ['profile_image_status', 'profile_image_reason_code']
    if fields:
        user.save(update_fields=fields)


def notify_owner_of_profile_removal(user, removed_parts):
    """Email an account's owner that parts of their profile were removed after a
    review. Like the post review-hide email it says nothing about who reported
    the account or how many did. Best-effort: a mail failure is logged."""
    if not removed_parts or not user.email:
        return
    what = ' and '.join(removed_parts)
    body = (
        f"Your {what} was re-checked against our content guidelines and did not "
        "pass, so it has been removed from your profile. You can set a new one "
        f"from the app or at {settings.FRONTEND_BASE_URL}."
    )
    try:
        send_mail(
            "Part of your profile was removed after a review",
            body,
            settings.EMAIL_HOST_USER,
            [user.email],
        )
    except Exception:
        logger.exception("Failed to send profile-removal email for user %s", user.pk)


def _strip_reviewed_account(review, moderator, note):
    """hide_reviewed_content for an account: remove its bio and photo."""
    with transaction.atomic():
        account = _lock_for_resolution(review)
        if account is None:
            return review
        removed_parts = [part for part, present in (('bio', bool(account.bio)),
                                                    ('profile photo', bool(account.profile_image_url)))
                         if present]
        strip_profile_content(account, bio=True, photo=True)
        review.resolve(REVIEW_STATUS_HIDDEN, moderator,
                       note or 'Bio and profile photo removed by a moderator after user reports')
    logger.info("hide_reviewed_content: account review %s removed %s.",
                review.review_identifier, ', '.join(removed_parts) or 'nothing (already empty)')
    notify_owner_of_profile_removal(account, removed_parts)
    return review


def profile_content_changed(user):
    """Release an account review's decision once the profile it judged is gone.

    A post's text is what it was when it was reviewed (an edit is re-checked on
    its own); a profile is not — its owner replaces the bio and photo whenever
    they like. A decision about the old profile must not bind the new one: a
    dismissal would make a later, unacceptable bio unreportable, and a
    moderator's removal would leave the account permanently deaf to reports. So
    when the bio or approved photo changes, a decided (or cleared) review drops
    back to cleared with its escalation count reset: reports filed from here on
    are about the profile as it now stands. A pending or escalated review is
    left alone — the automated re-review and the moderator both look at the
    profile as it is when they get to it.

    Call inside the transaction that wrote the change, with the user's row
    already locked (lock_reviewed_content(account=user)).
    """
    review = ModerationReview.objects.select_for_update().filter(account=user).first()
    if review is None:
        return
    if review.status not in (REVIEW_STATUS_CLEARED, *TERMINAL_REVIEW_STATUSES):
        return
    review.status = REVIEW_STATUS_CLEARED
    fields = review.restart_escalation_count()
    review.save(update_fields=['status', *fields, 'updated'])
    logger.info("profile_content_changed: account review %s reset to cleared after a profile change.",
                review.review_identifier)
