from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_fields
from ..classifiers.classifier_constants import POSITIVE_TEXT
from ..constants import Fields, MAX_BEFORE_HIDING_COMMENT
from ..views import report_comment, get_user_with_username, comment_on_post, login_user
from .test_constants import FAIL, SUCCESS, UserFields, false, ip
from ..classifiers import text_classifier_fake

invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_reason = 'DROP TABLE;'
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'


class CommentOnPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Need 2 more than max because a commenter cannot report their own comment and you need
        # one additional to get over the max before a comment is hidden.
        super().make_post_with_users(MAX_BEFORE_HIDING_COMMENT + 2)

        # Create an instance of a POST request.
        self.comment_on_post_request = self.factory.post("/user_system/comment_on_post")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.comment_on_post_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.comment_on_post_request)
        self.comment_on_post_request.session.save()

        # Comment on the post so we can report it
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

        # Create an instance of a POST request.
        self.report_comment_request = self.make_post_request_obj('report_comment', self.local_username)

        self.reason = "This is a negative comment"

        self.other_session_management_tokens = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])
        self.other_local_usernames = self.users.get(UserFields.USERNAME, [])
        self.other_local_passwords = self.users.get(UserFields.PASSWORD, [])

        self.reporter_session_management_token = self.other_session_management_tokens[2]
        self.reporter_local_username = self.other_local_usernames[2]
        self.reporter_local_password = self.other_local_passwords[2]

        # Login one of the users to do the reporting
        response = login_user(self.login_user_request, self.reporter_local_username, self.reporter_local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view report_comment
        response = report_comment(self.report_comment_request, invalid_session_management_token,
                                  str(self.post_identifier), str(self.comment_thread_identifier),
                                  str(self.comment_identifier), self.reason)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view report_comment
        response = report_comment(self.report_comment_request, self.reporter_session_management_token, invalid_post_identifier
                                  , str(self.comment_thread_identifier), str(self.comment_identifier), self.reason)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        # Test view report_comment
        response = report_comment(self.report_comment_request, self.reporter_session_management_token, invalid_post_identifier,
                                  str(self.comment_thread_identifier), str(self.comment_identifier), self.reason)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_comment_identifier_returns_bad_response(self):
        # Test view report_comment
        response = report_comment(self.report_comment_request, self.reporter_session_management_token, invalid_post_identifier,
                                  str(self.comment_thread_identifier), str(self.comment_identifier), self.reason)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_reason_returns_bad_response(self):
        # Test view report_comment
        response = report_comment(self.report_comment_request, self.reporter_session_management_token, invalid_post_identifier,
                                  str(self.comment_thread_identifier), str(self.comment_identifier), self.reason)
        self.assertEqual(response.status_code, FAIL)

    def test_report_comment_returns_good_response_and_reports_comment(self):
        # Test view report_comment
        response = report_comment(self.report_comment_request, self.reporter_session_management_token,
                                  str(self.post_identifier), str(self.comment_thread_identifier),
                                  str(self.comment_identifier), self.reason)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        comment_thread = post.commentthread_set.first()
        comment = comment_thread.comment_set.first()
        self.assertFalse(comment.hidden)

    def test_report_comment_more_than_max_returns_good_response_and_hides_comment(self):
        # Test view report_comment
        for i in range(1, len(self.other_session_management_tokens)):
            session_management_token = self.other_session_management_tokens[i]
            response = report_comment(self.report_comment_request, session_management_token,
                                      str(self.post_identifier), str(self.comment_thread_identifier),
                                      str(self.comment_identifier), self.reason)
            self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        comment_thread = post.commentthread_set.first()
        comment = comment_thread.comment_set.first()
        self.assertTrue(comment.hidden)
