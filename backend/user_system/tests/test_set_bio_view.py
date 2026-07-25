import os
from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields, MAX_BIO_LENGTH
from ..models import PositiveOnlySocialUser


class SetBioTests(PositiveOnlySocialTestCase):
    """Covers POST /profile/bio/ — the synchronous, text-classified bio update
    (issue #380). The text classifier runs in TESTING mode, where any text
    containing the substring "negative" is rejected and everything else is
    allowed, so the tests below drive accept/reject through the bio content."""

    def setUp(self):
        super().setUp()
        super().register_user_and_setup_local_fields()
        self.url = reverse('set_bio')
        self.valid_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.user = PositiveOnlySocialUser.objects.get(username=self.local_username)

    def _post(self, body, header=None):
        return self.client.post(
            self.url, data=body, content_type='application/json',
            **(header if header is not None else self.valid_header))

    def _reload(self):
        self.user.refresh_from_db()
        return self.user

    # -- auth / method / shape -------------------------------------------------

    def test_invalid_token_returns_401(self):
        header = {'HTTP_AUTHORIZATION': 'Bearer ?'}
        response = self._post({Fields.bio: "Hello there"}, header=header)
        self.assertEqual(response.status_code, 401)

    def test_get_not_allowed(self):
        response = self.client.get(self.url, **self.valid_header)
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url, data="not json", content_type='application/json', **self.valid_header)
        self.assertEqual(response.status_code, 400)

    def test_missing_bio_field_returns_400(self):
        response = self._post({})
        self.assertEqual(response.status_code, 400)

    def test_non_string_bio_returns_400(self):
        response = self._post({Fields.bio: 123})
        self.assertEqual(response.status_code, 400)

    # -- length / pattern ------------------------------------------------------

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_bio_too_long_returns_400(self):
        response = self._post({Fields.bio: "a" * (MAX_BIO_LENGTH + 1)})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._reload().bio, "")

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_bio_at_max_length_is_accepted(self):
        bio = "a" * MAX_BIO_LENGTH
        response = self._post({Fields.bio: bio})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._reload().bio, bio)

    def test_bio_with_semicolon_returns_400(self):
        response = self._post({Fields.bio: "Hello; world"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._reload().bio, "")

    # -- moderation ------------------------------------------------------------

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_positive_bio_is_stored(self):
        bio = "I love long walks and helping others."
        response = self._post({Fields.bio: bio})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[Fields.bio], bio)
        self.assertEqual(self._reload().bio, bio)

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_non_positive_bio_is_rejected_and_not_stored(self):
        response = self._post({Fields.bio: "This is a negative bio"})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn(Fields.reason_code, data)
        self.assertFalse(data[Fields.appealable])
        self.assertEqual(self._reload().bio, "")

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_rejected_bio_does_not_overwrite_existing(self):
        good = "Kindness matters."
        self.assertEqual(self._post({Fields.bio: good}).status_code, 200)
        # A later non-positive edit must not wipe the already-approved bio.
        self.assertEqual(self._post({Fields.bio: "negative"}).status_code, 400)
        self.assertEqual(self._reload().bio, good)

    # -- clearing --------------------------------------------------------------

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_empty_bio_clears_existing(self):
        self.assertEqual(self._post({Fields.bio: "Something nice"}).status_code, 200)
        response = self._post({Fields.bio: ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.bio], "")
        self.assertEqual(self._reload().bio, "")

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_whitespace_only_bio_clears_and_skips_classifier(self):
        self.assertEqual(self._post({Fields.bio: "Something nice"}).status_code, 200)
        # "   negative   " would fail the classifier, but blank-after-strip clears
        # without ever calling it.
        response = self._post({Fields.bio: "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._reload().bio, "")

    # -- visibility ------------------------------------------------------------

    @patch.dict(os.environ, {"TESTING": "True"}, clear=True)
    def test_bio_appears_in_profile_details(self):
        bio = "Aspiring gardener and dog lover."
        self.assertEqual(self._post({Fields.bio: bio}).status_code, 200)
        profile_url = reverse('get_profile_details', kwargs={'username': self.local_username})
        response = self.client.get(profile_url, **self.valid_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.bio], bio)
