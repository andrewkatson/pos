"""Tests for `convert_to_bool`.

Its contract is "returns a bool or raises TypeError", and callers lean on that:
every view that reads an optional boolean field wraps it in `except TypeError`
to turn a bad value into a 400. When a non-string slipped through to `.lower()`
it raised AttributeError instead, which no caller catches — so a request that
merely omitted `remember_me` came back as a 500.
"""

from django.test import SimpleTestCase

from ..utils import convert_to_bool


class ConvertToBoolTests(SimpleTestCase):

    def test_parses_the_string_forms_in_any_case(self):
        for value, expected in [
            ('true', True), ('True', True), ('TRUE', True),
            ('false', False), ('False', False), ('FALSE', False),
        ]:
            with self.subTest(value=value):
                self.assertIs(convert_to_bool(value), expected)

    def test_passes_an_actual_bool_straight_through(self):
        self.assertIs(convert_to_bool(True), True)
        self.assertIs(convert_to_bool(False), False)

    def test_an_unparseable_string_raises_type_error(self):
        with self.assertRaises(TypeError):
            convert_to_bool('perhaps')
        with self.assertRaises(TypeError):
            convert_to_bool('')

    def test_none_raises_type_error_rather_than_attribute_error(self):
        """The regression: `None.lower()` raised AttributeError, which escaped
        every caller's except clause and turned a missing field into a 500."""
        with self.assertRaises(TypeError):
            convert_to_bool(None)

    def test_non_string_types_raise_type_error(self):
        """A JSON body can carry a number, a list or an object here."""
        for value in (1, 0, 1.5, [], {}, object()):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    convert_to_bool(value)
