from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import BAN_TYPE_SHADOW, Fields
from ..models import Post, UserBan
from ..views import get_user_with_username


class ShadowBanVisibilityTests(PositiveOnlySocialTestCase):
    """
    Tests that content authored by a shadow-banned user (and content hidden
    by reports) is invisible to everyone except its author.
    """

    def setUp(self):
        super().setUp()

        # The poster will be shadow banned; the viewer is an ordinary user.
        self.poster = self.make_user_with_prefix(prefix='poster')
        self.viewer = self.make_user_with_prefix(prefix='viewer')

        self.poster_user = get_user_with_username(self.poster['username'])
        self.viewer_user = get_user_with_username(self.viewer['username'])

        self.poster_header = {'HTTP_AUTHORIZATION': f"Bearer {self.poster[Fields.session_management_token]}"}
        self.viewer_header = {'HTTP_AUTHORIZATION': f"Bearer {self.viewer[Fields.session_management_token]}"}

        post_data = self._make_post(self.poster[Fields.session_management_token])
        self.post_identifier = post_data[Fields.post_identifier]
        self.post = Post.objects.get(post_identifier=self.post_identifier)

    def _shadow_ban_poster(self, expires=None):
        return UserBan.objects.create(user=self.poster_user, ban_type=BAN_TYPE_SHADOW, expires=expires)

    def _get_feed(self, header):
        url = reverse('get_posts_in_feed', kwargs={'batch': 0})
        response = self.client.get(url, **header)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _get_posts_for_user(self, username, header):
        url = reverse('get_posts_for_user', kwargs={'username': username, 'batch': 0})
        response = self.client.get(url, **header)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _feed_post_ids(self, header):
        return [entry[Fields.post_identifier] for entry in self._get_feed(header)]

    # =========================================================================
    # POSTS
    # =========================================================================

    def test_shadow_banned_post_not_in_feed(self):
        self.assertIn(self.post_identifier, self._feed_post_ids(self.viewer_header))

        self._shadow_ban_poster()

        self.assertNotIn(self.post_identifier, self._feed_post_ids(self.viewer_header))

    def test_shadow_banned_user_still_sees_own_posts(self):
        self._shadow_ban_poster()

        posts = self._get_posts_for_user(self.poster['username'], self.poster_header)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][Fields.post_identifier], self.post_identifier)

    def test_shadow_banned_user_profile_posts_empty_for_others(self):
        self._shadow_ban_poster()

        posts = self._get_posts_for_user(self.poster['username'], self.viewer_header)
        self.assertEqual(posts, [])

    def test_shadow_banned_post_not_in_followed_feed(self):
        follow_url = reverse('follow_user', kwargs={'username_to_follow': self.poster['username']})
        response = self.client.post(follow_url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)

        followed_url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})
        response = self.client.get(followed_url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        self._shadow_ban_poster()

        response = self.client.get(followed_url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_shadow_banned_post_details_hidden_from_others_but_not_author(self):
        self._shadow_ban_poster()

        url = reverse('get_post_details', kwargs={'post_identifier': self.post_identifier})

        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 400)

        response = self.client.get(url, **self.poster_header)
        self.assertEqual(response.status_code, 200)

    def test_expired_shadow_ban_restores_visibility(self):
        self._shadow_ban_poster(expires=timezone.now() - timedelta(days=1))

        self.assertIn(self.post_identifier, self._feed_post_ids(self.viewer_header))

    # =========================================================================
    # HIDDEN CONTENT (report threshold)
    # =========================================================================

    def test_hidden_post_not_in_feed_but_author_still_sees_it(self):
        self.post.hidden = True
        self.post.save()

        self.assertNotIn(self.post_identifier, self._feed_post_ids(self.viewer_header))

        posts = self._get_posts_for_user(self.poster['username'], self.poster_header)
        self.assertEqual(len(posts), 1)

        details_url = reverse('get_post_details', kwargs={'post_identifier': self.post_identifier})
        response = self.client.get(details_url, **self.viewer_header)
        self.assertEqual(response.status_code, 400)

    # =========================================================================
    # COMMENTS
    # =========================================================================

    def test_shadow_banned_comment_invisible_to_others_but_not_author(self):
        # The thread must live on the *viewer's* post: a thread on the
        # banned user's own post would vanish along with the post itself.
        post_data = self._make_post(self.viewer[Fields.session_management_token])
        viewer_post_identifier = post_data[Fields.post_identifier]
        comment_data = self._comment_on_post(
            self.viewer[Fields.session_management_token], viewer_post_identifier)
        thread_identifier = comment_data[Fields.comment_thread_identifier]

        # The poster replies on the viewer's thread and is then shadow banned.
        self._reply_to_comment_thread(
            self.poster[Fields.session_management_token], viewer_post_identifier, thread_identifier)
        self._shadow_ban_poster()

        url = reverse('get_comments_for_thread', kwargs={
            'comment_thread_identifier': thread_identifier, 'batch': 0})

        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        authors = [comment[Fields.author_username] for comment in response.json()]
        self.assertNotIn(self.poster['username'], authors)
        self.assertIn(self.viewer['username'], authors)

        response = self.client.get(url, **self.poster_header)
        self.assertEqual(response.status_code, 200)
        authors = [comment[Fields.author_username] for comment in response.json()]
        self.assertIn(self.poster['username'], authors)

    def test_thread_with_only_shadow_banned_comments_excluded(self):
        # The viewer makes a post; the (about to be banned) poster starts the
        # only thread on it.
        post_data = self._make_post(self.viewer[Fields.session_management_token])
        viewer_post_identifier = post_data[Fields.post_identifier]
        self._comment_on_post(
            self.poster[Fields.session_management_token], viewer_post_identifier)

        url = reverse('get_comments_for_post', kwargs={
            'post_identifier': viewer_post_identifier, 'batch': 0})

        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(len(response.json()), 1)

        self._shadow_ban_poster()

        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.json(), [])

        # The banned user still sees their own thread.
        response = self.client.get(url, **self.poster_header)
        self.assertEqual(len(response.json()), 1)

    # =========================================================================
    # SEARCH & PROFILE
    # =========================================================================

    def test_shadow_banned_user_excluded_from_search(self):
        fragment = self.poster['username'][:10]
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': fragment})

        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        usernames = [user[Fields.username] for user in response.json()]
        self.assertIn(self.poster['username'], usernames)

        self._shadow_ban_poster()

        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        usernames = [user[Fields.username] for user in response.json()]
        self.assertNotIn(self.poster['username'], usernames)

    def test_profile_post_count_reflects_visibility(self):
        self._shadow_ban_poster()

        url = reverse('get_profile_details', kwargs={'username': self.poster['username']})

        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.post_count], 0)

        response = self.client.get(url, **self.poster_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.post_count], 1)
