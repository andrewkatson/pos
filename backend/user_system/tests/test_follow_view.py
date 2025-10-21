from .test_constants import FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..views import follow_user, get_user_with_username

invalid_session_management_token = '?'
non_existent_username = 'iamnotauser'


class FollowUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        # Set up the primary user who will do the following.
        self.main_username = 'MainUser02'
        main_user_login_fields, main_user_registration_fields = self.make_user_and_login(self.main_username)
        self.main_session_management_token = main_user_login_fields[Fields.session_management_token]

        # Create a second user to be the target of the follow action.
        self.other_user_username = "OtherUser11"
        other_user_registration_fields = self.make_user(self.other_user_username)

        # Create a request object for the follow view.
        self.follow_request = self.make_get_request_obj('follow_user', self.main_username)

    def test_follow_user_success(self):
        response = follow_user(self.follow_request, self.main_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 1)
        self.assertEqual(user.following.first().username, self.other_user_username)

    def test_follow_user_invalid_token_fails(self):
        response = follow_user(self.follow_request, invalid_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, FAIL)

    def test_follow_non_existent_user_fails(self):
        response = follow_user(self.follow_request, self.main_session_management_token, non_existent_username)
        self.assertEqual(response.status_code, FAIL)

    def test_follow_self_fails(self):
        response = follow_user(self.follow_request, self.main_session_management_token, self.main_username)
        self.assertEqual(response.status_code, FAIL)

        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 0)

    def test_follow_already_following_succeeds_without_duplicating(self):
        # First, follow the user.
        response = follow_user(self.follow_request, self.main_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 1)
        self.assertEqual(user.following.first().username, self.other_user_username)

        # Try to follow them again.
        response = follow_user(self.follow_request, self.main_session_management_token, self.other_user_username)
        self.assertEqual(response.status_code, FAIL)

        # The following count should remain 1.
        user = get_user_with_username(self.main_username)
        self.assertEqual(user.following.count(), 1)
