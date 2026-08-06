import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import (
    BAN_TYPE_OUTRIGHT,
    BAN_TYPE_SHADOW,
    Fields,
    HIDDEN_REASON_CLASSIFIER,
    HIDDEN_REASON_CLASSIFIER_FINAL,
    HIDDEN_REASON_PENDING_CLASSIFICATION,
    POST_AUDIENCE_FAMILY,
    POST_AUDIENCE_FRIENDS,
    POST_AUDIENCE_FOLLOWING,
)
from ..models import Comment, CommentThread, Post, UserBan
from ..utils import get_compressed_image_url
from ..views import get_user_with_username


class PublicShareViewTests(PositiveOnlySocialTestCase):
    """
    The signed-out half of sharing (issue #381): a recipient with no account can
    read a shared post and its comments, but only when the content is genuinely
    public. Everything the moderation rules hide is reported as a 404 that is
    indistinguishable from a post that never existed, so these endpoints cannot
    be used to probe moderation state.
    """

    def setUp(self):
        super().setUp()

        self.author = self.make_user_with_prefix(prefix='author')
        self.commenter = self.make_user_with_prefix(prefix='commenter')
        self.author_user = get_user_with_username(self.author['username'])

        post_data = self._make_post(self.author[Fields.session_management_token])
        self.post_identifier = post_data[Fields.post_identifier]
        self.post = Post.objects.get(post_identifier=self.post_identifier)

        comment_data = self._comment_on_post(
            self.commenter[Fields.session_management_token], self.post_identifier)
        self.thread_identifier = comment_data[Fields.comment_thread_identifier]
        self.comment_identifier = comment_data[Fields.comment_identifier]
        self.comment = Comment.objects.get(comment_identifier=self.comment_identifier)

        self.details_url = self._details_url(self.post_identifier)
        self.comments_url = self._comments_url(self.post_identifier)
        self.thread_url = self._thread_url(self.thread_identifier)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _details_url(self, post_identifier):
        return reverse('get_public_post_details', kwargs={'post_identifier': str(post_identifier)})

    def _comments_url(self, post_identifier, batch=0):
        return reverse('get_public_comments_for_post',
                       kwargs={'post_identifier': str(post_identifier), 'batch': batch})

    def _thread_url(self, thread_identifier, batch=0):
        return reverse('get_public_comments_for_thread',
                       kwargs={'comment_thread_identifier': str(thread_identifier), 'batch': batch})

    def _assert_all_hidden(self, message):
        """Every public endpoint for this post (and its thread) 404s."""
        for url in (self.details_url, self.comments_url, self.thread_url):
            self.assertEqual(self.client.get(url).status_code, 404, msg=f"{message}: {url}")

    def _assert_all_visible(self, message):
        for url in (self.details_url, self.comments_url, self.thread_url):
            self.assertEqual(self.client.get(url).status_code, 200, msg=f"{message}: {url}")

    # =========================================================================
    # THE HAPPY PATH
    # =========================================================================

    def test_public_post_is_served_without_a_token(self):
        response = self.client.get(self.details_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[Fields.post_identifier], str(self.post_identifier))
        self.assertEqual(data[Fields.caption], self.post.caption)
        self.assertEqual(data[Fields.author_username], self.author['username'])
        # Without CloudFront configured the image URLs degrade exactly as they do
        # for a signed-in viewer: compressed-bucket swap plus the raw original.
        self.assertEqual(data[Fields.image_url], get_compressed_image_url(self.post.image_url))
        self.assertEqual(data[Fields.original_image_url], self.post.image_url)
        self.assertEqual(data[Fields.post_likes], 0)

    def test_public_post_omits_per_viewer_and_author_only_state(self):
        """There is no viewer, so there are no like/save/report flags to report,
        and the author-only classification fields must not leak either."""
        data = self.client.get(self.details_url).json()

        for field in (Fields.is_liked, Fields.is_saved, Fields.is_reported, Fields.report_reason,
                      Fields.status, Fields.hidden, Fields.hidden_reason, Fields.appealable):
            self.assertNotIn(field, data)

    def test_public_comments_expose_the_whole_thread(self):
        """A shared `#comment-<id>` link needs the conversation around it, so the
        public view serves the thread list and each thread's comments."""
        threads = self.client.get(self.comments_url).json()
        self.assertEqual([t[Fields.comment_thread_identifier] for t in threads],
                         [str(self.thread_identifier)])

        comments = self.client.get(self.thread_url).json()
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0][Fields.comment_identifier], str(self.comment_identifier))
        self.assertEqual(comments[0][Fields.body], self.comment.body)
        self.assertEqual(comments[0][Fields.author_username], self.commenter['username'])
        self.assertEqual(comments[0][Fields.comment_likes], 0)

    def test_public_comments_omit_per_viewer_state(self):
        comment = self.client.get(self.thread_url).json()[0]

        for field in (Fields.is_liked, Fields.is_reported, Fields.report_reason):
            self.assertNotIn(field, comment)

    def test_public_post_likes_count_reflects_real_likes(self):
        like_url = reverse('like_post', kwargs={'post_identifier': str(self.post_identifier)})
        header = {'HTTP_AUTHORIZATION': f"Bearer {self.commenter[Fields.session_management_token]}"}
        self.assertEqual(self.client.post(like_url, **header).status_code, 200)

        self.assertEqual(self.client.get(self.details_url).json()[Fields.post_likes], 1)

    # =========================================================================
    # MODERATION: WHAT MUST NEVER BE PUBLIC
    # =========================================================================

    def test_missing_post_returns_not_found(self):
        response = self.client.get(self._details_url(uuid.uuid4()))
        self.assertEqual(response.status_code, 404)

    def test_hidden_post_is_not_public(self):
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()

        self._assert_all_hidden("a hidden post")

    def test_pending_post_is_not_public(self):
        """A post still awaiting classification is author-only; the share link
        must not publish it before a decision is made."""
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_PENDING_CLASSIFICATION
        self.post.save()

        self._assert_all_hidden("a pending post")

    def test_final_rejection_tombstone_is_not_public(self):
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER_FINAL
        self.post.save()

        self._assert_all_hidden("a final-rejection tombstone")

    def test_shadow_banned_authors_post_is_not_public(self):
        UserBan.objects.create(user=self.author_user, ban_type=BAN_TYPE_SHADOW)

        self._assert_all_hidden("a shadow-banned author's post")

    def test_expired_shadow_ban_makes_the_post_public_again(self):
        UserBan.objects.create(
            user=self.author_user, ban_type=BAN_TYPE_SHADOW,
            expires=timezone.now() - timedelta(days=1))

        self._assert_all_visible("an expired shadow ban")

    def test_outright_ban_does_not_hide_the_post(self):
        """An outright ban stops the account from acting; it is not a content
        takedown, so it leaves the already-approved post visible — matching what
        signed-in viewers see."""
        UserBan.objects.create(user=self.author_user, ban_type=BAN_TYPE_OUTRIGHT)

        self._assert_all_visible("an outright-banned author's post")

    def test_restricted_audience_posts_are_not_public(self):
        for audience in (POST_AUDIENCE_FOLLOWING, POST_AUDIENCE_FRIENDS, POST_AUDIENCE_FAMILY):
            with self.subTest(audience=audience):
                Post.objects.filter(pk=self.post.pk).update(audience=audience)
                self._assert_all_hidden(f"an audience={audience} post")

    def test_verified_minors_post_is_not_public(self):
        """Adults and verified minors are mutually invisible (issue #329), and an
        anonymous visitor's age is unknown — so it sits in the adult band and a
        minor's post is never served to the open internet."""
        get_user_model().objects.filter(username=self.author['username']).update(
            identity_is_verified=True, is_adult=False)

        self._assert_all_hidden("a verified minor's post")

    def test_verified_adults_post_stays_public(self):
        get_user_model().objects.filter(username=self.author['username']).update(
            identity_is_verified=True, is_adult=True)

        self._assert_all_visible("a verified adult's post")

    def test_hidden_comment_is_dropped_from_a_public_thread(self):
        self.comment.hidden = True
        self.comment.save()

        # The post is still public, but the thread has nothing left to show.
        self.assertEqual(self.client.get(self.details_url).status_code, 200)
        self.assertEqual(self.client.get(self.comments_url).json(), [])
        self.assertEqual(self.client.get(self.thread_url).json(), [])

    def test_restricted_audience_comment_is_dropped_from_a_public_thread(self):
        Comment.objects.filter(pk=self.comment.pk).update(audience=POST_AUDIENCE_FRIENDS)

        self.assertEqual(self.client.get(self.comments_url).json(), [])
        self.assertEqual(self.client.get(self.thread_url).json(), [])

    def test_verified_minors_comment_is_dropped_from_a_public_post(self):
        """The age-band rule applies per author, so a minor's comment is no more
        public than a minor's post — even on an adult's public post."""
        get_user_model().objects.filter(username=self.commenter['username']).update(
            identity_is_verified=True, is_adult=False)

        self.assertEqual(self.client.get(self.details_url).status_code, 200)
        self.assertEqual(self.client.get(self.comments_url).json(), [])
        self.assertEqual(self.client.get(self.thread_url).json(), [])

    def test_shadow_banned_commenters_comment_is_dropped(self):
        UserBan.objects.create(
            user=get_user_with_username(self.commenter['username']), ban_type=BAN_TYPE_SHADOW)

        self.assertEqual(self.client.get(self.comments_url).json(), [])
        self.assertEqual(self.client.get(self.thread_url).json(), [])

    def test_thread_on_a_non_public_post_returns_not_found(self):
        """A leaked thread id must not become a back door into a restricted
        post's conversation."""
        Post.objects.filter(pk=self.post.pk).update(audience=POST_AUDIENCE_FRIENDS)

        self.assertEqual(self.client.get(self.thread_url).status_code, 404)

    def test_missing_thread_returns_not_found(self):
        self.assertEqual(self.client.get(self._thread_url(uuid.uuid4())).status_code, 404)

    # =========================================================================
    # THE ANSWER DOES NOT DEPEND ON WHO IS ASKING
    # =========================================================================

    def test_author_gets_the_same_public_answer_for_their_own_hidden_post(self):
        """The signed-in endpoints let an author see their own hidden post. The
        public endpoints resolve against a fixed anonymous viewer instead, so a
        logged-in browser and a crawler get identical bytes."""
        self.post.hidden = True
        self.post.hidden_reason = HIDDEN_REASON_CLASSIFIER
        self.post.save()

        header = {'HTTP_AUTHORIZATION': f"Bearer {self.author[Fields.session_management_token]}"}
        self.assertEqual(self.client.get(self.details_url, **header).status_code, 404)

        # ...while the authenticated endpoint still shows it to its author.
        private_url = reverse('get_post_details', kwargs={'post_identifier': str(self.post_identifier)})
        self.assertEqual(self.client.get(private_url, **header).status_code, 200)

    # =========================================================================
    # INPUT VALIDATION
    # =========================================================================

    def test_below_zero_batch_does_not_route(self):
        # The URL converter only accepts non-negative ints, so a below-zero batch
        # never routes; the guard in the view is the belt to that suspenders.
        self.assertEqual(self.client.get(f'/user_index/public/posts/{self.post_identifier}/comments/-1/').status_code,
                         404)

    def test_non_uuid_identifier_does_not_route(self):
        self.assertEqual(self.client.get('/user_index/public/posts/not-a-uuid/details/').status_code, 404)

    def test_post_method_not_allowed(self):
        """These are read-only endpoints."""
        self.assertEqual(self.client.post(self.details_url).status_code, 405)


class PublicShareThreadOrderingTests(PositiveOnlySocialTestCase):
    """Public threads/comments come back through the same ranking and batching
    the signed-in endpoints use, so a shared link shows the same conversation."""

    def setUp(self):
        super().setUp()
        self.make_many_comments_on_thread(num=3)
        self.post = Post.objects.get(post_identifier=self.post_identifier)
        self.thread = CommentThread.objects.get(
            comment_thread_identifier=self.comment_thread_identifier)

    def test_every_visible_comment_in_the_thread_is_served(self):
        url = reverse('get_public_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.comment_thread_identifier), 'batch': 0})

        comments = self.client.get(url).json()

        self.assertEqual(len(comments), self.thread.comment_set.count())

    def test_like_counts_are_not_inflated_by_the_audience_join(self):
        """The like count is computed off a clean queryset (mirroring
        get_comments_for_thread), so an author's follow edges cannot multiply
        it."""
        url = reverse('get_public_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.comment_thread_identifier), 'batch': 0})

        for comment in self.client.get(url).json():
            self.assertEqual(comment[Fields.comment_likes], 0)
