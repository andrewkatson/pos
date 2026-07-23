import os
from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_TEXT
from ..constants import Fields, DEFAULT_STYLE_KEY
from ..models import Comment, Post
from ..views import get_user_with_username


class CaptionStyleTests(PositiveOnlySocialTestCase):
    """Whole-caption font + whole-tile background color on posts (issue #318)."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.make_url = reverse('make_post')

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def _create_post(self, **extra):
        data = {'caption': POSITIVE_TEXT, **extra}
        return self.client.post(self.make_url, data=data, content_type='application/json', **self.header)

    def _details(self, post_id):
        url = reverse('get_post_details', kwargs={'post_identifier': str(post_id)})
        return self.client.get(url, **self.header)

    def test_valid_font_and_color_are_stored_and_returned(self):
        response = self._create_post(caption_font='serif', background_color='mint')
        self.assertEqual(response.status_code, 201)
        post_id = response.json()[Fields.post_identifier]

        post = Post.objects.get(post_identifier=post_id)
        self.assertEqual(post.caption_font, 'serif')
        self.assertEqual(post.background_color, 'mint')

        details = self._details(post_id).json()
        self.assertEqual(details[Fields.caption_font], 'serif')
        self.assertEqual(details[Fields.background_color], 'mint')

    def test_absent_style_defaults(self):
        response = self._create_post()
        self.assertEqual(response.status_code, 201)
        details = self._details(response.json()[Fields.post_identifier]).json()
        self.assertEqual(details[Fields.caption_font], DEFAULT_STYLE_KEY)
        self.assertEqual(details[Fields.background_color], DEFAULT_STYLE_KEY)

    def test_invalid_font_is_rejected(self):
        response = self._create_post(caption_font='comic-sans')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.user.post_set.count(), 0)

    def test_invalid_color_is_rejected(self):
        response = self._create_post(background_color='#ff0000')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.user.post_set.count(), 0)


class CommentFormattingTests(PositiveOnlySocialTestCase):
    """Inline bold/italic/size formatting on comments (issue #318)."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.token = self.session_management_token
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        with patch.dict(os.environ, {"TESTING": "True"}, clear=True):
            self.post_id = self._make_post(self.token)[Fields.post_identifier]

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def _comment(self, text=POSITIVE_TEXT, formatting=None):
        url = reverse('comment_on_post', kwargs={'post_identifier': str(self.post_id)})
        data = {'comment_text': text}
        if formatting is not None:
            data[Fields.body_formatting] = formatting
        return self.client.post(url, data=data, content_type='application/json', **self.header)

    def _thread_comments(self, thread_id):
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(thread_id), 'batch': 0})
        return self.client.get(url, **self.header).json()

    def test_valid_formatting_is_stored_and_returned(self):
        # "positive" -> bold the first four chars, italic+large the rest.
        spans = [
            {'start': 0, 'end': 4, 'bold': True},
            {'start': 4, 'end': 8, 'italic': True, 'size': 'large'},
        ]
        response = self._comment(formatting=spans)
        self.assertEqual(response.status_code, 201)
        thread_id = response.json()[Fields.comment_thread_identifier]

        comment_id = response.json()[Fields.comment_identifier]
        stored = Comment.objects.get(comment_identifier=comment_id)
        # The plain body is untouched — moderation still classified plain text.
        self.assertEqual(stored.body, POSITIVE_TEXT)
        self.assertEqual(len(stored.body_formatting), 2)
        self.assertEqual(stored.body_formatting[0], {
            'start': 0, 'end': 4, 'bold': True, 'italic': False, 'size': 'normal'})

        returned = self._thread_comments(thread_id)
        self.assertEqual(returned[0][Fields.body], POSITIVE_TEXT)
        self.assertEqual(returned[0][Fields.body_formatting][1]['size'], 'large')

    def test_absent_formatting_is_null(self):
        response = self._comment()
        self.assertEqual(response.status_code, 201)
        stored = Comment.objects.get(comment_identifier=response.json()[Fields.comment_identifier])
        self.assertIsNone(stored.body_formatting)

    def test_out_of_bounds_span_rejected(self):
        # POSITIVE_TEXT is 8 chars; end past the length is invalid.
        response = self._comment(formatting=[{'start': 0, 'end': 99, 'bold': True}])
        self.assertEqual(response.status_code, 400)

    def test_overlapping_spans_rejected(self):
        response = self._comment(formatting=[
            {'start': 0, 'end': 5, 'bold': True},
            {'start': 3, 'end': 7, 'italic': True},
        ])
        self.assertEqual(response.status_code, 400)

    def test_bad_size_rejected(self):
        response = self._comment(formatting=[{'start': 0, 'end': 4, 'size': 'gigantic'}])
        self.assertEqual(response.status_code, 400)

    def test_empty_style_span_rejected(self):
        # A span that turns nothing on is meaningless and rejected.
        response = self._comment(formatting=[{'start': 0, 'end': 4}])
        self.assertEqual(response.status_code, 400)

    def test_too_many_spans_rejected(self):
        # 101 non-overlapping single-char spans over a long body exceeds the
        # MAX_COMMENT_FORMAT_SPANS cap of 100.
        response = self._comment(text='a' * 300, formatting=[
            {'start': i, 'end': i + 1, 'bold': True} for i in range(0, 101)])
        self.assertEqual(response.status_code, 400)

    def test_non_list_formatting_rejected(self):
        response = self._comment(formatting={'start': 0, 'end': 4, 'bold': True})
        self.assertEqual(response.status_code, 400)
