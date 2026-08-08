"""Tests for the "who liked this" listings (issue #478).

Both endpoints are owner-only: a user may look at the likers of their own post
or comment, and asking about somebody else's is answered exactly like asking
about one that does not exist.
"""
from unittest.mock import patch

from django.urls import reverse

from ..constants import BAN_TYPE_SHADOW, Fields
from ..models import CommentLike, PositiveOnlySocialUser, PostLike, UserBan
from .test_parent_case import PositiveOnlySocialTestCase


def _make_liker(name):
    """A bare account used only as the subject of a like row."""
    return PositiveOnlySocialUser.objects.create_user(
        username=name, email=f'{name}@email.com', password='LikerPassword123-')


class GetPostLikersViewTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        # User 0 makes the post and is the only account allowed to see who
        # liked it; user 1 is an unrelated signed-in account.
        super().make_post_with_users(2)

        self.author_header = {'HTTP_AUTHORIZATION': f'Bearer {self.session_management_token}'}
        self.other_header = {'HTTP_AUTHORIZATION': f'Bearer {self.users["token"][1]}'}

        self.url = reverse('get_post_likers',
                           kwargs={'post_identifier': str(self.post_identifier), 'batch': 0})

    def _like(self, name):
        liker = _make_liker(self._get_unique_username(name))
        PostLike.objects.create(user=liker, post=self.post)
        return liker

    def test_requires_authentication(self):
        """An unauthenticated request is rejected before any lookup."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_post_with_no_likes_returns_empty_list(self):
        """A post nobody liked yields an empty list rather than an error."""
        response = self.client.get(self.url, **self.author_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_likers_returned_most_recent_first(self):
        """Every liker is listed, newest like first, with the fields a row needs."""
        first = self._like('early_liker')
        second = self._like('later_liker')

        response = self.client.get(self.url, **self.author_header)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([user[Fields.username] for user in body],
                         [second.username, first.username])
        for user in body:
            self.assertIn(Fields.identity_is_verified, user)
            self.assertIn(Fields.author_profile_image_url, user)
            self.assertIn(Fields.author_profile_image_original_url, user)

    def test_another_users_post_is_reported_as_missing(self):
        """A signed-in user cannot read the likers of a post they did not write."""
        self._like('some_liker')

        response = self.client.get(self.url, **self.other_header)

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_unknown_post_returns_bad_response(self):
        """A well-formed identifier for a post that does not exist is a 400."""
        url = reverse('get_post_likers',
                      kwargs={'post_identifier': '11111111-1111-4111-8111-111111111111', 'batch': 0})

        response = self.client.get(url, **self.author_header)

        self.assertEqual(response.status_code, 400)

    def test_malformed_post_identifier_returns_bad_response(self):
        """A non-uuid identifier does not match the route at all."""
        response = self.client.get('/posts/?/likes/0/', **self.author_header)

        self.assertEqual(response.status_code, 404)

    def test_shadow_banned_liker_excluded(self):
        """A shadow-banned account is hidden from everyone but itself, so its
        like is not attributed to it here even though it still counts."""
        hidden = self._like('shadow_liker')
        visible = self._like('plain_liker')
        UserBan.objects.create(user=hidden, ban_type=BAN_TYPE_SHADOW)

        response = self.client.get(self.url, **self.author_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([user[Fields.username] for user in response.json()],
                         [visible.username])

    def test_cross_age_band_liker_excluded(self):
        """A liker outside the author's age band is never revealed (issue #329):
        the two bands are mutually invisible."""
        minor = self._like('minor_liker')
        PositiveOnlySocialUser.objects.filter(pk=minor.pk).update(
            identity_is_verified=True, is_adult=False)
        same_band = self._like('same_band_liker')

        response = self.client.get(self.url, **self.author_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([user[Fields.username] for user in response.json()],
                         [same_band.username])

    def test_blocked_liker_excluded(self):
        """A block hides the account in both directions, matching every other
        listing."""
        i_blocked = self._like('blocked_liker')
        blocked_me = self._like('blocking_liker')
        remaining = self._like('ordinary_liker')
        self.post.author.blocked.add(i_blocked)
        blocked_me.blocked.add(self.post.author)

        response = self.client.get(self.url, **self.author_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([user[Fields.username] for user in response.json()],
                         [remaining.username])

    @patch('user_system.views.LIKE_BATCH_SIZE', 2)
    def test_likers_are_batched(self):
        """Batches partition the list without dropping or repeating a liker, and
        a batch past the end is empty."""
        likers = [self._like(f'batched_liker_{index}') for index in range(5)]
        newest_first = [liker.username for liker in reversed(likers)]

        pages = []
        for batch in range(4):
            url = reverse('get_post_likers',
                          kwargs={'post_identifier': str(self.post_identifier), 'batch': batch})
            response = self.client.get(url, **self.author_header)
            self.assertEqual(response.status_code, 200)
            pages.append([user[Fields.username] for user in response.json()])

        self.assertEqual(pages, [newest_first[0:2], newest_first[2:4], newest_first[4:5], []])


class GetCommentLikersViewTests(PositiveOnlySocialTestCase):

    def setUp(self):
        super().setUp()
        # User 0 makes the post, user 1 writes the comment. The comment's author
        # — not the post's — is the one entitled to its likers.
        super().comment_on_post_with_users(2)

        self.commenter_header = {
            'HTTP_AUTHORIZATION': f'Bearer {self.commenter_session_management_token}'}
        self.post_author_header = {'HTTP_AUTHORIZATION': f'Bearer {self.users["token"][0]}'}

        self.url = self._url(0)

    def _url(self, batch):
        return reverse('get_comment_likers', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': str(self.comment_identifier),
            'batch': batch,
        })

    def _like(self, name):
        liker = _make_liker(self._get_unique_username(name))
        CommentLike.objects.create(user=liker, comment=self.comment)
        return liker

    def test_requires_authentication(self):
        """An unauthenticated request is rejected before any lookup."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_comment_with_no_likes_returns_empty_list(self):
        """A comment nobody liked yields an empty list rather than an error."""
        response = self.client.get(self.url, **self.commenter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_likers_returned_most_recent_first(self):
        """Every liker is listed, newest like first."""
        first = self._like('early_liker')
        second = self._like('later_liker')

        response = self.client.get(self.url, **self.commenter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([user[Fields.username] for user in response.json()],
                         [second.username, first.username])

    def test_post_author_cannot_read_someone_elses_comment_likers(self):
        """Owning the post is not owning the comment: only the comment's author
        may see who liked it."""
        self._like('some_liker')

        response = self.client.get(self.url, **self.post_author_header)

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_unknown_comment_returns_bad_response(self):
        """A well-formed identifier for a comment that does not exist is a 400."""
        url = reverse('get_comment_likers', kwargs={
            'post_identifier': str(self.post_identifier),
            'comment_thread_identifier': str(self.comment_thread_identifier),
            'comment_identifier': '11111111-1111-4111-8111-111111111111',
            'batch': 0,
        })

        response = self.client.get(url, **self.commenter_header)

        self.assertEqual(response.status_code, 400)

    def test_shadow_banned_liker_excluded(self):
        """Shadow-ban semantics apply to comment likers exactly as to post ones."""
        hidden = self._like('shadow_liker')
        visible = self._like('plain_liker')
        UserBan.objects.create(user=hidden, ban_type=BAN_TYPE_SHADOW)

        response = self.client.get(self.url, **self.commenter_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([user[Fields.username] for user in response.json()],
                         [visible.username])

    @patch('user_system.views.LIKE_BATCH_SIZE', 2)
    def test_likers_are_batched(self):
        """Batches partition the list without dropping or repeating a liker."""
        likers = [self._like(f'batched_liker_{index}') for index in range(3)]
        newest_first = [liker.username for liker in reversed(likers)]

        pages = []
        for batch in range(3):
            response = self.client.get(self._url(batch), **self.commenter_header)
            self.assertEqual(response.status_code, 200)
            pages.append([user[Fields.username] for user in response.json()])

        self.assertEqual(pages, [newest_first[0:2], newest_first[2:3], []])
