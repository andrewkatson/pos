from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from ..constants import MAX_USERNAME_LENGTH, MIN_USERNAME_LENGTH, Patterns
from ..input_validator import is_valid_pattern


class UsernamePatternTests(SimpleTestCase):
    """Patterns.username must never accept a name the username column cannot
    store, or registration fails at the database instead of as a 400."""

    def test_max_length_matches_username_column(self):
        column = get_user_model()._meta.get_field('username')
        self.assertEqual(MAX_USERNAME_LENGTH, column.max_length)

    def test_bounds(self):
        self.assertFalse(is_valid_pattern('a' * (MIN_USERNAME_LENGTH - 1), Patterns.username))
        self.assertTrue(is_valid_pattern('a' * MIN_USERNAME_LENGTH, Patterns.username))
        self.assertTrue(is_valid_pattern('a' * MAX_USERNAME_LENGTH, Patterns.username))
        self.assertFalse(is_valid_pattern('a' * (MAX_USERNAME_LENGTH + 1), Patterns.username))
        self.assertFalse(is_valid_pattern('a' * 500, Patterns.username))

    def test_trailing_newline_rejected(self):
        """`$` matches before a trailing newline; the pattern must not, or a
        150-character name plus "\n" reaches the 150-character column."""
        self.assertFalse(is_valid_pattern('a' * MAX_USERNAME_LENGTH + '\n', Patterns.username))
        self.assertFalse(is_valid_pattern('a' * MIN_USERNAME_LENGTH + '\n', Patterns.username))

    def test_search_fragment_capped_at_username_length(self):
        self.assertTrue(is_valid_pattern('abc', Patterns.short_alphanumeric))
        self.assertTrue(is_valid_pattern('a' * MAX_USERNAME_LENGTH, Patterns.short_alphanumeric))
        self.assertFalse(is_valid_pattern('a' * (MAX_USERNAME_LENGTH + 1), Patterns.short_alphanumeric))
        self.assertFalse(is_valid_pattern('abc\n', Patterns.short_alphanumeric))

    def test_non_word_characters_rejected(self):
        self.assertFalse(is_valid_pattern('has a space', Patterns.username))
        self.assertFalse(is_valid_pattern('dash-in-the-name', Patterns.username))

    def test_token_pattern_keeps_its_own_bound(self):
        """Session and login-cookie tokens share Patterns.alphanumeric, which
        is not a username rule — tightening usernames must not reject them."""
        self.assertTrue(is_valid_pattern('a' * 500, Patterns.alphanumeric))
