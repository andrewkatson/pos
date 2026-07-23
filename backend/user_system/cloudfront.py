import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlparse, urlunparse

from django.conf import settings

from .s3 import image_url_to_key
from .utils import get_compressed_image_url

logger = logging.getLogger(__name__)


def _redact(url):
    """Drop the query/fragment from a URL before logging it, so signing
    parameters (Signature, Key-Pair-Id, ...) are never written to logs.
    Mirrors s3._redact."""
    if not url:
        return url
    try:
        return urlparse(url)._replace(query='', fragment='').geturl()
    except Exception:
        return '<unparseable url>'


def _rsa_signer(private_key_pem):
    """Build the RSA-SHA1 signer callable CloudFront requires from a PEM private
    key. `cryptography` is imported lazily so the graceful-fallback path (no
    CloudFront configured) never needs the dependency at import time."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'), password=None
    )

    def _sign(message):
        return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())

    return _sign


def _private_key_pem():
    """Return the CloudFront signing private key PEM, read either from the
    CLOUDFRONT_PRIVATE_KEY setting (inline PEM) or CLOUDFRONT_PRIVATE_KEY_PATH
    (a file the deploy mounts), or None if neither is configured."""
    inline = (getattr(settings, 'CLOUDFRONT_PRIVATE_KEY', '') or '').strip()
    if inline:
        return inline
    path = (getattr(settings, 'CLOUDFRONT_PRIVATE_KEY_PATH', '') or '').strip()
    if path:
        return _read_key_file(path)
    return None


# Successful PEM file reads are cached per path so the key is read from disk at
# most once per process (a signed URL is built once per serialized image, many
# times per request). Failures are not cached, so a transient read error retries.
_key_file_cache = {}


def _read_key_file(path):
    if path in _key_file_cache:
        return _key_file_cache[path]
    try:
        with open(path, 'r', encoding='utf-8') as f:
            pem = f.read().strip()
    except OSError:
        logger.exception("Could not read CLOUDFRONT_PRIVATE_KEY_PATH=%s", path)
        return None
    _key_file_cache[path] = pem
    return pem


@lru_cache(maxsize=1)
def _signer(key_pair_id, private_key_pem):
    """A cached CloudFrontSigner. Keyed on (key_pair_id, pem) so a settings
    change in tests rebuilds it, and so the RSA key is parsed only once in
    production."""
    from botocore.signers import CloudFrontSigner
    return CloudFrontSigner(key_pair_id, _rsa_signer(private_key_pem))


def _sign(domain, stored_image_url, fallback):
    """Sign `https://{domain}/{key}` with a CloudFront canned policy, where key
    is derived from the stored S3 URL. Returns `fallback` unchanged if CloudFront
    is not fully configured, if no key can be derived, or if signing fails — so a
    missing/broken signing config degrades to today's behavior rather than
    breaking image serving."""
    domain = (domain or '').strip()
    key_pair_id = (getattr(settings, 'CLOUDFRONT_KEY_PAIR_ID', '') or '').strip()
    private_key_pem = _private_key_pem()

    if not domain or not key_pair_id or not private_key_pem:
        return fallback
    if not stored_image_url:
        return stored_image_url

    key = image_url_to_key(stored_image_url)
    if not key:
        logger.warning("Could not derive an S3 key from url=%r; serving unsigned.", _redact(stored_image_url))
        return fallback

    url = urlunparse(('https', domain, f'/{key}', '', '', ''))

    try:
        # Inside the try so a mis-typed expiry (e.g. injected via override_settings)
        # degrades to the fallback rather than 500ing — honoring the graceful
        # fallback contract.
        expiry_seconds = int(getattr(settings, 'CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS', 86400))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
        return _signer(key_pair_id, private_key_pem).generate_presigned_url(
            url, date_less_than=expires_at
        )
    except Exception:
        logger.exception("Failed to sign CloudFront URL for key=%s; serving unsigned.", key)
        return fallback


def sign_compressed_url(stored_image_url):
    """Return a CloudFront signed URL for the compressed copy of a post's image.

    `stored_image_url` is the canonical source-bucket URL saved on the Post. When
    CloudFront is configured this returns a signed URL on CLOUDFRONT_IMAGES_DOMAIN;
    otherwise it falls back to the legacy compressed-bucket URL swap so local dev
    and tests work without a signing key."""
    return _sign(
        getattr(settings, 'CLOUDFRONT_IMAGES_DOMAIN', ''),
        stored_image_url,
        fallback=get_compressed_image_url(stored_image_url),
    )


def sign_original_url(stored_image_url):
    """Return a CloudFront signed URL for the full-resolution original of a post's
    image (the client fallback used while the compressed copy is still missing).

    Signed on CLOUDFRONT_ORIGINALS_DOMAIN when configured; otherwise falls back to
    the stored URL unchanged."""
    return _sign(
        getattr(settings, 'CLOUDFRONT_ORIGINALS_DOMAIN', ''),
        stored_image_url,
        fallback=stored_image_url,
    )
