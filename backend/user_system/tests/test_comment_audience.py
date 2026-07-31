import ast
import json
import os
from unittest.mock import patch

from django.urls import reverse

from .test_relationship_categories import RelationshipCategoryTestBase, POSITIVE_CAPTION
from ..constants import (
    Fields,
    FOLLOW_CATEGORY_FOLLOWING,
    FOLLOW_CATEGORY_FRIEND,
    FOLLOW_CATEGORY_FAMILY,
    POST_AUDIENCE_PUBLIC,
    POST_AUDIENCE_FOLLOWING,
    POST_AUDIENCE_FRIENDS,
    POST_AUDIENCE_FAMILY,
)
from ..models import Comment, PositiveOnlySocialUser


class CommentAudienceTestBase(RelationshipCategoryTestBase):
    """Shared setup: a public post by the author hosting a comment thread, so a
    comment's own audience — not the post's — is what is under test."""

    def setUp(self):
        super().setUp()
        self.post = self._make_visible_post(self.author, POST_AUDIENCE_PUBLIC)
        self.thread = self.post.commentthread_set.create()

    def _make_comment(self, author, audience=POST_AUDIENCE_PUBLIC, thread=None,
                      body=POSITIVE_CAPTION):
        """A live (non-hidden) comment, created directly so the classifier is
        not involved."""
        thread = thread or self.thread
        return thread.comment_set.create(
            author=author, body=body, hidden=False, audience=audience)

    def _thread_comment_ids(self, header, category=None):
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.thread.comment_thread_identifier),
            'batch': 0,
        })
        if category:
            url = f'{url}?{Fields.category}={category}'
        response = self.client.get(url, **header)
        self.assertEqual(response.status_code, 200)
        return {c[Fields.comment_identifier] for c in response.json()}


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class CommentOnPostAudienceTests(CommentAudienceTestBase):
    """comment_on_post / reply_to_comment_thread accept and store an audience.
    TESTING=True makes the classifier approve the positive body so the endpoint
    reaches the create path (mirroring test_comment_on_post_view)."""

    def _comment(self, audience_value):
        url = reverse('comment_on_post', kwargs={'post_identifier': str(self.post.post_identifier)})
        data = {Fields.comment_text: POSITIVE_CAPTION}
        if audience_value is not None:
            data[Fields.audience] = audience_value
        return self.client.post(
            url, data=json.dumps(data), content_type='application/json',
            **self.author_header)

    def _reply(self, audience_value):
        url = reverse('reply_to_comment_thread', kwargs={
            'post_identifier': str(self.post.post_identifier),
            'comment_thread_identifier': str(self.thread.comment_thread_identifier),
        })
        data = {Fields.comment_text: POSITIVE_CAPTION}
        if audience_value is not None:
            data[Fields.audience] = audience_value
        return self.client.post(
            url, data=json.dumps(data), content_type='application/json',
            **self.author_header)

    def test_comment_audience_defaults_to_public(self):
        response = self._comment(None)
        self.assertEqual(response.status_code, 201)
        comment = Comment.objects.get(comment_identifier=response.json()[Fields.comment_identifier])
        self.assertEqual(comment.audience, POST_AUDIENCE_PUBLIC)

    def test_comment_valid_audience_stored(self):
        for audience in (POST_AUDIENCE_FOLLOWING, POST_AUDIENCE_FRIENDS, POST_AUDIENCE_FAMILY):
            with self.subTest(audience=audience):
                response = self._comment(audience)
                self.assertEqual(response.status_code, 201)
                comment = Comment.objects.get(comment_identifier=response.json()[Fields.comment_identifier])
                self.assertEqual(comment.audience, audience)

    def test_comment_invalid_audience_rejected(self):
        response = self._comment('everyone_i_dislike')
        self.assertEqual(response.status_code, 400)
        # No comment persisted for the rejected request (only the setUp thread
        # exists, which has no comments).
        self.assertFalse(Comment.objects.filter(comment_thread=self.thread).exists())

    def test_reply_valid_audience_stored(self):
        response = self._reply(POST_AUDIENCE_FAMILY)
        self.assertEqual(response.status_code, 201)
        comment = Comment.objects.get(comment_identifier=response.json()[Fields.comment_identifier])
        self.assertEqual(comment.audience, POST_AUDIENCE_FAMILY)

    def test_reply_invalid_audience_rejected(self):
        response = self._reply('nope')
        self.assertEqual(response.status_code, 400)


