from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import unfollow_user, follow_user, get_user_with_username
from .test_constants import false, FAIL, SUCCESS

invalid_session_management_token = '?'
non_existent_username = 'iamnotauser'


class UnfollowUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        # Set up the primary user who will do the following.
        self.main_username = 'MainUser12'
        main_user_login_fields, main_user_registration_fields = self.make_user_and_login(self.main_username)
        self.main_session_management_token = main_user_login_fields[Fields.session_management_token]

        # Create a second user to be the target of the follow action.
        self.other_user_username = "OtherUser23"
        other_user_registration_fields =  self.make_user(self.other_user_username)

        # Create a request object for the follow view.
        self.follow_request = self.make_get_request_obj('follow_user', self.main_username)

        # Follow the user
        response = follow_user(self.follow_request, self.main_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 1)
        self.assertEqual(user.following.first().username, self.other_user_username)

        # Create a request object for the unfollow view.
        self.unfollow_request = self.make_get_request_obj('unfollow_user', self.main_username)

    def test_unfollow_user_success(self):
        # Now, unfollow them.
        response = unfollow_user(self.unfollow_request, self.main_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, SUCCESS)

        # The following count should be back to 0.
        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 0)

    def test_unfollow_user_invalid_token_fails(self):
        response = unfollow_user(self.unfollow_request, invalid_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, FAIL)

    def test_unfollow_non_existent_user_fails(self):
        response = unfollow_user(self.unfollow_request, self.main_session_management_token, non_existent_username)
        self.assertEqual(response.status_code, FAIL)

    def test_unfollow_user_not_following_fails(self):
        # Make sure they are really not following anyone.
        response = unfollow_user(self.unfollow_request, self.main_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, SUCCESS)

        # The user is not following anyone.
        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 0)

        # Attempt to unfollow the other user.
        response = unfollow_user(self.unfollow_request, self.main_session_management_token, self.other_user_username)

        self.assertEqual(response.status_code, FAIL)

        # The following count should still be 0.
        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 0)