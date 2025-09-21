from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from ..views import login_user, like_post, get_user_with_username, unlike_post
from ..constants import MAX_BEFORE_HIDING_POST
from .test_constants import ip, false, FAIL, SUCCESS, UserFields

invalid_session_management_token = '?'
invalid_post_identifier = '?'


class UnlikePostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Need two more than max since the first user will be the default user who makes the post
        # and you need one more than max before a post is hidden
        super().make_post_with_users(MAX_BEFORE_HIDING_POST + 2)

        other_session_management_tokens = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])
        other_local_usernames = self.users.get(UserFields.USERNAME, [])
        other_local_passwords = self.users.get(UserFields.PASSWORD, [])

        self.other_session_management_token = other_session_management_tokens[1]
        self.other_local_username = other_local_usernames[1]
        self.other_local_password = other_local_passwords[1]

        # Create an instance of a POST request.
        self.like_post_request = self.factory.post("/user_system/like_post")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.like_post_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.like_post_request)
        self.like_post_request.session.save()

        # Login one of the users to do the liking and unliking
        response = login_user(self.login_user_request, self.other_local_username, self.other_local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

        # Like a post
        response = like_post(self.like_post_request, self.other_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        # Create an instance of a POST request.
        self.unlike_post_request = self.factory.post("/user_system/unlike_post")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.unlike_post_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.unlike_post_request)
        self.unlike_post_request.session.save()

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view unlike_post
        response = unlike_post(self.unlike_post_request, invalid_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view unlike_post
        response = unlike_post(self.unlike_post_request, self.other_session_management_token, invalid_post_identifier)
        self.assertEqual(response.status_code, FAIL)

    def test_unlike_own_post_returns_bad_response(self):
        # Test view unlike_post
        response = unlike_post(self.unlike_post_request, self.session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_unlike_post_twice_returns_bad_response(self):
        # Test view unlike_post
        response = unlike_post(self.unlike_post_request, self.other_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        self.assertEqual(post.postlike_set.count(), 0)

        response = unlike_post(self.unlike_post_request, self.other_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_unlike_post_returns_good_response_and_removes_like_post_from_user(self):
        # Test view unlike_post
        response = unlike_post(self.unlike_post_request, self.other_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        self.assertEqual(post.postlike_set.count(), 0)
