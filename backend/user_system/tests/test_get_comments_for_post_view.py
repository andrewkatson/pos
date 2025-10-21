from .test_constants import false, FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_content
from ..feed_algorithm import feed_algorithm_fake
from ..views import get_comments_for_post

invalid_post_identifier = '?'
invalid_batch = -1


class GetCommentsForPostTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        super().make_many_comments(30)

        super().setup_local_values(false)

        # Create an instance of a GET request.
        self.get_comments_for_post_request = self.make_get_request_obj('get_comments_for_post', self.local_username)

    def test_invalid_post_identifier_token_returns_bad_response(self):
        # Test view make_post
        response = get_comments_for_post(self.get_comments_for_post_request, invalid_post_identifier, 1,
                                         feed_algorithm_fake)
        self.assertEqual(response.status_code, FAIL)

    def test_invalid_batch_returns_bad_response(self):
        # Test view make_post
        response = get_comments_for_post(self.get_comments_for_post_request, str(self.post_identifier), invalid_batch,
                                         feed_algorithm_fake)
        self.assertEqual(response.status_code, FAIL)

    def test_one_beyond_max_batch_returns_good_response(self):
        # Test view make_post
        response = get_comments_for_post(self.get_comments_for_post_request, str(self.post_identifier), 4,
                                         feed_algorithm_fake)

        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        # We should grab no posts with a batch beyond the max number.
        self.assertEqual(len(responses), 0)

    def test_first_batch_amount_batch_returns_good_response(self):
        # Test view make_post
        response = get_comments_for_post(self.get_comments_for_post_request, str(self.post_identifier), 0,
                                         feed_algorithm_fake)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        self.assertEqual(len(responses), 10)

    def test_last_batch_returns_good_response(self):
        # Test view make_post
        response = get_comments_for_post(self.get_comments_for_post_request, str(self.post_identifier), 2,
                                         feed_algorithm_fake)
        self.assertEqual(response.status_code, SUCCESS)

        responses = get_response_content(response)

        self.assertEqual(len(responses), 10)
