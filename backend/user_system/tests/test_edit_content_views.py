"""Editing a post caption or a comment (issue #462).

Both edits are re-judged before they replace anything, and any rejection
leaves the approved original exactly as it was.
"""
from unittest.mock import patch
import os

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from .. import views
from ..classifiers.classifier_constants import NEGATIVE_TEXT, POSITIVE_TEXT
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import Fields, MAX_CAPTION_LENGTH, MAX_COMMENT_LENGTH, HIDDEN_REASON_CLASSIFIER, \
    HIDDEN_REASON_PENDING_CLASSIFICATION, HIDDEN_REASON_REPORTS, REVIEW_STATUS_CLEARED, \
    REVIEW_STATUS_DISMISSED, REVIEW_STATUS_ESCALATED, REVIEW_STATUS_HIDDEN, REVIEW_STATUS_PENDING
from ..models import Comment, ModerationReview, Post

profane_caption = 'what a shit day'
edited_text = 'positive and edited #sunny'


def _provider_failure(*_args, **_kwargs):
    return ClassificationResult(allowed=False, provider_failure=True)


def _allowed_by(tier):
    def classify(*_args, **_kwargs):
        return ClassificationResult(allowed=True, consulted=[tier], decided_by=tier)
    return classify


ALL_TIERS = ['gemma', 'gemini', 'openai', 'claude']


