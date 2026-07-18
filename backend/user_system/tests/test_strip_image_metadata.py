import io
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from ..image_metadata import strip_jpeg_metadata

SOURCE_BUCKET = "src-bucket"
COMPRESSED_BUCKET = "compressed-bucket"

ORIENTATION_TAG = 0x0112
MAKE_TAG = 0x010F  # stands in for private metadata (camera make)


def make_jpeg(orientation=None, make=None, comment=None, trailer=b''):
    """JPEG bytes for a small image with the requested metadata attached."""
    img = Image.new('RGB', (8, 4), color='red')
    save_kwargs = {'format': 'JPEG', 'quality': 90}
    exif = Image.Exif()
    if orientation is not None:
        exif[ORIENTATION_TAG] = orientation
    if make is not None:
        exif[MAKE_TAG] = make
    if orientation is not None or make is not None:
        save_kwargs['exif'] = exif.tobytes()
    if comment is not None:
        save_kwargs['comment'] = comment
    buf = io.BytesIO()
    img.save(buf, **save_kwargs)
    return buf.getvalue() + trailer


def pixels(data):
    return Image.open(io.BytesIO(data)).tobytes()


def exif_of(data):
    return Image.open(io.BytesIO(data)).getexif()


class StripJpegMetadataTests(TestCase):

    def test_strips_exif_but_keeps_orientation(self):
        original = make_jpeg(orientation=8, make="SecretCam 3000")
        self.assertIn(b"SecretCam 3000", original)

        stripped = strip_jpeg_metadata(original)

        self.assertNotIn(b"SecretCam 3000", stripped)
        exif = exif_of(stripped)
        self.assertEqual(exif.get(ORIENTATION_TAG), 8)
        self.assertIsNone(exif.get(MAKE_TAG))

    def test_is_lossless(self):
        original = make_jpeg(orientation=6, make="SecretCam 3000")
        stripped = strip_jpeg_metadata(original)
        self.assertEqual(pixels(stripped), pixels(original))

    def test_drops_comment_segments(self):
        original = make_jpeg(comment=b"taken at my house")
        self.assertIn(b"taken at my house", original)

        stripped = strip_jpeg_metadata(original)

        self.assertNotIn(b"taken at my house", stripped)
        self.assertEqual(pixels(stripped), pixels(original))

    def test_truncates_trailer_after_eoi(self):
        original = make_jpeg(trailer=b"MotionPhoto_Data with embedded video")

        stripped = strip_jpeg_metadata(original)

        self.assertNotIn(b"MotionPhoto_Data", stripped)
        self.assertTrue(stripped.endswith(b'\xff\xd9'))
        self.assertEqual(pixels(stripped), pixels(original))

    def test_clean_jpeg_is_unchanged(self):
        original = make_jpeg()
        self.assertEqual(strip_jpeg_metadata(original), original)

    def test_upright_orientation_is_not_reinserted(self):
        original = make_jpeg(orientation=1, make="SecretCam 3000")
        stripped = strip_jpeg_metadata(original)
        self.assertIsNone(exif_of(stripped).get(ORIENTATION_TAG))

    def test_non_jpeg_is_returned_unchanged(self):
        img = Image.new('RGB', (4, 4))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        data = buf.getvalue()
        self.assertEqual(strip_jpeg_metadata(data), data)

    def test_garbage_is_returned_unchanged(self):
        # Starts like a JPEG but is unparseable — must fall back to the input.
        data = b'\xff\xd8\xff\xe1\x00\x05ab'
        self.assertEqual(strip_jpeg_metadata(data), data)


def _make_client(objects_by_bucket, bodies_by_key):
    """A mock S3 client listing the given objects and serving the given bodies."""
    client = MagicMock()

    def get_paginator(_op):
        paginator = MagicMock()
        paginator.paginate.side_effect = lambda Bucket: [
            {'Contents': objects_by_bucket.get(Bucket, [])}
        ]
        return paginator

    client.get_paginator.side_effect = get_paginator

    def get_object(Bucket, Key):
        return {'Body': io.BytesIO(bodies_by_key[Key])}

    client.get_object.side_effect = get_object
    return client


