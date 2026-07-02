from django.urls import reverse
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields

invalid_post_identifier = '?'


class GetPostDetailsTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # Create a user and a post to fetch
        # This helper is assumed to set self.post, self.post_identifier,
        # and self.local_username
        self.post, self.post_identifier = super().make_post_and_login_user()

        # Define the valid URL for the test
        self.url = reverse('get_post_details', kwargs={'post_identifier': str(self.post_identifier)})

        # get_post_details now requires authentication
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def test_missing_auth_returns_unauthorized(self):
        """
        Tests that an unauthenticated request is rejected with 401.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL
        is rejected with a 400 Bad Request.
        """
        invalid_url = f'posts/{invalid_post_identifier}/details/'

        # Make a GET request to the invalid URL
        response = self.client.get(invalid_url)

        # Fails at the 'is_valid_pattern' check
        self.assertEqual(response.status_code, 404)

    def test_non_existent_post_identifier_returns_bad_response(self):
        """
        Tests that a validly formatted but non-existent post_identifier
        is rejected with a 400 Bad Request.
        """
        import uuid
        non_existent_uuid = str(uuid.uuid4())

        invalid_url = reverse('get_post_details', kwargs={'post_identifier': non_existent_uuid})

        response = self.client.get(invalid_url, **self.header)

        # Fails at 'get_post_with_identifier'
        self.assertEqual(response.status_code, 400)

    def test_existing_post_returns_good_response_and_details(self):
        """
        Tests that a valid request for an existing post returns
        a 200 OK and the correct post data.
        """
        response = self.client.get(self.url, **self.header)

        self.assertEqual(response.status_code, 200)

        # Parse the JSON response
        data = response.json()

        # Check that the data matches the post we created in setUp
        self.assertEqual(data[Fields.post_identifier], str(self.post_identifier))
        self.assertEqual(data[Fields.image_url], self.post.image_url)
        self.assertEqual(data[Fields.caption], self.post.caption)
        self.assertEqual(data[Fields.author_username], self.local_username)

        # Check default/calculated values
        self.assertEqual(data[Fields.post_likes], 0)
        # The author has not liked their own post
        self.assertFalse(data[Fields.is_liked])

    def test_text_only_post_returns_null_image_url(self):
        """
        A text-only post (#307) serializes with a null image_url (and null
        original_image_url) rather than being broken or omitted.
        """
        self.post.image_url = None
        self.post.save()

        response = self.client.get(self.url, **self.header)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data[Fields.image_url])
        self.assertEqual(data[Fields.caption], self.post.caption)

    def test_is_liked_true_when_requesting_user_liked_post(self):
        """
        Tests that is_liked is True when the authenticated requester has
        liked the post.
        """
        # A second user likes the post (users cannot like their own post)
        liker = self.make_user_with_prefix(prefix='liker')
        liker_header = {'HTTP_AUTHORIZATION': f'Bearer {liker[Fields.session_management_token]}'}

        like_url = reverse('like_post', kwargs={'post_identifier': str(self.post_identifier)})
        like_response = self.client.post(like_url, **liker_header)
        self.assertEqual(like_response.status_code, 200)

        # Fetch details as the liker
        response = self.client.get(self.url, **liker_header)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()[Fields.is_liked])