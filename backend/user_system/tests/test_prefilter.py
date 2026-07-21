from django.test import SimpleTestCase

from ..classifiers.prefilter import prefilter_text


class PrefilterTests(SimpleTestCase):
    """The cheap local pre-filter (issue #282): blatant hits are final,
    everything else passes through to the async cascade."""

    def test_clean_caption_is_allowed(self):
        self.assertTrue(prefilter_text('what a lovely sunny day'))

    def test_profanity_is_rejected_final_with_reason(self):
        result = prefilter_text('what a shit day')
        self.assertFalse(result)
        self.assertFalse(result.appealable)
        self.assertEqual(result.public_reason_code(), 'profanity')

    def test_profanity_match_is_case_insensitive(self):
        self.assertFalse(prefilter_text('FUCK this'))

    def test_slur_is_rejected_as_hate_speech(self):
        result = prefilter_text('you are a retard')
        self.assertFalse(result)
        self.assertEqual(result.public_reason_code(), 'hate_speech')

    def test_slur_outranks_profanity_in_the_reported_reason(self):
        result = prefilter_text('shit, what a retard')
        self.assertEqual(result.public_reason_code(), 'hate_speech')

    def test_matches_whole_words_only(self):
        # "shiitake" contains no whole-word hit; neither does "class".
        self.assertTrue(prefilter_text('shiitake mushrooms are the best in class'))

    def test_non_string_input_is_coerced_not_crashed(self):
        self.assertTrue(prefilter_text(12345))
