from unittest.mock import patch, MagicMock
import os
from io import BytesIO
from PIL import Image
from ..classifiers.text_classifier import is_text_positive
from ..classifiers.image_classifier import is_image_positive
from ..classifiers.classifier_constants import POSITIVE_TEXT, POSITIVE_IMAGE_URL, TEXT_CLASSIFIER_PROMPT, IMAGE_CLASSIFIER_PROMPT
from ..classifiers.classifier_constants import GENERIC_REASON_CODE, REASON_PHRASES
from ..classifiers.classifier_utils import (
    API_GEMINI, API_CLAUDE, API_OPENAI, parse_probability, parse_probability_and_rule,
)
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
_AWS_KEYS_NO_BUCKET = {
    "AWS_ACCESS_KEY_ID": "fake_aws_key",
    "AWS_SECRET_ACCESS_KEY": "fake_aws_secret",
}

_TEXT_DISPATCH = "user_system.classifiers.classifier_utils.TEXT_API_DISPATCH"
_IMAGE_DISPATCH = "user_system.classifiers.classifier_utils.IMAGE_API_DISPATCH"

# Representative scores for each probability zone.
ALLOW_SCORE = 0.9
MIDDLE_SCORE = 0.5
REJECT_SCORE = 0.1


def _make_fake_image_bytes():
    img = Image.new('RGB', (10, 10), color='red')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class TestClassifiers(PositiveOnlySocialTestCase):

    # ------------------------------------------------------------------ #
    # Probability parsing                                                  #
    # ------------------------------------------------------------------ #

    def test_parse_probability_valid(self):
        self.assertEqual(parse_probability("0.85"), 0.85)
        self.assertEqual(parse_probability(" 1.00 "), 1.0)
        self.assertEqual(parse_probability("0"), 0.0)
        self.assertEqual(parse_probability("Probability: 0.4"), 0.4)
        self.assertEqual(parse_probability(".75"), 0.75)

    def test_parse_probability_ignores_echoed_range(self):
        # Models sometimes echo the prompt's "between 0.00 and 1.00" bounds
        # before answering; the answer (last in-range number) must win.
        self.assertEqual(parse_probability("On a scale between 0.00 and 1.00, I would say 0.85"), 0.85)
        self.assertEqual(parse_probability("between 0.00 and 1.00: 0.4"), 0.4)
        # Out-of-range numbers are ignored in favor of an in-range answer.
        self.assertEqual(parse_probability("I rate it 0.9 (not 100)"), 0.9)

    def test_parse_probability_invalid(self):
        self.assertIsNone(parse_probability("yes"))
        self.assertIsNone(parse_probability(""))
        self.assertIsNone(parse_probability("100"))
        self.assertIsNone(parse_probability("1.5"))

    def test_parse_probability_and_rule_pair_format(self):
        self.assertEqual(parse_probability_and_rule("0.15,3"), (0.15, 3))
        self.assertEqual(parse_probability_and_rule("0.15, 5"), (0.15, 5))
        # A cited rule of 0 means "no specific rule".
        self.assertEqual(parse_probability_and_rule("0.95,0"), (0.95, None))
        self.assertEqual(parse_probability_and_rule("1.00,0"), (1.0, None))

    def test_parse_probability_and_rule_takes_last_pair(self):
        # A response that echoes the prompt's example before answering must
        # parse the answer, not the echo.
        self.assertEqual(parse_probability_and_rule("For example: 0.95,0 ... my answer is 0.2,6"), (0.2, 6))

    def test_parse_probability_and_rule_falls_back_to_bare_score(self):
        # A model that ignores the rule instruction still yields a probability.
        self.assertEqual(parse_probability_and_rule("0.85"), (0.85, None))
        self.assertEqual(parse_probability_and_rule("Probability: 0.4"), (0.4, None))
        self.assertEqual(parse_probability_and_rule("yes"), (None, None))

    def test_parse_probability_and_rule_skips_out_of_range_pairs(self):
        # "10,3" is not a valid probability; the earlier valid pair wins.
        self.assertEqual(parse_probability_and_rule("0.3,2 then 10,3"), (0.3, 2))
        # A two-digit "rule" is not a rule citation at all.
        self.assertEqual(parse_probability_and_rule("0.5,42"), (0.5, None))

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
        result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertFalse(result.appealable)
        # No provider could even be consulted — flagged so the async worker
        # (issue #282) retries instead of recording a real rejection.
        self.assertTrue(result.provider_failure)

    # ------------------------------------------------------------------ #
    # Text classifier – single API                                         #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_text_classifier_single_gemini_allow_zone(self):
        mock_gemini = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini}):
            self.assertTrue(is_text_positive("I am happy"))
        mock_gemini.assert_called_once_with("I am happy", TEXT_CLASSIFIER_PROMPT)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_text_classifier_single_gemini_reject_zone_not_appealable(self):
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=REJECT_SCORE)}):
            result = is_text_positive("I am sad")
        self.assertFalse(result)
        self.assertFalse(result.appealable)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_text_classifier_single_gemini_middle_zone_rejected_but_appealable(self):
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=MIDDLE_SCORE)}):
            result = is_text_positive("ambiguous text")
        self.assertFalse(result)
        self.assertTrue(result.appealable)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake_key"}, clear=True)
    def test_text_classifier_single_claude_allow_zone(self):
        mock_claude = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_CLAUDE: mock_claude}):
            self.assertTrue(is_text_positive("Great day"))
        mock_claude.assert_called_once_with("Great day", TEXT_CLASSIFIER_PROMPT)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"}, clear=True)
    def test_text_classifier_single_openai_allow_zone(self):
        mock_openai = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_OPENAI: mock_openai}):
            self.assertTrue(is_text_positive("Wonderful"))
        mock_openai.assert_called_once_with("Wonderful", TEXT_CLASSIFIER_PROMPT)

    # ------------------------------------------------------------------ #
    # Text classifier – zone boundaries                                    #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_text_classifier_boundary_scores(self):
        # Exactly 0.3 is the reject zone (not appealable).
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=0.3)}):
            result = is_text_positive("some text")
            self.assertFalse(result)
            self.assertFalse(result.appealable)
        # Exactly 0.7 is the allow zone.
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=0.7)}):
            self.assertTrue(is_text_positive("some text"))
        # Just inside the middle zone on either side: rejected but appealable.
        for score in (0.35, 0.65):
            with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=score)}):
                result = is_text_positive("some text")
                self.assertFalse(result)
                self.assertTrue(result.appealable)

    # ------------------------------------------------------------------ #
    # Text classifier – cascade between AIs                                #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_first_ai_allows_no_escalation(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_gemini = MagicMock(return_value=ALLOW_SCORE)
        mock_claude = MagicMock(return_value=ALLOW_SCORE)
        mock_openai = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            self.assertTrue(is_text_positive("nice text"))
        mock_claude.assert_not_called()
        mock_openai.assert_not_called()

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_first_ai_rejects_no_escalation_not_appealable(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_gemini = MagicMock(return_value=REJECT_SCORE)
        mock_claude = MagicMock(return_value=ALLOW_SCORE)
        mock_openai = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            result = is_text_positive("bad text")
        self.assertFalse(result)
        self.assertFalse(result.appealable)
        mock_claude.assert_not_called()
        mock_openai.assert_not_called()

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_middle_then_second_allows(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_gemini = MagicMock(return_value=MIDDLE_SCORE)
        mock_claude = MagicMock(return_value=ALLOW_SCORE)
        mock_openai = MagicMock(return_value=REJECT_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            self.assertTrue(is_text_positive("some text"))
        mock_openai.assert_not_called()

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_middle_then_reject_then_third_allows(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_gemini = MagicMock(return_value=MIDDLE_SCORE)
        mock_claude = MagicMock(return_value=REJECT_SCORE)
        mock_openai = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            self.assertTrue(is_text_positive("some text"))
        mock_openai.assert_called_once()

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_third_middle_rejected_but_appealable(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_gemini = MagicMock(return_value=MIDDLE_SCORE)
        mock_claude = MagicMock(return_value=MIDDLE_SCORE)
        mock_openai = MagicMock(return_value=MIDDLE_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertTrue(result.appealable)

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_third_reject_not_appealable(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_gemini = MagicMock(return_value=MIDDLE_SCORE)
        mock_claude = MagicMock(return_value=REJECT_SCORE)
        mock_openai = MagicMock(return_value=REJECT_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertFalse(result.appealable)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "gk", "ANTHROPIC_API_KEY": "ak"}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_two_apis_second_middle_no_third_rejected_appealable(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        mock_gemini = MagicMock(return_value=MIDDLE_SCORE)
        mock_claude = MagicMock(return_value=MIDDLE_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude}):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertTrue(result.appealable)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "gk", "ANTHROPIC_API_KEY": "ak"}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_two_apis_second_reject_no_third_rejected_not_appealable(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        mock_gemini = MagicMock(return_value=MIDDLE_SCORE)
        mock_claude = MagicMock(return_value=REJECT_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude}):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertFalse(result.appealable)

    # ------------------------------------------------------------------ #
    # Rejection reasons                                                    #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_rejection_reason_from_single_ai(self):
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=(REJECT_SCORE, 5))}):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertEqual(result.reason_code, 'hate_speech')
        self.assertEqual(result.public_reason_code(), 'hate_speech')
        self.assertEqual(result.public_reason(), 'may contain hate speech')

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_rejection_without_cited_rule_uses_generic_reason(self):
        # A bare score (legacy mocks / models that ignore the rule instruction)
        # still rejects, with the generic reason.
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=REJECT_SCORE)}):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertIsNone(result.reason_code)
        self.assertEqual(result.public_reason_code(), GENERIC_REASON_CODE)
        self.assertEqual(result.public_reason(), REASON_PHRASES[GENERIC_REASON_CODE])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_allowed_result_has_no_reason(self):
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=(ALLOW_SCORE, 2))}):
            result = is_text_positive("some text")
        self.assertTrue(result)
        self.assertIsNone(result.reason_code)

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_rejection_reason_majority_wins(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mocks = {
            API_GEMINI: MagicMock(return_value=(MIDDLE_SCORE, 2)),
            API_CLAUDE: MagicMock(return_value=(REJECT_SCORE, 5)),
            API_OPENAI: MagicMock(return_value=(REJECT_SCORE, 5)),
        }
        with patch.dict(_TEXT_DISPATCH, mocks):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertEqual(result.reason_code, 'hate_speech')

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_rejection_reason_tie_broken_by_decisive_ai(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mocks = {
            API_GEMINI: MagicMock(return_value=(MIDDLE_SCORE, 2)),
            API_CLAUDE: MagicMock(return_value=(MIDDLE_SCORE, 6)),
            API_OPENAI: MagicMock(return_value=(MIDDLE_SCORE, 6)),
        }
        with patch.dict(_TEXT_DISPATCH, mocks):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertTrue(result.appealable)
        self.assertEqual(result.reason_code, 'harassment')

    @patch.dict(os.environ, _ALL_AI_KEYS, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_rejection_reason_single_citation_wins(self, mock_random):
        # When only one AI cites a rule, that rule is the reason even though
        # the others scored without citing anything.
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mocks = {
            API_GEMINI: MagicMock(return_value=(MIDDLE_SCORE, None)),
            API_CLAUDE: MagicMock(return_value=(MIDDLE_SCORE, 7)),
            API_OPENAI: MagicMock(return_value=(MIDDLE_SCORE, None)),
        }
        with patch.dict(_TEXT_DISPATCH, mocks):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertEqual(result.reason_code, 'bullying')

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_testing_mode_rejection_has_generic_reason(self):
        result = is_text_positive("negative random text")
        self.assertFalse(result)
        self.assertEqual(result.public_reason_code(), GENERIC_REASON_CODE)

    # ------------------------------------------------------------------ #
    # Text classifier – API errors are skipped                             #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "gk", "ANTHROPIC_API_KEY": "ak"}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    def test_text_cascade_errored_api_is_skipped(self, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE]
        mock_gemini = MagicMock(side_effect=Exception("boom"))
        mock_claude = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude}):
            self.assertTrue(is_text_positive("some text"))
        mock_claude.assert_called_once()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_text_cascade_all_apis_error_rejected_not_appealable(self):
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(side_effect=Exception("boom"))}):
            result = is_text_positive("some text")
        self.assertFalse(result)
        self.assertFalse(result.appealable)
        # No usable score at all is infrastructure, not a verdict (issue #282).
        self.assertTrue(result.provider_failure)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}, clear=True)
    def test_genuine_rejection_is_not_a_provider_failure(self):
        with patch.dict(_TEXT_DISPATCH, {API_GEMINI: MagicMock(return_value=REJECT_SCORE)}):
            result = is_text_positive("I am sad")
        self.assertFalse(result)
        self.assertFalse(result.provider_failure)

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
        result = is_image_positive("some_image.png")
        self.assertFalse(result)
        self.assertTrue(result.provider_failure)

    # ------------------------------------------------------------------ #
    # Image classifier – single API                                        #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_image_classifier_single_gemini_allow_zone(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        mock_gemini = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: mock_gemini}):
            self.assertTrue(is_image_positive("some_image.png"))
        mock_s3.get_object.assert_called_with(Bucket="fake_bucket", Key="some_image.png")
        mock_gemini.assert_called_once()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_image_classifier_single_gemini_reject_zone(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=REJECT_SCORE)}):
            result = is_image_positive("some_image.png")
        self.assertFalse(result)
        self.assertFalse(result.appealable)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_image_classifier_single_gemini_middle_zone_appealable(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=MIDDLE_SCORE)}):
            result = is_image_positive("some_image.png")
        self.assertFalse(result)
        self.assertTrue(result.appealable)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_image_classifier_single_claude_allow_zone(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        mock_claude = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_IMAGE_DISPATCH, {API_CLAUDE: mock_claude}):
            self.assertTrue(is_image_positive("some_image.png"))
        mock_claude.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_image_classifier_single_openai_allow_zone(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        mock_openai = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_IMAGE_DISPATCH, {API_OPENAI: mock_openai}):
            self.assertTrue(is_image_positive("some_image.png"))
        mock_openai.assert_called_once()

    # ------------------------------------------------------------------ #
    # Image classifier – cascade                                           #
    # ------------------------------------------------------------------ #

    @patch.dict(os.environ, {**_ALL_AI_KEYS, **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_image_cascade_first_allows_no_escalation(self, mock_boto3, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        mock_gemini = MagicMock(return_value=ALLOW_SCORE)
        mock_claude = MagicMock(return_value=ALLOW_SCORE)
        mock_openai = MagicMock(return_value=ALLOW_SCORE)
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            self.assertTrue(is_image_positive("img.png"))
        mock_claude.assert_not_called()
        mock_openai.assert_not_called()

    @patch.dict(os.environ, {**_ALL_AI_KEYS, **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.classifier_utils.random")
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_image_cascade_middle_then_reject_then_reject_not_appealable(self, mock_boto3, mock_random):
        mock_random.sample.return_value = [API_GEMINI, API_CLAUDE, API_OPENAI]
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}

        mock_gemini = MagicMock(return_value=MIDDLE_SCORE)
        mock_claude = MagicMock(return_value=REJECT_SCORE)
        mock_openai = MagicMock(return_value=REJECT_SCORE)
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: mock_gemini, API_CLAUDE: mock_claude, API_OPENAI: mock_openai}):
            result = is_image_positive("img.png")
        self.assertFalse(result)
        self.assertFalse(result.appealable)
        mock_openai.assert_called_once()

    # ------------------------------------------------------------------ #
    # Image classifier – S3 URL parsing                                    #
    # ------------------------------------------------------------------ #

    def _make_mock_s3(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = _make_fake_image_bytes()
        mock_s3.get_object.return_value = {'Body': mock_body}
        return mock_s3

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_url_parsing_virtual_hosted_with_bucket_env_var(self, mock_boto3):
        """When AWS_STORAGE_BUCKET_NAME is set, virtual-hosted URL key is still extracted from path."""
        mock_s3 = self._make_mock_s3(mock_boto3)
        url = "https://goodvibesonly-images.s3.us-east-2.amazonaws.com/folder/image.jpg"
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=ALLOW_SCORE)}):
            is_image_positive(url)
        mock_s3.get_object.assert_called_with(Bucket="fake_bucket", Key="folder/image.jpg")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS_NO_BUCKET}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_url_parsing_virtual_hosted_without_bucket_env_var(self, mock_boto3):
        """When AWS_STORAGE_BUCKET_NAME is unset, bucket is derived from virtual-hosted URL hostname."""
        mock_s3 = self._make_mock_s3(mock_boto3)
        url = "https://goodvibesonly-images.s3.us-east-2.amazonaws.com/folder/image.jpg"
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=ALLOW_SCORE)}):
            is_image_positive(url)
        mock_s3.get_object.assert_called_with(Bucket="goodvibesonly-images", Key="folder/image.jpg")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS_NO_BUCKET}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_url_parsing_path_style(self, mock_boto3):
        """Path-style URL (s3.amazonaws.com/bucket/key) correctly splits bucket and key."""
        mock_s3 = self._make_mock_s3(mock_boto3)
        url = "https://s3.amazonaws.com/mybucket/path/to/image.jpg"
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=ALLOW_SCORE)}):
            is_image_positive(url)
        mock_s3.get_object.assert_called_with(Bucket="mybucket", Key="path/to/image.jpg")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS_NO_BUCKET}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_url_parsing_path_style_dashed_region(self, mock_boto3):
        """Dashed-region path-style URL (s3-region.amazonaws.com/bucket/key) is not misread as virtual-hosted."""
        mock_s3 = self._make_mock_s3(mock_boto3)
        url = "https://s3-us-west-2.amazonaws.com/mybucket/path/to/image.jpg"
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=ALLOW_SCORE)}):
            is_image_positive(url)
        mock_s3.get_object.assert_called_with(Bucket="mybucket", Key="path/to/image.jpg")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS_NO_BUCKET}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_url_parsing_virtual_hosted_s3_dash_bucket(self, mock_boto3):
        """A virtual-hosted bucket whose name starts with 's3-' is not misread as path-style."""
        mock_s3 = self._make_mock_s3(mock_boto3)
        url = "https://s3-my-bucket.s3.amazonaws.com/123/abc.jpeg"
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=ALLOW_SCORE)}):
            is_image_positive(url)
        mock_s3.get_object.assert_called_with(Bucket="s3-my-bucket", Key="123/abc.jpeg")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS_NO_BUCKET}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_url_parsing_virtual_hosted_s3_dash_bucket_with_region(self, mock_boto3):
        """An 's3-' virtual-hosted bucket with a region is still parsed as virtual-hosted."""
        mock_s3 = self._make_mock_s3(mock_boto3)
        url = "https://s3-my-bucket.s3.us-east-2.amazonaws.com/123/abc.jpeg"
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=ALLOW_SCORE)}):
            is_image_positive(url)
        mock_s3.get_object.assert_called_with(Bucket="s3-my-bucket", Key="123/abc.jpeg")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", **_AWS_KEYS_NO_BUCKET}, clear=True)
    @patch("user_system.classifiers.image_classifier.boto3")
    def test_url_parsing_virtual_hosted_s3_dash_bucket_accelerate(self, mock_boto3):
        """An 's3-' virtual-hosted bucket on a non-literal-'s3' endpoint label is still virtual-hosted."""
        mock_s3 = self._make_mock_s3(mock_boto3)
        url = "https://s3-my-bucket.s3-accelerate.amazonaws.com/123/abc.jpeg"
        with patch.dict(_IMAGE_DISPATCH, {API_GEMINI: MagicMock(return_value=ALLOW_SCORE)}):
            is_image_positive(url)
        mock_s3.get_object.assert_called_with(Bucket="s3-my-bucket", Key="123/abc.jpeg")

    # ------------------------------------------------------------------ #
    # Prompt content                                                       #
    # ------------------------------------------------------------------ #

    def test_text_classifier_prompt_content(self):
        for phrase in [
            "neutral",
            "sexually suggestive content",
            "misinformation",
            "begins sad but ends on a happy or hopeful note",
            "between 0.00 and 1.00",
            "separated by a comma",
            "or 0 if none",
        ]:
            self.assertIn(phrase, TEXT_CLASSIFIER_PROMPT, msg=f"Missing in TEXT_CLASSIFIER_PROMPT: {phrase!r}")

    def test_image_classifier_prompt_content(self):
        for phrase in [
            "neutral",
            "sexually suggestive content",
            "misinformation",
            "begins sad but ends on a happy or hopeful note",
            "between 0.00 and 1.00",
            "separated by a comma",
            "or 0 if none",
        ]:
            self.assertIn(phrase, IMAGE_CLASSIFIER_PROMPT, msg=f"Missing in IMAGE_CLASSIFIER_PROMPT: {phrase!r}")
