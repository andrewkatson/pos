import os
from unittest.mock import patch

from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import HIDDEN_REASON_REPORTS, HIDDEN_REASON_CLASSIFIER, \
    REVIEW_STATUS_CLEARED, REVIEW_STATUS_ESCALATED
from ..models import ModerationReview, Post

# --- Constants ---
invalid_session_management_token = '?'
invalid_post_identifier = '?'
reason = "This is a negative post"

# Reporters available in setUp, comfortably more than any escalation bar.
NUM_USERS = 8


class RetractReportPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Create User 0 (poster) and Users 1..NUM_USERS-1 (reporters)
        self.make_post_with_users(NUM_USERS)

        # 2. Get the first "reporter's" info (User 1)
        self.reporter_token = self.users[UserFields.TOKEN][1]
        self.reporter_header = {'HTTP_AUTHORIZATION': f'Bearer {self.reporter_token}'}

        # 3. Get the post object for DB assertions
        self.post = Post.objects.get(post_identifier=self.post_identifier)

        # 4. Define the URLs used by the tests
        self.report_url = reverse('report_post', kwargs={'post_identifier': str(self.post_identifier)})
        self.url = reverse('retract_report_post', kwargs={'post_identifier': str(self.post_identifier)})
        self.valid_report_data = {'reason': reason}

    def _report(self, header):
        response = self.client.post(
            self.report_url, data=self.valid_report_data, content_type='application/json', **header
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_session_management_token_returns_bad_response(self):
        """
        Tests that @api_login_required rejects an invalid token.
        """
        invalid_header = {'HTTP_AUTHORIZATION': f'Bearer {invalid_session_management_token}'}

        response = self.client.post(self.url, **invalid_header)

        self.assertEqual(response.status_code, 401)

    def test_invalid_post_identifier_returns_bad_response(self):
        """
        Tests that a malformed post_identifier in the URL is rejected.
        """
        invalid_url = f'posts/{invalid_post_identifier}/report/retract/'

        response = self.client.post(invalid_url, **self.reporter_header)

        self.assertEqual(response.status_code, 404)

    def test_non_existent_post_returns_bad_response(self):
        """
        Tests that a valid UUID for a missing post is rejected.
        """
        import uuid
        missing_url = reverse('retract_report_post', kwargs={'post_identifier': str(uuid.uuid4())})

        response = self.client.post(missing_url, **self.reporter_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'No post with that identifier'})

    def test_retract_without_report_returns_bad_response(self):
        """
        Tests that retracting before ever reporting fails.
        """
        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Post not reported yet'})

    def test_retract_report_returns_good_response_and_deletes_report(self):
        """
        Tests the happy path: report, then retract, and the report row is gone.
        """
        self._report(self.reporter_header)
        self.assertEqual(self.post.postreport_set.count(), 1)

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Post report retracted'})
        self.assertEqual(self.post.postreport_set.count(), 0)

    def test_can_report_again_after_retracting(self):
        """
        Tests that report -> retract -> report works (the "twice" guard only
        applies to an active report).
        """
        self._report(self.reporter_header)

        retract_response = self.client.post(self.url, **self.reporter_header)
        self.assertEqual(retract_response.status_code, 200)

        # Reporting again should now succeed instead of "Cannot report post twice".
        self._report(self.reporter_header)
        self.assertEqual(self.post.postreport_set.count(), 1)

    def test_retract_only_deletes_own_report(self):
        """
        Tests that retracting removes only the caller's report, not other users'.
        """
        self._report(self.reporter_header)
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][2]}'}
        self._report(other_header)
        self.assertEqual(self.post.postreport_set.count(), 2)

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post.postreport_set.count(), 1)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_retract_does_not_unhide_post_hidden_by_a_moderator(self):
        """Issue #467: hiding is a decision, not a reversible group vote. A post a
        moderator hid after reviewing reports stays hidden when the reporters
        withdraw — only an appeal (or the moderator) can bring it back."""
        self._report(self.reporter_header)
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_REPORTS
        self.post.save()

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_REPORTS)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_retracting_every_report_takes_the_post_off_the_moderator_queue(self):
        """An escalation nobody is still reporting has nothing for a moderator to
        look at, so the last retraction de-escalates it."""
        for i in range(1, NUM_USERS):
            self._report({'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][i]}'})
        review = ModerationReview.objects.get(post=self.post)
        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)

        for i in range(1, NUM_USERS):
            header = {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][i]}'}
            self.assertEqual(self.client.post(self.url, **header).status_code, 200)

        review.refresh_from_db()
        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)
        self.assertEqual(self.post.postreport_set.count(), 0)

    def test_retract_does_not_unhide_classifier_hidden_post(self):
        """
        Tests that a post hidden by the classifier stays hidden even when a
        report against it is retracted.
        """
        self._report(self.reporter_header)

        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_CLASSIFIER)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_retracting_one_of_many_reports_keeps_the_escalation(self):
        """One reporter backing out does not clear an escalation others are still
        asking for."""
        for i in range(1, NUM_USERS):
            self._report({'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][i]}'})

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        review = ModerationReview.objects.get(post=self.post)
        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)
