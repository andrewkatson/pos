from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from ..classifiers.classifier_constants import POSITIVE_IMAGE_URL, POSITIVE_TEXT
from ..views import register, login_user, make_post, report_post, get_user_with_username
from ..constants import Fields, MAX_BEFORE_HIDING_POST
from .test_constants import username, email, password, ip, false, FAIL, SUCCESS, UserFields
from .test_utils import get_response_fields
from ..classifiers import image_classifier_fake, text_classifier_fake

invalid_session_management_token = '?'
invalid_post_identifier = '?'

class ReportPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().make_post_with_users(MAX_BEFORE_HIDING_POST)

        other_session_management_tokens = self.users.get(UserFields.SESSION_MANAGEMENT_TOKEN, [])
        other_local_usernames = self.users.get(UserFields.USERNAME, [])
        other_local_passwords = self.users.get(UserFields.PASSWORD, [])

        self.other_session_management_token = other_session_management_tokens[1]
        self.other_local_username = other_local_usernames[1]
        self.other_local_password = other_local_passwords[1]

        # Create an instance of a POST request.
        self.report_post_request = self.factory.post("/user_system/report_post")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.report_post_request.user = self.user

        # Login one of the users to do the reporting
        response = login_user(self.login_user_request, self.other_local_username, self.other_local_password, false, ip)
        self.assertEqual(response.status_code, SUCCESS)

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view report_post
        response = report_post(self.report_post_request, invalid_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view report_post
        response = report_post(self.report_post_request, self.other_session_management_token, invalid_post_identifier)
        self.assertEqual(response.status_code, FAIL)

    def test_report_own_post_returns_bad_response(self):
        # Test view report_post
        response = report_post(self.report_post_request, self.session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, FAIL)

    def test_report_post_returns_good_response_and_reports_post_from_user(self):
        # Test view report_post
        response = report_post(self.report_post_request, self.other_session_management_token, str(self.post_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        self.assertEqual(post.postreport_set.count(), 1)

    def test_report_post_multiple_times_returns_good_response_and_hides_post_from_user(self):

        for i, user in enumerate(self.users.values()):
            # Test view report_post
            response = report_post(self.report_post_request, user.get(UserFields.SESSION_MANAGEMENT_TOKEN)[i], str(self.post_identifier))
            self.assertEqual(response.status_code, SUCCESS)

        user = get_user_with_username(self.local_username)
        post = user.post_set.first()
        self.assertEqual(post.postreport_set.count(), MAX_BEFORE_HIDING_POST)
        self.assertTrue(post.hidden)
