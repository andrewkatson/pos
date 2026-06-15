import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from ..s3 import delete_image, image_url_to_key

_AWS_CREDS = {
    "AWS_ACCESS_KEY_ID": "fake_key",
    "AWS_SECRET_ACCESS_KEY": "fake_secret",
}

SOURCE_BUCKET = "src-bucket"
COMPRESSED_BUCKET = "compressed-bucket"


class ImageUrlToKeyTests(SimpleTestCase):

    def test_virtual_hosted_style(self):
        url = "https://my-bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_path_style_strips_bucket_segment(self):
        url = "https://s3.amazonaws.com/my-bucket/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_dashed_region_path_style_strips_bucket_segment(self):
        url = "https://s3-us-west-1.amazonaws.com/my-bucket/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_bucket_name_starting_with_s3_is_not_treated_as_path_style(self):
        url = "https://s3bucket.s3.amazonaws.com/123/abc.jpeg"
        self.assertEqual(image_url_to_key(url), "123/abc.jpeg")

    def test_empty_url_returns_empty(self):
        self.assertEqual(image_url_to_key(""), "")
        self.assertEqual(image_url_to_key(None), "")


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

        delete_image("https://my-bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg")

        client.delete_object.assert_any_call(Bucket=SOURCE_BUCKET, Key="123/abc.jpeg")
        client.delete_object.assert_any_call(Bucket=COMPRESSED_BUCKET, Key="123/abc.jpeg")
        self.assertEqual(client.delete_object.call_count, 2)

    @patch.dict(os.environ, _AWS_CREDS, clear=True)
    @patch("user_system.s3.boto3")
    def test_swallows_delete_errors(self, mock_boto3):
        client = MagicMock()
        client.delete_object.side_effect = Exception("boom")
        mock_boto3.client.return_value = client

        # Must not raise even though every delete fails.
        delete_image("https://my-bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg")
        self.assertEqual(client.delete_object.call_count, 2)

    @patch.dict(os.environ, {}, clear=True)
    @patch("user_system.s3.boto3")
    def test_no_op_without_credentials(self, mock_boto3):
        delete_image("https://my-bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg")
        mock_boto3.client.assert_not_called()

    @patch.dict(os.environ, _AWS_CREDS, clear=True)
    @patch("user_system.s3.boto3")
    def test_no_op_when_no_key(self, mock_boto3):
        delete_image("")
        mock_boto3.client.assert_not_called()
