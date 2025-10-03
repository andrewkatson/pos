from django.contrib.sessions.middleware import SessionMiddleware

from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_content
from ..views import get_user_with_username, get_posts_for_user
from .test_constants import false, FAIL, SUCCESS
from ..feed_algorithm import feed_algorithm_fake

invalid_session_management_token = '?'
invalid_batch = -1


class GetPostsForUserTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().make_many_posts(10)

        super().setup_local_values(false)

        # Create an instance of a GET request.
        self.get_posts_for_user_request = self.make_get_request_obj('get_posts_for_user', self.local_username)

    def test_invalid_session_management_token_returns_bad_response(self):
        # Test view make_post
        response = get_posts_for_user(self.get_posts_for_user_request, invalid_session_management_token,
                                      self.local_username, 1,
                                      feed_algorithm_fake)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_batch_returns_bad_response(self):
        # Test view make_post
        response = get_posts_for_user(self.get_posts_for_user_request, self.session_management_token,
                                      self.local_username, invalid_batch,
                                      feed_algorithm_fake)
        self.assertEqual(response.status_code, FAIL)

    def test_one_beyond_max_batch_returns_good_response(self):
        # Test view make_post
        response = get_posts_for_user(self.get_posts_for_user_request, self.session_management_token,
                                      self.local_username, 1,
                                      feed_algorithm_fake)

        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        # We should grab no posts with a batch beyond the max number.
        self.assertEqual(len(responses), 0)

    def test_only_batch_amount_batch_returns_good_response(self):
        # Test view make_post
        response = get_posts_for_user(self.get_posts_for_user_request, self.session_management_token,
                                      self.local_username, 0,
                                      feed_algorithm_fake)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        # This doesn't include anyone else's posts
        self.assertEqual(len(responses), 1)
