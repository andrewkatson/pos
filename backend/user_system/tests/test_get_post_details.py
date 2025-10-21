from .test_constants import FAIL, SUCCESS
from .test_parent_case import PositiveOnlySocialTestCase
from .test_utils import get_response_fields
from ..constants import Fields
from ..views import get_post_details

invalid_post_identifier = '?'


class GetPostDetailsTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()

        self.post, self.post_identifier = super().make_post_and_login_user()

        # Create an instance of a GET request.
        self.get_post_details_request = self.make_get_request_obj('get_post_details', self.local_username)

    def test_invalid_post_identifier_returns_bad_response(self):
        # Test view get_post_details
        response = get_post_details(self.get_post_details_request, invalid_post_identifier)
        self.assertEqual(response.status_code, FAIL)

    def test_existing_post_returns_good_response_and_details(self):
        # Test view get_post_details
        response = get_post_details(self.get_post_details_request, str(self.post_identifier))
        self.assertEqual(response.status_code, SUCCESS)

        fields = get_response_fields(response)

        self.assertTrue(fields[Fields.post_identifier])
        self.assertTrue(fields[Fields.image_url])
        self.assertTrue(fields[Fields.caption])
        self.assertEqual(fields[Fields.post_likes], 0)
