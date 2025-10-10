from .test_constants import FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_content
from ..constants import Fields
from ..views import get_user_with_username, get_posts_for_followed_users, follow_user

invalid_session_management_token = '?'
invalid_batch = -1


class GetFollowedPostsTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Create a second user to be the target of the follow action.
        self.other_user_username = "OtherUser231"
        other_user_registration_fields, other_user_login_fields, posts = self.make_user_with_posts(
            self.other_user_username, posts_num=15)
        self.other_session_management_token = other_user_login_fields[Fields.session_management_token]

        # Set up the primary user who will do the following.
        self.main_username = 'MainUser2344'
        main_user_login_fields, main_user_registration_fields = self.make_user_and_login(self.main_username)
        self.main_session_management_token = main_user_login_fields[Fields.session_management_token]

        # Create a request object for the follow view.
        self.follow_request = self.make_get_request_obj('follow_user', self.main_username)

        # Follow the user
        response = follow_user(self.follow_request, self.main_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 1)
        self.assertEqual(user.following.first().username, self.other_user_username)

        # Create an instance of a GET request for the new view.
        self.get_posts_for_followed_users_request = self.make_get_request_obj('get_posts_for_followed_users',
                                                                              self.main_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        response = get_posts_for_followed_users(self.get_posts_for_followed_users_request,
                                                invalid_session_management_token, 0)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_batch_returns_bad_response(self):
        response = get_posts_for_followed_users(self.get_posts_for_followed_users_request,
                                                self.main_session_management_token, invalid_batch)
        self.assertEqual(response.status_code, FAIL)

    def test_no_followed_users_returns_empty_list(self):
        response = get_posts_for_followed_users(self.get_posts_for_followed_users_request,
                                                self.other_session_management_token, 0)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)
        self.assertEqual(len(responses), 0)

    def test_first_batch_returns_correct_number_of_posts(self):
        # The first batch (batch=0) should return 10 posts (the default POST_BATCH_SIZE).
        response = get_posts_for_followed_users(self.get_posts_for_followed_users_request,
                                                self.main_session_management_token, 0)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)
        self.assertEqual(len(responses), 10)

    def test_last_batch_returns_correct_number_of_posts(self):
        # We are following a user with 15 posts, so with a batch size of 10,
        # the second batch (batch=1) should contain the remaining 5 posts.
        response = get_posts_for_followed_users(self.get_posts_for_followed_users_request,
                                                self.main_session_management_token, 1)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)
        self.assertEqual(len(responses), 5)

    def test_batch_beyond_max_returns_empty_list(self):
        # With 15 posts total, the last valid batch is 1. Batch 2 should be empty.
        response = get_posts_for_followed_users(self.get_posts_for_followed_users_request,
                                                self.main_session_management_token, 2)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)
        self.assertEqual(len(responses), 0)
