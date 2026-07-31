import os
from unittest.mock import patch

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    Fields, INTEREST_CATEGORY_CHOICES, INTEREST_CATEGORY_SLUGS,
    MAX_FREEFORM_INTEREST_LENGTH,
)
from ..models import InterestCategory, PositiveOnlySocialUser, UserFreeformInterest


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class InterestOptionsTests(PositiveOnlySocialTestCase):
    """GET /interests/options/ — the public bucket vocabulary."""

    def test_options_are_public_and_complete(self):
        response = self.client.get(reverse('get_interest_options'))
        self.assertEqual(response.status_code, 200)
        options = response.json()[Fields.options]
        self.assertEqual(len(options), len(INTEREST_CATEGORY_CHOICES))
        slugs = {o[Fields.slug] for o in options}
        self.assertEqual(slugs, set(INTEREST_CATEGORY_SLUGS))
        # Each option carries a human label.
        self.assertTrue(all(o[Fields.name] for o in options))


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class InterestsViewTests(PositiveOnlySocialTestCase):
    """GET /interests/ and POST /interests/set/ (issues #446/#35). The text
    classifier runs in TESTING mode (any text containing "negative" is
    rejected), and the interest categorizer keyword-matches a term against the
    bucket slugs, so "nature" maps to the nature bucket and "hiking" maps to
    nothing."""

    def setUp(self):
        super().setUp()
        self.register_user_and_setup_local_fields()
        self.user = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.get_url = reverse('get_interests')
        self.set_url = reverse('set_interests')

    def _set(self, categories=None, freeform=None):
        body = {
            Fields.categories: categories if categories is not None else [],
            Fields.freeform: freeform if freeform is not None else [],
        }
        return self.client.post(self.set_url, data=body, content_type='application/json', **self.header)

    def _get(self):
        return self.client.get(self.get_url, **self.header)

    def _slugs(self):
        return sorted(self.user.interest_categories.values_list('slug', flat=True))

    # -- auth / method ---------------------------------------------------------

    def test_get_requires_auth(self):
        self.assertEqual(self.client.get(self.get_url).status_code, 401)

    def test_set_requires_auth(self):
        response = self.client.post(self.set_url, data={}, content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_set_rejects_get(self):
        self.assertEqual(self.client.get(self.set_url, **self.header).status_code, 405)

    def test_set_invalid_json_returns_400(self):
        response = self.client.post(self.set_url, data="nope", content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 400)

    def test_set_non_list_fields_return_400(self):
        body = {Fields.categories: "nature", Fields.freeform: []}
        response = self.client.post(self.set_url, data=body, content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 400)

    # -- presets ---------------------------------------------------------------

    def test_initial_state_empty(self):
        data = self._get().json()
        self.assertEqual(data[Fields.categories], [])
        self.assertEqual(data[Fields.freeform], [])

    def test_set_preset_categories(self):
        response = self._set(categories=['nature', 'music'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._slugs(), ['music', 'nature'])
        self.assertEqual(self._get().json()[Fields.categories], ['music', 'nature'])

    def test_unknown_slug_is_ignored(self):
        self._set(categories=['nature', 'not_a_bucket'])
        self.assertEqual(self._slugs(), ['nature'])

    # -- freeform --------------------------------------------------------------

    def test_freeform_positive_term_maps_to_bucket(self):
        response = self._set(freeform=['nature'])
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('nature', body[Fields.freeform][Fields.accepted])
        self.assertEqual(body[Fields.freeform][Fields.rejected], [])
        # Mapped into the weighting set and stored as a freeform row.
        self.assertIn('nature', self._slugs())
        self.assertEqual(self._get().json()[Fields.freeform], ['nature'])

    def test_freeform_unmapped_term_stored_without_bucket(self):
        # "hiking" is positive but matches no bucket slug: it is kept and shown,
        # but contributes nothing to the weighting set.
        self._set(freeform=['hiking'])
        self.assertEqual(self._get().json()[Fields.freeform], ['hiking'])
        self.assertEqual(self._slugs(), [])
        row = UserFreeformInterest.objects.get(user=self.user, text='hiking')
        self.assertEqual(row.categories.count(), 0)

    def test_freeform_multi_bucket_term_keeps_all_buckets_across_saves(self):
        # A single freeform term that maps to several buckets keeps them ALL,
        # even after a re-save that doesn't re-classify it (regression: only the
        # first mapped bucket used to survive the second save).
        self._set(freeform=['nature outdoors'])
        self.assertEqual(self._slugs(), ['nature', 'outdoors'])
        row = UserFreeformInterest.objects.get(user=self.user, text='nature outdoors')
        self.assertEqual(sorted(row.categories.values_list('slug', flat=True)),
                         ['nature', 'outdoors'])
        # Re-save the same term (now a kept row): both buckets still contribute.
        self._set(freeform=['nature outdoors'])
        self.assertEqual(self._slugs(), ['nature', 'outdoors'])

    def test_freeform_disallowed_term_is_rejected(self):
        response = self._set(freeform=['negative vibes'])
        rejected = response.json()[Fields.freeform][Fields.rejected]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0][Fields.text], 'negative vibes')
        self.assertFalse(UserFreeformInterest.objects.filter(user=self.user).exists())

    def test_freeform_too_long_is_rejected(self):
        long_term = 'a' * (MAX_FREEFORM_INTEREST_LENGTH + 1)
        response = self._set(freeform=[long_term])
        rejected = response.json()[Fields.freeform][Fields.rejected]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0][Fields.reason_code], 'too_long')

    def test_freeform_deduped_case_insensitively(self):
        self._set(freeform=['Nature', 'nature', 'NATURE'])
        self.assertEqual(
            list(UserFreeformInterest.objects.filter(user=self.user).values_list('text', flat=True)),
            ['nature'])

    # -- removal / replace semantics ------------------------------------------

    def test_resubmit_removes_dropped_preset(self):
        self._set(categories=['nature', 'music'])
        self._set(categories=['music'])
        self.assertEqual(self._slugs(), ['music'])

    def test_resubmit_removes_dropped_freeform(self):
        self._set(freeform=['nature', 'hiking'])
        self.assertIn('nature', self._slugs())
        self._set(freeform=['hiking'])
        self.assertEqual(
            list(UserFreeformInterest.objects.filter(user=self.user).values_list('text', flat=True)),
            ['hiking'])
        # Dropping the freeform "nature" drops its mapped bucket from the union.
        self.assertEqual(self._slugs(), [])

    def test_empty_payload_clears_everything(self):
        self._set(categories=['nature'], freeform=['music'])
        self.assertTrue(self.user.interest_categories.exists())
        self._set(categories=[], freeform=[])
        self.assertEqual(self._slugs(), [])
        self.assertFalse(UserFreeformInterest.objects.filter(user=self.user).exists())

    def test_concurrent_insert_during_classification_is_replaced(self):
        # Classification runs outside the write transaction (it calls external
        # providers), so another save can land in that window. Full-replace must
        # still hold: the term this request never asked for is gone afterwards.
        # Simulated by inserting a row from inside the classifier call, which is
        # exactly when the real race would occur.
        def insert_concurrent_row(term, *args, **kwargs):
            UserFreeformInterest.objects.get_or_create(user=self.user, text='ghost')
            return []

        with patch('user_system.views.interest_classifier_class.categorize_text_interests',
                   side_effect=insert_concurrent_row):
            self._set(freeform=['music'])

        stored = sorted(UserFreeformInterest.objects.filter(user=self.user)
                        .values_list('text', flat=True))
        self.assertEqual(stored, ['music'])

    def test_concurrent_row_buckets_do_not_survive_this_requests_mapping(self):
        # get_or_create can *find* a row a concurrent save inserted, already
        # carrying that writer's buckets. This request mapped the term to
        # nothing, so those buckets must be cleared — otherwise the next save
        # (which treats a stored term as already-accepted and folds its buckets
        # back into the union) would reintroduce them.
        nature = InterestCategory.objects.get(slug='nature')

        def insert_row_with_bucket(term, *args, **kwargs):
            row, _ = UserFreeformInterest.objects.get_or_create(user=self.user, text='jazz')
            row.categories.set([nature])
            return []  # this request maps 'jazz' to no bucket

        with patch('user_system.views.interest_classifier_class.categorize_text_interests',
                   side_effect=insert_row_with_bucket):
            self._set(freeform=['jazz'])

        row = UserFreeformInterest.objects.get(user=self.user, text='jazz')
        self.assertEqual(row.categories.count(), 0)

        # The real damage would show up here: re-saving must not resurrect it.
        self._set(freeform=['jazz'])
        self.assertEqual(self._slugs(), [])

    def test_kept_freeform_not_reclassified(self):
        self._set(freeform=['nature'])
        with patch('user_system.views.text_classifier_class.is_text_positive') as positive:
            # Resubmitting the same term must not re-run the classifier on it.
            self._set(freeform=['nature'])
            positive.assert_not_called()


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class RegistrationInterestsTests(PositiveOnlySocialTestCase):
    """Interests ride along in the register payload (no session exists yet)."""

    def test_register_applies_interests(self):
        username = self._get_unique_username('interested')
        body = {
            'username': username,
            'email': f'{username}@email.com',
            'password': f'Password_{self.prefix}123-',
            'remember_me': 'false',
            Fields.interest_categories: ['nature'],
            Fields.interest_freeform: ['music'],
        }
        response = self.client.post(reverse('register'), data=body, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user = PositiveOnlySocialUser.objects.get(username=username)
        slugs = set(user.interest_categories.values_list('slug', flat=True))
        # Preset pick + freeform "music" (maps to the music bucket).
        self.assertEqual(slugs, {'nature', 'music'})

    def test_register_bad_interests_do_not_block_signup(self):
        username = self._get_unique_username('resilient')
        body = {
            'username': username,
            'email': f'{username}@email.com',
            'password': f'Password_{self.prefix}123-',
            'remember_me': 'false',
            Fields.interest_categories: 'not-a-list',  # malformed on purpose
            Fields.interest_freeform: ['negative'],    # rejected term
        }
        response = self.client.post(reverse('register'), data=body, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(PositiveOnlySocialUser.objects.filter(username=username).exists())
