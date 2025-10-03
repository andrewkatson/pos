from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_fields
from ..classifiers.classifier_constants import POSITIVE_TEXT, NEGATIVE_TEXT
from ..constants import Fields
from ..views import delete_comment, get_user_with_username, comment_on_post
from .test_constants import FAIL, SUCCESS
from ..classifiers import text_classifier_fake

invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'
invalid_comment_text = 'DROP TABLE;'


class DeleteCommentTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        self.post, self.post_identifier = super().make_post_and_login_user()

        # Create an instance of a POST request.
        self.comment_on_post_request = self.make_post_request_obj('comment_on_post', self.local_username)

        # Make a comment
        response = comment_on_post(self.comment_on_post_request, self.session_management_token,
                                   str(self.post_identifier), POSITIVE_TEXT, text_classifier_fake)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        comment_thread = post.commentthread_set.first()
        self.assertEqual(comment_thread.comment_set.count(), 1)

        fields = get_response_fields(response)
        self.comment_thread_identifier = fields[Fields.comment_thread_identifier]
        self.comment_identifier = fields[Fields.comment_identifier]

        # Create an instance of a DELETE request.
        self.delete_comment_request = self.make_delete_request_obj('delete_comment', self.local_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view delete_comment
        response = delete_comment(self.delete_comment_request, invalid_session_management_token,
                                  str(self.post_identifier), str(self.comment_thread_identifier),
                                  str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view delete_comment
        response = delete_comment(self.delete_comment_request, self.session_management_token, invalid_post_identifier,
                                  str(self.comment_thread_identifier), str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        # Test view delete_comment
        response = delete_comment(self.delete_comment_request, self.session_management_token, str(self.post_identifier),
                                  invalid_comment_thread_identifier, str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_comment_identifier_returns_bad_response(self):
        # Test view delete_comment
        response = delete_comment(self.delete_comment_request, self.session_management_token, str(self.post_identifier),
                                  str(self.comment_thread_identifier), invalid_comment_identifier)
        self.assertEqual(response.status_code, FAIL)

    def test_delete_comment_returns_good_response_and_deletes_comment(self):
        # Test view delete_comment
        response = delete_comment(self.delete_comment_request, self.session_management_token,
                                  str(self.post_identifier), str(self.comment_thread_identifier),
                                  str(self.comment_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        comment_thread = post.commentthread_set.first()
        self.assertEqual(comment_thread.comment_set.count(), 0)
