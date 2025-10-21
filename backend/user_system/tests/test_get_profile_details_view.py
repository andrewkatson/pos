from ..views import get_profile_details  # Import the view we are testing
from ..constants import Fields
from .test_constants import FAIL, SUCCESS, false
# Import the helper for parsing single JSON object responses
from .test_utils import get_response_fields
from .test_parent_case import PositiveOnlySocialTestCase

# Constants from your example
invalid_session_management_token = '?'
invalid_username_fragment = '?' # Using as a proxy for an invalid username pattern

# New constants for this test case
other_username = 'barbara'
non_existent_username = 'charlie'

class GetProfileDetailsTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Login the main user (the one making the request)
        # This sets self.local_username and self.session_management_token
        super().login_user_setup(false)

        # 2. Register a second user (the one whose profile we will view)
        self.profile_username = other_username
        super().register_user_with_name(self.profile_username, self.users)

        # 3. Create an instance of a GET request.
        self.get_profile_details_request = self.make_get_request_obj('get_profile_details', self.local_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        response = get_profile_details(self.get_profile_details_request,
                                       invalid_session_management_token,
                                       self.profile_username)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_username_pattern_returns_bad_response(self):
        # Assumes the view validates the username pattern
        response = get_profile_details(self.get_profile_details_request,
                                       self.session_management_token,
                                       invalid_username_fragment)
        self.assertEqual(response.status_code, FAIL)

    def test_non_existent_username_returns_bad_response(self):
        # Tests that a validly patterned but non-existent username fails
        response = get_profile_details(self.get_profile_details_request,
                                       self.session_management_token,
                                       non_existent_username)
        self.assertEqual(response.status_code, FAIL)

    def test_valid_request_for_own_profile_returns_correct_details(self):
        # Tests that a user can successfully request their own profile
        response = get_profile_details(self.get_profile_details_request,
                                       self.session_management_token,
                                       self.local_username) # Requesting user's own name
        self.assertEqual(response.status_code, SUCCESS)

        # Assumes get_response_fields parses a single JSON object response
        fields = get_response_fields(response)

        # Check that all default values are correct
        self.assertEqual(fields[Fields.username], self.local_username)
        self.assertEqual(fields[Fields.post_count], 0)
        self.assertEqual(fields[Fields.follower_count], 0)
        self.assertEqual(fields[Fields.following_count], 0)
        self.assertEqual(fields[Fields.is_following], False) # Can't follow self

    def test_valid_request_for_other_user_returns_correct_default_details(self):
        # This is the main "happy path" test for default values.
        response = get_profile_details(self.get_profile_details_request,
                                       self.session_management_token,
                                       self.profile_username) # Other user's name
        self.assertEqual(response.status_code, SUCCESS)

        fields = get_response_fields(response)

        # Check that all default values are correct for the *other user*
        self.assertEqual(fields[Fields.username], self.profile_username)
        self.assertEqual(fields[Fields.post_count], 0)
        self.assertEqual(fields[Fields.follower_count], 0)
        self.assertEqual(fields[Fields.following_count], 0)
        self.assertEqual(fields[Fields.is_following], False) # Not followed yet