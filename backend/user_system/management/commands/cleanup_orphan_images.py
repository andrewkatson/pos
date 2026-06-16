import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from user_system import s3
from user_system.models import Post

logger = logging.getLogger(__name__)

DEFAULT_GRACE_HOURS = 24


class Command(BaseCommand):
    help = (
        "Delete images in the source and compressed S3 buckets that no live Post "
        "references. A grace window protects objects too new to have become a Post "
        "yet (in-flight uploads) and the brief window where the compression Lambda "
        "writes a copy just after a rejection has already cleaned up the source."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--grace-hours', type=int, default=DEFAULT_GRACE_HOURS,
            help=f"Only delete objects older than this many hours (default {DEFAULT_GRACE_HOURS}).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        client = s3._s3_client()
        if client is None:
            self.stderr.write("No AWS credentials configured; aborting.")
            return

        grace_hours = options['grace_hours']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(hours=grace_hours)

        # Keys that a live Post still points at must never be deleted.
        live_keys = {
            s3.image_url_to_key(url)
            for url in Post.objects.exclude(image_url__isnull=True).values_list('image_url', flat=True)
        }
        live_keys.discard('')

        # Collect candidate keys from both buckets, tracking the newest
        # LastModified seen across them so a key that is recent in either bucket
        # gets the full grace window (the compressed copy is written after the
        # original, so its timestamp is the one that protects an in-flight pair).
        candidates = {}
        for bucket in (settings.AWS_STORAGE_BUCKET_NAME, settings.AWS_COMPRESSED_STORAGE_BUCKET_NAME):
            if not bucket:
                continue
            for obj in s3.iter_bucket_objects(bucket, client):
                key = obj['Key']
                last_modified = obj['LastModified']
                if key not in candidates or last_modified > candidates[key]:
                    candidates[key] = last_modified

        swept = skipped_live = skipped_recent = 0
        for key, last_modified in candidates.items():
            if key in live_keys:
                skipped_live += 1
                continue
            if last_modified > cutoff:
                skipped_recent += 1
                continue
            if dry_run:
                self.stdout.write(f"[dry-run] would delete {key}")
            else:
                s3.delete_key(key, client=client)
            swept += 1

        verb = "Would sweep" if dry_run else "Swept"
        summary = (f"{verb} {swept} orphan object(s); kept {skipped_live} live, "
                   f"{skipped_recent} within {grace_hours}h grace.")
        self.stdout.write(summary)
        logger.info("cleanup_orphan_images: %s", summary)
