from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_content
from ..views import get_user_with_username, get_posts_in_feed
from .test_constants import false, FAIL, SUCCESS
from ..feed_algorithm import feed_algorithm_fake

invalid_session_management_token = '?'
invalid_batch = -1


class GetPostsInFeedTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().make_many_posts(30)

        super().setup_local_values(false)

        # Create an instance of a POST request.
        self.get_posts_in_feed_request = self.factory.post("/user_system/get_posts_in_feed_request")

        # Recall that middleware are not supported. You can simulate a
        # logged-in user by setting request.user manually.
        self.get_posts_in_feed_request.user = get_user_with_username(self.local_username)

        # Also add a session
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(self.get_posts_in_feed_request)
        self.get_posts_in_feed_request.session.save()

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view make_post
        response = get_posts_in_feed(self.get_posts_in_feed_request, invalid_session_management_token, 1,
                                     feed_algorithm_fake)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_batch_returns_bad_response(self):
        # Test view make_post
        response = get_posts_in_feed(self.get_posts_in_feed_request, self.session_management_token, invalid_batch,
                                     feed_algorithm_fake)
        self.assertEqual(response.status_code, FAIL)

    def test_one_beyond_max_batch_returns_good_response(self):
        # Test view make_post
        response = get_posts_in_feed(self.get_posts_in_feed_request, self.session_management_token, 4,
                                      feed_algorithm_fake)

        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        # We should grab no posts with a batch beyond the max number.
        self.assertEqual(len(responses), 0)

    def test_first_batch_amount_batch_returns_good_response(self):
        # Test view make_post
        response = get_posts_in_feed(self.get_posts_in_feed_request, self.session_management_token, 0,
                                      feed_algorithm_fake)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        # This doesn't include users posts so we get the max per batch
        self.assertEqual(len(responses), 10)

    def test_last_batch_returns_good_response(self):
        # Test view make_post
        response = get_posts_in_feed(self.get_posts_in_feed_request, self.session_management_token, 2,
                                      feed_algorithm_fake)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        # One fewer than total made because the posts won't include the user's own posts
        self.assertEqual(len(responses), 9)