class EditPostTests(PositiveOnlySocialTestCase):

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def setUp(self):
        super().setUp()
        self.post, self.post_identifier = super().make_post_and_login_user()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('edit_post', kwargs={'post_identifier': str(self.post_identifier)})
        self.post.refresh_from_db()
        self.assertFalse(self.post.hidden)

    def _edit(self, caption, header=None):
        return self.client.post(self.url, data={Fields.caption: caption},
                                content_type='application/json', **(header or self.valid_header))

    def test_requires_a_session(self):
        response = self._edit(edited_text, {'HTTP_AUTHORIZATION': 'Bearer ?'})
        self.assertEqual(response.status_code, 401)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_edit_replaces_caption_marks_edited_and_retags(self):
        response = self._edit(edited_text)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[Fields.caption], edited_text)
        self.assertIsNotNone(body[Fields.edited_time])
        self.assertEqual(body[Fields.tags], ['sunny'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, edited_text)
        self.assertIsNotNone(self.post.edited_time)
        self.assertFalse(self.post.hidden)
        self.assertEqual([t.name for t in self.post.tags.all()], ['sunny'])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_listings_report_edited_time(self):
        # Lists carry it too, so a client holding a locally saved caption can
        # tell when a refreshed row is newer (issue #462).
        list_url = reverse('get_posts_for_user', kwargs={'username': self.local_username, 'batch': 0})
        self.assertIsNone(self.client.get(list_url, **self.valid_header).json()[0][Fields.edited_time])

        self._edit(edited_text)

        self.assertIsNotNone(self.client.get(list_url, **self.valid_header).json()[0][Fields.edited_time])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_post_details_report_edited_time(self):
        details_url = reverse('get_post_details', kwargs={'post_identifier': str(self.post_identifier)})
        before = self.client.get(details_url, **self.valid_header).json()
        self.assertIsNone(before[Fields.edited_time])

        self._edit(edited_text)

        after = self.client.get(details_url, **self.valid_header).json()
        self.assertEqual(after[Fields.caption], edited_text)
        self.assertIsNotNone(after[Fields.edited_time])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_unchanged_caption_is_not_an_edit(self):
        with patch.object(views.text_classifier_class, 'is_text_positive') as classifier:
            response = self._edit(self.post.caption)

        self.assertEqual(response.status_code, 200)
        classifier.assert_not_called()
        self.post.refresh_from_db()
        self.assertIsNone(self.post.edited_time)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_rejected_caption_keeps_the_original(self):
        original = self.post.caption

        response = self._edit(NEGATIVE_TEXT)

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("not saved", body['error'])
        self.assertFalse(body[Fields.appealable])
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, original)
        self.assertIsNone(self.post.edited_time)
        self.assertFalse(self.post.hidden)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_prefiltered_caption_is_refused_without_the_cascade(self):
        with patch.object(views.text_classifier_class, 'is_text_positive') as classifier:
            response = self._edit(profane_caption)

        self.assertEqual(response.status_code, 400)
        classifier.assert_not_called()
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)

    def test_provider_failure_keeps_the_original(self):
        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=_provider_failure):
            response = self._edit(edited_text)

        self.assertEqual(response.status_code, 503)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_cannot_edit_another_users_post(self):
        other = self.make_user_with_prefix()
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other[Fields.session_management_token]}'}

        response = self._edit(edited_text, other_header)

        self.assertEqual(response.status_code, 400)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_invalid_and_overlong_captions_are_rejected(self):
        for caption in ('', None, 'semi;colon', 'p' * (MAX_CAPTION_LENGTH + 1)):
            with self.subTest(caption=caption):
                self.assertEqual(self._edit(caption).status_code, 400)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_hidden_posts_cannot_be_edited(self):
        for reason in (HIDDEN_REASON_PENDING_CLASSIFICATION, HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_REPORTS):
            with self.subTest(reason=reason):
                Post.objects.filter(pk=self.post.pk).update(hidden=True, hidden_reason=reason)
                self.assertEqual(self._edit(edited_text).status_code, 409)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_open_report_review_blocks_edits(self):
        review = ModerationReview.objects.create(post=self.post, status=REVIEW_STATUS_PENDING)
        self.assertEqual(self._edit(edited_text).status_code, 409)

        review.status = REVIEW_STATUS_ESCALATED
        review.save()
        self.assertEqual(self._edit(edited_text).status_code, 409)

        # Cleared content is live again and nobody is looking at it.
        review.status = REVIEW_STATUS_CLEARED
        review.save()
        self.assertEqual(self._edit(edited_text).status_code, 200)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_decided_report_review_blocks_caption_edits(self):
        # A moderator's decision is final for the text it was made about, so
        # new text must not inherit it (a dismissal makes the content immune
        # to further report review).
        for status in (REVIEW_STATUS_DISMISSED, REVIEW_STATUS_HIDDEN):
            with self.subTest(status=status):
                ModerationReview.objects.filter(post=self.post).delete()
                ModerationReview.objects.create(post=self.post, status=status)
                self.assertEqual(self._edit(edited_text).status_code, 409)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)
        # The decision itself is left alone, for the audit trail.
        self.assertEqual(ModerationReview.objects.get(post=self.post).status, REVIEW_STATUS_HIDDEN)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_edit_keeps_the_image_judges_in_the_model_chain(self):
        # The chain covers the image too, which the edit leaves alone, so the
        # caption's judge is folded in rather than replacing the record.
        Post.objects.filter(pk=self.post.pk).update(
            classification_models_tried=['gemma'], classification_model_chain=['gemma'])

        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=_allowed_by('gemini')), \
                patch.object(views, 'get_available_apis', return_value=ALL_TIERS):
            self.assertEqual(self._edit(edited_text).status_code, 200)

        self.post.refresh_from_db()
        self.assertEqual(self.post.classification_models_tried, ['gemma', 'gemini'])
        self.assertEqual(self.post.classification_model_chain, ['gemma', 'gemini'])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_report_review_opened_during_classification_refuses_the_edit(self):
        real = views.text_classifier_class.is_text_positive

        def classify_then_report(text, *args, **kwargs):
            ModerationReview.objects.create(post=self.post, status=REVIEW_STATUS_PENDING)
            return real(text, *args, **kwargs)

        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=classify_then_report):
            response = self._edit(edited_text)

        self.assertEqual(response.status_code, 409)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_hidden_during_classification_refuses_the_edit(self):
        real = views.text_classifier_class.is_text_positive

        def classify_then_hide(text, *args, **kwargs):
            Post.objects.filter(pk=self.post.pk).update(hidden=True, hidden_reason=HIDDEN_REASON_REPORTS)
            return real(text, *args, **kwargs)

        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=classify_then_hide):
            response = self._edit(edited_text)

        self.assertEqual(response.status_code, 409)
        self.post.refresh_from_db()
        self.assertEqual(self.post.caption, POSITIVE_TEXT)


