import os
from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, POST_BATCH_SIZE
from ..classifiers.classifier_constants import NEGATIVE_TEXT

invalid_session_management_token = '?'


class GetPostsForTagTests(PositiveOnlySocialTestCase):
    """Browse-posts-by-tag endpoint (issue #379)."""

    def setUp(self):
        super().setUp()

        # Viewer (the caller of the tag feed).
        self.register_user_and_setup_local_fields()
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        # Poster (author of the tagged posts).
        poster = self.make_user_with_prefix(prefix='poster')
        self.poster_username = poster['username']
        self.poster_token = poster[Fields.session_management_token]

    def _url(self, tag, batch=0):
        return reverse('get_posts_for_tag', kwargs={'tag': tag, 'batch': batch})

    def _post_as_poster(self, caption):
        return self._make_post(self.poster_token, caption=caption)

    def test_invalid_token_returns_unauthorized(self):
        response = self.client.get(
            self._url('sunset'),
            HTTP_AUTHORIZATION=f'Bearer {invalid_session_management_token}',
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_tag_returns_bad_request(self):
        # '$' is not a word character, so it fails Patterns.tag.
        response = self.client.get(self._url('$'), **self.header)
        self.assertEqual(response.status_code, 400)

    # Named "below_zero" rather than "negative" on purpose: the test classifier
    # treats any text containing "negative" as non-positive, and the method name
    # becomes part of the registered username in setUp.
    def test_below_zero_batch_returns_not_found(self):
        # The int URL converter never matches a leading '-', so the route 404s
        # before the view runs (same as the other listing endpoints).
        negative_batch_url = self._url('sunset', 0).replace('/0/', '/-1/')
        response = self.client.get(negative_batch_url, **self.header)
        self.assertEqual(response.status_code, 404)

    def test_unknown_tag_returns_empty_list(self):
        response = self.client.get(self._url('nothinghere'), **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_returns_only_posts_with_that_tag(self):
        self._post_as_poster('a lovely #sunset over the sea')
        self._post_as_poster('another #sunset tonight')
        self._post_as_poster('some #rain today')

        response = self.client.get(self._url('sunset'), **self.header)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 2)
        for post in body:
            self.assertIn('sunset', post[Fields.tags])

    def test_tag_lookup_is_case_insensitive(self):
        self._post_as_poster('mixed case #SunSet')

        # Query with a different case than the caption used.
        response = self.client.get(self._url('sunset'), **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        # And an upper-case query resolves to the same normalized tag.
        response_upper = self.client.get(self._url('SUNSET'), **self.header)
        self.assertEqual(len(response_upper.json()), 1)

    def test_payload_includes_tags_field(self):
        self._post_as_poster('beach day #sunset #beach')

        response = self.client.get(self._url('sunset'), **self.header)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0][Fields.tags], ['beach', 'sunset'])
        # Sanity: the usual post fields are present too.
        self.assertIn(Fields.post_identifier, body[0])
        self.assertIn(Fields.caption, body[0])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_hidden_post_is_excluded_for_other_viewers(self):
        # A caption containing "negative" is final-rejected by the eager test
        # worker, so the post is hidden — but it was still tagged at creation.
        self._make_post(self.poster_token, caption=f'{NEGATIVE_TEXT} #sunset')

        response = self.client.get(self._url('sunset'), **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_blocked_authors_posts_are_excluded(self):
        self._post_as_poster('great #sunset')

        # Viewer blocks the poster.
        block_url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.poster_username})
        block_response = self.client.post(block_url, **self.header)
        self.assertEqual(block_response.status_code, 200)

        response = self.client.get(self._url('sunset'), **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_results_are_paginated(self):
        total = POST_BATCH_SIZE + 2
        for i in range(total):
            self._post_as_poster(f'view number {i} #sunset')

        first = self.client.get(self._url('sunset', batch=0), **self.header)
        second = self.client.get(self._url('sunset', batch=1), **self.header)
        self.assertEqual(len(first.json()), POST_BATCH_SIZE)
        self.assertEqual(len(second.json()), total - POST_BATCH_SIZE)
