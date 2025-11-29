from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, MAX_BEFORE_HIDING_COMMENT
from ..models import Comment

# --- Constants ---
invalid_session_management_token = '?'
invalid_post_identifier = '?'
invalid_reason = ''
invalid_comment_identifier = '?'
invalid_comment_thread_identifier = '?'


class ReportCommentTests(PositiveOnlySocialTestCase):

    # use these classifiers.
    def setUp(self):
        super().setUp()

        # 1. Create User 0 (poster/commenter) and Users 1..MAX+1 (reporters)
        # Total users = MAX + 2
        self.make_post_with_users(MAX_BEFORE_HIDING_COMMENT + 2)

        # 2. User 0 (the poster) makes the comment
        self.commenter_token = self.session_management_token  # User 0's token
        self.commenter_header = {'HTTP_AUTHORIZATION': f'Bearer {self.commenter_token}'}

        comment_data = self._comment_on_post(self.commenter_token, self.post_identifier)
        self.comment_thread_identifier = comment_data[Fields.comment_thread_identifier]
        self.comment_identifier = comment_data[Fields.comment_identifier]

        # 3. Get the comment object for DB assertions
        self.comment = Comment.objects.get(comment_identifier=self.comment_identifier)
        self.reason = "This is a negative comment"
        self.valid_data = {'reason': self.reason}

        # 4. Get the first reporter's info (User 1)
        self.reporter_token = self.users[Fields.session_management_token][1]
        self.reporter_header = {'HTTP_AUTHORIZATION': f'Bearer {self.reporter_token}'}

        # 5. Define the URL for all tests
        self.url = reverse('report_comment', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': str(self.comment_identifier)
        })

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
        invalid_url = f'posts/{invalid_post_identifier}/threads/{self.comment_thread_identifier}/comments/{self.comment_identifier}/report/'

        response = self.client.post(
            invalid_url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_thread_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_thread_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{self.post_identifier}/threads/{invalid_comment_thread_identifier}/comments/{self.comment_identifier}/report/'

        response = self.client.post(
            invalid_url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_comment_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_identifier in the URL is rejected.
        """

        invalid_url = f'posts/{self.post_identifier}/threads/{self.comment_thread_identifier}/comments/{invalid_comment_identifier}/report/'

        response = self.client.post(
            invalid_url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_reason_returns_bad_response(self):
        """
        Tests that a malformed reason in the JSON body is rejected.
        """
        invalid_data = {'reason': invalid_reason}

        response = self.client.post(
            self.url, data=invalid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 400)

    def test_report_own_comment_fails(self):
        """
        Tests that a user cannot report their own comment.
        """
        # Use the *commenter's* header (User 0)
        response = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.commenter_header
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Cannot report own comment", response.json().get('error', ''))

    def test_report_comment_twice_fails(self):
        """
        Tests that a user cannot report the same comment twice.
        """
        # 1. First report (should succeed)
        response1 = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )
        self.assertEqual(response1.status_code, 200)

        # 2. Second report (should fail)
        response2 = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )
        self.assertEqual(response2.status_code, 400)
        self.assertIn("Cannot report comment twice", response2.json().get('error', ''))

    def test_report_comment_returns_good_response_and_reports_comment(self):
        """
        Tests the "happy path" for a single report.
        """
        self.assertFalse(self.comment.hidden)

        response = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 200)

        self.comment.refresh_from_db()
        self.assertEqual(self.comment.commentreport_set.count(), 1)
        self.assertFalse(self.comment.hidden)  # Should not be hidden after 1 report

    def test_report_comment_more_than_max_returns_good_response_and_hides_comment(self):
        """
        Tests that the comment becomes hidden after MAX_BEFORE_HIDING_COMMENT reports.
        """
        # Loop through all users *except* the commenter (User 0)
        # This will be MAX + 1 reports
        for i in range(1, MAX_BEFORE_HIDING_COMMENT + 2):
            token = self.users[Fields.session_management_token][i]
            header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

            response = self.client.post(
                self.url, data=self.valid_data, content_type='application/json', **header
            )

            self.assertEqual(response.status_code, 200)

            # Check its state after each report
            self.comment.refresh_from_db()
            if i > MAX_BEFORE_HIDING_COMMENT:
                self.assertTrue(self.comment.hidden)
            else:
                self.assertFalse(self.comment.hidden)

        # Final check after the loop
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.hidden)
        self.assertEqual(self.comment.commentreport_set.count(), MAX_BEFORE_HIDING_COMMENT + 1)