class EditCommentTests(PositiveOnlySocialTestCase):

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def setUp(self):
        super().setUp()
        self.post, self.post_identifier = super().make_post_and_login_user()
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        created = self._comment_on_post(self.session_management_token, self.post_identifier)
        self.thread_identifier = created[Fields.comment_thread_identifier]
        self.comment_identifier = created[Fields.comment_identifier]
        self.comment = Comment.objects.get(comment_identifier=self.comment_identifier)
        self.url = self._url(self.comment_identifier)

    def _url(self, comment_identifier, thread_identifier=None):
        return reverse('edit_comment', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(thread_identifier or self.thread_identifier),
            'comment_identifier': str(comment_identifier),
        })

    def _edit(self, text, formatting=None, header=None, url=None):
        data = {Fields.comment_text: text}
        if formatting is not None:
            data[Fields.body_formatting] = formatting
        return self.client.post(url or self.url, data=data, content_type='application/json',
                                **(header or self.valid_header))

    def test_requires_a_session(self):
        response = self._edit(edited_text, header={'HTTP_AUTHORIZATION': 'Bearer ?'})
        self.assertEqual(response.status_code, 401)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_edit_replaces_body_and_formatting(self):
        formatting = [{'start': 0, 'end': 8, 'bold': True}]

        response = self._edit(edited_text, formatting)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[Fields.body], edited_text)
        self.assertEqual(body[Fields.body_formatting][0]['start'], 0)
        self.assertIsNotNone(body[Fields.edited_time])
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, edited_text)
        self.assertIsNotNone(self.comment.body_formatting)
        self.assertIsNotNone(self.comment.edited_time)
        self.assertFalse(self.comment.hidden)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_replies_can_be_edited(self):
        reply = self._reply_to_comment_thread(self.session_management_token, self.post_identifier,
                                              self.thread_identifier)

        response = self._edit(edited_text, url=self._url(reply[Fields.comment_identifier]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.get(comment_identifier=reply[Fields.comment_identifier]).body, edited_text)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_thread_listing_reports_edited_time(self):
        list_url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.thread_identifier), 'batch': 0})
        self.assertIsNone(self.client.get(list_url, **self.valid_header).json()[0][Fields.edited_time])

        self._edit(edited_text)

        listed = self.client.get(list_url, **self.valid_header).json()[0]
        self.assertEqual(listed[Fields.body], edited_text)
        self.assertIsNotNone(listed[Fields.edited_time])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_formatting_only_change_skips_the_classifier(self):
        with patch.object(views.text_classifier_class, 'is_text_positive') as classifier:
            response = self._edit(self.comment.body, [{'start': 0, 'end': 3, 'italic': True}])

        self.assertEqual(response.status_code, 200)
        classifier.assert_not_called()
        self.comment.refresh_from_db()
        self.assertIsNotNone(self.comment.body_formatting)
        self.assertIsNotNone(self.comment.edited_time)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_unchanged_comment_is_not_an_edit(self):
        response = self._edit(self.comment.body)

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertIsNone(self.comment.edited_time)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_rejected_text_keeps_the_original_visible(self):
        response = self._edit(NEGATIVE_TEXT)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()[Fields.appealable])
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)
        self.assertFalse(self.comment.hidden)
        self.assertIsNone(self.comment.edited_time)

    def test_provider_failure_keeps_the_original(self):
        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=_provider_failure):
            response = self._edit(edited_text)

        self.assertEqual(response.status_code, 503)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_cannot_edit_someone_elses_comment(self):
        other = self.make_user_with_prefix()
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other[Fields.session_management_token]}'}

        response = self._edit(edited_text, header=other_header)

        # Answered like a missing comment, so whose comment it is never leaks.
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "Comment not found")
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_invalid_text_and_formatting_are_rejected(self):
        for text in ('', None, 'semi;colon', 'p' * (MAX_COMMENT_LENGTH + 1)):
            with self.subTest(text=text):
                self.assertEqual(self._edit(text).status_code, 400)
        # A span past the end of the new text.
        self.assertEqual(self._edit('short', [{'start': 0, 'end': 50, 'bold': True}]).status_code, 400)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_locked_comments_freeze_existing_ones(self):
        Post.objects.filter(pk=self.post.pk).update(comments_disabled=True)

        self.assertEqual(self._edit(edited_text).status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_lock_during_classification_refuses_the_edit(self):
        real = views.text_classifier_class.is_text_positive

        def classify_then_lock(text, *args, **kwargs):
            Post.objects.filter(pk=self.post.pk).update(comments_disabled=True)
            return real(text, *args, **kwargs)

        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=classify_then_lock):
            response = self._edit(edited_text)

        self.assertEqual(response.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_hidden_comment_cannot_be_edited(self):
        Comment.objects.filter(pk=self.comment.pk).update(hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)

        self.assertEqual(self._edit(edited_text).status_code, 409)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_comment_on_hidden_post_cannot_be_edited(self):
        # The post's author still sees their own hidden post, so check with a
        # commenter who is not its author.
        other_token = self.make_user_with_prefix()[Fields.session_management_token]
        created = self._comment_on_post(other_token, self.post_identifier)
        Post.objects.filter(pk=self.post.pk).update(hidden=True, hidden_reason=HIDDEN_REASON_REPORTS)

        response = self._edit(edited_text, header={'HTTP_AUTHORIZATION': f'Bearer {other_token}'},
                              url=self._url(created[Fields.comment_identifier],
                                            created[Fields.comment_thread_identifier]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.get(comment_identifier=created[Fields.comment_identifier]).body,
                         POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_open_report_review_blocks_edits(self):
        ModerationReview.objects.create(comment=self.comment, status=REVIEW_STATUS_ESCALATED)

        self.assertEqual(self._edit(edited_text).status_code, 409)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_edited_text_starts_a_fresh_model_chain(self):
        # The comment is text only, so new text is wholly new content.
        Comment.objects.filter(pk=self.comment.pk).update(
            classification_models_tried=['gemma', 'gemini'], classification_model_chain=['gemma'])

        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=_allowed_by('openai')):
            self.assertEqual(self._edit(edited_text).status_code, 200)

        self.comment.refresh_from_db()
        self.assertEqual(self.comment.classification_models_tried, ['openai'])
        self.assertEqual(self.comment.classification_model_chain, ['openai'])

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_decided_report_review_blocks_text_edits_but_not_formatting(self):
        ModerationReview.objects.create(comment=self.comment, status=REVIEW_STATUS_DISMISSED)

        self.assertEqual(self._edit(edited_text).status_code, 409)
        # Restyling the reviewed text keeps what the decision covered.
        self.assertEqual(self._edit(self.comment.body, [{'start': 0, 'end': 3, 'bold': True}]).status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, POSITIVE_TEXT)
        self.assertIsNotNone(self.comment.body_formatting)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_post_hidden_during_classification_refuses_the_edit(self):
        # A commenter who is not the post's author: once the post is hidden
        # they can no longer see it, so their edit must not land.
        other_token = self.make_user_with_prefix()[Fields.session_management_token]
        created = self._comment_on_post(other_token, self.post_identifier)
        real = views.text_classifier_class.is_text_positive

        def classify_then_hide_post(text, *args, **kwargs):
            Post.objects.filter(pk=self.post.pk).update(hidden=True, hidden_reason=HIDDEN_REASON_REPORTS)
            return real(text, *args, **kwargs)

        with patch.object(views.text_classifier_class, 'is_text_positive', side_effect=classify_then_hide_post):
            response = self._edit(edited_text, header={'HTTP_AUTHORIZATION': f'Bearer {other_token}'},
                                  url=self._url(created[Fields.comment_identifier],
                                                created[Fields.comment_thread_identifier]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.get(comment_identifier=created[Fields.comment_identifier]).body,
                         POSITIVE_TEXT)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_edit_keeps_the_audience(self):
        Comment.objects.filter(pk=self.comment.pk).update(audience='friends')

        self.assertEqual(self._edit(edited_text).status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.audience, 'friends')
