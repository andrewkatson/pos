from .test_constants import false, FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_content
from ..views import get_users_matching_fragment

invalid_session_management_token = '?'
username_fragment = 'aaa'
other_username_fragment = 'baa'
invalid_username_fragment = '?'


class GetUsersMatchingFragmentTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().login_user_setup(false)

        # Register a couple more users
        super().register_user_with_name(f'{username_fragment}_something', self.users)
        super().register_user_with_name(f'{username_fragment}_another', self.users)

        # Create an instance of a GET request.
        self.get_users_matching_fragment_request = self.make_get_request_obj('get_users_matching_fragment',
                                                                             self.local_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        response = get_users_matching_fragment(self.get_users_matching_fragment_request,
                                               invalid_session_management_token, username_fragment)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_username_fragment_returns_bad_response(self):
        response = get_users_matching_fragment(self.get_users_matching_fragment_request, self.session_management_token,
                                               invalid_username_fragment)
        self.assertEqual(response.status_code, FAIL)

    def test_none_matching_fragment_returns_empty_response(self):
        response = get_users_matching_fragment(self.get_users_matching_fragment_request, self.session_management_token,
                                               other_username_fragment)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        self.assertEqual(len(responses), 0)

    def test_some_match_fragment_returns_those_users(self):
        response = get_users_matching_fragment(self.get_users_matching_fragment_request, self.session_management_token,
                                               username_fragment)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        self.assertEqual(len(responses), 2)
