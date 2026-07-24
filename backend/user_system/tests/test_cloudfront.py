from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, override_settings

from .. import cloudfront
from ..cloudfront import sign_compressed_url, sign_original_url


def _generate_private_key_pem():
    """A throwaway RSA private key in PEM form, for exercising the signer without
    a real CloudFront key pair."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')


PRIVATE_KEY_PEM = _generate_private_key_pem()

STORED_URL = 'https://goodvibesonly-images.s3.amazonaws.com/42/abc.jpeg'

signing_settings = override_settings(
    CLOUDFRONT_IMAGES_DOMAIN='images.example.com',
    CLOUDFRONT_ORIGINALS_DOMAIN='originals.example.com',
    CLOUDFRONT_KEY_PAIR_ID='K123456789',
    CLOUDFRONT_PRIVATE_KEY=PRIVATE_KEY_PEM,
    CLOUDFRONT_PRIVATE_KEY_PATH='',
    CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS=3600,
    AWS_STORAGE_BUCKET_NAME='goodvibesonly-images',
    AWS_COMPRESSED_STORAGE_BUCKET_NAME='goodvibesonly-imagescompressed',
)


@signing_settings
class CloudFrontSigningTests(SimpleTestCase):
    """The signer builds a CloudFront signed URL on the configured domain from the
    stored S3 object key."""

    def setUp(self):
        # The signer is cached on (key_pair_id, pem); clear it so per-test
        # override_settings changes take effect.
        cloudfront._signer.cache_clear()

    def _assert_signed(self, url, expected_host):
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.netloc, expected_host)
        # The object key is preserved as the path, and the bucket name is gone.
        self.assertEqual(parsed.path, '/42/abc.jpeg')
        self.assertNotIn('goodvibesonly-images', url)
        # Canned-policy signing params are present.
        qs = parse_qs(parsed.query)
        self.assertIn('Expires', qs)
        self.assertIn('Signature', qs)
        self.assertEqual(qs['Key-Pair-Id'], ['K123456789'])

    def test_sign_compressed_url_uses_images_domain(self):
        self._assert_signed(sign_compressed_url(STORED_URL), 'images.example.com')

    def test_sign_original_url_uses_originals_domain(self):
        self._assert_signed(sign_original_url(STORED_URL), 'originals.example.com')

    def test_empty_input_is_returned_unchanged(self):
        self.assertIsNone(sign_compressed_url(None))
        self.assertEqual(sign_compressed_url(''), '')
        self.assertIsNone(sign_original_url(None))

    def test_private_key_read_from_file_path(self):
        """The private key may be supplied via a mounted file rather than inline."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile('w', suffix='.pem', delete=False) as f:
            f.write(PRIVATE_KEY_PEM)
            key_path = f.name

        try:
            with override_settings(CLOUDFRONT_PRIVATE_KEY='', CLOUDFRONT_PRIVATE_KEY_PATH=key_path):
                cloudfront._signer.cache_clear()
                self._assert_signed(sign_compressed_url(STORED_URL), 'images.example.com')
        finally:
            cloudfront._key_file_cache.pop(key_path, None)
            os.unlink(key_path)


class CloudFrontFallbackTests(SimpleTestCase):
    """With CloudFront unconfigured (local dev / tests / not-yet-provisioned
    deploy) the signer degrades to the legacy unsigned behavior."""

    @override_settings(
        CLOUDFRONT_IMAGES_DOMAIN='',
        CLOUDFRONT_ORIGINALS_DOMAIN='',
        CLOUDFRONT_KEY_PAIR_ID='',
        CLOUDFRONT_PRIVATE_KEY='',
        CLOUDFRONT_PRIVATE_KEY_PATH='',
        AWS_STORAGE_BUCKET_NAME='goodvibesonly-images',
        AWS_COMPRESSED_STORAGE_BUCKET_NAME='goodvibesonly-imagescompressed',
    )
    def test_compressed_falls_back_to_bucket_swap(self):
        # Legacy behavior: swap the source bucket name for the compressed one.
        self.assertEqual(
            sign_compressed_url(STORED_URL),
            'https://goodvibesonly-imagescompressed.s3.amazonaws.com/42/abc.jpeg',
        )

    @override_settings(
        CLOUDFRONT_ORIGINALS_DOMAIN='',
        CLOUDFRONT_KEY_PAIR_ID='',
        CLOUDFRONT_PRIVATE_KEY='',
        CLOUDFRONT_PRIVATE_KEY_PATH='',
    )
    def test_original_falls_back_to_passthrough(self):
        self.assertEqual(sign_original_url(STORED_URL), STORED_URL)

    @signing_settings
    def test_non_positive_expiry_falls_back(self):
        """A zero/negative expiry would mint already-expired URLs, so it's treated
        as misconfiguration and degrades to unsigned rather than breaking loads."""
        cloudfront._signer.cache_clear()
        with override_settings(CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS=0):
            self.assertEqual(
                sign_compressed_url(STORED_URL),
                'https://goodvibesonly-imagescompressed.s3.amazonaws.com/42/abc.jpeg',
            )
        with override_settings(CLOUDFRONT_SIGNED_URL_EXPIRY_SECONDS=-5):
            self.assertEqual(sign_original_url(STORED_URL), STORED_URL)

    @signing_settings
    def test_undecodable_key_falls_back(self):
        """A URL with no derivable object key degrades to the fallback rather than
        producing a broken signed URL."""
        cloudfront._signer.cache_clear()
        # A host with no path -> image_url_to_key returns '' -> fallback (bucket
        # swap, a no-op here since the source bucket name is absent).
        no_key_url = 'https://cdn.example.com'
        self.assertEqual(sign_compressed_url(no_key_url), no_key_url)
