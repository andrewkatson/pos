from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    BAN_TYPE_OUTRIGHT,
    BAN_TYPE_SHADOW,
    Fields,
    TOP_USERS_BATCH_SIZE,
    TOP_USERS_LIMIT,
)
from ..models import PositiveOnlySocialUser, UserBan, UserFollow


class GetTopUsersTests(PositiveOnlySocialTestCase):
    """The most-followed people board (issue #562)."""

    def setUp(self):
        super().setUp()

        self.register_user_and_setup_local_fields()
        self.viewer = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

    def _user(self, username):
        return PositiveOnlySocialUser.objects.create(username=username, email=f'{username}@test.com')

    def _followed_by(self, user, count, prefix=None):
        """Give `user` `count` fresh followers."""
        followers = [self._user(f'{prefix or user.username}_fan{i}') for i in range(count)]
        UserFollow.objects.bulk_create(UserFollow(user_from=f, user_to=user) for f in followers)
        return followers

    def _get(self, batch=0, header=None):
        return self.client.get(reverse('get_top_users', kwargs={'batch': batch}), **(header or self.header))

    def _names(self, batch=0):
        response = self._get(batch)
        self.assertEqual(response.status_code, 200)
        return [row[Fields.username] for row in response.json()]

    def test_invalid_token_returns_unauthorized(self):
        self.assertEqual(self._get(header={'HTTP_AUTHORIZATION': 'Bearer ?'}).status_code, 401)

    # "below_zero" not "negative": the test name becomes part of a registered
    # username, and the test classifier rejects text containing "negative".
    def test_below_zero_batch_does_not_route(self):
        url = reverse('get_top_users', kwargs={'batch': 0}).replace('/0/', '/-1/')
        self.assertEqual(self.client.get(url, **self.header).status_code, 404)

    def test_ranked_by_follower_count(self):
        one = self._user('one')
        three = self._user('three')
        two = self._user('two')
        self._followed_by(one, 1)
        self._followed_by(three, 3)
        self._followed_by(two, 2)

        self.assertEqual(self._names(), ['three', 'two', 'one'])

    def test_rows_carry_count_and_profile_fields(self):
        star = self._user('star')
        self._followed_by(star, 2)

        [row] = self._get().json()
        self.assertEqual(row[Fields.username], 'star')
        self.assertEqual(row[Fields.follower_count], 2)
        for field in (Fields.identity_is_verified, Fields.author_profile_image_url):
            self.assertIn(field, row)

    def test_ties_broken_by_username(self):
        for name in ('bravo', 'alpha'):
            self._followed_by(self._user(name), 1)

        self.assertEqual(self._names(), ['alpha', 'bravo'])

    def test_unfollowed_accounts_left_off(self):
        self._user('lonely')
        self.assertEqual(self._names(), [])

    def test_count_matches_profile_count(self):
        # A shadow-banned follower and a cross-age-band follower are hidden from
        # the profile's follower count (#398), so the board must not count them.
        # Long enough to pass the profile endpoint's username pattern.
        star = self._user('starperson')
        regular, shadowed, minor = self._followed_by(star, 3)
        UserBan.objects.create(user=shadowed, ban_type=BAN_TYPE_SHADOW)
        PositiveOnlySocialUser.objects.filter(pk=minor.pk).update(identity_is_verified=True, is_adult=False)

        [row] = self._get().json()
        self.assertEqual(row[Fields.follower_count], 1)

        profile = self.client.get(
            reverse('get_profile_details', kwargs={'username': 'starperson'}), **self.header).json()
        self.assertEqual(profile[Fields.follower_count], row[Fields.follower_count])

    def test_shadow_banned_account_left_off(self):
        star = self._user('star')
        self._followed_by(star, 2)
        UserBan.objects.create(user=star, ban_type=BAN_TYPE_SHADOW)

        self.assertEqual(self._names(), [])

    def test_outright_banned_account_left_off(self):
        star = self._user('star')
        self._followed_by(star, 2)
        UserBan.objects.create(user=star, ban_type=BAN_TYPE_OUTRIGHT)

        self.assertEqual(self._names(), [])

    def test_cross_age_band_account_left_off(self):
        star = self._user('star')
        self._followed_by(star, 2)
        PositiveOnlySocialUser.objects.filter(pk=star.pk).update(identity_is_verified=True, is_adult=False)

        self.assertEqual(self._names(), [])

    def test_blocked_account_left_off_both_directions(self):
        star = self._user('star')
        self._followed_by(star, 2)

        self.viewer.blocked.add(star)
        self.assertEqual(self._names(), [])

        self.viewer.blocked.remove(star)
        star.blocked.add(self.viewer)
        self.assertEqual(self._names(), [])

    def test_viewer_can_rank(self):
        self._followed_by(self.viewer, 1, prefix='viewer')
        self.assertEqual(self._names(), [self.viewer.username])

    def test_paginates_and_stops_at_limit(self):
        # Each account follows the next one, so every account but the first
        # has a follower and more accounts rank than the board shows.
        users = [self._user(f'user{i:03d}') for i in range(TOP_USERS_LIMIT + 5)]
        UserFollow.objects.bulk_create(
            UserFollow(user_from=users[i], user_to=users[i + 1]) for i in range(len(users) - 1))

        last_batch = TOP_USERS_LIMIT // TOP_USERS_BATCH_SIZE
        self.assertEqual(len(self._names(0)), TOP_USERS_BATCH_SIZE)
        self.assertEqual(len(self._names(last_batch - 1)), TOP_USERS_BATCH_SIZE)
        self.assertEqual(self._names(last_batch), [])
