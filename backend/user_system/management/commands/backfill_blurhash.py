import logging

from django.core.management.base import BaseCommand, CommandError

from user_system.blurhash_utils import compute_blurhash_for_image_url
from user_system.models import Post

logger = logging.getLogger(__name__)

# Rows fetched per query. Each row triggers an S3 fetch + pure-Python encode, so
# keep chunks modest; the point of chunking is only to avoid loading the whole
# table into memory, not throughput.
DEFAULT_BATCH_SIZE = 200


class Command(BaseCommand):
    help = (
        "Compute a BlurHash placeholder for every post that has an image but no "
        "hash yet (issue #438). New posts get a hash from the classification "
        "worker (issue #387); this is the backfill for posts published before "
        "that shipped, whose feed tiles otherwise show a flat grey placeholder. "
        "Reuses the exact same encoder as the worker, so clients need no change. "
        "Safe to re-run: it only touches posts whose image_blurhash is still null "
        "and never overwrites a hash the worker may have set concurrently. Posts "
        "whose image can't be fetched/encoded are left null (still grey) and "
        "examined only once per run, so a broken object never wedges the command; "
        "a later run re-attempts them, which lets a transient failure recover."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
            help=f"Posts fetched per query (default {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help="Stop after examining this many posts (default: no limit).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report how many posts are missing a hash without writing anything.",
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        limit = options['limit']
        dry_run = options['dry_run']

        # Fail fast on nonsensical flags: a non-positive batch size slices an
        # empty chunk (the loop would just exit having done nothing), and a
        # negative limit would print a negative count / short-circuit oddly.
        if batch_size < 1:
            raise CommandError("--batch-size must be a positive integer.")
        if limit is not None and limit < 1:
            raise CommandError("--limit must be a positive integer when given.")

        # image_url__isnull=False already excludes text-only posts and
        # terminally-rejected ones (their image_url is cleared on rejection), so
        # every match is a post that renders an image but has no placeholder.
        base_qs = Post.objects.filter(image_url__isnull=False, image_blurhash__isnull=True)

        if dry_run:
            count = base_qs.count()
            if limit is not None:
                count = min(count, limit)
            self.stdout.write(f"[dry-run] {count} post(s) would be backfilled.")
            return

        updated = 0
        skipped = 0
        processed = 0
        # Cursor by primary key (a UUID) rather than re-selecting "still null"
        # rows: a post whose image can't be encoded stays null, so a null-only
        # filter would hand it back every batch and loop forever within this run.
        # Advancing past each pk guarantees this run terminates and processes each
        # failure at most once. (A later run still re-examines any remaining nulls,
        # which is intended: a transient S3/encode failure gets another attempt.)
        last_pk = None
        while True:
            if limit is not None and processed >= limit:
                break
            chunk_size = batch_size
            if limit is not None:
                chunk_size = min(batch_size, limit - processed)

            chunk_qs = base_qs.order_by('post_identifier')
            if last_pk is not None:
                chunk_qs = chunk_qs.filter(post_identifier__gt=last_pk)
            chunk = list(chunk_qs[:chunk_size])
            if not chunk:
                break

            for post in chunk:
                last_pk = post.post_identifier
                processed += 1
                image_blurhash = compute_blurhash_for_image_url(post.image_url)
                if not image_blurhash:
                    skipped += 1
                    continue
                # Conditional update: only write if the row is still null, so a
                # hash the worker set for this post since we read it is never
                # clobbered. This is also what makes the command safe to re-run.
                updated += Post.objects.filter(
                    post_identifier=post.post_identifier, image_blurhash__isnull=True
                ).update(image_blurhash=image_blurhash)

        logger.info(
            "Backfilled BlurHash for %s post(s); %s could not be computed.",
            updated, skipped,
        )
        self.stdout.write(
            f"Backfilled {updated} post(s); skipped {skipped} that could not be computed."
        )
