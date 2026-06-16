from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from ..models import Post

SOURCE_BUCKET = "src-bucket"
COMPRESSED_BUCKET = "compressed-bucket"


def _url_for_key(key):
    return f"https://{SOURCE_BUCKET}.s3.us-east-2.amazonaws.com/{key}"


def _make_client(objects_by_bucket):
    """A mock S3 client whose paginator yields the given objects per bucket."""
    client = MagicMock()

    def get_paginator(_op):
        paginator = MagicMock()
        paginator.paginate.side_effect = lambda Bucket: [
            {'Contents': objects_by_bucket.get(Bucket, [])}
        ]
        return paginator

    client.get_paginator.side_effect = get_paginator
    return client


def _deleted_pairs(client):
    """The (Bucket, Key) pairs delete_object was called with."""
    return {(c.kwargs['Bucket'], c.kwargs['Key']) for c in client.delete_object.call_args_list}


@override_settings(
    AWS_STORAGE_BUCKET_NAME=SOURCE_BUCKET,
    AWS_COMPRESSED_STORAGE_BUCKET_NAME=COMPRESSED_BUCKET,
)
class CleanupOrphanImagesTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create(username="sweeper_user")
        self.now = timezone.now()
        self.old = self.now - timedelta(hours=48)
        self.recent = self.now - timedelta(hours=1)

    def _run(self, client, **kwargs):
        out = StringIO()
        with patch('user_system.s3._s3_client', return_value=client):
            call_command('cleanup_orphan_images', stdout=out, **kwargs)
        return out.getvalue()

    def test_old_orphan_deleted_from_both_buckets(self):
        key = f"{self.user.id}/orphan.jpeg"
        client = _make_client({SOURCE_BUCKET: [{'Key': key, 'LastModified': self.old}]})

        self._run(client)

        self.assertEqual(
            _deleted_pairs(client),
            {(SOURCE_BUCKET, key), (COMPRESSED_BUCKET, key)},
        )

    def test_live_key_is_kept(self):
        key = f"{self.user.id}/live.jpeg"
        Post.objects.create(author=self.user, image_url=_url_for_key(key), caption="hi")
        client = _make_client({SOURCE_BUCKET: [{'Key': key, 'LastModified': self.old}]})

        out = self._run(client)

        client.delete_object.assert_not_called()
        self.assertIn("kept 1 live", out)

    def test_recent_orphan_is_kept(self):
        key = f"{self.user.id}/recent.jpeg"
        client = _make_client({SOURCE_BUCKET: [{'Key': key, 'LastModified': self.recent}]})

        out = self._run(client)

        client.delete_object.assert_not_called()
        self.assertIn("within 24h grace", out)

    def test_recent_in_compressed_bucket_protects_pair(self):
        """A key old in the source bucket but freshly written to the compressed
        bucket (Lambda-after-rejection race) is kept until the grace passes."""
        key = f"{self.user.id}/racing.jpeg"
        client = _make_client({
            SOURCE_BUCKET: [{'Key': key, 'LastModified': self.old}],
            COMPRESSED_BUCKET: [{'Key': key, 'LastModified': self.recent}],
        })

        self._run(client)

        client.delete_object.assert_not_called()

    def test_dry_run_deletes_nothing(self):
        key = f"{self.user.id}/orphan.jpeg"
        client = _make_client({SOURCE_BUCKET: [{'Key': key, 'LastModified': self.old}]})

        out = self._run(client, dry_run=True)

        client.delete_object.assert_not_called()
        self.assertIn("[dry-run] would delete", out)
        self.assertIn("Would sweep 1", out)

    def test_grace_hours_argument(self):
        """A tighter grace window lets a 1-hour-old orphan be swept."""
        key = f"{self.user.id}/recent.jpeg"
        client = _make_client({SOURCE_BUCKET: [{'Key': key, 'LastModified': self.recent}]})

        self._run(client, grace_hours=0)

        self.assertEqual(
            _deleted_pairs(client),
            {(SOURCE_BUCKET, key), (COMPRESSED_BUCKET, key)},
        )

    def test_aborts_without_credentials(self):
        err = StringIO()
        with patch('user_system.s3._s3_client', return_value=None):
            call_command('cleanup_orphan_images', stderr=err)
        self.assertIn("No AWS credentials", err.getvalue())
