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
    @patch(TEXT, return_value=FINAL_REJECT)
    def test_image_check_skipped_on_final_caption_rejection(self, _text, mock_image):
        """A final text rejection short-circuits before the costly image check."""
        self._post()
        mock_image.assert_not_called()

    @patch(IMAGE, return_value=FINAL_REJECT)
    @patch(TEXT, return_value=APPEALABLE)
    def test_appealable_caption_with_final_image_is_blocked(self, _text, _image):
        """One final rejection makes the whole post final, even if text is appealable."""
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.user.post_set.count(), 0)


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
