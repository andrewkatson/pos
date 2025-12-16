from django.urls import reverse

from backend.user_system.constants import Fields
from .test_parent_case import PositiveOnlySocialTestCase

# --- Constants ---
invalid_session_management_token = '?'
username_fragment = 'aaa'
other_username_fragment = 'baa'
invalid_username_fragment = '?'


class GetUsersMatchingFragmentTests(PositiveOnlySocialTestCase):

    def test_blocked_by_user_excludes_from_search(self):
        # 1. User 1 (me) blocks User 2 (first_username)
        # Wait, the requirement is "If user A blocks user B then user A can search for user B but user B cannot search for user A"
        # So if I am B (blocked by A), I cannot find A.
        
        # Let's say local_user is A. first_username is B.
        # A blocks B.
        me = self.get_user_by_username(self.local_username)
        user_b = self.get_user_by_username(self.first_username)
        me.blocked.add(user_b)
        
        # A searches B -> Should find
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': self.first_username})
        response = self.client.get(url, **self.valid_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        
        # B searches A -> Should NOT find
        # We need authentication for B
        # self.make_user_with_prefix creates user but returns fields.
        # We didn't keep B's token in setUp but we can generate one or mock login?
        # self.make_user_with_prefix implies we know the password or can create a session.
        # Actually `make_user_with_prefix` uses `register_user`.
        # We can just login as B.
        
        # Simpler: create a new user C, logged in.
        fields_c = self.make_user_with_prefix('charlie')
        user_c = self.get_user_by_username(fields_c[Fields.username])
        token_c = fields_c[Fields.session_management_token]
        header_c = {'HTTP_AUTHORIZATION': f'Bearer {token_c}'}
        
        # Me (A) blocks C.
        me.blocked.add(user_c)
        
        # C searches A (me)
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': self.local_username})
        response = self.client.get(url, **header_c)
        
        # Should not find A
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)


    def setUp(self):
        super().setUp()

        # This helper is assumed to create and log in a user,
        # setting self.local_username and self.session_management_token
        super().register_user_and_setup_local_fields()

        # Store the valid header for all tests
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        # Register a couple more users to be found in the search
        # We assume self.users is a list from the parent class
        first_user_fields = self.make_user_with_prefix(f'{username_fragment}_something')
        self.first_username = first_user_fields[Fields.username]
        second_user_fields = self.make_user_with_prefix(f'{username_fragment}_another')
        self.second_username = second_user_fields[Fields.username]

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': username_fragment})
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.get(url, **invalid_header)

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_invalid_username_fragment_returns_bad_response(self):
        """
        Tests that a malformed username fragment is rejected.
        """
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': invalid_username_fragment})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 400)  # 400 Bad Request

    def test_none_matching_fragment_returns_empty_response(self):
        """
        Tests that a valid search for a non-existent fragment
        returns a 200 OK and an empty list.
        """
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': other_username_fragment})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()
        self.assertEqual(responses, [])
        self.assertEqual(len(responses), 0)

    def test_some_match_fragment_returns_those_users(self):
        """
        Tests the "happy path" where multiple users match the fragment.
        """
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': username_fragment})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()

        # Should find the two users we created in setUp
        self.assertEqual(len(responses), 2)

        # Verify the correct users were returned
        found_usernames = {user['username'] for user in responses}
        self.assertIn(self.first_username, found_usernames)
        self.assertIn(self.second_username,  found_usernames)

    def test_search_fragment_excludes_self(self):
        """
        Tests that the user making the request is excluded from
        the search results, even if they match the fragment.
        """
        # We search for the logged-in user's own name
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': self.local_username})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        responses = response.json()

        # The list should be empty because the only match was excluded
        self.assertEqual(len(responses), 0)