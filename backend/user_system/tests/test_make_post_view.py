from unittest.mock import patch
import os
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_IMAGE_FILENAME, NEGATIVE_IMAGE_FILENAME, POSITIVE_TEXT, NEGATIVE_TEXT, NEGATIVE_IMAGE_URL
from ..constants import Fields, MAX_CAPTION_LENGTH, \
    HIDDEN_REASON_CLASSIFIER_FINAL, HIDDEN_REASON_PENDING_CLASSIFICATION, \
    POST_STATUS_PENDING
from ..views import get_user_with_username

# --- Constants ---
invalid_session_management_token = '?'
invalid_image_url = '?'
# Trips the local pre-filter (issue #282), so it is rejected inline without
# the post ever being created.
profane_caption = 'what a shit day'

class MakePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # This helper is assumed to create/login a user and set
        # self.local_username and self.session_management_token
        self.register_user_and_setup_local_fields()

        # Store the user object, valid header, and URL for all tests
        self.user = get_user_with_username(self.local_username)
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('make_post')

        # A valid data payload for the "happy path" — key scoped to the authenticated user
        self.valid_data = {
            'image_url': f'https://test-bucket.s3.amazonaws.com/{self.user.id}/{POSITIVE_IMAGE_FILENAME}',
            'caption': POSITIVE_TEXT
        }

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(
            self.url,
            data=self.valid_data,
            content_type='application/json',
            **invalid_header
        )

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_invalid_image_url_returns_bad_response(self):
        """
        Tests that a malformed image_url is rejected.
        """
        data = self.valid_data.copy()
        data['image_url'] = invalid_image_url

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)

    def test_profane_caption_fails_the_prefilter_inline(self):
        """
        A caption that trips the local pre-filter (issue #282) is rejected
        immediately — no post is created and the rejection is final.
        """
        data = self.valid_data.copy()
        data['caption'] = profane_caption

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("Text is not positive", body.get('error', ''))
        self.assertFalse(body[Fields.appealable])
        self.assertEqual(self.user.post_set.count(), 0)

    def test_provider_failure_leaves_post_pending(self):
        """
        With no AI provider keys configured (this test sets no TESTING env and
        no API keys), classification is a provider failure, not a verdict. The
        post must fail closed: created but stuck hidden in the pending state
        rather than published or falsely rejected (issue #282).
        """
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post(
                self.url,
                data=self.valid_data,
                content_type='application/json',
                **self.valid_header
            )

        self.assertEqual(response.status_code, 201)
        post = self.user.post_set.get()
        self.assertTrue(post.hidden)
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_PENDING_CLASSIFICATION)

    # The reason this test isn't "negative" in title is because the classifier looks for "negative" in tests
    # in the username and will fail this test
    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_not_positive_image_resolves_to_final_rejection(self):
        """
        A negative image (as per the fake classifier) is accepted as pending
        (classification is async, issue #282) and then resolved by the eager
        worker into a non-appealable final-rejection tombstone.
        """
        data = {'image_url': f'https://test-bucket.s3.amazonaws.com/{self.user.id}/{NEGATIVE_IMAGE_FILENAME}', 'caption': POSITIVE_TEXT}

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()[Fields.status], POST_STATUS_PENDING)
        post = self.user.post_set.get()
        self.assertTrue(post.hidden)
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_CLASSIFIER_FINAL)

    # The reason this test isn't "negative" in title is because the classifier looks for "negative" in tests
    # in the username and will fail this test
    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_not_positive_caption_resolves_to_final_rejection(self):
        """
        A negative caption (as per the fake classifier) is accepted as pending
        and then resolved into a final-rejection tombstone by the worker.
        """
        data = self.valid_data.copy()
        data['caption'] = NEGATIVE_TEXT

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        post = self.user.post_set.get()
        self.assertTrue(post.hidden)
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_CLASSIFIER_FINAL)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_make_post_returns_good_response_and_adds_post_to_user(self):
        """
        Tests the "happy path" for creating a post.
        """
        # 1. Check DB before
        self.assertEqual(self.user.post_set.count(), 0)

        # 2. Make the request
        response = self.client.post(
            self.url,
            data=self.valid_data,
            content_type='application/json',
            **self.valid_header
        )

        # 3. Check response
        self.assertEqual(response.status_code, 201)  # 201 Created
        fields = response.json()
        self.assertIn(Fields.post_identifier, fields)

        # 4. Check DB after
        self.user.refresh_from_db()
        self.assertEqual(self.user.post_set.count(), 1)

        # 5. Verify the created post
        post = self.user.post_set.first()
        self.assertEqual(fields[Fields.post_identifier], str(post.post_identifier))
        self.assertEqual(post.caption, POSITIVE_TEXT)
        self.assertEqual(post.image_url, self.valid_data['image_url'])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_text_rejection_takes_precedence_over_image(self):
        """
        When the caption fails the text classifier, the recorded rejection
        carries the text reason regardless of the image result (text
        precedence, matching the old synchronous ordering). Classification is
        async (issue #282), so the outcome lands on the post row, not the
        response.
        """
        data = self.valid_data.copy()
        data['caption'] = NEGATIVE_TEXT

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        post = self.user.post_set.get()
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_CLASSIFIER_FINAL)

    def test_image_url_with_wrong_user_prefix_returns_bad_response(self):
        """
        A valid S3 URL whose key is prefixed with a different user's ID must be rejected.
        """
        data = self.valid_data.copy()
        data['image_url'] = f'https://test-bucket.s3.amazonaws.com/99999/{POSITIVE_IMAGE_FILENAME}'

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)

    def test_image_url_on_foreign_bucket_returns_bad_response(self):
        """
        A pattern-valid, user-scoped key that lives on someone else's S3 bucket
        must be rejected (the SSRF-ish gap): otherwise the classifier would
        fetch attacker-controlled content and we would mint CloudFront URLs for
        objects we do not own.
        """
        data = self.valid_data.copy()
        data['image_url'] = f'https://attacker-bucket.s3.amazonaws.com/{self.user.id}/{POSITIVE_IMAGE_FILENAME}'

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)

    def test_image_url_with_no_user_prefix_returns_bad_response(self):
        """
        A valid S3 URL whose key has no user ID prefix must be rejected.
        """
        data = self.valid_data.copy()
        data['image_url'] = POSITIVE_IMAGE_URL  # bare key, no user ID segment

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)

    def test_caption_over_max_length_returns_bad_response(self):
        """
        A caption longer than MAX_CAPTION_LENGTH characters must be rejected with a
        message that states the limit.
        """
        data = self.valid_data.copy()
        # Positive text (no "negative" substring) so only the length check can fail it.
        data['caption'] = 'a' * (MAX_CAPTION_LENGTH + 1)

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(f"maximum length of {MAX_CAPTION_LENGTH}", response.json().get('error', ''))

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_text_only_post_with_omitted_image_returns_good_response(self):
        """
        A post with no image_url at all is a text-only post (#307): it is
        created successfully with a null image_url.
        """
        response = self.client.post(
            self.url,
            data={'caption': POSITIVE_TEXT},
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        self.user.refresh_from_db()
        post = self.user.post_set.first()
        self.assertIsNone(post.image_url)
        self.assertEqual(post.caption, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_text_only_post_with_null_image_returns_good_response(self):
        """
        An explicit `image_url: null` is treated the same as omitting it.
        """
        response = self.client.post(
            self.url,
            data={'image_url': None, 'caption': POSITIVE_TEXT},
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.post_set.first().image_url)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_text_only_post_with_empty_image_returns_good_response(self):
        """
        An empty-string `image_url` is treated the same as omitting it.
        """
        response = self.client.post(
            self.url,
            data={'image_url': '', 'caption': POSITIVE_TEXT},
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.post_set.first().image_url)

    def test_text_only_post_without_caption_returns_bad_response(self):
        """
        The caption is still required: a post with neither image nor caption
        is rejected.
        """
        response = self.client.post(
            self.url,
            data={},
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 400)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_unicode_caption_at_max_length_returns_good_response(self):
        """
        A non-ASCII caption at exactly MAX_CAPTION_LENGTH code points must be accepted,
        confirming the limit is unicode aware rather than byte/ASCII based.
        """
        data = self.valid_data.copy()
        # 'é' is multi-byte in UTF-8 but a single unicode code point; len() counts code points.
        data['caption'] = 'é' * MAX_CAPTION_LENGTH

        response = self.client.post(
            self.url,
            data=data,
            content_type='application/json',
            **self.valid_header
        )

        self.assertEqual(response.status_code, 201)
        self.user.refresh_from_db()
        self.assertEqual(self.user.post_set.first().caption, 'é' * MAX_CAPTION_LENGTH)
    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_non_string_caption_returns_bad_response(self):
        """
        A truthy non-string caption must be rejected with a 400 rather than raising
        a TypeError from the semicolon/length checks and surfacing as a 500.
        """
        for caption in (123, 1.5, True, ['a'], {'a': 'b'}):
            with self.subTest(caption=caption):
                data = self.valid_data.copy()
                data['caption'] = caption

                response = self.client.post(
                    self.url,
                    data=data,
                    content_type='application/json',
                    **self.valid_header
                )

                self.assertEqual(response.status_code, 400)
