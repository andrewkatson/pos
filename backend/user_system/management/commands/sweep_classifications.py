import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from user_system import tasks
from user_system.constants import (
    CLASSIFICATION_MAX_ATTEMPTS,
    HIDDEN_REASON_CLASSIFIER_FINAL,
    HIDDEN_REASON_PENDING_CLASSIFICATION,
)
from user_system.models import Post

logger = logging.getLogger(__name__)

# A healthy classification finishes in under a minute, so a pending post with
# no classification activity for this long has fallen out of the queue
# (worker crash, deploy, Redis flush). "Activity" is the post's updated_time,
# which the worker bumps on every attempt — keying on it rather than
# creation_time means back-to-back sweep runs don't pile duplicate jobs onto
# a post that was attempted moments ago.
DEFAULT_STUCK_MINUTES = 15

# Final-rejection tombstones only exist so the author's client can reconcile
# the outcome; after this long every client has had ample opportunity.
DEFAULT_TOMBSTONE_DAYS = 7


class Command(BaseCommand):
    help = (
        "Reconcile async post classification (issue #282): re-enqueue posts "
        "stuck in pending_classification past a threshold (alerting instead "
        "once their retry budget is exhausted — they stay hidden, fail "
        "closed), and purge final-rejection tombstone rows old enough that "
        "every client has reconciled. Run from cron alongside "
        "cleanup_orphan_images."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--stuck-minutes', type=int, default=DEFAULT_STUCK_MINUTES,
            help=("Re-enqueue pending posts with no classification activity for this many "
                  f"minutes (default {DEFAULT_STUCK_MINUTES})."),
        )
        parser.add_argument(
            '--tombstone-days', type=int, default=DEFAULT_TOMBSTONE_DAYS,
            help=f"Delete final-rejection tombstones older than this (default {DEFAULT_TOMBSTONE_DAYS}).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would be done without enqueueing or deleting anything.",
        )

    def handle(self, *args, **options):
        stuck_minutes = options['stuck_minutes']
        tombstone_days = options['tombstone_days']
        if stuck_minutes < 0 or tombstone_days < 0:
            raise CommandError("--stuck-minutes and --tombstone-days must be non-negative.")
        dry_run = options['dry_run']
        now = timezone.now()

        # --- Stuck pending posts: re-enqueue or alert. ---
        # Keyed on updated_time (bumped by every worker attempt, and set at
        # creation) so "stuck" means "no classification activity recently",
        # not merely "old": a post that was just attempted or re-enqueued is
        # left alone until the window passes again.
        stuck_cutoff = now - timedelta(minutes=stuck_minutes)
        # only() + iterator(): the sweep touches two columns per row, so a
        # large backlog streams through in chunks instead of materializing
        # full model instances for every stuck post.
        stuck = Post.objects.filter(
            hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION,
            updated_time__lte=stuck_cutoff,
        ).only('post_identifier', 'classification_attempts', 'classification_alerted')
        requeued = exhausted = newly_alerted = 0
        for post in stuck.iterator():
            if post.classification_attempts >= CLASSIFICATION_MAX_ATTEMPTS:
                # Fail closed: the post stays hidden-pending forever rather
                # than ever publishing unclassified content. The error log is
                # the operator alert; classification_alerted persists that it
                # fired so the same post cannot flood alerts on every cron run
                # (the summary still counts it while it stays exhausted).
                exhausted += 1
                if not post.classification_alerted:
                    newly_alerted += 1
                    if dry_run:
                        self.stdout.write(f"[dry-run] would alert on exhausted post {post.post_identifier}")
                    else:
                        logger.error(
                            "sweep_classifications: post %s has exhausted its %d classification "
                            "attempts and needs operator attention.",
                            post.post_identifier, post.classification_attempts)
                        Post.objects.filter(pk=post.pk).update(classification_alerted=True)
                continue
            requeued += 1
            if dry_run:
                self.stdout.write(f"[dry-run] would re-enqueue {post.post_identifier} "
                                  f"(attempts={post.classification_attempts})")
            else:
                tasks.enqueue_classification(post.post_identifier)

        # --- Old final-rejection tombstones: purge. ---
        tombstone_cutoff = now - timedelta(days=tombstone_days)
        tombstones = Post.objects.filter(
            hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL,
            creation_time__lte=tombstone_cutoff,
        )
        # Count posts before deleting: delete() reports cascaded rows too.
        purged = tombstones.count()
        if dry_run:
            for post in tombstones.only('post_identifier').iterator():
                self.stdout.write(f"[dry-run] would purge tombstone {post.post_identifier}")
        else:
            # The worker already stripped image_url on the transition, so no S3
            # cleanup is owed here (cleanup_orphan_images backstops any miss).
            tombstones.delete()

        verb = "Would re-enqueue" if dry_run else "Re-enqueued"
        purge_verb = "would purge" if dry_run else "purged"
        summary = (f"{verb} {requeued} stuck pending post(s); {exhausted} exhausted "
                   f"(fail-closed, {newly_alerted} newly alerted); {purge_verb} {purged} "
                   f"tombstone(s) older than {tombstone_days}d.")
        self.stdout.write(summary)
        logger.info("sweep_classifications: %s", summary)
