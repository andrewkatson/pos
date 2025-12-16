from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..models import PositiveOnlySocialUser  # Import model for setup

# Constants for this test case
invalid_session_management_token = '?'
invalid_username = '??!!'  # A malformed username
other_username = 'Barbara123'
non_existent_username = 'Charlie222'


class GetProfileDetailsTests(PositiveOnlySocialTestCase):

    def test_is_blocked_is_true_when_blocked(self):
        # 1. Block the profile user
        self.requesting_user.blocked.add(self.profile_user)
        
        # 2. Get profile
        url = reverse('get_profile_details', kwargs={'username': self.profile_username})
        response = self.client.get(url, **self.valid_header)
        
        # 3. Verify 'is_blocked' is true
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_blocked'])

    def test_profile_details_hidden_when_blocked_by(self):
        # 1. Profile user blocks requesting user
        self.profile_user.blocked.add(self.requesting_user)
        
        # 2. Get profile
        url = reverse('get_profile_details', kwargs={'username': self.profile_username})
        response = self.client.get(url, **self.valid_header)
        
        # 3. Verify stats are hidden (0 or false)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[Fields.post_count], 0)
        self.assertEqual(data[Fields.follower_count], 0)
        self.assertEqual(data[Fields.following_count], 0)


    def setUp(self):
        super().setUp()

        # 1. Login the main user (the one making the request)
        # This sets self.local_username and self.session_management_token
        super().register_user_and_setup_local_fields()  # Assumes login_user_setup is now just login_user

        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.requesting_user = PositiveOnlySocialUser.objects.get(username=self.local_username)

        # 2. Register a second user (the one whose profile we will view)
        self.profile_username = other_username
        super().make_user(self.profile_username)
        self.profile_user = PositiveOnlySocialUser.objects.get(username=self.profile_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        url = reverse('get_profile_details', kwargs={'username': self.profile_username})
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.get(url, **invalid_header)

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_invalid_username_pattern_returns_bad_response(self):
        """
        Tests that a malformed username in the URL is rejected.
        """
        url = reverse('get_profile_details', kwargs={'username': invalid_username})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 400)  # 400 Bad Request

    def test_non_existent_username_returns_bad_response(self):
        """
        Tests that a validly formatted but non-existent username fails.
        """
        url = reverse('get_profile_details', kwargs={'username': non_existent_username})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 400)  # 400 Bad Request

    def test_valid_request_for_own_profile_returns_correct_details(self):
        """
        Tests that a user can successfully request their own profile.
        """
        url = reverse('get_profile_details', kwargs={'username': self.local_username})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Check that all default values are correct
        self.assertEqual(data[Fields.username], self.local_username)
        self.assertEqual(data[Fields.post_count], 0)
        self.assertEqual(data[Fields.follower_count], 0)
        self.assertEqual(data[Fields.following_count], 0)
        self.assertEqual(data[Fields.is_following], False)  # Can't follow self
        self.assertFalse(data[Fields.identity_is_verified])
        self.assertFalse(data[Fields.is_adult])

    def test_valid_request_for_other_user_returns_correct_default_details(self):
        """
        Tests the "happy path" for default values (not following).
        """
        url = reverse('get_profile_details', kwargs={'username': self.profile_username})

        response = self.client.get(url, **self.valid_header)

        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Check that all default values are correct for the *other user*
        self.assertEqual(data[Fields.username], self.profile_username)
        self.assertEqual(data[Fields.post_count], 0)
        self.assertEqual(data[Fields.follower_count], 0)
        self.assertEqual(data[Fields.following_count], 0)
        self.assertEqual(data[Fields.is_following], False)  # Not followed yet

    def test_is_following_is_true_when_following(self):
        """
        Tests that the 'is_following' flag is correctly set to True.
        """
        # 1. Create the follow relationship
        self.requesting_user.following.add(self.profile_user)

        url = reverse('get_profile_details', kwargs={'username': self.profile_username})

        # 2. Make the request
        response = self.client.get(url, **self.valid_header)

        # 3. Check the response
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # 4. Verify the 'is_following' flag is now true
        self.assertEqual(data[Fields.username], self.profile_username)
        self.assertEqual(data[Fields.follower_count], 1)  # The profile user now has 1 follower
        self.assertEqual(data[Fields.is_following], True)