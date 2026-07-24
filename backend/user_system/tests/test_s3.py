import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from ..s3 import delete_image, image_url_to_key, is_source_bucket_url

_AWS_CREDS = {
    "AWS_ACCESS_KEY_ID": "fake_key",
    "AWS_SECRET_ACCESS_KEY": "fake_secret",
}

SOURCE_BUCKET = "src-bucket"
COMPRESSED_BUCKET = "compressed-bucket"

# A virtual-hosted-style URL and the object key it maps to, reused across tests.
VIRTUAL_HOSTED_URL = "https://my-bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg"
EXPECTED_KEY = "123/abc.jpeg"


class ImageUrlToKeyTests(SimpleTestCase):

    def test_virtual_hosted_style(self):
        self.assertEqual(image_url_to_key(VIRTUAL_HOSTED_URL), EXPECTED_KEY)

    def test_path_style_strips_bucket_segment(self):
        url = "https://s3.amazonaws.com/my-bucket/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_dashed_region_path_style_strips_bucket_segment(self):
        url = "https://s3-us-west-1.amazonaws.com/my-bucket/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_dotted_region_path_style_strips_bucket_segment(self):
        url = "https://s3.us-east-1.amazonaws.com/my-bucket/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_bucket_name_starting_with_s3_is_not_treated_as_path_style(self):
        url = "https://s3bucket.s3.amazonaws.com/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_virtual_hosted_bucket_starting_with_s3_dash(self):
        # The bucket name itself starts with "s3-" — must not be mistaken for a
        # path-style host and have its first path segment stripped.
        url = "https://s3-my-bucket.s3.amazonaws.com/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_virtual_hosted_bucket_starting_with_s3_dash_with_region(self):
        url = "https://s3-my-bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_virtual_hosted_s3_dash_bucket_on_s3_accelerate_endpoint(self):
        # The S3 service label is "s3-accelerate" — it starts with "s3" but is
        # not the literal "s3" — and the bucket name itself starts with "s3-".
        # This is still virtual-hosted, so the path's first segment must not be
        # stripped.
        url = "https://s3-my-bucket.s3-accelerate.amazonaws.com/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_empty_url_returns_empty(self):
        self.assertEqual(image_url_to_key(""), "")
        self.assertEqual(image_url_to_key(None), "")


@override_settings(AWS_STORAGE_BUCKET_NAME=SOURCE_BUCKET)
class IsSourceBucketUrlTests(SimpleTestCase):

    def test_virtual_hosted_matching_bucket(self):
        url = f"https://{SOURCE_BUCKET}.s3.amazonaws.com/123/abc.jpeg"
        self.assertTrue(is_source_bucket_url(url))

    def test_virtual_hosted_matching_bucket_with_region(self):
        url = f"https://{SOURCE_BUCKET}.s3.us-east-2.amazonaws.com/123/abc.jpeg"
        self.assertTrue(is_source_bucket_url(url))

    def test_path_style_matching_bucket(self):
        url = f"https://s3.amazonaws.com/{SOURCE_BUCKET}/123/abc.jpeg"
        self.assertTrue(is_source_bucket_url(url))

    def test_path_style_matching_bucket_dashed_region(self):
        url = f"https://s3-us-west-1.amazonaws.com/{SOURCE_BUCKET}/123/abc.jpeg"
        self.assertTrue(is_source_bucket_url(url))

    def test_virtual_hosted_foreign_bucket_rejected(self):
        # The SSRF-ish gap this guards: a valid-looking key on someone else's
        # S3 bucket must be rejected.
        url = "https://attacker-bucket.s3.amazonaws.com/123/abc.jpeg"
        self.assertFalse(is_source_bucket_url(url))

    def test_path_style_foreign_bucket_rejected(self):
        url = "https://s3.amazonaws.com/attacker-bucket/123/abc.jpeg"
        self.assertFalse(is_source_bucket_url(url))

    def test_foreign_bucket_with_our_name_as_dotted_prefix_rejected(self):
        # `{our-bucket}.evil.s3.amazonaws.com` is really bucket
        # `{our-bucket}.evil`. Deriving the bucket by splitting on the first dot
        # would wrongly accept it; the label after our bucket must be the S3
        # service label.
        url = f"https://{SOURCE_BUCKET}.evil.s3.amazonaws.com/123/abc.jpeg"
        self.assertFalse(is_source_bucket_url(url))

    def test_path_style_foreign_bucket_with_our_name_as_dotted_prefix_rejected(self):
        url = f"https://s3.amazonaws.com/{SOURCE_BUCKET}.evil/123/abc.jpeg"
        self.assertFalse(is_source_bucket_url(url))

    @override_settings(AWS_STORAGE_BUCKET_NAME="my.dotted.bucket")
    def test_dotted_bucket_name_matches(self):
        # Bucket names may legitimately contain dots.
        url = "https://my.dotted.bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg"
        self.assertTrue(is_source_bucket_url(url))

    def test_non_s3_host_rejected(self):
        # A non-S3 host whose first label equals our bucket name must not pass —
        # only real *.amazonaws.com hosts count.
        self.assertFalse(is_source_bucket_url(f"https://{SOURCE_BUCKET}.evil.com/123/abc.jpeg"))
        self.assertFalse(is_source_bucket_url("https://evil.com/123/abc.jpeg"))

    def test_empty_and_none_rejected(self):
        self.assertFalse(is_source_bucket_url(""))
        self.assertFalse(is_source_bucket_url(None))

    @override_settings(AWS_STORAGE_BUCKET_NAME="")
    def test_unconfigured_bucket_rejects_everything(self):
        url = f"https://{SOURCE_BUCKET}.s3.amazonaws.com/123/abc.jpeg"
        self.assertFalse(is_source_bucket_url(url))