@override_settings(
    AWS_STORAGE_BUCKET_NAME=SOURCE_BUCKET,
    AWS_COMPRESSED_STORAGE_BUCKET_NAME=COMPRESSED_BUCKET,
)
class StripImageMetadataCommandTests(TestCase):

    def _run(self, client, **kwargs):
        out = StringIO()
        err = StringIO()
        with patch('user_system.s3._s3_client', return_value=client):
            call_command('strip_image_metadata', stdout=out, stderr=err, **kwargs)
        return out.getvalue(), err.getvalue()

    def test_rewrites_object_with_metadata(self):
        key = "1/dirty.jpeg"
        original = make_jpeg(orientation=8, make="SecretCam 3000")
        client = _make_client({SOURCE_BUCKET: [{'Key': key}]}, {key: original})

        out, _ = self._run(client)

        client.put_object.assert_called_once()
        kwargs = client.put_object.call_args.kwargs
        self.assertEqual(kwargs['Bucket'], SOURCE_BUCKET)
        self.assertEqual(kwargs['Key'], key)
        self.assertEqual(kwargs['ContentType'], 'image/jpeg')
        self.assertNotIn(b"SecretCam 3000", kwargs['Body'])
        self.assertEqual(exif_of(kwargs['Body']).get(ORIENTATION_TAG), 8)
        self.assertIn("Rewrote 1 object(s)", out)

    def test_clean_object_is_not_rewritten(self):
        key = "1/clean.jpeg"
        client = _make_client({COMPRESSED_BUCKET: [{'Key': key}]}, {key: make_jpeg()})

        out, _ = self._run(client)

        client.put_object.assert_not_called()
        self.assertIn("1 already clean", out)

    def test_dry_run_writes_nothing(self):
        key = "1/dirty.jpeg"
        original = make_jpeg(make="SecretCam 3000")
        client = _make_client({SOURCE_BUCKET: [{'Key': key}]}, {key: original})

        out, _ = self._run(client, dry_run=True)

        client.put_object.assert_not_called()
        self.assertIn(f"[dry-run] would rewrite s3://{SOURCE_BUCKET}/{key}", out)
        self.assertIn("Would rewrite 1 object(s)", out)

    def test_sweeps_both_buckets(self):
        src_key = "1/a.jpeg"
        comp_key = "1/b.jpeg"
        dirty = make_jpeg(make="SecretCam 3000")
        client = _make_client(
            {SOURCE_BUCKET: [{'Key': src_key}], COMPRESSED_BUCKET: [{'Key': comp_key}]},
            {src_key: dirty, comp_key: dirty},
        )

        self._run(client)

        buckets_written = {c.kwargs['Bucket'] for c in client.put_object.call_args_list}
        self.assertEqual(buckets_written, {SOURCE_BUCKET, COMPRESSED_BUCKET})

    def test_one_failure_does_not_stop_the_sweep(self):
        bad_key = "1/bad.jpeg"
        good_key = "1/good.jpeg"
        dirty = make_jpeg(make="SecretCam 3000")

        client = _make_client(
            {SOURCE_BUCKET: [{'Key': bad_key}, {'Key': good_key}]},
            {bad_key: dirty, good_key: dirty},
        )
        original_get = client.get_object.side_effect

        def get_object(Bucket, Key):
            if Key == bad_key:
                raise RuntimeError("boom")
            return original_get(Bucket=Bucket, Key=Key)

        client.get_object.side_effect = get_object

        out, err = self._run(client)

        client.put_object.assert_called_once()
        self.assertEqual(client.put_object.call_args.kwargs['Key'], good_key)
        self.assertIn("1 failed", out)
        self.assertIn(f"Failed to strip s3://{SOURCE_BUCKET}/{bad_key}", err)

    def test_listing_failure_skips_bucket_but_continues(self):
        key = "1/dirty.jpeg"
        dirty = make_jpeg(make="SecretCam 3000")
        client = _make_client({COMPRESSED_BUCKET: [{'Key': key}]}, {key: dirty})

        def get_paginator(_op):
            paginator = MagicMock()

            def paginate(Bucket):
                if Bucket == SOURCE_BUCKET:
                    raise RuntimeError("AccessDenied")
                return [{'Contents': [{'Key': key}]}]

            paginator.paginate.side_effect = paginate
            return paginator

        client.get_paginator.side_effect = get_paginator

        out, err = self._run(client)

        self.assertIn(f"Failed to list bucket {SOURCE_BUCKET}", err)
        # The compressed bucket is still swept.
        client.put_object.assert_called_once()
        self.assertEqual(client.put_object.call_args.kwargs['Bucket'], COMPRESSED_BUCKET)

    def test_aborts_without_credentials(self):
        err = StringIO()
        with patch('user_system.s3._s3_client', return_value=None):
            call_command('strip_image_metadata', stdout=StringIO(), stderr=err)
        self.assertIn("No AWS credentials", err.getvalue())
