import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import HIDDEN_REASON_CLASSIFIER, MAX_REPORTS_PER_USER_PER_DAY, \
    REVIEW_STATUS_ESCALATED
from ..models import ModerationReview, Post, PostReport

# --- Constants ---
invalid_session_management_token = '?'
invalid_post_identifier = '?'
reason = "This is a negative post"

# Reporters available in setUp, comfortably more than any escalation bar.
NUM_USERS = 8

class ReportPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Create User 0 (poster) and Users 1..NUM_USERS-1 (reporters)
        self.make_post_with_users(NUM_USERS)

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

        self.assertEqual(response.status_code, 400)
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
        self.assertEqual(response2.status_code, 400)
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

    def _report_with_every_user(self):
        """Every user but the poster reports the post."""
        for i in range(1, NUM_USERS):
            header = {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][i]}'}
            response = self.client.post(
                self.url, data=self.valid_data, content_type='application/json', **header
            )
            self.assertEqual(response.status_code, 200)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_no_number_of_reports_hides_a_post(self):
        """Issue #467: reports are not a vote. However many users report a post
        whose content passes review, it stays visible — it is only escalated to
        a human moderator."""
        self._report_with_every_user()

        self.post.refresh_from_db()
        self.assertEqual(self.post.postreport_set.count(), NUM_USERS - 1)
        self.assertFalse(self.post.hidden)

        # What all those reports bought is a moderator's attention, nothing more.
        review = ModerationReview.objects.get(post=self.post)
        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_reports_do_not_overwrite_classifier_hidden_reason(self):
        """A post already hidden by the classifier keeps that reason however many
        reports it draws, so appeals can still tell why."""
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()

        self._report_with_every_user()

        self.post.refresh_from_db()
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_report_beyond_the_daily_limit_is_refused(self):
        """One account cannot flood the queue: past MAX_REPORTS_PER_USER_PER_DAY
        reports in a rolling day, its reports are refused."""
        reporter = get_user_model().objects.get(username=self.users[UserFields.USERNAME][1])
        # Stand in for a day's worth of reporting by this account.
        other_post = Post.objects.create(author=self.post.author, caption='another')
        for _ in range(MAX_REPORTS_PER_USER_PER_DAY):
            PostReport.objects.create(user=reporter, post=other_post, reason=reason)

        response = self.client.post(
            self.url, data=self.valid_data, content_type='application/json', **self.reporter_header
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Daily report limit reached'})
        self.assertEqual(self.post.postreport_set.count(), 0)