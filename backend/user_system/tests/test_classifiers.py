import unittest
from unittest.mock import patch, MagicMock
import os
from io import BytesIO
from PIL import Image
from user_system.classifiers.text_classifier import is_text_positive
from user_system.classifiers.image_classifier import is_image_positive
from user_system.classifiers.classifier_constants import POSITIVE_TEXT, POSITIVE_IMAGE_URL

class TestClassifiers(unittest.TestCase):

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"})
    @patch("user_system.classifiers.text_classifier.genai")
    def test_text_classifier_positive(self, mock_genai):
        # Setup mock
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "True"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Test
        result = is_text_positive("I am happy")
        self.assertTrue(result)
        mock_model.generate_content.assert_called()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"})
    @patch("user_system.classifiers.text_classifier.genai")
    def test_text_classifier_negative(self, mock_genai):
        # Setup mock
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "False"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Test
        result = is_text_positive("I am sad")
        self.assertFalse(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_text_classifier_no_api_key(self):
        # Test fallback
        self.assertTrue(is_text_positive(POSITIVE_TEXT))
        self.assertFalse(is_text_positive("random text"))

    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "fake_key",
        "AWS_ACCESS_KEY_ID": "fake_aws_key",
        "AWS_SECRET_ACCESS_KEY": "fake_aws_secret",
        "AWS_STORAGE_BUCKET_NAME": "fake_bucket"
    })
    @patch("user_system.classifiers.image_classifier.boto3")
    @patch("user_system.classifiers.image_classifier.genai")
    def test_image_classifier_positive(self, mock_genai, mock_boto3):
        # Setup Gemini mock
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "True"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Setup S3 mock
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        
        # Create a fake image
        img = Image.new('RGB', (10, 10), color = 'red')
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        mock_s3_body = MagicMock()
        mock_s3_body.read.return_value = img_byte_arr.getvalue()
        mock_s3.get_object.return_value = {'Body': mock_s3_body}

        # Test
        result = is_image_positive("some_image.png")
        self.assertTrue(result)
        mock_s3.get_object.assert_called_with(Bucket="fake_bucket", Key="some_image.png")
        mock_model.generate_content.assert_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_image_classifier_no_api_key(self):
        # Test fallback
        self.assertTrue(is_image_positive(POSITIVE_IMAGE_URL))
        self.assertFalse(is_image_positive("random_image.png"))
