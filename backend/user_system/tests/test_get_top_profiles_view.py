from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    BAN_TYPE_SHADOW,
    Fields,
    TOP_PROFILES_BATCH_SIZE,
    TOP_PROFILES_LIMIT,
)
from ..models import PositiveOnlySocialUser, UserBan, UserFollow


class GetTopProfilesTests(PositiveOnlySocialTestCase):
    """The Top profiles scoreboard (issue #588): public accounts ranked by how
    many followers the viewer can see, most first."""

    def setUp(self):
        super().setUp()

        self.register_user_and_setup_local_fields()
        self.viewer = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self._next_user = 0

    def _user(self, **fields):
        """An account created directly, skipping registration (and its
        classifier round trip) since these rows only need to exist."""
        self._next_user += 1
        name = fields.pop('username', f'topprofile{self._next_user}')
        return PositiveOnlySocialUser.objects.create(
            username=name, email=f'{name}@email.com', **fields)

    def _with_followers(self, count, **fields):
        user = self._user(**fields)
        for _ in range(count):
            UserFollow.objects.create(user_from=self._user(), user_to=user)
        return user

    def _get(self, batch=0, header=None):
        url = reverse('get_top_profiles', kwargs={'batch': batch})
        return self.client.get(url, **(header or self.header))

    def _ranked(self, **kwargs):
        response = self._get(**kwargs)
        self.assertEqual(response.status_code, 200)
        return [(row[Fields.username], row[Fields.follower_count]) for row in response.json()]

    def test_invalid_token_returns_unauthorized(self):
        response = self._get(header={'HTTP_AUTHORIZATION': 'Bearer ?'})
        self.assertEqual(response.status_code, 401)

    # "below_zero" not "negative": the test name becomes part of a registered
    # username, and the test classifier rejects text containing "negative".
    def test_below_zero_batch_does_not_route(self):
        url = reverse('get_top_profiles', kwargs={'batch': 0}).replace('/0/', '/-1/')
        self.assertEqual(self.client.get(url, **self.header).status_code, 404)

    def test_ranks_by_follower_count(self):
        one = self._with_followers(1)
        three = self._with_followers(3)
        two = self._with_followers(2)

        self.assertEqual(self._ranked(), [
            (three.username, 3), (two.username, 2), (one.username, 1)])

    def test_ties_break_by_username(self):
        b = self._user(username='zz_tied')
        a = self._user(username='aa_tied')
        for user in (a, b):
            UserFollow.objects.create(user_from=self._user(), user_to=user)

        self.assertEqual([name for name, _ in self._ranked()], ['aa_tied', 'zz_tied'])

    def test_accounts_without_followers_excluded(self):
        self._user()
        self.assertEqual(self._ranked(), [])

    def test_viewer_competes(self):
        UserFollow.objects.create(user_from=self._user(), user_to=self.viewer)
        self.assertEqual(self._ranked(), [(self.viewer.username, 1)])

    def test_private_account_excluded_even_for_followers(self):
        # A private account shows non-followers no counts (issue #96), so a
        # public scoreboard never ranks it, even for its approved followers.
        private = self._with_followers(3, is_private=True)
        UserFollow.objects.create(user_from=self.viewer, user_to=private)

        self.assertEqual(self._ranked(), [])

    def test_shadow_banned_account_excluded(self):
        banned = self._with_followers(2)
        UserBan.objects.create(user=banned, ban_type=BAN_TYPE_SHADOW)

        self.assertEqual(self._ranked(), [])

    def test_blocked_account_excluded_both_directions(self):
        other = self._with_followers(2)
        self.viewer.blocked.add(other)
        self.assertEqual(self._ranked(), [])

        self.viewer.blocked.remove(other)
        other.blocked.add(self.viewer)
        self.assertEqual(self._ranked(), [])

    def test_cross_age_band_account_excluded(self):
        self._with_followers(2, identity_is_verified=True, is_adult=False)
        self.assertEqual(self._ranked(), [])

    def test_hidden_followers_not_counted(self):
        # The count matches the profile page's follower_count (issue #398):
        # shadow-banned and cross-age-band followers don't inflate it.
        account = self._with_followers(1)
        banned_follower = self._user()
        UserFollow.objects.create(user_from=banned_follower, user_to=account)
        UserBan.objects.create(user=banned_follower, ban_type=BAN_TYPE_SHADOW)
        minor_follower = self._user(identity_is_verified=True, is_adult=False)
        UserFollow.objects.create(user_from=minor_follower, user_to=account)

        self.assertEqual(self._ranked(), [(account.username, 1)])

        profile = self.client.get(
            reverse('get_profile_details', kwargs={'username': account.username}), **self.header)
        self.assertEqual(profile.json()[Fields.follower_count], 1)

    def test_minor_sees_own_band_board(self):
        minor_viewer = self.make_user_with_prefix(prefix='minorviewer')
        PositiveOnlySocialUser.objects.filter(username=minor_viewer[Fields.username]).update(
            identity_is_verified=True, is_adult=False)
        minor_header = {'HTTP_AUTHORIZATION': f'Bearer {minor_viewer[Fields.session_management_token]}'}

        adult = self._with_followers(2)
        minor = self._user(identity_is_verified=True, is_adult=False)
        UserFollow.objects.create(
            user_from=self._user(identity_is_verified=True, is_adult=False), user_to=minor)
        # An adult follower is outside the minor viewer's band, so not counted.
        UserFollow.objects.create(user_from=self._user(), user_to=minor)

        self.assertEqual(self._ranked(), [(adult.username, 2)])
        self.assertEqual(self._ranked(header=minor_header), [(minor.username, 1)])

    def test_paginates_in_batches(self):
        for _ in range(TOP_PROFILES_BATCH_SIZE + 3):
            UserFollow.objects.create(user_from=self.viewer, user_to=self._user())

        self.assertEqual(len(self._ranked(batch=0)), TOP_PROFILES_BATCH_SIZE)
        self.assertEqual(len(self._ranked(batch=1)), 3)
        self.assertEqual(self._ranked(batch=2), [])

    def test_stops_at_limit(self):
        last_batch = TOP_PROFILES_LIMIT // TOP_PROFILES_BATCH_SIZE
        for _ in range(TOP_PROFILES_LIMIT + 5):
            UserFollow.objects.create(user_from=self.viewer, user_to=self._user())

        self.assertEqual(len(self._ranked(batch=last_batch - 1)), TOP_PROFILES_BATCH_SIZE)
        self.assertEqual(self._ranked(batch=last_batch), [])

    def test_rows_carry_profile_fields(self):
        self._with_followers(1)
        [row] = self._get().json()
        for field in (Fields.username, Fields.identity_is_verified, Fields.follower_count,
                      Fields.author_profile_image_url, Fields.author_profile_image_original_url):
            self.assertIn(field, row)
