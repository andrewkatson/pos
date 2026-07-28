"""Unit tests for the BlurHash placeholder helper (issue #387)."""
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from PIL import Image

from .. import blurhash_utils

IMAGE_URL = 'https://test-bucket.s3.amazonaws.com/1/photo.jpeg'


def _jpeg_bytes():
    """A small non-uniform JPEG so the encoder produces a real, varied hash."""
    image = Image.new('RGB', (120, 90))
    for x in range(120):
        for y in range(90):
            image.putpixel((x, y), ((x * 255) // 120, (y * 255) // 90, 100))
    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    return buffer.getvalue()


class ComputeBlurhashTests(TestCase):
    def test_returns_none_for_empty_url(self):
        self.assertIsNone(blurhash_utils.compute_blurhash_for_image_url(None))
        self.assertIsNone(blurhash_utils.compute_blurhash_for_image_url(''))

    @patch('user_system.blurhash_utils._s3_client', return_value=None)
    def test_returns_none_without_s3_client(self, _client):
        """No AWS credentials (the test/CI default) yields None, not a crash."""
        self.assertIsNone(blurhash_utils.compute_blurhash_for_image_url(IMAGE_URL))

    @override_settings(AWS_STORAGE_BUCKET_NAME='test-bucket')
    @patch('user_system.blurhash_utils._s3_client')
    def test_encodes_a_blurhash_from_image_bytes(self, mock_client):
        client = MagicMock()
        client.get_object.return_value = {'Body': BytesIO(_jpeg_bytes())}
        mock_client.return_value = client

        result = blurhash_utils.compute_blurhash_for_image_url(IMAGE_URL)

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 6)
        # It read the object from the right bucket/key derived from the URL.
        _, kwargs = client.get_object.call_args
        self.assertEqual(kwargs['Bucket'], 'test-bucket')
        self.assertEqual(kwargs['Key'], '1/photo.jpeg')

    @override_settings(AWS_STORAGE_BUCKET_NAME='test-bucket')
    @patch('user_system.blurhash_utils._s3_client')
    def test_returns_none_for_url_outside_source_bucket(self, mock_client):
        # A look-alike / non-S3 host must never be coerced into our bucket + key
        # (the SSRF guard make_post applies is enforced here too): no fetch happens.
        client = MagicMock()
        mock_client.return_value = client
        self.assertIsNone(
            blurhash_utils.compute_blurhash_for_image_url('https://evil.com/1/photo.jpeg'))
        client.get_object.assert_not_called()

    @override_settings(AWS_STORAGE_BUCKET_NAME='test-bucket')
    @patch('user_system.blurhash_utils._s3_client')
    def test_returns_none_on_fetch_error(self, mock_client):
        client = MagicMock()
        client.get_object.side_effect = Exception('boom')
        mock_client.return_value = client
        self.assertIsNone(blurhash_utils.compute_blurhash_for_image_url(IMAGE_URL))
