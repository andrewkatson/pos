import logging

from django.core.management.base import BaseCommand, CommandError

from user_system.blurhash_utils import compute_blurhash_for_image_url
from user_system.models import Post, PositiveOnlySocialUser

logger = logging.getLogger(__name__)

# Rows fetched per query. Each row triggers an S3 fetch + pure-Python encode, so
# keep chunks modest; the point of chunking is only to avoid loading the whole
# table into memory, not throughput.
DEFAULT_BATCH_SIZE = 200

TARGET_POSTS = 'posts'
TARGET_PROFILES = 'profiles'
TARGET_ALL = 'all'


class _Target:
    """One kind of image to backfill: which rows are missing a hash, where the
    image URL lives, and which column receives the computed hash.

    Posts and profile photos differ only in those three details, so the chunked
    cursor loop below is written once against this description rather than twice.
    """

    def __init__(self, name, noun, model, pk_field, url_field, hash_field):
        self.name = name
        self.noun = noun                # what the human-readable counts say
        self.model = model
        self.pk_field = pk_field        # the column the cursor orders/advances by
        self.url_field = url_field
        self.hash_field = hash_field

    def queryset(self):
        return self.model.objects.filter(**{
            f'{self.url_field}__isnull': False,
            f'{self.hash_field}__isnull': True,
        })


TARGETS = {
    # image_url__isnull=False already excludes text-only posts and
    # terminally-rejected ones (their image_url is cleared on rejection), so
    # every match is a post that renders an image but has no placeholder.
    TARGET_POSTS: _Target(
        TARGET_POSTS, 'post', Post, 'post_identifier', 'image_url', 'image_blurhash'),
    # Only the *approved* photo (profile_image_url) — a pending or rejected
    # upload is never shown to anyone else, so it needs no placeholder, and the
    # worker will compute one if and when it approves the photo.
    TARGET_PROFILES: _Target(
        TARGET_PROFILES, 'profile photo', PositiveOnlySocialUser, 'id',
        'profile_image_url', 'profile_image_blurhash'),
}


class Command(BaseCommand):
    help = (
        "Compute a BlurHash placeholder for every post image (issue #438) and "
        "approved profile photo (issue #460) that has no hash yet. New images get "
        "a hash from the classification worker (issues #387/#460); this is the "
        "backfill for images published before that shipped, whose tiles/avatars "
        "otherwise show a flat grey placeholder. Reuses the exact same encoder as "
        "the worker, so clients need no change. Safe to re-run: it only touches "
        "rows whose hash is still null and never overwrites one the worker may "
        "have set concurrently. Images that can't be fetched/encoded are left "
        "null (still grey) and examined only once per run, so a broken object "
        "never wedges the command; a later run re-attempts them, which lets a "
        "transient failure recover."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
            help=f"Rows fetched per query (default {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help="Stop after examining this many rows *per target* (default: no limit).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report how many rows are missing a hash without writing anything.",
        )
        parser.add_argument(
            '--target', choices=[TARGET_POSTS, TARGET_PROFILES, TARGET_ALL],
            default=TARGET_ALL,
            help="Which images to backfill (default: all).",
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        limit = options['limit']
        dry_run = options['dry_run']
        target = options['target']

        # Fail fast on nonsensical flags: a non-positive batch size slices an
        # empty chunk (the loop would just exit having done nothing), and a
        # negative limit would print a negative count / short-circuit oddly.
        if batch_size < 1:
            raise CommandError("--batch-size must be a positive integer.")
        if limit is not None and limit < 1:
            raise CommandError("--limit must be a positive integer when given.")

        selected = ([TARGET_POSTS, TARGET_PROFILES] if target == TARGET_ALL
                    else [target])
        for name in selected:
            self._run_target(TARGETS[name], batch_size, limit, dry_run)

    def _run_target(self, target, batch_size, limit, dry_run):
        base_qs = target.queryset()

        if dry_run:
            count = base_qs.count()
            if limit is not None:
                count = min(count, limit)
            self.stdout.write(f"[dry-run] {count} {target.noun}(s) would be backfilled.")
            return

        updated = 0
        skipped = 0
        processed = 0
        # Cursor by this target's primary key (target.pk_field — post_identifier
        # for posts, id for users; both are UUIDs) rather than re-selecting
        # "still null" rows: a row whose image can't be encoded stays null, so a
        # null-only filter would hand it back every batch and loop forever within
        # this run. Advancing past each pk guarantees this run terminates and
        # processes each failure at most once. (A later run still re-examines any
        # remaining nulls, which is intended: a transient S3/encode failure gets
        # another attempt.)
        last_pk = None
        while True:
            if limit is not None and processed >= limit:
                break
            chunk_size = batch_size
            if limit is not None:
                chunk_size = min(batch_size, limit - processed)

            chunk_qs = base_qs.order_by(target.pk_field)
            if last_pk is not None:
                chunk_qs = chunk_qs.filter(**{f'{target.pk_field}__gt': last_pk})
            chunk = list(chunk_qs[:chunk_size])
            if not chunk:
                break

            for row in chunk:
                last_pk = getattr(row, target.pk_field)
                processed += 1
                image_blurhash = compute_blurhash_for_image_url(
                    getattr(row, target.url_field))
                if not image_blurhash:
                    skipped += 1
                    continue
                # Conditional update: only write if the row is still null, so a
                # hash the worker set for this row since we read it is never
                # clobbered. This is also what makes the command safe to re-run.
                updated += target.model.objects.filter(**{
                    target.pk_field: last_pk,
                    f'{target.hash_field}__isnull': True,
                }).update(**{target.hash_field: image_blurhash})

        logger.info(
            "Backfilled BlurHash for %s %s(s); %s could not be computed.",
            updated, target.noun, skipped,
        )
        self.stdout.write(
            f"Backfilled {updated} {target.noun}(s); "
            f"skipped {skipped} that could not be computed."
        )
