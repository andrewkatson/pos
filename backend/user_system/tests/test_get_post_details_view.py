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

        response = self.client.get(invalid_url)

        # Fails at 'get_post_with_identifier'
        self.assertEqual(response.status_code, 400)

    def test_existing_post_returns_good_response_and_details(self):
        """
        Tests that a valid request for an existing post returns
        a 200 OK and the correct post data.
        """
        response = self.client.get(self.url)

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