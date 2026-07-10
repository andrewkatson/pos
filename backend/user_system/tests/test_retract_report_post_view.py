from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, MAX_BEFORE_HIDING_POST, HIDDEN_REASON_REPORTS, HIDDEN_REASON_CLASSIFIER, \
    HIDDEN_REASON_NONE
from ..models import Post

# --- Constants ---
invalid_session_management_token = '?'
invalid_post_identifier = '?'
reason = "This is a negative post"


class RetractReportPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        # 1. Create User 0 (poster) and Users 1..MAX+1 (reporters)
        # Total users = MAX + 2
        self.make_post_with_users(MAX_BEFORE_HIDING_POST + 2)

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

    def test_retract_unhides_post_hidden_by_reports(self):
        """
        Tests that a post hidden because reports crossed the threshold is
        un-hidden when a retraction drops the count back under it.
        """
        # Cross the hiding threshold (MAX + 1 reports).
        for i in range(1, MAX_BEFORE_HIDING_POST + 2):
            token = self.users[UserFields.TOKEN][i]
            self._report({'HTTP_AUTHORIZATION': f'Bearer {token}'})

        self.post.refresh_from_db()
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_REPORTS)

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertFalse(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_NONE)

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

    def test_retract_does_not_unhide_while_still_over_threshold(self):
        """
        Tests that the post stays hidden if the report count is still over the
        threshold after one retraction.
        """
        # MAX + 2 users total, so users 1..MAX+1 give MAX+1 reports; hiding
        # trips at count > MAX. After one retraction the count is MAX+... we
        # need count to remain > MAX, so add one more reporting user first.
        extra = self.make_user_with_prefix(prefix='extrareporter')
        self._report({'HTTP_AUTHORIZATION': f'Bearer {extra[Fields.session_management_token]}'})
        for i in range(1, MAX_BEFORE_HIDING_POST + 2):
            token = self.users[UserFields.TOKEN][i]
            self._report({'HTTP_AUTHORIZATION': f'Bearer {token}'})

        self.post.refresh_from_db()
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.postreport_set.count(), MAX_BEFORE_HIDING_POST + 2)

        response = self.client.post(self.url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        # Count dropped to MAX + 1, still over the "count > MAX" hiding bar.
        self.assertTrue(self.post.hidden)
        self.assertEqual(self.post.hidden_reason, HIDDEN_REASON_REPORTS)
