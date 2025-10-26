from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import MAX_BEFORE_HIDING_POST
from ..models import Post

# --- Constants ---
invalid_session_management_token = '?'
invalid_post_identifier = '?'
reason = "This is a negative post"

class ReportPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Create User 0 (poster) and Users 1..MAX+1 (reporters)
        # Total users = MAX + 2
        self.make_post_with_users(MAX_BEFORE_HIDING_POST + 2)

        # 2. Get the "poster's" info (User 0)
        self.poster_token = self.session_management_token  # Set by parent helper
        self.poster_header = {'HTTP_AUTHORIZATION': f'Bearer {self.poster_token}'}

        # 3. Get the first "reporter's" info (User 1)
        self.reporter_token = self.users[UserFields.TOKEN][1]
        self.reporter_header = {'HTTP_AUTHORIZATION': f'Bearer {self.reporter_token}'}

        # 4. Get the post object for DB assertions
        self.post = Post.objects.get(post_identifier=self.post_identifier)

        # 5. Define the URL and valid data for all tests
        self.url = reverse('report_post', kwargs={'post_identifier': str(self.post_identifier)})
        self.valid_data = {'reason': reason}

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **invalid_header
        )

        self.assertEqual(response.status_code, 401)  # 401 Unauthorized

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{invalid_post_identifier}/report/'

        response = self.client.post(
            invalid_url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 404)

    def test_report_own_post_returns_bad_response(self):
        """
        Tests that a user cannot report their own post.
        """
        # Use the *poster's* header (User 0)
        response = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.poster_header
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'Cannot report own post'})

    def test_report_post_twice_returns_bad_response(self):
        """
        Tests that a user cannot report the same post twice.
        """
        # 1. First report (should succeed)
        response1 = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )
        self.assertEqual(response1.status_code, 200)

        # 2. Check database
        self.post.refresh_from_db()
        self.assertEqual(self.post.postreport_set.count(), 1)

        # 3. Second report (should fail)
        response2 = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )
        self.assertEqual(response2.status_code, 404)
        self.assertEqual(response2.json(), {'error': 'Cannot report post twice'})

        # 4. Verify database count hasn't changed
        self.post.refresh_from_db()
        self.assertEqual(self.post.postreport_set.count(), 1)

    def test_report_post_returns_good_response_and_reports_post(self):
        """
        Tests the "happy path" for a single report.
        """
        # 1. Check DB before
        self.assertEqual(self.post.postreport_set.count(), 0)

        # 2. Make the request
        response = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        # 3. Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Post reported'})

        # 4. Check DB after
        self.post.refresh_from_db()
        self.assertEqual(self.post.postreport_set.count(), 1)
        self.assertFalse(self.post.hidden)  # Should not be hidden after 1 report

    def test_report_post_multiple_times_hides_post(self):
        """
        Tests that the post becomes hidden after MAX_BEFORE_HIDING_POST reports.
        """
        # Loop through all users *except* the poster (User 0)
        # This will be MAX + 1 reports
        for i in range(1, MAX_BEFORE_HIDING_POST + 2):
            token = self.users[UserFields.TOKEN][i]
            header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

            response = self.client.post(
                self.url, data=self.valid_data, content_type='application/json', **header
            )

            self.assertEqual(response.status_code, 200)

            # Check its state after each report
            self.post.refresh_from_db()
            if i > MAX_BEFORE_HIDING_POST:
                # This should only be true on the (MAX+1)-th report
                self.assertTrue(self.post.hidden)
            else:
                self.assertFalse(self.post.hidden)

        # Final check after the loop
        self.post.refresh_from_db()
        self.assertEqual(self.post.postreport_set.count(), MAX_BEFORE_HIDING_POST + 1)
        self.assertTrue(self.post.hidden)