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

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import tasks
from .constants import (
    HIDDEN_REASON_NONE, HIDDEN_REASON_REPORTS,
    MAX_REPORTS_PER_USER_PER_DAY, REPORTS_AFTER_CLEAR_BEFORE_ESCALATION,
    REVIEW_STATUS_CLEARED, REVIEW_STATUS_DISMISSED, REVIEW_STATUS_ESCALATED,
    REVIEW_STATUS_HIDDEN,
)
from .models import CommentReport, ModerationReview, PostReport

logger = logging.getLogger(__name__)


def reports_filed_in_last_day(user):
    """How many reports this account has filed in the trailing 24 hours, posts
    and comments together."""
    since = timezone.now() - timedelta(days=1)
    return (PostReport.objects.filter(user=user, creation_time__gte=since).count()
            + CommentReport.objects.filter(user=user, creation_time__gte=since).count())


def daily_report_limit_reached(user):
    """Whether this account has spent its daily report budget.

    A second bound under the per-endpoint rate limits: those cap how *fast* one
    account can report, this caps how much it can report at all, so a single
    account cannot flood the moderation queue no matter how patiently it paces
    itself.
    """
    return reports_filed_in_last_day(user) >= MAX_REPORTS_PER_USER_PER_DAY


def _get_or_create_review(post, comment):
    """The review row for this content, creating it on the first report.

    The atomic block keeps a lost race on the unique constraint from poisoning
    the caller's transaction; the loser simply adopts the winner's row.
    """
    try:
        with transaction.atomic():
            return ModerationReview.objects.get_or_create(post=post, comment=comment)
    except IntegrityError:
        return ModerationReview.objects.get(post=post, comment=comment), False


def record_report(post=None, comment=None):
    """Advance the moderation review for freshly reported content.

    The first report opens a review and queues the automated re-review of the
    content. Later reports never hide anything by themselves: while a review is
    pending or already escalated they do nothing at all, once a moderator has
    decided (hidden or dismissed) they do nothing forever, and on content the
    automated re-review cleared they only count toward escalating it to a human.
    """
    review, created = _get_or_create_review(post, comment)
    if created:
        logger.info("record_report: opened review %s for %s; queuing automated re-review.",
                    review.review_identifier, review.target_kind)
        tasks.enqueue_report_review(review.review_identifier)
        return review

    if review.status != REVIEW_STATUS_CLEARED:
        # Pending (already queued), escalated (a human is on it), or terminal
        # (decided — piling on is exactly what must not work).
        logger.info("record_report: review %s is %s; the report changes nothing.",
                    review.review_identifier, review.status)
        return review

    if review.reports_since_last_review() >= REPORTS_AFTER_CLEAR_BEFORE_ESCALATION:
        review.status = REVIEW_STATUS_ESCALATED
        review.save(update_fields=['status', 'updated'])
        logger.info("record_report: review %s escalated to a moderator after %d further reports.",
                    review.review_identifier, review.reports_since_last_review())
    return review


def withdraw_report(post=None, comment=None):
    """Fold a retracted report back into the review.

    A retraction is not a moderation decision, so it never un-hides anything —
    that is the whole point of dropping the old un-hide-on-retraction rule, which
    made hiding a reversible group vote. The one thing it does is spare a
    moderator a pointless queue entry: an escalation whose reports have all been
    withdrawn has nothing left to look at, so it drops back to cleared.
    """
    review = ModerationReview.objects.filter(post=post, comment=comment).first()
    if review is None or review.status != REVIEW_STATUS_ESCALATED:
        return review
    if review.report_count() == 0:
        review.status = REVIEW_STATUS_CLEARED
        review.reports_at_last_review = 0
        review.save(update_fields=['status', 'reports_at_last_review', 'updated'])
        logger.info("withdraw_report: review %s de-escalated; every report was retracted.",
                    review.review_identifier)
    return review


def hide_reviewed_content(review, moderator=None, note=''):
    """Apply a moderator's decision to hide the content a review is about.

    Hidden as HIDDEN_REASON_REPORTS — a human hid it after reading the reports —
    which is appealable, so the author still gets a route back. Content already
    hidden for another reason keeps that reason, so an appeal can still tell the
    author what actually happened to it.
    """
    target = review.target
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
    keeps reporting it cannot reopen the case. Content this queue had previously
    hidden (HIDDEN_REASON_REPORTS) is restored, which is how a moderator undoes
    their own hide without making the author file an appeal; content hidden by
    the classifier is left alone, since dismissing *reports* says nothing about
    an automated rejection.
    """
    target = review.target
    if target.hidden and target.hidden_reason == HIDDEN_REASON_REPORTS:
        target.hidden = False
        target.hidden_reason = HIDDEN_REASON_NONE
        target.save(update_fields=['hidden', 'hidden_reason'])
        logger.info("dismiss_reports: %s restored by moderator review %s.",
                    review.target_kind, review.review_identifier)
    review.resolve(REVIEW_STATUS_DISMISSED, moderator, note or 'Reports dismissed by a moderator')
    return review