class CommentAudienceVisibilityTests(CommentAudienceTestBase):
    """The nested-circle rule enforced for comments by visibility.visible_comments
    via get_comments_for_thread. A comment by the author reaches the viewer only
    when the author has labeled the viewer closely enough."""

    def _viewer_sees(self, comment):
        return str(comment.comment_identifier) in self._thread_comment_ids(self.viewer_header)

    def test_public_comment_visible_to_stranger(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_PUBLIC)
        self.assertTrue(self._viewer_sees(comment))

    def test_following_comment_hidden_from_unlabeled_viewer(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_FOLLOWING)
        self.assertFalse(self._viewer_sees(comment))

    def test_following_comment_visible_to_any_labeled_viewer(self):
        self._label(self.author, self.viewer, FOLLOW_CATEGORY_FOLLOWING)
        comment = self._make_comment(self.author, POST_AUDIENCE_FOLLOWING)
        self.assertTrue(self._viewer_sees(comment))

    def test_friends_comment_visible_to_friend_and_family_not_following(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_FRIENDS)

        edge = self._label(self.author, self.viewer, FOLLOW_CATEGORY_FOLLOWING)
        self.assertFalse(self._viewer_sees(comment))

        edge.category = FOLLOW_CATEGORY_FRIEND
        edge.save(update_fields=['category'])
        self.assertTrue(self._viewer_sees(comment))

        edge.category = FOLLOW_CATEGORY_FAMILY
        edge.save(update_fields=['category'])
        self.assertTrue(self._viewer_sees(comment))

    def test_family_comment_visible_only_to_family(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_FAMILY)

        edge = self._label(self.author, self.viewer, FOLLOW_CATEGORY_FRIEND)
        self.assertFalse(self._viewer_sees(comment))

        edge.category = FOLLOW_CATEGORY_FAMILY
        edge.save(update_fields=['category'])
        self.assertTrue(self._viewer_sees(comment))

    def test_author_always_sees_own_restricted_comment(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_FAMILY)
        ids = self._thread_comment_ids(self.author_header)
        self.assertIn(str(comment.comment_identifier), ids)

    def test_restricted_comment_thread_hidden_from_get_comments_for_post(self):
        """A thread whose only comment is audience-restricted away is not listed
        for the excluded viewer (visible_comment_threads applies the same rule),
        but the author still sees it."""
        self._make_comment(self.author, POST_AUDIENCE_FAMILY)
        url = reverse('get_comments_for_post', kwargs={
            'post_identifier': str(self.post.post_identifier), 'batch': 0,
        })

        viewer_resp = self.client.get(url, **self.viewer_header)
        self.assertEqual(viewer_resp.status_code, 200)
        self.assertEqual(viewer_resp.json(), [])

        author_resp = self.client.get(url, **self.author_header)
        self.assertEqual(author_resp.status_code, 200)
        author_thread_ids = {t[Fields.comment_thread_identifier] for t in author_resp.json()}
        self.assertIn(str(self.thread.comment_thread_identifier), author_thread_ids)


