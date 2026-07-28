import os
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase
from PIL import Image

from ..classifiers import image_prefilter
from ..classifiers.image_classifier import is_image_positive
from ..classifiers.classifier_constants import (
    LOCAL_NUDITY_THRESHOLD, LOCAL_GORE_THRESHOLD,
)
from ..classifiers.classifier_utils import API_GEMINI

_IMAGE_DISPATCH = "user_system.classifiers.classifier_utils.IMAGE_API_DISPATCH"
_AWS_KEYS = {
    "AWS_ACCESS_KEY_ID": "fake_aws_key",
    "AWS_SECRET_ACCESS_KEY": "fake_aws_secret",
    "AWS_STORAGE_BUCKET_NAME": "fake_bucket",
}


def _image():
    return Image.new('RGB', (10, 10), color='red')


def _image_bytes():
    buf = BytesIO()
    _image().save(buf, format='PNG')
    return buf.getvalue()


class ImagePrefilterTests(SimpleTestCase):
    """The local, zero-API nudity/gore pre-filter (issue #393): confident hits
    are final rejections, everything else (and every model failure) passes
    through to the AI cascade."""

    def test_clean_image_is_allowed(self):
        with patch.object(image_prefilter, '_detect_nudity', return_value=0.0), \
             patch.object(image_prefilter, '_detect_gore', return_value=0.0):
            self.assertTrue(image_prefilter.prefilter_image(_image()))

    def test_nudity_hit_is_final_rejection(self):
        with patch.object(image_prefilter, '_detect_nudity', return_value=LOCAL_NUDITY_THRESHOLD), \
             patch.object(image_prefilter, '_detect_gore', return_value=0.0):
            result = image_prefilter.prefilter_image(_image())
        self.assertFalse(result)
        self.assertFalse(result.appealable)
        self.assertFalse(result.provider_failure)
        self.assertEqual(result.public_reason_code(), 'nudity')

    def test_gore_hit_is_final_rejection(self):
        with patch.object(image_prefilter, '_detect_nudity', return_value=0.0), \
             patch.object(image_prefilter, '_detect_gore', return_value=LOCAL_GORE_THRESHOLD):
            result = image_prefilter.prefilter_image(_image())
        self.assertFalse(result)
        self.assertFalse(result.appealable)
        self.assertEqual(result.public_reason_code(), 'gore')

    def test_nudity_checked_before_gore(self):
        # Both fire; the reported reason is nudity (checked first) and gore is
        # never consulted.
        gore = MagicMock(return_value=1.0)
        with patch.object(image_prefilter, '_detect_nudity', return_value=1.0), \
             patch.object(image_prefilter, '_detect_gore', gore):
            result = image_prefilter.prefilter_image(_image())
        self.assertEqual(result.public_reason_code(), 'nudity')
        gore.assert_not_called()

    def test_scores_below_threshold_are_allowed(self):
        with patch.object(image_prefilter, '_detect_nudity', return_value=LOCAL_NUDITY_THRESHOLD - 0.01), \
             patch.object(image_prefilter, '_detect_gore', return_value=LOCAL_GORE_THRESHOLD - 0.01):
            self.assertTrue(image_prefilter.prefilter_image(_image()))

    def test_detector_error_fails_open(self):
        # A crashing detector must never fail the image shut; the cascade is
        # the real gate.
        with patch.object(image_prefilter, '_detect_nudity', side_effect=RuntimeError('boom')), \
             patch.object(image_prefilter, '_detect_gore', return_value=0.0):
            self.assertTrue(image_prefilter.prefilter_image(_image()))

    def test_missing_models_fail_open(self):
        # With neither NudeNet nor a gore model available (CI/dev), the real
        # detector entry points return 0.0 and the image is allowed. Patch the
        # cache sentinels (auto-restored on exit) rather than assigning them, so
        # this never clobbers cached state and leaks order dependence into other
        # tests.
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(image_prefilter, '_nudenet_unavailable', True), \
             patch.object(image_prefilter, '_gore_unavailable', True):
            self.assertTrue(image_prefilter.prefilter_image(_image()))


    def test_pil_to_temp_file_cleans_up_on_save_error(self):
        # If save() fails the caller never receives the path, so the helper
        # itself must unlink the mkstemp file rather than orphan it in /tmp.
        created = {}
        real_mkstemp = image_prefilter.tempfile.mkstemp

        def spy_mkstemp(*args, **kwargs):
            fd, path = real_mkstemp(*args, **kwargs)
            created['path'] = path
            return fd, path

        with patch.object(image_prefilter.tempfile, 'mkstemp', side_effect=spy_mkstemp), \
             patch('PIL.Image.Image.save', side_effect=RuntimeError('encoder boom')):
            with self.assertRaises(RuntimeError):
                image_prefilter._pil_to_temp_file(_image())
        self.assertIn('path', created)
        self.assertFalse(os.path.exists(created['path']))


class ImagePrefilterCascadeIntegrationTests(SimpleTestCase):
    """The pre-filter short-circuits is_image_positive: a local hit is returned
    without ever consulting the paid AI cascade."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_local_hit_skips_cascade(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        cascade_api = MagicMock(return_value=0.99)
        with patch.object(image_prefilter, '_detect_nudity', return_value=0.95), \
             patch.dict(_IMAGE_DISPATCH, {API_GEMINI: cascade_api}):
            result = is_image_positive("some_image.png")

        self.assertFalse(result)
        self.assertEqual(result.public_reason_code(), 'nudity')
        cascade_api.assert_not_called()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_clean_local_prefilter_defers_to_cascade(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        cascade_api = MagicMock(return_value=0.95)
        with patch.object(image_prefilter, '_detect_nudity', return_value=0.0), \
             patch.object(image_prefilter, '_detect_gore', return_value=0.0), \
             patch.dict(_IMAGE_DISPATCH, {API_GEMINI: cascade_api}):
            result = is_image_positive("some_image.png")

        self.assertTrue(result)
        cascade_api.assert_called_once()
