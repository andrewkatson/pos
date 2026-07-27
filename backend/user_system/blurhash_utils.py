"""BlurHash placeholders for post images (issue #387).

A BlurHash is a ~30-character string that encodes a very low-resolution, blurred
version of an image (https://github.com/woltapp/blurhash). The web/iOS/Android
clients decode it into a smooth blurred preview rendered *while the real image
is still loading*, so a loading feed tile shows a soft blur of the actual photo
instead of a flat grey square.

It is purely decorative metadata. Computing it must never influence whether a
post is published or wedge the classification pipeline, so every failure here is
logged and swallowed and the function returns None — in which case the clients
simply keep their existing plain placeholder.
"""
import logging
from io import BytesIO

import blurhash
from django.conf import settings
from PIL import Image, ImageOps

from .s3 import _s3_client, image_url_to_key, is_source_bucket_url

logger = logging.getLogger(__name__)

# BlurHash component counts (how many horizontal/vertical basis functions the
# hash encodes). 4x3 is the value Wolt uses in their own examples: enough detail
# to read as a blurred version of the image while keeping the string short.
BLURHASH_X_COMPONENTS = 4
BLURHASH_Y_COMPONENTS = 3

# The encoder walks every pixel in pure Python, so encoding a full-resolution
# original would take seconds. A BlurHash only captures a handful of
# low-frequency components, so downscaling to a tiny thumbnail first is both
# dramatically faster and visually identical.
_ENCODE_MAX_DIMENSION = 32


def _image_to_pixel_rows(image):
    """Convert a PIL RGB image to the nested ``[y][x][r, g, b]`` list of 0-255
    ints that ``blurhash.encode`` expects, without pulling in numpy."""
    width, height = image.size
    pixels = list(image.getdata())  # row-major flat list of (r, g, b) tuples
    return [
        [list(pixels[row * width + col]) for col in range(width)]
        for row in range(height)
    ]


def compute_blurhash_for_image_url(image_url):
    """Return a BlurHash string for the image at ``image_url``, or None on any failure.

    Fetches the object from the source S3 bucket, downscales it, and encodes a
    4x3 BlurHash. Never raises: a missing object, unreadable bytes, absent AWS
    credentials, or an encode error all just yield None so the caller records no
    placeholder and the clients fall back to a plain tile.
    """
    if not image_url:
        return None
    try:
        client = _s3_client()
        if client is None:
            return None
        # Only ever fetch from our own source bucket. is_source_bucket_url rejects
        # any URL whose bucket isn't derivable from the host or doesn't match the
        # configured source bucket (the same SSRF guard make_post applies), so a
        # look-alike or non-S3 URL can never be coerced into a bucket+key here.
        if not is_source_bucket_url(image_url):
            logger.warning("Image URL is not in the source bucket; skipping BlurHash.")
            return None
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        key = image_url_to_key(image_url)
        if not key:
            logger.warning("Could not derive an S3 key for BlurHash; skipping.")
            return None
        response = client.get_object(Bucket=bucket, Key=key)
        image = Image.open(BytesIO(response['Body'].read()))
        # exif_transpose so the blur matches the orientation the clients render;
        # convert to RGB so the encoder always sees three 0-255 channels.
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((_ENCODE_MAX_DIMENSION, _ENCODE_MAX_DIMENSION))
        return blurhash.encode(
            _image_to_pixel_rows(image),
            BLURHASH_X_COMPONENTS,
            BLURHASH_Y_COMPONENTS,
        )
    except Exception:
        logger.exception("Failed to compute BlurHash for a post image; leaving it unset.")
        return None
