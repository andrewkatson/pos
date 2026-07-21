from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields
from ..models import Comment, Post, PostLike, PostReport
from ..views import get_user_with_username

report_reason = 'This is a negative post'

# Every field the clients need to render an actionable post row (issue #267):
# a like button that knows its own state, and a report/retract menu that knows
# whether the caller already has a report on file.
INTERACTION_FIELDS = (
    Fields.post_likes,
    Fields.is_liked,
    Fields.is_reported,
    Fields.report_reason,
)

# What a feed row displays alongside the author (issue #249): how many comments
# it has, and when it was posted.
DETAIL_FIELDS = (
    Fields.comment_count,
    Fields.creation_time,
)


class PostListingInteractionStateTests(PositiveOnlySocialTestCase):
    """The three post-listing endpoints carry the same like/report state as the
    post-details endpoint, so grids can be interacted with without first opening
    each post (issue #267).
    """

    def setUp(self):
        super().setUp()

        # The author, with a handful of posts.
        poster = self.make_user_with_posts(num_posts=3)
        self.poster_username = poster[Fields.username]
        self.poster_user = get_user_with_username(self.poster_username)

        # The viewer, who does the liking/reporting and fetches the listings.
        viewer = self.make_user_with_prefix('viewer')
        self.viewer_username = viewer['username']
        self.viewer_user = get_user_with_username(self.viewer_username)
        self.viewer_token = viewer[Fields.session_management_token]
        self.viewer_header = {'HTTP_AUTHORIZATION': f'Bearer {self.viewer_token}'}

        self.posts = list(self.poster_user.post_set.all())

    def _get_user_posts(self, header=None):
        url = reverse('get_posts_for_user', kwargs={
            'username': self.poster_username,
            'batch': 0
        })
        response = self.client.get(url, **(header or self.viewer_header))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _by_identifier(self, payload, post):
        match = [p for p in payload if p[Fields.post_identifier] == str(post.post_identifier)]
        self.assertEqual(len(match), 1)
        return match[0]

    def test_user_posts_include_interaction_fields(self):
        """Every row in a user's post grid carries the full interaction state."""
        payload = self._get_user_posts()

        self.assertEqual(len(payload), 3)
        for post in payload:
            for field in INTERACTION_FIELDS:
                self.assertIn(field, post)

    def test_unliked_unreported_post_reports_clean_state(self):
        """A post the caller hasn't touched comes back with zeroed-out state."""
        payload = self._get_user_posts()

        row = self._by_identifier(payload, self.posts[0])
        self.assertEqual(row[Fields.post_likes], 0)
        self.assertFalse(row[Fields.is_liked])
        self.assertFalse(row[Fields.is_reported])
        self.assertIsNone(row[Fields.report_reason])

    def test_liked_post_reports_like_state_and_count(self):
        """is_liked is true only for the caller's own like, and the count is total."""
        liked = self.posts[0]
        other = self.posts[1]

        # The viewer likes one post; the author likes a different one, so the
        # count and the caller-specific flag can't be conflated.
        PostLike.objects.create(user=self.viewer_user, post=liked)
        PostLike.objects.create(user=self.poster_user, post=liked)
        PostLike.objects.create(user=self.poster_user, post=other)

        payload = self._get_user_posts()

        liked_row = self._by_identifier(payload, liked)
        self.assertEqual(liked_row[Fields.post_likes], 2)
        self.assertTrue(liked_row[Fields.is_liked])

        other_row = self._by_identifier(payload, other)
        self.assertEqual(other_row[Fields.post_likes], 1)
        self.assertFalse(other_row[Fields.is_liked])

    def test_reported_post_reports_own_reason_only(self):
        """The reason returned is the caller's own, not another user's report."""
        reported = self.posts[0]
        PostReport.objects.create(user=self.viewer_user, post=reported, reason=report_reason)
        # A third party's report on a different post must not leak into the
        # caller's state for that post.
        third_party = self.make_user_with_prefix('third')
        PostReport.objects.create(
            user=get_user_with_username(third_party['username']),
            post=self.posts[1],
            reason='someone else reason',
        )

        payload = self._get_user_posts()

        reported_row = self._by_identifier(payload, reported)
        self.assertTrue(reported_row[Fields.is_reported])
        self.assertEqual(reported_row[Fields.report_reason], report_reason)

        untouched_row = self._by_identifier(payload, self.posts[1])
        self.assertFalse(untouched_row[Fields.is_reported])
        self.assertIsNone(untouched_row[Fields.report_reason])

    def test_feed_includes_interaction_fields(self):
        """The For You feed carries the same state as the profile grid."""
        liked = self.posts[0]
        PostLike.objects.create(user=self.viewer_user, post=liked)
        PostReport.objects.create(user=self.viewer_user, post=self.posts[1], reason=report_reason)

        url = reverse('get_posts_in_feed', kwargs={'batch': 0})
        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertTrue(payload)
        for post in payload:
            for field in INTERACTION_FIELDS:
                self.assertIn(field, post)

        liked_row = self._by_identifier(payload, liked)
        self.assertTrue(liked_row[Fields.is_liked])
        self.assertEqual(liked_row[Fields.post_likes], 1)

        reported_row = self._by_identifier(payload, self.posts[1])
        self.assertTrue(reported_row[Fields.is_reported])
        self.assertEqual(reported_row[Fields.report_reason], report_reason)

    def test_followed_posts_include_interaction_fields(self):
        """The Following feed carries the same state as the profile grid."""
        self.viewer_user.following.add(self.poster_user)
        liked = self.posts[0]
        PostLike.objects.create(user=self.viewer_user, post=liked)

        url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})
        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(len(payload), 3)
        for post in payload:
            for field in INTERACTION_FIELDS:
                self.assertIn(field, post)

        liked_row = self._by_identifier(payload, liked)
        self.assertTrue(liked_row[Fields.is_liked])
        self.assertEqual(liked_row[Fields.post_likes], 1)

    def test_listing_state_matches_post_details(self):
        """A row's state agrees with what the post-details endpoint reports, so
        opening a post never contradicts the grid the user just acted on."""
        post = self.posts[0]
        PostLike.objects.create(user=self.viewer_user, post=post)
        PostReport.objects.create(user=self.viewer_user, post=post, reason=report_reason)

        row = self._by_identifier(self._get_user_posts(), post)

        details_url = reverse('get_post_details', kwargs={
            'post_identifier': str(post.post_identifier)
        })
        details_response = self.client.get(details_url, **self.viewer_header)
        self.assertEqual(details_response.status_code, 200)
        details = details_response.json()

        for field in INTERACTION_FIELDS:
            self.assertEqual(row[field], details[field])

    def test_rows_include_comment_count_and_creation_time(self):
        """Feed/profile rows show a comment count and a post time (issue #249)."""
        payload = self._get_user_posts()

        for post in payload:
            for field in DETAIL_FIELDS:
                self.assertIn(field, post)

        # No comments yet, and a real timestamp to render "x ago" against.
        row = self._by_identifier(payload, self.posts[0])
        self.assertEqual(row[Fields.comment_count], 0)
        self.assertIsNotNone(row[Fields.creation_time])

    def test_comment_count_counts_every_comment_on_the_post(self):
        """The count spans all of a post's threads, not just the first."""
        commented = self.posts[0]

        # Two separate threads, one with a reply, so a per-thread count would
        # disagree with a per-post count.
        first = self._comment_on_post(self.viewer_token, str(commented.post_identifier))
        self._comment_on_post(self.viewer_token, str(commented.post_identifier))
        self._reply_to_comment_thread(
            self.viewer_token,
            str(commented.post_identifier),
            first[Fields.comment_thread_identifier],
        )

        row = self._by_identifier(self._get_user_posts(), commented)
        self.assertEqual(row[Fields.comment_count], 3)

        # A different post is unaffected.
        untouched = self._by_identifier(self._get_user_posts(), self.posts[1])
        self.assertEqual(untouched[Fields.comment_count], 0)

    def test_comment_count_excludes_hidden_comments(self):
        """A hidden comment isn't advertised to someone who can't see it."""
        commented = self.posts[0]
        self._comment_on_post(self.viewer_token, str(commented.post_identifier))
        hidden = self._comment_on_post(self.viewer_token, str(commented.post_identifier))
        Comment.objects.filter(
            comment_identifier=hidden[Fields.comment_identifier]
        ).update(hidden=True)

        # The author of a hidden comment still sees their own, so check with a
        # third party who should only see the one visible comment.
        third_party = self.make_user_with_prefix('viewer2')
        header = {
            'HTTP_AUTHORIZATION': f'Bearer {third_party[Fields.session_management_token]}'
        }
        row = self._by_identifier(self._get_user_posts(header), commented)
        self.assertEqual(row[Fields.comment_count], 1)

    def test_interaction_state_uses_constant_number_of_queries(self):
        """The state is gathered in grouped queries, so a bigger batch doesn't
        add a query per post (the N+1 the comments listing already avoids)."""
        url = reverse('get_posts_for_user', kwargs={
            'username': self.poster_username,
            'batch': 0
        })

        baseline = self._count_queries(url)

        # Five more posts, still inside one batch of POST_BATCH_SIZE (10). If the
        # state were gathered per post this count would climb with the batch.
        for index in range(5):
            Post.objects.create(author=self.poster_user, image_url=None, caption=f'another {index}')

        self.assertEqual(self._count_queries(url), baseline)

    def _count_queries(self, url):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url, **self.viewer_header)
            self.assertEqual(response.status_code, 200)
        return len(context.captured_queries)
