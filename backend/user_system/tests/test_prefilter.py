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

    def test_ldnoobw_word_outside_curated_list_is_rejected(self):
        # 'bollocks' is in the vendored LDNOOBW list but not the curated floor,
        # so this only passes when the LDNOOBW file is actually loaded (#393).
        result = prefilter_text('what a load of bollocks')
        self.assertFalse(result)
        self.assertEqual(result.public_reason_code(), 'profanity')

    def test_ldnoobw_multiword_phrase_is_rejected(self):
        # A multi-word LDNOOBW entry must match as a phrase, across arbitrary
        # whitespace between its tokens.
        self.assertFalse(prefilter_text('the alabama  hot pocket incident'))

    def test_ldnoobw_substring_does_not_trip_on_word_boundary(self):
        # 'analysis' contains 'anal' but is a whole different word.
        self.assertTrue(prefilter_text('a careful analysis of the class scunthorpe'))

    def test_ldnoobw_non_word_char_entry_is_matched(self):
        # A term that begins/ends with a non-word character (the LDNOOBW emoji
        # entry) must still match — \b could never catch these; the lookaround
        # matcher does.
        result = prefilter_text('right back at you \U0001f595')
        self.assertFalse(result)
        self.assertEqual(result.public_reason_code(), 'profanity')