@override_settings(
    AWS_STORAGE_BUCKET_NAME=SOURCE_BUCKET,
    AWS_COMPRESSED_STORAGE_BUCKET_NAME=COMPRESSED_BUCKET,
)
class DeleteImageTests(SimpleTestCase):

    @patch.dict(os.environ, _AWS_CREDS, clear=True)
    @patch("user_system.s3.boto3")
    def test_deletes_key_from_both_buckets(self, mock_boto3):
        client = MagicMock()
        mock_boto3.client.return_value = client

        delete_image(VIRTUAL_HOSTED_URL)

        client.delete_object.assert_any_call(Bucket=SOURCE_BUCKET, Key=EXPECTED_KEY)
        client.delete_object.assert_any_call(Bucket=COMPRESSED_BUCKET, Key=EXPECTED_KEY)
        self.assertEqual(client.delete_object.call_count, 2)

    @patch.dict(os.environ, _AWS_CREDS, clear=True)
    @patch("user_system.s3.boto3")
    def test_swallows_delete_errors(self, mock_boto3):
        client = MagicMock()
        client.delete_object.side_effect = Exception("boom")
        mock_boto3.client.return_value = client

        # Must not raise even though every delete fails.
        delete_image(VIRTUAL_HOSTED_URL)
        self.assertEqual(client.delete_object.call_count, 2)

    @patch.dict(os.environ, {}, clear=True)
    @patch("user_system.s3.boto3")
    def test_no_op_without_credentials(self, mock_boto3):
        delete_image(VIRTUAL_HOSTED_URL)
        mock_boto3.client.assert_not_called()

    @patch.dict(os.environ, _AWS_CREDS, clear=True)
    @patch("user_system.s3.boto3")
    def test_no_op_when_no_key(self, mock_boto3):
        delete_image("")
        mock_boto3.client.assert_not_called()

    @patch.dict(os.environ, _AWS_CREDS, clear=True)
    @patch("user_system.s3.boto3")
    def test_redacts_query_params_in_logs(self, mock_boto3):
        # A URL with a query but no object key hits the warning log; the
        # pre-signed signature must not leak into it.
        url = "https://my-bucket.s3.amazonaws.com/?X-Amz-Signature=supersecret"
        with self.assertLogs("user_system.s3", level="WARNING") as cm:
            delete_image(url)
        self.assertNotIn("supersecret", "\n".join(cm.output))
        mock_boto3.client.assert_not_called()
