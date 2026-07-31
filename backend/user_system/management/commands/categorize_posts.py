import logging

from django.core.management.base import BaseCommand, CommandError

from user_system import tasks
from user_system.constants import NON_CATEGORIZABLE_HIDDEN_REASONS
from user_system.models import Post

logger = logging.getLogger(__name__)

# Bound how many posts one run touches so a large backlog is worked through in
# manageable, restartable chunks rather than one giant pass. Each run re-queries
# for still-uncategorized posts, so scheduling it from cron drains the backlog
# over successive runs.
DEFAULT_LIMIT = 500


class Command(BaseCommand):
    help = (
        "Backfill interest categorization (issues #446/#35): enqueue offline "
        "interest tagging for approved posts that have no interest buckets yet "
        "— existing posts from before the feature, and any the approval hook "
        "missed (worker crash, deploy, provider blip). Idempotent and "
        "best-effort; safe to run from cron alongside sweep_classifications and "
        "cleanup_orphan_images."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=DEFAULT_LIMIT,
            help=f"Maximum posts to (re)categorize this run (default {DEFAULT_LIMIT}).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would be categorized without enqueueing anything.",
        )

    def handle(self, *args, **options):
        limit = options['limit']
        if limit <= 0:
            raise CommandError("--limit must be a positive integer.")
        dry_run = options['dry_run']

        # Approved posts (passed classification, so not pending/classifier-hidden;
        # a report-hidden post still has categorizable content and may return to
        # the feed) that carry no interest buckets yet. categorize_post itself
        # re-checks the hidden state, so a post that changes between this query
        # and the job is handled correctly.
        candidates = (
            Post.objects
            .exclude(hidden_reason__in=NON_CATEGORIZABLE_HIDDEN_REASONS)
            .filter(interest_categories__isnull=True)
            .order_by('creation_time')
            .values_list('post_identifier', flat=True)[:limit]
        )

        processed = 0
        for post_identifier in list(candidates):
            processed += 1
            if dry_run:
                self.stdout.write(f"[dry-run] would categorize {post_identifier}")
            else:
                tasks.enqueue_post_categorization(post_identifier)

        summary = f"categorize_posts: {'would process' if dry_run else 'processed'} {processed} post(s)."
        self.stdout.write(summary)
        logger.info(summary)
