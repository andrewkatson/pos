from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from ..views import login_user, unlike_comment, get_user_with_username, like_comment
from .test_constants import ip, false, FAIL, SUCCESS, UserFields

invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'


class UnlikeCommentTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().comment_on_post_with_users()

        other_session_management_tokens = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])
        other_local_usernames = self.users.get(UserFields.USERNAME, [])
        other_local_passwords = self.users.get(UserFields.PASSWORD, [])

        self.liker_session_management_token = other_session_management_tokens[2]
        self.liker_local_username = other_local_usernames[2]
        self.liker_local_password = other_local_passwords[2]

        # Login one of the users to do the liking
        response = login_user(self.login_user_request, self.liker_local_username, self.liker_local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Create an instance of a POST request.
        self.like_comment_request = self.factory.post("/user_system/like_comment")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.like_comment_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.like_comment_request)
        self.like_comment_request.session.save()

        # Like the comment
        response = like_comment(self.like_comment_request, self.liker_session_management_token,
                                str(self.post_identifier), str(self.comment_thread_identifier),
                                str(self.comment_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        comment_thread = post.commentthread_set.first()
        comment = comment_thread.comment_set.first()
        self.assertEqual(comment.commentlike_set.count(), 1)

        # Create an instance of a POST request.
        self.unlike_comment_request = self.factory.post("/user_system/unlike_comment")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.unlike_comment_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.unlike_comment_request)
        self.unlike_comment_request.session.save()

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view unlike_comment
        response = unlike_comment(self.unlike_comment_request, invalid_session_management_token, str(self.post_identifier),
                                str(self.comment_thread_identifier), str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view unlike_comment
        response = unlike_comment(self.unlike_comment_request, self.liker_session_management_token, invalid_post_identifier,
                                str(self.comment_thread_identifier), str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        # Test view unlike_comment
        response = unlike_comment(self.unlike_comment_request, self.liker_session_management_token,
                                str(self.post_identifier), invalid_comment_thread_identifier,
                                str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_comment_identifier_returns_bad_response(self):
        # Test view unlike_comment
        response = unlike_comment(self.unlike_comment_request, self.liker_session_management_token,
                                str(self.post_identifier), str(self.comment_thread_identifier),
                                invalid_comment_identifier)
        self.assertEqual(response.status_code, FAIL)

    def test_unlike_own_comment_returns_bad_response(self):
        # Test view unlike_comment
        response = unlike_comment(self.unlike_comment_request, self.commenter_session_management_token, str(self.post_identifier),
                                str(self.comment_thread_identifier), str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_unlike_comment_twice_returns_bad_response(self):
        # Test view unlike_comment
        response = unlike_comment(self.unlike_comment_request, self.liker_session_management_token,
                                str(self.post_identifier), str(self.comment_thread_identifier),
                                str(self.comment_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        comment_thread = post.commentthread_set.first()
        comment = comment_thread.comment_set.first()
        self.assertEqual(comment.commentlike_set.count(), 0)

        response = unlike_comment(self.unlike_comment_request, self.liker_session_management_token,
                                str(self.post_identifier), str(self.comment_thread_identifier),
                                str(self.comment_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_unlike_comment_returns_good_response_and_unlikes_comment_from_user(self):
        # Test view unlike_comment
        response = unlike_comment(self.unlike_comment_request, self.liker_session_management_token,
                                str(self.post_identifier), str(self.comment_thread_identifier),
                                str(self.comment_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        comment_thread = post.commentthread_set.first()
        comment = comment_thread.comment_set.first()
        self.assertEqual(comment.commentlike_set.count(), 0)
