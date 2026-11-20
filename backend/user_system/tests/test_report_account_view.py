"""POST /users/<username>/report/ and /report/retract/ (issue #602), plus the
viewer's own report state on GET /users/<username>/profile/."""
import os
from unittest.mock import patch

from django.urls import reverse

from .test_constants import UserFields
from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_utils import ClassificationResult
from ..constants import Fields, MAX_REPORTS_PER_USER_PER_DAY, REVIEW_STATUS_CLEARED, REVIEW_STATUS_DISMISSED
from ..models import AccountReport, ModerationReview, PositiveOnlySocialUser

ALLOWED = ClassificationResult(allowed=True)
TEXT = 'user_system.tasks.text_classifier_class.is_text_positive'
REASON = 'Their bio is unkind'


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
@patch(TEXT, return_value=ALLOWED)
class ReportAccountTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        with patch.dict(os.environ, {"TESTING": "True"}, clear=True):
            for i in range(3):
                self.make_user(self._get_unique_username(f'acct{i}'))
        self.target_name = self.users[UserFields.USERNAME][0]
        self.target = PositiveOnlySocialUser.objects.get(username=self.target_name)
        self.reporter = PositiveOnlySocialUser.objects.get(username=self.users[UserFields.USERNAME][1])
        self.target_header = self._header(0)
        self.reporter_header = self._header(1)
        self.url = reverse('report_account', kwargs={'username': self.target_name})
        self.retract_url = reverse('retract_report_account', kwargs={'username': self.target_name})

    def _header(self, index):
        return {'HTTP_AUTHORIZATION': f'Bearer {self.users[UserFields.TOKEN][index]}'}

    def _report(self, header=None, reason=REASON, url=None):
        return self.client.post(url or self.url, data={'reason': reason}, content_type='application/json',
                                **(header or self.reporter_header))

    def _profile(self, header):
        return self.client.get(reverse('get_profile_details', kwargs={'username': self.target_name}), **header)

    # --- reporting --------------------------------------------------------

    def test_requires_authentication(self, text):
        response = self._report(header={'HTTP_AUTHORIZATION': 'Bearer ?'})
        self.assertEqual(response.status_code, 401)

    def test_report_opens_a_review_and_hides_nothing(self, text):
        response = self._report()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Account reported'})
        report = AccountReport.objects.get()
        self.assertEqual((report.user, report.reported_user, report.reason), (self.reporter, self.target, REASON))
        # Eager mode: the automated re-review already ran and found nothing.
        self.assertEqual(ModerationReview.objects.get(account=self.target).status, REVIEW_STATUS_CLEARED)
        self.assertTrue(PositiveOnlySocialUser.objects.filter(pk=self.target.pk, is_active=True).exists())

    def test_cannot_report_own_account(self, text):
        response = self._report(header=self.target_header)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Cannot report own account'})
        self.assertFalse(AccountReport.objects.exists())

    def test_cannot_report_twice(self, text):
        self._report()
        response = self._report()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Cannot report account twice'})
        self.assertEqual(AccountReport.objects.count(), 1)

    def test_a_reason_is_required(self, text):
        response = self._report(reason='')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AccountReport.objects.exists())

    def test_unknown_account(self, text):
        url = reverse('report_account', kwargs={'username': 'nobody_by_this_name'})
        response = self._report(url=url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'User does not exist'})

    def test_a_cross_age_band_account_is_treated_as_absent(self, text):
        # A verified minor: the other band from an adult or unverified reporter.
        PositiveOnlySocialUser.objects.filter(pk=self.target.pk).update(identity_is_verified=True, is_adult=False)
        response = self._report()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'User does not exist'})
        self.assertFalse(AccountReport.objects.exists())

    def test_a_blocked_requester_can_still_report(self, text):
        # Blocking hides a profile's details, not who someone is.
        self.target.blocked.add(self.reporter)
        response = self._report()
        self.assertEqual(response.status_code, 200)

    def test_the_daily_budget_is_shared(self, text):
        for i in range(MAX_REPORTS_PER_USER_PER_DAY):
            other = PositiveOnlySocialUser.objects.create(username=f'budget_other_{i}', email=f'bo{i}@test.com')
            AccountReport.objects.create(user=self.reporter, reported_user=other, reason='x')
        response = self._report()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Daily report limit reached'})

    # --- retracting -------------------------------------------------------

    def test_retract_stamps_the_report_and_allows_reporting_again(self, text):
        self._report()
        response = self.client.post(self.retract_url, **self.reporter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'message': 'Account report retracted'})
        report = AccountReport.objects.get()
        self.assertIsNotNone(report.retracted_time)
        self.assertEqual(self._report().status_code, 200)

    def test_retract_without_a_report(self, text):
        response = self.client.post(self.retract_url, **self.reporter_header)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Account not reported yet'})

    # --- profile details --------------------------------------------------

    def test_profile_details_carry_the_viewers_own_report(self, text):
        data = self._profile(self.reporter_header).json()
        self.assertFalse(data[Fields.is_reported])
        self.assertIsNone(data[Fields.report_reason])

        self._report()
        data = self._profile(self.reporter_header).json()
        self.assertTrue(data[Fields.is_reported])
        self.assertEqual(data[Fields.report_reason], REASON)

        # Another viewer never learns about someone else's report.
        data = self._profile(self._header(2)).json()
        self.assertFalse(data[Fields.is_reported])

    def test_the_owner_sees_no_report_state(self, text):
        self._report()
        data = self._profile(self.target_header).json()
        self.assertNotIn(Fields.is_reported, data)
        self.assertNotIn(Fields.report_reason, data)

    # --- profile changes release a decision -------------------------------

    def test_clearing_the_bio_releases_a_dismissal(self, text):
        PositiveOnlySocialUser.objects.filter(pk=self.target.pk).update(bio='an old bio')
        self._report()
        ModerationReview.objects.filter(account=self.target).update(status=REVIEW_STATUS_DISMISSED)
        text.reset_mock()

        response = self.client.post(reverse('set_bio'), data={Fields.bio: '   '},
                                    content_type='application/json', **self.target_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ModerationReview.objects.get(account=self.target).status, REVIEW_STATUS_CLEARED)
        self.target.refresh_from_db()
        self.assertEqual(self.target.bio, '')