class CommentCategoryFilterTests(CommentAudienceTestBase):
    """?category= narrows the comment list to that exact group — the same toggle
    the following feed offers. The viewer follows two commenters it labels
    differently, each with one public comment on the thread."""

    def setUp(self):
        super().setUp()

        family_fields = self.make_user_with_prefix(prefix='cfam')
        self.family_commenter = PositiveOnlySocialUser.objects.get(username=family_fields[Fields.username])
        friend_fields = self.make_user_with_prefix(prefix='cfri')
        self.friend_commenter = PositiveOnlySocialUser.objects.get(username=friend_fields[Fields.username])

        self._label(self.viewer, self.family_commenter, FOLLOW_CATEGORY_FAMILY)
        self._label(self.viewer, self.friend_commenter, FOLLOW_CATEGORY_FRIEND)

        self.family_comment = self._make_comment(self.family_commenter, POST_AUDIENCE_PUBLIC)
        self.friend_comment = self._make_comment(self.friend_commenter, POST_AUDIENCE_PUBLIC)

    def test_unfiltered_has_both(self):
        ids = self._thread_comment_ids(self.viewer_header)
        self.assertIn(str(self.family_comment.comment_identifier), ids)
        self.assertIn(str(self.friend_comment.comment_identifier), ids)

    def test_family_filter_only_family(self):
        ids = self._thread_comment_ids(self.viewer_header, FOLLOW_CATEGORY_FAMILY)
        self.assertIn(str(self.family_comment.comment_identifier), ids)
        self.assertNotIn(str(self.friend_comment.comment_identifier), ids)

    def test_friend_filter_only_friend(self):
        ids = self._thread_comment_ids(self.viewer_header, FOLLOW_CATEGORY_FRIEND)
        self.assertIn(str(self.friend_comment.comment_identifier), ids)
        self.assertNotIn(str(self.family_comment.comment_identifier), ids)

    def test_filter_excludes_viewers_own_comment(self):
        """The exact-category filter drops your own comments (you do not follow
        yourself), matching the followed-feed toggle."""
        own = self._make_comment(self.viewer, POST_AUDIENCE_PUBLIC)
        unfiltered = self._thread_comment_ids(self.viewer_header)
        self.assertIn(str(own.comment_identifier), unfiltered)
        filtered = self._thread_comment_ids(self.viewer_header, FOLLOW_CATEGORY_FAMILY)
        self.assertNotIn(str(own.comment_identifier), filtered)

    def test_invalid_category_filter_rejected(self):
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.thread.comment_thread_identifier),
            'batch': 0,
        })
        response = self.client.get(f'{url}?{Fields.category}=nope', **self.viewer_header)
        self.assertEqual(response.status_code, 400)

    def test_empty_category_filter_returns_full(self):
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.thread.comment_thread_identifier),
            'batch': 0,
        })
        response = self.client.get(f'{url}?{Fields.category}=', **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        ids = {c[Fields.comment_identifier] for c in response.json()}
        self.assertIn(str(self.family_comment.comment_identifier), ids)
        self.assertIn(str(self.friend_comment.comment_identifier), ids)

    def test_get_comments_for_post_category_filter_narrows_threads(self):
        """The thread-listing endpoint applies the same toggle: a family filter
        keeps only threads with a visible family-labeled comment."""
        # A second thread whose only comment is by the friend commenter.
        friend_thread = self.post.commentthread_set.create()
        self._make_comment(self.friend_commenter, POST_AUDIENCE_PUBLIC, thread=friend_thread)

        url = reverse('get_comments_for_post', kwargs={
            'post_identifier': str(self.post.post_identifier), 'batch': 0,
        })
        response = self.client.get(f'{url}?{Fields.category}={FOLLOW_CATEGORY_FAMILY}', **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        thread_ids = {t[Fields.comment_thread_identifier] for t in response.json()}
        # The setUp thread has a family comment; the friend-only thread does not.
        self.assertIn(str(self.thread.comment_thread_identifier), thread_ids)
        self.assertNotIn(str(friend_thread.comment_thread_identifier), thread_ids)

    def test_serialized_comment_carries_audience(self):
        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': str(self.thread.comment_thread_identifier),
            'batch': 0,
        })
        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        audiences = {c[Fields.audience] for c in response.json()}
        self.assertEqual(audiences, {POST_AUDIENCE_PUBLIC})


class CommentAudienceInteractionGateTests(CommentAudienceTestBase):
    """A comment whose audience excludes the caller is treated as absent for
    likes and reports, so a restricted comment cannot be reached by a known id."""

    def _like(self, comment):
        url = reverse('like_comment', kwargs={
            'post_identifier': str(self.post.post_identifier),
            'comment_thread_identifier': str(self.thread.comment_thread_identifier),
            'comment_identifier': str(comment.comment_identifier),
        })
        return self.client.post(url, **self.viewer_header)

    def _report(self, comment):
        url = reverse('report_comment', kwargs={
            'post_identifier': str(self.post.post_identifier),
            'comment_thread_identifier': str(self.thread.comment_thread_identifier),
            'comment_identifier': str(comment.comment_identifier),
        })
        return self.client.post(
            url, data=json.dumps({Fields.reason: 'spam'}),
            content_type='application/json', **self.viewer_header)

    def test_cannot_like_comment_audience_excludes_viewer(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_FAMILY)
        response = self._like(comment)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Comment not found', ast.literal_eval(response.content.decode())['error'])
        self.assertEqual(comment.commentlike_set.count(), 0)

    def test_can_like_comment_when_labeled_close_enough(self):
        self._label(self.author, self.viewer, FOLLOW_CATEGORY_FAMILY)
        comment = self._make_comment(self.author, POST_AUDIENCE_FAMILY)
        response = self._like(comment)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(comment.commentlike_set.count(), 1)

    def test_cannot_report_comment_audience_excludes_viewer(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_FAMILY)
        response = self._report(comment)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(comment.commentreport_set.count(), 0)

    def test_public_comment_still_likeable(self):
        comment = self._make_comment(self.author, POST_AUDIENCE_PUBLIC)
        response = self._like(comment)
        self.assertEqual(response.status_code, 200)
