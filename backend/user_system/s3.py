import logging
import os
from urllib.parse import urlparse

import boto3
from django.conf import settings

logger = logging.getLogger(__name__)


def image_url_to_key(image_url):
    """Extract the S3 object key from an uploaded image URL.

    Clients upload to `{user_id}/{uuid}.jpeg`. For path-style hosts
    (`s3[.-]region.amazonaws.com/bucket/key`) the leading bucket segment is
    stripped; for virtual-hosted hosts (`bucket.s3...amazonaws.com/key`) the
    path is already just the key. Returns '' if no key can be derived.
    """
    if not image_url:
        return ''
    parsed = urlparse(image_url)
    key = parsed.path.lstrip('/')
    labels = parsed.hostname.split('.') if parsed.hostname else []
    first_label = labels[0] if labels else ''
    second_label = labels[1] if len(labels) > 1 else ''
    # Path-style hosts (s3.amazonaws.com, s3.<region>.amazonaws.com,
    # s3-<region>.amazonaws.com) carry the bucket as the first path segment, so
    # strip it. A virtual-hosted bucket whose own name starts with "s3-" (e.g.
    # s3-my-bucket.s3.amazonaws.com) is NOT path-style — there the second label
    # is the literal "s3" and the path is already just the key — so exclude it.
    is_path_style = (first_label == 's3' or first_label.startswith('s3-')) and second_label != 's3'
    if is_path_style:
        _, _, key = key.partition('/')
    return key


def _s3_client():
    """A boto3 S3 client built from the backend's AWS credentials, or None if
    they are not configured (deletion is best-effort and must not hard-fail)."""
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not aws_access_key or not aws_secret_key:
        logger.error("Missing AWS credentials — cannot perform S3 delete.")
        return None
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=region,
    )


def delete_image(image_url):
    """Best-effort delete of an uploaded image from both buckets.

    A post's image is uploaded to the source bucket and a Lambda mirrors a
    compressed copy to the compressed bucket under the same key, so cleanup must
    remove both. S3 DeleteObject is idempotent (deleting a missing key is not an
    error), so this needs no special 404 handling. Never raises: failures are
    logged and swallowed so cleanup cannot break the request that triggered it.

    Note: the backend's IAM credentials need s3:DeleteObject on both
    AWS_STORAGE_BUCKET_NAME and AWS_COMPRESSED_STORAGE_BUCKET_NAME.
    """
    key = image_url_to_key(image_url)
    if not key:
        logger.warning("Could not derive an S3 key from image_url=%r; skipping delete.", image_url)
        return

    client = _s3_client()
    if client is None:
        return

    for bucket in (settings.AWS_STORAGE_BUCKET_NAME, settings.AWS_COMPRESSED_STORAGE_BUCKET_NAME):
        if not bucket:
            continue
        try:
            client.delete_object(Bucket=bucket, Key=key)
            logger.info("Deleted s3://%s/%s", bucket, key)
        except Exception:
            logger.exception("Failed to delete s3://%s/%s", bucket, key)
