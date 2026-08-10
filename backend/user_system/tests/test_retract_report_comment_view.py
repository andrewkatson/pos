import os
from unittest.mock import patch

from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, HIDDEN_REASON_REPORTS, HIDDEN_REASON_CLASSIFIER, \
    REVIEW_STATUS_CLEARED, REVIEW_STATUS_ESCALATED
from ..models import Comment, ModerationReview

# --- Constants ---
invalid_session_management_token = '?'
invalid_comment_identifier = '?'
reason = "This is a negative comment"

# Reporters available in setUp, comfortably more than any escalation bar.
NUM_USERS = 8


class RetractReportCommentTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Create User 0 (poster/commenter) and Users 1..NUM_USERS-1 (reporters)
        self.make_post_with_users(NUM_USERS)

        # 2. User 0 (the poster) makes the comment
        self.commenter_token = self.session_management_token
        comment_data = self._comment_on_post(self.commenter_token, self.post_identifier)
        self.comment_thread_identifier = comment_data[Fields.comment_thread_identifier]
        self.comment_identifier = comment_data[Fields.comment_identifier]

        # 3. Get the comment object for DB assertions
        self.comment = Comment.objects.get(comment_identifier=self.comment_identifier)

        # 4. Get the first reporter's info (User 1)
        self.reporter_token = self.users[UserFields.TOKEN][1]
        self.reporter_header = {'HTTP_AUTHORIZATION': f'Bearer {self.reporter_token}'}

        # 5. Define the URLs used by the tests
        url_kwargs = {
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': str(self.comment_identifier)
        }
        self.report_url = reverse('report_comment', kwargs=url_kwargs)
        self.url = reverse('retract_report_comment', kwargs=url_kwargs)
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

    def test_invalid_comment_identifier_returns_bad_response(self):
        """
        Tests that a malformed comment_identifier in the URL is rejected.
        """
        invalid_url = (
            f'/posts/{self.post_identifier}/threads/{self.comment_thread_identifier}'
            f'/comments/{invalid_comment_identifier}/report/retract/'
        )

        response = self.client.post(invalid_url, **self.reporter_header)

        self.assertEqual(response.status_code, 404)

    def test_non_existent_comment_returns_bad_response(self):
        """
        Tests that a valid UUID for a missing comment is rejected.
        """
        import uuid
        missing_url = reverse('retract_report_comment', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': str(uuid.uuid4())
        })

        response = self.client.post(missing_url, **self.reporter_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Comment not found'})

    def test_retract_without_report_returns_bad_response(self):
        """
        Tests that retracting before ever reporting fails.
        """
        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Comment not reported yet'})

    def test_retract_report_returns_good_response_and_withdraws_report(self):
        """
        Tests the happy path: report, then retract, and the report no longer
        stands against the comment (its row is kept as a filing record — #467).
        """
        self._report(self.reporter_header)
        self.assertEqual(self.comment.commentreport_set.active().count(), 1)

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Comment report retracted'})
        self.assertEqual(self.comment.commentreport_set.active().count(), 0)

    def test_can_report_again_after_retracting(self):
        """
        Tests that report -> retract -> report works (the "twice" guard only
        applies to an active report).
        """
        self._report(self.reporter_header)

        retract_response = self.client.post(self.url, **self.reporter_header)
        self.assertEqual(retract_response.status_code, 200)

        # Reporting again should now succeed instead of "Cannot report comment twice".
        self._report(self.reporter_header)
        self.assertEqual(self.comment.commentreport_set.active().count(), 1)

    def test_retract_only_withdraws_own_report(self):
        """
        Tests that retracting withdraws only the caller's report, not other users'.
        """
        self._report(self.reporter_header)
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][2]}'}
        self._report(other_header)
        self.assertEqual(self.comment.commentreport_set.active().count(), 2)

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.comment.commentreport_set.active().count(), 1)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_retract_does_not_unhide_comment_hidden_by_a_moderator(self):
        """Issue #467: as for posts, withdrawing reports does not undo a
        moderator's decision to hide a comment."""
        self._report(self.reporter_header)
        self.comment.hidden = True
        self.comment.hidden_reason = HIDDEN_REASON_REPORTS
        self.comment.save()

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.hidden)
        self.assertEqual(self.comment.hidden_reason, HIDDEN_REASON_REPORTS)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_retracting_every_report_takes_the_comment_off_the_moderator_queue(self):
        """An escalation nobody is still reporting de-escalates itself."""
        for i in range(1, NUM_USERS):
            self._report({'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][i]}'})
        review = ModerationReview.objects.get(comment=self.comment)
        self.assertEqual(review.status, REVIEW_STATUS_ESCALATED)

        for i in range(1, NUM_USERS):
            header = {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][i]}'}
            self.assertEqual(self.client.post(self.url, **header).status_code, 200)

        review.refresh_from_db()
        self.assertEqual(review.status, REVIEW_STATUS_CLEARED)

    def test_retract_does_not_unhide_classifier_hidden_comment(self):
        """
        Tests that a comment hidden by the classifier stays hidden even when a
        report against it is retracted.
        """
        self._report(self.reporter_header)

        self.comment.hidden = True
        self.comment.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.comment.save()

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.hidden)
        self.assertEqual(self.comment.hidden_reason, HIDDEN_REASON_CLASSIFIER)
