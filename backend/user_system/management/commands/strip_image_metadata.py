import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from user_system import s3
from user_system.image_metadata import strip_jpeg_metadata

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Strip metadata (EXIF/XMP/IPTC/comments/trailers) from images already in "
        "the source and compressed S3 buckets, keeping only the EXIF Orientation "
        "tag so existing photos still display upright. The rewrite is lossless — "
        "pixel data is copied verbatim, never re-encoded. This is a one-off "
        "backfill for images uploaded before the clients stripped metadata "
        "themselves (issue #346); objects that are already clean are left "
        "untouched, so re-running it is cheap and safe."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report which objects would be rewritten without writing anything.",
        )

    def handle(self, *args, **options):
        client = s3._s3_client()
        if client is None:
            self.stderr.write("No AWS credentials configured; aborting.")
            return

        dry_run = options['dry_run']
        rewritten = clean = failed = 0

        for bucket in (settings.AWS_STORAGE_BUCKET_NAME, settings.AWS_COMPRESSED_STORAGE_BUCKET_NAME):
            if not bucket:
                continue
            # Iterate the paginator directly so memory stays bounded on large
            # buckets. Per-object failures are caught inside the loop, so the
            # outer except only fires when the listing itself breaks.
            try:
                for obj in s3.iter_bucket_objects(bucket, client):
                    key = obj['Key']
                    try:
                        body = client.get_object(Bucket=bucket, Key=key)['Body'].read()
                        stripped = strip_jpeg_metadata(body)
                        if stripped == body:
                            # Not a JPEG, unparseable, or already metadata-free —
                            # either way there is nothing to rewrite.
                            clean += 1
                            continue
                        if dry_run:
                            self.stdout.write(f"[dry-run] would rewrite s3://{bucket}/{key}")
                        else:
                            # Mirrors how the compression Lambda writes objects.
                            # Note: rewriting a source-bucket object re-triggers
                            # that Lambda, which refreshes the compressed copy —
                            # harmless, since its output is already metadata-free.
                            client.put_object(
                                Bucket=bucket,
                                Key=key,
                                Body=stripped,
                                ContentType=s3.UPLOAD_CONTENT_TYPE,
                            )
                            logger.info("Stripped metadata from s3://%s/%s", bucket, key)
                        rewritten += 1
                    except Exception:
                        logger.exception("Failed to strip s3://%s/%s; continuing.", bucket, key)
                        self.stderr.write(f"Failed to strip s3://{bucket}/{key}; continuing.")
                        failed += 1
            except Exception:
                logger.exception("Failed to list bucket %s; skipping it.", bucket)
                self.stderr.write(f"Failed to list bucket {bucket}; skipping it.")
                failed += 1

        verb = "Would rewrite" if dry_run else "Rewrote"
        summary = (f"{verb} {rewritten} object(s); {clean} already clean; "
                   f"{failed} failed.")
        self.stdout.write(summary)
        logger.info("strip_image_metadata: %s", summary)
