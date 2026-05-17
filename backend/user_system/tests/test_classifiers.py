from unittest.mock import patch, MagicMock
import os
from io import BytesIO
from PIL import Image
from ..classifiers.text_classifier import is_text_positive
from ..classifiers.image_classifier import is_image_positive
from ..classifiers.classifier_constants import POSITIVE_TEXT, POSITIVE_IMAGE_URL, TEXT_CLASSIFIER_PROMPT, IMAGE_CLASSIFIER_PROMPT
from ..classifiers.classifier_utils import API_GEMINI, API_CLAUDE, API_OPENAI
from .test_parent_case import PositiveOnlySocialTestCase

_ALL_AI_KEYS = {
    "GEMINI_API_KEY": "fake_gemini",
    "ANTHROPIC_API_KEY": "fake_claude",
    "OPENAI_API_KEY": "fake_openai",
}
_AWS_KEYS = {
    "AWS_ACCESS_KEY_ID": "fake_aws_key",
    "AWS_SECRET_ACCESS_KEY": "fake_aws_secret",
    "AWS_STORAGE_BUCKET_NAME": "fake_bucket",
}


def _make_fake_image_bytes():
    img = Image.new('RGB', (10, 10), color='red')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class TestClassifiers(PositiveOnlySocialTestCase):

    # ------------------------------------------------------------------ #
    # Text classifier – testing mode                                       #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_text_classifier_testing_mode(self):
        self.assertTrue(is_text_positive(POSITIVE_TEXT))
        self.assertFalse(is_text_positive("negative random text"))

    # ------------------------------------------------------------------ #
    # Text classifier – no API keys                                        #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {}, clear=True)
    def test_text_classifier_no_api_keys(self):
        self.assertFalse(is_text_positive("some text"))

    # ------------------------------------------------------------------ #
    # Text classifier – single API                                         #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    @patch("user_system.classifiers.text_classifier.call_text_gemini", return_value=True)
    def test_text_classifier_single_gemini_positive(self, mock_gemini):
        self.assertTrue(is_text_positive("I am happy"))
        mock_gemini.assert_called_once_with("I am happy", TEXT_CLASSIFIER_PROMPT)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    @patch("user_system.classifiers.text_classifier.call_text_gemini", return_value=False)
    def test_text_classifier_single_gemini_negative(self, mock_gemini):
        self.assertFalse(is_text_positive("I am sad"))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake_key"}, clear=True)
    @patch("user_system.classifiers.text_classifier.call_text_claude", return_value=True)
    def test_text_classifier_single_claude_positive(self, mock_claude):
        self.assertTrue(is_text_positive("Great day"))
        mock_claude.assert_called_once_with("Great day", TEXT_CLASSIFIER_PROMPT)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"}, clear=True)
    @patch("user_system.classifiers.text_classifier.call_text_openai", return_value=True)
    def test_text_classifier_single_openai_positive(self, mock_openai):
        self.assertTrue(is_text_positive("Wonderful"))
        mock_openai.assert_called_once_with("Wonderful", TEXT_CLASSIFIER_PROMPT)

    # ------------------------------------------------------------------ #
    # Text classifier – voting: two APIs agree                             #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.text_classifier.call_text_openai", return_value=True)
    @patch("user_system.classifiers.text_classifier.call_text_claude", return_value=True)
    @patch("user_system.classifiers.text_classifier.call_text_gemini", return_value=True)
    def test_text_voting_two_agree_true(self, mock_gemini, mock_claude, mock_openai, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        self.assertTrue(is_text_positive("nice text"))
        mock_openai.assert_not_called()

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.text_classifier.call_text_openai", return_value=False)
    @patch("user_system.classifiers.text_classifier.call_text_claude", return_value=False)
    @patch("user_system.classifiers.text_classifier.call_text_gemini", return_value=False)
    def test_text_voting_two_agree_false(self, mock_gemini, mock_claude, mock_openai, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        self.assertFalse(is_text_positive("bad text"))
        mock_openai.assert_not_called()

    # ------------------------------------------------------------------ #
    # Text classifier – voting: disagree with tiebreaker                   #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.text_classifier.call_text_openai", return_value=True)
    @patch("user_system.classifiers.text_classifier.call_text_claude", return_value=False)
    @patch("user_system.classifiers.text_classifier.call_text_gemini", return_value=True)
    def test_text_voting_disagree_tiebreaker_true(self, mock_gemini, mock_claude, mock_openai, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        self.assertTrue(is_text_positive("some text"))
        mock_openai.assert_called_once()

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.text_classifier.call_text_openai", return_value=False)
    @patch("user_system.classifiers.text_classifier.call_text_claude", return_value=False)
    @patch("user_system.classifiers.text_classifier.call_text_gemini", return_value=True)
    def test_text_voting_disagree_tiebreaker_false(self, mock_gemini, mock_claude, mock_openai, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        self.assertFalse(is_text_positive("some text"))
        mock_openai.assert_called_once()

    # ------------------------------------------------------------------ #
    # Text classifier – voting: two APIs, no tiebreaker, disagree          #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "gk", "ANTHROPIC_API_KEY": "ak"}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.text_classifier.call_text_claude", return_value=False)
    @patch("user_system.classifiers.text_classifier.call_text_gemini", return_value=True)
    def test_text_voting_two_apis_disagree_no_tiebreaker(self, mock_gemini, mock_claude, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        self.assertFalse(is_text_positive("some text"))

    # ------------------------------------------------------------------ #
    # Image classifier – testing mode                                      #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_image_classifier_testing_mode(self):
        self.assertTrue(is_image_positive(POSITIVE_IMAGE_URL))
        self.assertFalse(is_image_positive("random_image.png"))

    # ------------------------------------------------------------------ #
    # Image classifier – no API keys                                       #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, _AWS_KEYS, clear=True)
    def test_image_classifier_no_api_keys(self):
        self.assertFalse(is_image_positive("some_image.png"))

    # ------------------------------------------------------------------ #
    # Image classifier – single API                                        #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    @patch("user_system.classifiers.image_classifier.call_image_gemini", return_value=True)
    def test_image_classifier_single_gemini_positive(self, mock_gemini, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        self.assertTrue(is_image_positive("some_image.png"))
        mock_s3.get_object.assert_called_with(Bucket="fake_bucket", Key="some_image.png")
        mock_gemini.assert_called_once()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    @patch("user_system.classifiers.image_classifier.call_image_gemini", return_value=False)
    def test_image_classifier_single_gemini_negative(self, mock_gemini, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        self.assertFalse(is_image_positive("some_image.png"))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    @patch("user_system.classifiers.image_classifier.call_image_claude", return_value=True)
    def test_image_classifier_single_claude_positive(self, mock_claude, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        self.assertTrue(is_image_positive("some_image.png"))
        mock_claude.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    @patch("user_system.classifiers.image_classifier.call_image_openai", return_value=True)
    def test_image_classifier_single_openai_positive(self, mock_openai, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        self.assertTrue(is_image_positive("some_image.png"))
        mock_openai.assert_called_once()

    # ------------------------------------------------------------------ #
    # Image classifier – voting: two agree                                 #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {**_ALL_AI_KEYS, **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.image_classifier.boto3")
    @patch("user_system.classifiers.image_classifier.call_image_openai", return_value=True)
    @patch("user_system.classifiers.image_classifier.call_image_claude", return_value=True)
    @patch("user_system.classifiers.image_classifier.call_image_gemini", return_value=True)
    def test_image_voting_two_agree_true(self, mock_gemini, mock_claude, mock_openai, mock_boto3, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        self.assertTrue(is_image_positive("img.png"))
        mock_openai.assert_not_called()

    # ------------------------------------------------------------------ #
    # Image classifier – voting: disagree with tiebreaker                  #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {**_ALL_AI_KEYS, **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.image_classifier.boto3")
    @patch("user_system.classifiers.image_classifier.call_image_openai", return_value=False)
    @patch("user_system.classifiers.image_classifier.call_image_claude", return_value=False)
    @patch("user_system.classifiers.image_classifier.call_image_gemini", return_value=True)
    def test_image_voting_disagree_tiebreaker_false(self, mock_gemini, mock_claude, mock_openai, mock_boto3, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        self.assertFalse(is_image_positive("img.png"))
        mock_openai.assert_called_once()

    # ------------------------------------------------------------------ #
    # Prompt content                                                       #
    # ------------------------------------------------------------------ #

    def test_text_classifier_prompt_content(self):
        for phrase in [
            "neutral",
            "sexually suggestive content",
            "misinformation",
            "begins sad but ends on a happy or hopeful note",
        ]:
            self.assertIn(phrase, TEXT_CLASSIFIER_PROMPT, msg=f"Missing in TEXT_CLASSIFIER_PROMPT: {phrase!r}")

    def test_image_classifier_prompt_content(self):
        for phrase in [
            "neutral",
            "sexually suggestive content",
            "misinformation",
            "begins sad but ends on a happy or hopeful note",
        ]:
            self.assertIn(phrase, IMAGE_CLASSIFIER_PROMPT, msg=f"Missing in IMAGE_CLASSIFIER_PROMPT: {phrase!r}")
