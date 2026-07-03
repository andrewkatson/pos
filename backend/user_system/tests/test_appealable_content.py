import uuid
from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from .test_constants import UserFields
from ..classifiers.classifier_constants import POSITIVE_IMAGE_FILENAME, POSITIVE_TEXT
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import Fields, HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_NONE
from ..models import Comment, Post
from ..views import get_user_with_username

ALLOWED = ClassificationResult(allowed=True)
APPEALABLE = ClassificationResult(allowed=False, appealable=True)
FINAL_REJECT = ClassificationResult(allowed=False, appealable=False)
APPEALABLE_HATE = ClassificationResult(allowed=False, appealable=True, reason_code='hate_speech')
FINAL_REJECT_GORE = ClassificationResult(allowed=False, appealable=False, reason_code='gore')

TEXT = 'user_system.views.text_classifier_class.is_text_positive'
IMAGE = 'user_system.views.image_classifier_class.is_image_positive'


class MakePostAppealableTests(PositiveOnlySocialTestCase):
    """make_post posts-but-hides appealable rejections; final rejections 400."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = get_user_with_username(self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.url = reverse('make_post')
        self.data = {
            'image_url': f'https://test-bucket.s3.amazonaws.com/{self.user.id}/{POSITIVE_IMAGE_FILENAME}',
            'caption': POSITIVE_TEXT,
        }

    def _post(self):
        return self.client.post(self.url, data=self.data, content_type='application/json', **self.header)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_allowed_post_is_visible(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn(Fields.hidden, response.json())
        post = self.user.post_set.get()
        self.assertFalse(post.hidden)
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_NONE)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_caption_is_posted_but_hidden(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body[Fields.hidden])
        self.assertEqual(body[Fields.hidden_reason], HIDDEN_REASON_CLASSIFIER)
        self.assertIn('appeal', body['message'].lower())

        post = self.user.post_set.get()
        self.assertTrue(post.hidden)
        self.assertEqual(post.hidden_reason, HIDDEN_REASON_CLASSIFIER)

    @patch(IMAGE, return_value=APPEALABLE)
    @patch(TEXT, return_value=ALLOWED)
    def test_appealable_image_is_posted_but_hidden(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()[Fields.hidden])
        self.assertTrue(self.user.post_set.get().hidden)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_caption_rejection_is_blocked(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertIn('Text is not positive', response.json().get('error', ''))
        self.assertEqual(self.user.post_set.count(), 0)

    @patch(IMAGE, return_value=FINAL_REJECT)
    @patch(TEXT, return_value=ALLOWED)
    def test_final_image_rejection_is_blocked(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertIn('Image is not positive', response.json().get('error', ''))
        self.assertEqual(self.user.post_set.count(), 0)

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT_GORE)
    def test_final_caption_rejection_includes_reason_and_no_appeal(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn('may contain gore', body['error'])
        self.assertIn('cannot be appealed', body['error'])
        self.assertEqual(body[Fields.reason_code], 'gore')
        self.assertFalse(body[Fields.appealable])

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_rejection_without_cited_rule_uses_generic_reason(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn('did not meet our positivity guidelines', body['error'])
        self.assertEqual(body[Fields.reason_code], 'guidelines')

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE_HATE)
    def test_appealable_caption_message_includes_reason(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('your caption may contain hate speech', body['message'])
        self.assertIn('appeal', body['message'].lower())
        self.assertEqual(body[Fields.reason_code], 'hate_speech')
        self.assertTrue(body[Fields.appealable])

    @patch(IMAGE, return_value=APPEALABLE_HATE)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_caption_and_image_message_mentions_both(self, _text, _image):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('your caption did not meet our positivity guidelines', body['message'])
        self.assertIn('your image may contain hate speech', body['message'])
        # Text precedence for the machine-readable code.
        self.assertEqual(body[Fields.reason_code], 'guidelines')

    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_caption_rejection_wins_over_allowed_image(self, _text, _image):
        """
        Text and image are classified concurrently, so the image check may run,
        but a final text rejection still blocks the post with the text error.
        """
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertIn('Text is not positive', response.json().get('error', ''))
        self.assertEqual(self.user.post_set.count(), 0)

    @patch(IMAGE, return_value=FINAL_REJECT)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_caption_with_final_image_is_blocked(self, _text, _image):
        """One final rejection makes the whole post final, even if text is appealable."""
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.user.post_set.count(), 0)

    @patch('user_system.views.delete_image')
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_caption_rejection_deletes_uploaded_image(self, _text, _image, mock_delete):
        self._post()
        mock_delete.assert_called_once_with(self.data['image_url'])

    @patch('user_system.views.delete_image')
    @patch(IMAGE, return_value=FINAL_REJECT)
    @patch(TEXT, return_value=ALLOWED)
    def test_final_image_rejection_deletes_uploaded_image(self, _text, _image, mock_delete):
        self._post()
        mock_delete.assert_called_once_with(self.data['image_url'])

    @patch('user_system.views.delete_image')
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_post_keeps_uploaded_image(self, _text, _image, mock_delete):
        """An appealable post is created hidden, so its image must be kept."""
        self._post()
        mock_delete.assert_not_called()

    @patch('user_system.views.delete_image')
    @patch(IMAGE, return_value=ALLOWED)
    @patch(TEXT, return_value=ALLOWED)
    def test_allowed_post_keeps_uploaded_image(self, _text, _image, mock_delete):
        self._post()
        mock_delete.assert_not_called()


class CommentAppealableTests(PositiveOnlySocialTestCase):
    """comment_on_post and reply_to_comment_thread hide appealable rejections."""

    def setUp(self):
        super().setUp()
        # User 0 makes a post (classifiers patched via TESTING in the helper).
        self.make_post_with_users(num=2)
        self.commenter_token = self.users[UserFields.TOKEN][1]
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.commenter_token}'}

    def _comment(self, text=POSITIVE_TEXT):
        url = reverse('comment_on_post', kwargs={'post_identifier': str(self.post_identifier)})
        return self.client.post(url, data={'comment_text': text}, content_type='application/json', **self.header)

    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_comment_is_posted_but_hidden(self, _text):
        response = self._comment()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body[Fields.hidden])
        self.assertEqual(body[Fields.hidden_reason], HIDDEN_REASON_CLASSIFIER)

        comment = Comment.objects.get(comment_identifier=body[Fields.comment_identifier])
        self.assertTrue(comment.hidden)
        self.assertEqual(comment.hidden_reason, HIDDEN_REASON_CLASSIFIER)

    @patch(TEXT, return_value=FINAL_REJECT)
    def test_final_comment_rejection_is_blocked(self, _text):
        response = self._comment()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    @patch(TEXT, return_value=FINAL_REJECT_GORE)
    def test_final_comment_rejection_includes_reason_and_no_appeal(self, _text):
        response = self._comment()
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn('your comment may contain gore', body['error'])
        self.assertIn('cannot be appealed', body['error'])
        self.assertEqual(body[Fields.reason_code], 'gore')
        self.assertFalse(body[Fields.appealable])

    @patch(TEXT, return_value=APPEALABLE_HATE)
    def test_appealable_comment_message_includes_reason(self, _text):
        response = self._comment()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('it may contain hate speech', body['message'])
        self.assertIn('appeal', body['message'].lower())
        self.assertEqual(body[Fields.reason_code], 'hate_speech')
        self.assertTrue(body[Fields.appealable])

    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_reply_is_posted_but_hidden(self, _text):
        # First create a visible thread to reply to.
        with patch(TEXT, return_value=ALLOWED):
            thread_id = self._comment().json()[Fields.comment_thread_identifier]

        url = reverse('reply_to_comment_thread', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(thread_id),
        })
        response = self.client.post(url, data={'comment_text': POSITIVE_TEXT},
                                    content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body[Fields.hidden])

        comment = Comment.objects.get(comment_identifier=body[Fields.comment_identifier])
        self.assertTrue(comment.hidden)
        self.assertEqual(comment.hidden_reason, HIDDEN_REASON_CLASSIFIER)


class CommentOnHiddenPostVisibilityTests(PositiveOnlySocialTestCase):
    """A hidden post is visible only to its author, so others cannot comment on
    or reply to it via a leaked/guessed UUID."""

    def setUp(self):
        super().setUp()
        self.make_post_with_users(num=2)
        self.author_token = self.session_management_token
        self.other_token = self.users[UserFields.TOKEN][1]
        # Hide the post as if the classifier flagged it.
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()

    def _comment(self, token, text=POSITIVE_TEXT):
        url = reverse('comment_on_post', kwargs={'post_identifier': str(self.post_identifier)})
        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        return self.client.post(url, data={'comment_text': text}, content_type='application/json', **header)

    @patch(TEXT, return_value=ALLOWED)
    def test_other_user_cannot_comment_on_hidden_post(self, _text):
        response = self._comment(self.other_token)
        self.assertEqual(response.status_code, 400)
        self.assertIn('No post with that identifier', response.json().get('error', ''))
        self.assertEqual(Comment.objects.count(), 0)

    @patch(TEXT, return_value=ALLOWED)
    def test_author_can_comment_on_own_hidden_post(self, _text):
        response = self._comment(self.author_token)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Comment.objects.count(), 1)

    @patch(TEXT, return_value=ALLOWED)
    def test_other_user_cannot_reply_on_hidden_post(self, _text):
        # The author creates a thread on their own hidden post.
        thread_id = self._comment(self.author_token).json()[Fields.comment_thread_identifier]

        url = reverse('reply_to_comment_thread', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(thread_id),
        })
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.other_token}'}
        response = self.client.post(url, data={'comment_text': POSITIVE_TEXT},
                                    content_type='application/json', **header)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Comment thread not found', response.json().get('error', ''))

    @patch(TEXT, return_value=ALLOWED)
    def test_classifier_not_run_for_hidden_post_comment(self, mock_text):
        """The post is visibility-checked before the classifier, so an
        unviewable target cannot trigger (billable) classifier calls."""
        self._comment(self.other_token)
        mock_text.assert_not_called()

    @patch(TEXT, return_value=ALLOWED)
    def test_classifier_not_run_for_missing_post_comment(self, mock_text):
        url = reverse('comment_on_post', kwargs={'post_identifier': str(uuid.uuid4())})
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.author_token}'}
        self.client.post(url, data={'comment_text': POSITIVE_TEXT},
                         content_type='application/json', **header)
        mock_text.assert_not_called()

    @patch(TEXT, return_value=ALLOWED)
    def test_classifier_not_run_for_hidden_post_reply(self, mock_text):
        # The author creates a thread on their own hidden post (this call does
        # run the classifier); reset, then a non-author reply must not.
        thread_id = self._comment(self.author_token).json()[Fields.comment_thread_identifier]
        mock_text.reset_mock()

        url = reverse('reply_to_comment_thread', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(thread_id),
        })
        header = {'HTTP_AUTHORIZATION': f'Bearer {self.other_token}'}
        self.client.post(url, data={'comment_text': POSITIVE_TEXT},
                         content_type='application/json', **header)
        mock_text.assert_not_called()
