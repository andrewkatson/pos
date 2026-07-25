import os
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, MAX_TAG_LENGTH, MAX_TAGS_PER_POST
from ..tags import extract_tag_names
from ..views import get_user_with_username


class ExtractTagNamesTests(SimpleTestCase):
    """Unit tests for the caption -> tag-names parser (issue #379)."""

    def test_no_tags_returns_empty(self):
        self.assertEqual(extract_tag_names('just a plain caption'), [])

    def test_empty_or_none_returns_empty(self):
        self.assertEqual(extract_tag_names(''), [])
        self.assertEqual(extract_tag_names(None), [])

    def test_single_tag(self):
        self.assertEqual(extract_tag_names('what a #sunset'), ['sunset'])

    def test_multiple_tags_keep_first_seen_order(self):
        self.assertEqual(
            extract_tag_names('#beach then #sunset then #waves'),
            ['beach', 'sunset', 'waves'],
        )

    def test_tags_are_lowercased(self):
        self.assertEqual(extract_tag_names('#Sunset #BEACH'), ['sunset', 'beach'])

    def test_case_insensitive_dedupe(self):
        # #Sun and #sun are the same tag; only the first is kept.
        self.assertEqual(extract_tag_names('#Sun rises then #sun sets'), ['sun'])

    def test_punctuation_terminates_a_tag(self):
        self.assertEqual(extract_tag_names('great #day! and #ok.'), ['day', 'ok'])

    def test_digits_and_underscores_are_part_of_a_tag(self):
        self.assertEqual(extract_tag_names('#a_1 and #2024'), ['a_1', '2024'])

    def test_unicode_letters_are_part_of_a_tag(self):
        self.assertEqual(extract_tag_names('#café time'), ['café'])

    def test_bare_hash_is_not_a_tag(self):
        self.assertEqual(extract_tag_names('a # b #real'), ['real'])

    def test_overlong_tag_is_skipped(self):
        caption = '#' + ('a' * (MAX_TAG_LENGTH + 1)) + ' #ok'
        # The overlong token cannot be stored, so it is dropped; the valid one stays.
        self.assertEqual(extract_tag_names(caption), ['ok'])

    def test_tag_at_max_length_is_kept(self):
        name = 'a' * MAX_TAG_LENGTH
        self.assertEqual(extract_tag_names('#' + name), [name])

    def test_caps_number_of_tags(self):
        caption = ' '.join(f'#t{i}' for i in range(MAX_TAGS_PER_POST + 5))
        self.assertEqual(len(extract_tag_names(caption)), MAX_TAGS_PER_POST)


class MakePostTaggingTests(PositiveOnlySocialTestCase):
    """make_post harvests #hashtags from the caption into Tag rows (issue #379)."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('make_post')

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_tags_are_extracted_and_normalized(self):
        response = self.client.post(
            self.url,
            data={'caption': 'loving this #Sunset and #beach #Sunset'},
            content_type='application/json',
            **self.header,
        )
        self.assertEqual(response.status_code, 201)
        post = self.user.post_set.get()
        # Lowercased and de-duplicated.
        self.assertEqual(sorted(t.name for t in post.tags.all()), ['beach', 'sunset'])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_caption_without_tags_creates_no_tags(self):
        response = self.client.post(
            self.url,
            data={'caption': 'positive vibes only'},
            content_type='application/json',
            **self.header,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.user.post_set.get().tags.count(), 0)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_tag_rows_are_shared_between_posts(self):
        for _ in range(2):
            self.client.post(
                self.url,
                data={'caption': 'another #sunset'},
                content_type='application/json',
                **self.header,
            )
        # Two posts, but they point at the same single Tag row.
        from ..models import Tag
        self.assertEqual(Tag.objects.filter(name='sunset').count(), 1)
        self.assertEqual(Tag.objects.get(name='sunset').posts.count(), 2)
