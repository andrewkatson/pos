import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ..constants import HIDDEN_REASON_NONE
from ..models import Post, InterestCategory
from ..feed_algorithm import feed_algorithm


@override_settings(RATELIMIT_ENABLE=False)
@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class FeedInterestWeightingTests(TestCase):
    """calculate_weights boosts posts whose interest buckets overlap the
    viewer's interests (issues #446/#35), and is a no-op when the viewer has
    none."""

    def setUp(self):
        User = get_user_model()
        self.viewer = User.objects.create_user(username='viewer', email='v@t.com')
        self.author = User.objects.create_user(username='author', email='a@t.com')
        self.nature = InterestCategory.objects.get(slug='nature')

    def _post(self, caption, categories=()):
        post = Post.objects.create(author=self.author, caption=caption,
                                   hidden=False, hidden_reason=HIDDEN_REASON_NONE)
        for slug in categories:
            post.interest_categories.add(InterestCategory.objects.get(slug=slug))
        return post

    def _ordered(self):
        return list(feed_algorithm.get_posts_weighted(self.viewer, Post))

    def test_matching_post_outranks_equivalent_nonmatching(self):
        # Two posts, same age and likes; only the matching one shares a bucket.
        plain = self._post("off topic")
        match = self._post("on topic", categories=['nature'])
        self.viewer.interest_categories.add(self.nature)

        ordered = self._ordered()
        self.assertEqual(ordered[0].pk, match.pk)
        self.assertGreater(ordered[0].score, ordered[1].score)
        self.assertEqual(ordered[1].pk, plain.pk)

    def test_no_interests_is_plain_hot_rank(self):
        # With no viewer interests both posts score identically (old behavior).
        self._post("off topic")
        self._post("on topic", categories=['nature'])
        scores = [round(p.score, 6) for p in self._ordered()]
        self.assertEqual(scores[0], scores[1])

    def test_more_overlap_scores_higher(self):
        one = self._post("one", categories=['nature'])
        two = self._post("two", categories=['nature', 'music'])
        self.viewer.interest_categories.add(
            self.nature, InterestCategory.objects.get(slug='music'))
        by_pk = {p.pk: p.score for p in self._ordered()}
        self.assertGreater(by_pk[two.pk], by_pk[one.pk])

    def test_like_count_unaffected_by_audience_join_fanout(self):
        # visible_posts' audience filter LEFT JOINs the author's following_set,
        # which fans out (see visibility._audience_q). A non-distinct COUNT
        # counted each like once per follow edge, so an author who follows many
        # people had their posts scored as if they had many times the likes.
        from ..models import PostLike, UserFollow
        from ..visibility import visible_posts
        from ..constants import FOLLOW_CATEGORY_FRIEND, POST_AUDIENCE_PUBLIC

        User = get_user_model()
        for i in range(4):
            other = User.objects.create_user(username=f'followed{i}', email=f'f{i}@t.com')
            UserFollow.objects.create(user_from=self.author, user_to=other,
                                      category=FOLLOW_CATEGORY_FRIEND)
        # An edge to the viewer too, so the audience OR branch actually matches.
        UserFollow.objects.create(user_from=self.author, user_to=self.viewer,
                                  category=FOLLOW_CATEGORY_FRIEND)

        post = self._post("public post")
        post.audience = POST_AUDIENCE_PUBLIC
        post.save(update_fields=['audience'])
        liker = User.objects.create_user(username='onlyliker', email='ol@t.com')
        PostLike.objects.create(user=liker, post=post)

        ranked = visible_posts(feed_algorithm.get_posts_weighted(self.viewer, Post), self.viewer)
        by_pk = {p.pk: p for p in ranked}
        self.assertEqual(by_pk[post.pk].like_count, 1)

    def test_like_count_unaffected_by_interest_join(self):
        # The interest subquery must not multiply the like_count aggregate.
        from ..models import PostLike
        liker = get_user_model().objects.create_user(username='liker', email='l@t.com')
        liker2 = get_user_model().objects.create_user(username='liker2', email='l2@t.com')
        post = self._post("nature post", categories=['nature'])
        PostLike.objects.create(user=liker, post=post)
        PostLike.objects.create(user=liker2, post=post)
        self.viewer.interest_categories.add(self.nature)
        ranked = {p.pk: p for p in self._ordered()}
        self.assertEqual(ranked[post.pk].like_count, 2)
