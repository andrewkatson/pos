import logging
import os
from urllib.parse import urlparse

import boto3
from django.conf import settings

logger = logging.getLogger(__name__)


def _redact(image_url):
    """Drop the query/fragment from a URL before logging it, so pre-signed-URL
    parameters (e.g. X-Amz-Signature) are never written to logs."""
    if not image_url:
        return image_url
    try:
        return urlparse(image_url)._replace(query='', fragment='').geturl()
    except Exception:
        return '<unparseable url>'


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
    # strip it. A virtual-hosted bucket whose own name starts with "s3-" is NOT
    # path-style — there the second label is the S3 service label (e.g. "s3" in
    # s3-my-bucket.s3.amazonaws.com, or "s3-accelerate" in
    # s3-my-bucket.s3-accelerate.amazonaws.com) and the path is already just the
    # key — so exclude any host whose second label starts with "s3". A genuine
    # path-style host's second label is a region or "amazonaws", neither of
    # which starts with "s3", so this is safe.
    is_path_style = (first_label == 's3' or first_label.startswith('s3-')) and not second_label.startswith('s3')
    if is_path_style:
        _, _, key = key.partition('/')
    return key


def _s3_client():
    """A boto3 S3 client built from the backend's AWS credentials, or None if
    they are not configured (callers treat a missing client as a soft failure)."""
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not aws_access_key or not aws_secret_key:
        logger.error("Missing AWS credentials — cannot build an S3 client.")
        return None
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=region,
    )


# Post images are always JPEG (both clients transcode before uploading), and the
# presigned URL is signed over this content type so the uploader cannot PUT
# anything else without the signature check failing.
UPLOAD_CONTENT_TYPE = "image/jpeg"

# Presigned upload URLs are single-use in practice (the client PUTs immediately
# after asking), so keep the validity window short.
UPLOAD_URL_EXPIRES_SECONDS = 300


def generate_presigned_upload(key, client=None):
    """Create a short-lived presigned PUT URL for `key` in the images bucket.

    Returns `(upload_url, image_url)` where `upload_url` is the presigned URL
    the client PUTs the JPEG bytes to, and `image_url` is the same URL with the
    signing query stripped — i.e. the canonical object URL the client should
    send back to make_post. Returns `(None, None)` if AWS credentials are not
    configured or signing fails.

    This exists so clients never hold AWS credentials: the backend picks the
    key (scoped to the authenticated user) and hands out a signature that is
    only valid for that exact key and content type (issue #310).
    """
    if client is None:
        client = _s3_client()
    if client is None:
        return None, None
    try:
        upload_url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': key,
                'ContentType': UPLOAD_CONTENT_TYPE,
            },
            ExpiresIn=UPLOAD_URL_EXPIRES_SECONDS,
        )
    except Exception:
        logger.exception("Failed to generate a presigned upload URL for key=%s", key)
        return None, None
    image_url = urlparse(upload_url)._replace(query='', fragment='').geturl()
    return upload_url, image_url


def delete_key(key, client=None):
    """Best-effort delete of an object key from both buckets.

    A post's image is uploaded to the source bucket and a Lambda mirrors a
    compressed copy to the compressed bucket under the same key, so cleanup must
    remove both. S3 DeleteObject is idempotent (deleting a missing key is not an
    error), so this needs no special 404 handling. Never raises: failures are
    logged and swallowed so cleanup cannot break its caller. Callers deleting
    many keys (the sweeper) should pass a shared client.

    Note: the backend's IAM credentials need s3:DeleteObject on both
    AWS_STORAGE_BUCKET_NAME and AWS_COMPRESSED_STORAGE_BUCKET_NAME.
    """
    if not key:
        return
    if client is None:
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


def delete_image(image_url):
    """Best-effort delete of an uploaded image (by its URL) from both buckets."""
    key = image_url_to_key(image_url)
    if not key:
        logger.warning("Could not derive an S3 key from image_url=%r; skipping delete.", _redact(image_url))
        return
    delete_key(key)


def iter_bucket_objects(bucket, client):
    """Yield each object summary ({'Key', 'LastModified', ...}) in a bucket,
    transparently paging through large listings."""
    paginator = client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            yield obj
