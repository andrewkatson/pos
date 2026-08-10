import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from .test_constants import UserFields
from ..constants import Fields, MAX_REPORTS_PER_USER_PER_DAY, REVIEW_STATUS_ESCALATED
from ..models import Comment, ModerationReview

# Reporters available in setUp, comfortably more than any escalation bar.
NUM_USERS = 8

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

        # 1. Create User 0 (poster/commenter) and Users 1..NUM_USERS-1 (reporters)
        self.make_post_with_users(NUM_USERS)

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
        self.reporter_token = self.users[UserFields.TOKEN][1]
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

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_no_number_of_reports_hides_a_comment(self):
        """Issue #467: as for posts, reports are not a vote. However many users
        report a comment whose content passes review, it stays visible and is
        only escalated to a human moderator."""
        for i in range(1, NUM_USERS):
            header = {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][i]}'}
            response = self.client.post(
                self.url, data=self.valid_data, content_type='application/json', **header
            )
            self.assertEqual(response.status_code, 200)

        self.comment.refresh_from_db()
        self.assertFalse(self.comment.hidden)
        self.assertEqual(self.comment.commentreport_set.count(), NUM_USERS - 1)

        review = ModerationReview.objects.get(comment=self.comment)
        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_report_beyond_the_daily_limit_is_refused(self):
        """The daily budget is shared with posts, so it has to be enforced on
        this endpoint too — otherwise comments are the way around it."""
        reporter = get_user_model().objects.get(username=self.users[UserFields.USERNAME][1])
        # Stand in for a day's worth of reporting by this account.
        for _ in range(MAX_REPORTS_PER_USER_PER_DAY):
            self.post.postreport_set.create(user=reporter, reason=self.reason)

        response = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Daily report limit reached'})
        self.assertEqual(self.comment.commentreport_set.count(), 0)
