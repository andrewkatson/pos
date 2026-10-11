from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    BAN_TYPE_SHADOW,
    Fields,
    FOLLOW_CATEGORY_FAMILY,
    HIDDEN_REASON_CLASSIFIER,
    HIDDEN_REASON_PENDING_CLASSIFICATION,
    POST_AUDIENCE_FAMILY,
    POST_AUDIENCE_PUBLIC,
    POST_BATCH_SIZE,
    TOP_POSTS_LIMIT,
)
from ..models import Post, PostLike, PositiveOnlySocialUser, UserBan, UserFollow

POSITIVE_CAPTION = "what a lovely and positive day this is"


class GetTopPostsTests(PositiveOnlySocialTestCase):
    """The Top posts scoreboard (issue #558): public, approved posts created in
    the chosen window, ranked by like count."""

    def setUp(self):
        super().setUp()

        self.register_user_and_setup_local_fields()
        self.viewer = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}

        poster_fields = self.make_user_with_prefix(prefix='poster')
        self.poster = PositiveOnlySocialUser.objects.get(username=poster_fields[Fields.username])

        # Likers to hand out likes from; a user may like a post only once.
        self.likers = [
            PositiveOnlySocialUser.objects.get(
                username=self.make_user_with_prefix(prefix=f'liker{i}')[Fields.username])
            for i in range(3)
        ]

    def _post(self, likes=0, age=timedelta(hours=1), author=None, **fields):
        """A live post created directly (bypassing the async classifier), with
        `likes` likes and backdated by `age`."""
        post = Post.objects.create(
            author=author or self.poster, caption=POSITIVE_CAPTION, image_url=None,
            **{'hidden': False, 'audience': POST_AUDIENCE_PUBLIC, **fields})
        for liker in self.likers[:likes]:
            PostLike.objects.create(user=liker, post=post)
        # creation_time is auto_now_add, so backdate it with an update.
        Post.objects.filter(pk=post.pk).update(creation_time=timezone.now() - age)
        return str(post.post_identifier)

    def _get(self, batch=0, period=None, header=None):
        url = reverse('get_top_posts', kwargs={'batch': batch})
        if period is not None:
            url += f'?{Fields.period}={period}'
        return self.client.get(url, **(header or self.header))

    def _ids(self, **kwargs):
        response = self._get(**kwargs)
        self.assertEqual(response.status_code, 200)
        return [post[Fields.post_identifier] for post in response.json()]

    def test_invalid_token_returns_unauthorized(self):
        response = self._get(header={'HTTP_AUTHORIZATION': 'Bearer ?'})
        self.assertEqual(response.status_code, 401)

    def test_invalid_period_returns_bad_request(self):
        response = self._get(period='decade')
        self.assertEqual(response.status_code, 400)

    # "below_zero" not "negative": the test name becomes part of a registered
    # username, and the test classifier rejects text containing "negative".
    def test_below_zero_batch_does_not_route(self):
        url = reverse('get_top_posts', kwargs={'batch': 0}).replace('/0/', '/-1/')
        self.assertEqual(self.client.get(url, **self.header).status_code, 404)

    def test_no_posts_returns_empty_list(self):
        self.assertEqual(self._ids(), [])

    def test_ranked_by_like_count(self):
        one = self._post(likes=1)
        three = self._post(likes=3)
        none = self._post(likes=0)
        two = self._post(likes=2)

        self.assertEqual(self._ids(), [three, two, one, none])

    def test_ties_broken_newest_first(self):
        older = self._post(likes=1, age=timedelta(hours=5))
        newer = self._post(likes=1, age=timedelta(hours=1))

        self.assertEqual(self._ids(), [newer, older])

    def test_like_count_matches_payload(self):
        self._post(likes=2)
        [post] = self._get().json()
        self.assertEqual(post[Fields.post_likes], 2)

    def test_like_count_not_inflated_by_author_follow_edges(self):
        # visible_posts joins the author's follow edges; a non-distinct count
        # would score this post's one like once per account the author follows.
        for liker in self.likers:
            UserFollow.objects.create(user_from=self.poster, user_to=liker)
        well_followed = self._post(likes=1)
        two_likes = self._post(likes=2, author=self.likers[0])

        self.assertEqual(self._ids(), [two_likes, well_followed])

    def test_default_period_is_week(self):
        recent = self._post(age=timedelta(days=6))
        self._post(age=timedelta(days=8))

        self.assertEqual(self._ids(), [recent])

    def test_period_windows(self):
        hour = self._post(age=timedelta(hours=1))
        days_3 = self._post(age=timedelta(days=3))
        days_20 = self._post(age=timedelta(days=20))
        days_200 = self._post(age=timedelta(days=200))
        self._post(age=timedelta(days=400))

        cases = {
            'day': {hour},
            'week': {hour, days_3},
            'month': {hour, days_3, days_20},
            'year': {hour, days_3, days_20, days_200},
        }
        for period, expected in cases.items():
            with self.subTest(period=period):
                self.assertEqual(set(self._ids(period=period)), expected)

    def test_empty_period_uses_default(self):
        self._post()
        self.assertEqual(self._get(period='').status_code, 200)

    def test_restricted_audience_excluded_even_when_viewer_admitted(self):
        # The viewer is in the author's family, so the post is visible to them
        # elsewhere — but the scoreboard ranks public posts only.
        UserFollow.objects.create(
            user_from=self.poster, user_to=self.viewer, category=FOLLOW_CATEGORY_FAMILY)
        self._post(likes=3, audience=POST_AUDIENCE_FAMILY)
        public = self._post(likes=0)

        self.assertEqual(self._ids(), [public])

    def test_hidden_post_excluded(self):
        self._post(likes=3, hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)
        self.assertEqual(self._ids(), [])

    def test_own_unapproved_posts_excluded(self):
        # visible_posts lets an author see their own pending/rejected posts in
        # their feeds, but a scoreboard only ranks approved content.
        for reason in (HIDDEN_REASON_PENDING_CLASSIFICATION, HIDDEN_REASON_CLASSIFIER):
            self._post(author=self.viewer, hidden=True, hidden_reason=reason)
        own_live = self._post(author=self.viewer)

        self.assertEqual(self._ids(), [own_live])

    def test_shadow_banned_author_excluded(self):
        self._post(likes=3)
        UserBan.objects.create(user=self.poster, ban_type=BAN_TYPE_SHADOW)

        self.assertEqual(self._ids(), [])

    def test_blocked_author_excluded_both_directions(self):
        self._post(likes=3)
        self.viewer.blocked.add(self.poster)
        self.assertEqual(self._ids(), [])

        self.viewer.blocked.remove(self.poster)
        self.poster.blocked.add(self.viewer)
        self.assertEqual(self._ids(), [])

    def test_cross_age_band_excluded(self):
        self._post(likes=3)
        PositiveOnlySocialUser.objects.filter(pk=self.poster.pk).update(
            identity_is_verified=True, is_adult=False)

        self.assertEqual(self._ids(), [])

    def test_paginates_in_post_batches(self):
        for _ in range(POST_BATCH_SIZE + 3):
            self._post()

        self.assertEqual(len(self._ids(batch=0)), POST_BATCH_SIZE)
        self.assertEqual(len(self._ids(batch=1)), 3)
        self.assertEqual(self._ids(batch=2), [])

    def test_stops_at_limit(self):
        last_batch = TOP_POSTS_LIMIT // POST_BATCH_SIZE
        PostLike.objects.all().delete()
        Post.objects.bulk_create(
            Post(author=self.poster, caption=POSITIVE_CAPTION, image_url=None,
                 audience=POST_AUDIENCE_PUBLIC)
            for _ in range(TOP_POSTS_LIMIT + 5)
        )

        self.assertEqual(len(self._ids(batch=last_batch - 1)), POST_BATCH_SIZE)
        self.assertEqual(self._ids(batch=last_batch), [])

    def test_rows_carry_listing_fields(self):
        self._post(likes=1)
        [post] = self._get().json()
        for field in (Fields.author_username, Fields.caption, Fields.is_liked,
                      Fields.is_saved, Fields.comment_count, Fields.creation_time,
                      Fields.audience, Fields.tags):
            self.assertIn(field, post)
