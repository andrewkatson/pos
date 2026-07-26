import ast
import json

from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
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
from ..models import Post, PositiveOnlySocialUser, UserFollow

POSITIVE_CAPTION = "what a lovely and positive day this is"


class RelationshipCategoryTestBase(PositiveOnlySocialTestCase):
    """Shared setup: an authenticated author (A) and a viewer (B)."""

    def setUp(self):
        super().setUp()

        super().register_user_and_setup_local_fields()
        self.author = PositiveOnlySocialUser.objects.get(username=self.local_username)
        self.author_token = self.session_management_token
        self.author_header = {'HTTP_AUTHORIZATION': f'Bearer {self.author_token}'}

        viewer_fields = self.make_user_with_prefix(prefix='viewer')
        self.viewer_username = viewer_fields[Fields.username]
        self.viewer = PositiveOnlySocialUser.objects.get(username=self.viewer_username)
        self.viewer_token = viewer_fields[Fields.session_management_token]
        self.viewer_header = {'HTTP_AUTHORIZATION': f'Bearer {self.viewer_token}'}

    def _make_visible_post(self, author, audience=POST_AUDIENCE_PUBLIC):
        """A live (already-classified, visible) post, created directly so the
        async classifier is not involved."""
        return Post.objects.create(
            author=author, caption=POSITIVE_CAPTION, image_url=None,
            hidden=False, audience=audience)

    def _label(self, follower, followee, category):
        return UserFollow.objects.create(
            user_from=follower, user_to=followee, category=category)


class FollowWithCategoryTests(RelationshipCategoryTestBase):

    def test_follow_defaults_to_following_category(self):
        url = reverse('follow_user', kwargs={'username_to_follow': self.viewer_username})
        response = self.client.post(url, **self.author_header)

        self.assertEqual(response.status_code, 200)
        edge = UserFollow.objects.get(user_from=self.author, user_to=self.viewer)
        self.assertEqual(edge.category, FOLLOW_CATEGORY_FOLLOWING)

    def test_follow_with_explicit_category(self):
        url = reverse('follow_user', kwargs={'username_to_follow': self.viewer_username})
        response = self.client.post(
            url, data=json.dumps({Fields.category: FOLLOW_CATEGORY_FAMILY}),
            content_type='application/json', **self.author_header)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[Fields.follow_category], FOLLOW_CATEGORY_FAMILY)
        edge = UserFollow.objects.get(user_from=self.author, user_to=self.viewer)
        self.assertEqual(edge.category, FOLLOW_CATEGORY_FAMILY)

    def test_follow_with_invalid_category_rejected(self):
        url = reverse('follow_user', kwargs={'username_to_follow': self.viewer_username})
        response = self.client.post(
            url, data=json.dumps({Fields.category: 'acquaintance'}),
            content_type='application/json', **self.author_header)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid category', ast.literal_eval(response.content.decode())['error'])
        self.assertFalse(UserFollow.objects.filter(user_from=self.author, user_to=self.viewer).exists())


class SetFollowCategoryTests(RelationshipCategoryTestBase):

    def setUp(self):
        super().setUp()
        # Author already follows viewer (plain following) so there is an edge
        # to re-categorize.
        self._label(self.author, self.viewer, FOLLOW_CATEGORY_FOLLOWING)
        self.url = reverse('set_follow_category', kwargs={'username': self.viewer_username})

    def test_set_category_success(self):
        response = self.client.post(
            self.url, data=json.dumps({Fields.category: FOLLOW_CATEGORY_FRIEND}),
            content_type='application/json', **self.author_header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[Fields.follow_category], FOLLOW_CATEGORY_FRIEND)
        edge = UserFollow.objects.get(user_from=self.author, user_to=self.viewer)
        self.assertEqual(edge.category, FOLLOW_CATEGORY_FRIEND)

    def test_set_category_requires_existing_follow(self):
        # A third user the author does NOT follow.
        stranger = self.make_user_with_prefix(prefix='stranger')[Fields.username]
        url = reverse('set_follow_category', kwargs={'username': stranger})
        response = self.client.post(
            url, data=json.dumps({Fields.category: FOLLOW_CATEGORY_FAMILY}),
            content_type='application/json', **self.author_header)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Not following user', ast.literal_eval(response.content.decode())['error'])

    def test_set_category_invalid_value_rejected(self):
        response = self.client.post(
            self.url, data=json.dumps({Fields.category: 'bestie'}),
            content_type='application/json', **self.author_header)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid category', ast.literal_eval(response.content.decode())['error'])

    def test_set_category_on_self_rejected(self):
        url = reverse('set_follow_category', kwargs={'username': self.local_username})
        response = self.client.post(
            url, data=json.dumps({Fields.category: FOLLOW_CATEGORY_FRIEND}),
            content_type='application/json', **self.author_header)

        self.assertEqual(response.status_code, 400)

    def test_set_category_requires_auth(self):
        response = self.client.post(
            self.url, data=json.dumps({Fields.category: FOLLOW_CATEGORY_FRIEND}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer notarealtoken')
        self.assertEqual(response.status_code, 401)


class ProfileFollowCategoryTests(RelationshipCategoryTestBase):

    def _get_profile(self, username, header):
        url = reverse('get_profile_details', kwargs={'username': username})
        return self.client.get(url, **header)

    def test_profile_reports_null_category_when_not_following(self):
        response = self._get_profile(self.viewer_username, self.author_header)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body[Fields.is_following])
        self.assertIsNone(body[Fields.follow_category])

    def test_profile_reports_assigned_category(self):
        self._label(self.author, self.viewer, FOLLOW_CATEGORY_FAMILY)
        response = self._get_profile(self.viewer_username, self.author_header)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body[Fields.is_following])
        self.assertEqual(body[Fields.follow_category], FOLLOW_CATEGORY_FAMILY)


class MakePostAudienceTests(RelationshipCategoryTestBase):

    def _create_post(self, audience_value):
        url = reverse('make_post')
        data = {'caption': POSITIVE_CAPTION}
        if audience_value is not None:
            data[Fields.audience] = audience_value
        return self.client.post(
            url, data=json.dumps(data), content_type='application/json',
            **self.author_header)

    def test_audience_defaults_to_public(self):
        response = self._create_post(None)
        self.assertEqual(response.status_code, 201)
        post = Post.objects.get(post_identifier=response.json()[Fields.post_identifier])
        self.assertEqual(post.audience, POST_AUDIENCE_PUBLIC)

    def test_valid_audience_stored(self):
        for audience in (POST_AUDIENCE_FOLLOWING, POST_AUDIENCE_FRIENDS, POST_AUDIENCE_FAMILY):
            with self.subTest(audience=audience):
                response = self._create_post(audience)
                self.assertEqual(response.status_code, 201)
                post = Post.objects.get(post_identifier=response.json()[Fields.post_identifier])
                self.assertEqual(post.audience, audience)

    def test_invalid_audience_rejected(self):
        response = self._create_post('everyone_i_dislike')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Post.objects.filter(author=self.author).exists())


class PostAudienceVisibilityTests(RelationshipCategoryTestBase):
    """The nested-circle rule enforced by visibility.can_view_post via the
    post-details endpoint. A post by the author reaches the viewer only when the
    author has labeled the viewer closely enough."""

    def _viewer_can_see(self, post):
        url = reverse('get_post_details', kwargs={'post_identifier': str(post.post_identifier)})
        response = self.client.get(url, **self.viewer_header)
        return response.status_code == 200

    def test_public_post_visible_to_stranger(self):
        post = self._make_visible_post(self.author, POST_AUDIENCE_PUBLIC)
        self.assertTrue(self._viewer_can_see(post))

    def test_following_post_hidden_from_unlabeled_viewer(self):
        post = self._make_visible_post(self.author, POST_AUDIENCE_FOLLOWING)
        self.assertFalse(self._viewer_can_see(post))

    def test_following_post_visible_to_any_labeled_viewer(self):
        self._label(self.author, self.viewer, FOLLOW_CATEGORY_FOLLOWING)
        post = self._make_visible_post(self.author, POST_AUDIENCE_FOLLOWING)
        self.assertTrue(self._viewer_can_see(post))

    def test_friends_post_visible_to_friend_and_family_not_following(self):
        post = self._make_visible_post(self.author, POST_AUDIENCE_FRIENDS)

        edge = self._label(self.author, self.viewer, FOLLOW_CATEGORY_FOLLOWING)
        self.assertFalse(self._viewer_can_see(post))

        edge.category = FOLLOW_CATEGORY_FRIEND
        edge.save(update_fields=['category'])
        self.assertTrue(self._viewer_can_see(post))

        edge.category = FOLLOW_CATEGORY_FAMILY
        edge.save(update_fields=['category'])
        self.assertTrue(self._viewer_can_see(post))

    def test_family_post_visible_only_to_family(self):
        post = self._make_visible_post(self.author, POST_AUDIENCE_FAMILY)

        edge = self._label(self.author, self.viewer, FOLLOW_CATEGORY_FRIEND)
        self.assertFalse(self._viewer_can_see(post))

        edge.category = FOLLOW_CATEGORY_FAMILY
        edge.save(update_fields=['category'])
        self.assertTrue(self._viewer_can_see(post))

    def test_author_always_sees_own_restricted_post(self):
        post = self._make_visible_post(self.author, POST_AUDIENCE_FAMILY)
        url = reverse('get_post_details', kwargs={'post_identifier': str(post.post_identifier)})
        response = self.client.get(url, **self.author_header)
        self.assertEqual(response.status_code, 200)


class FollowedFeedCategoryFilterTests(RelationshipCategoryTestBase):
    """?category= narrows the following feed to that exact group. The viewer
    follows two authors it labels differently, each with a public post."""

    def setUp(self):
        super().setUp()

        family_fields = self.make_user_with_prefix(prefix='fam')
        self.family_author = PositiveOnlySocialUser.objects.get(username=family_fields[Fields.username])
        friend_fields = self.make_user_with_prefix(prefix='fri')
        self.friend_author = PositiveOnlySocialUser.objects.get(username=friend_fields[Fields.username])

        # The viewer follows and labels both, and each has one public post.
        self._label(self.viewer, self.family_author, FOLLOW_CATEGORY_FAMILY)
        self._label(self.viewer, self.friend_author, FOLLOW_CATEGORY_FRIEND)
        self.family_post = self._make_visible_post(self.family_author, POST_AUDIENCE_PUBLIC)
        self.friend_post = self._make_visible_post(self.friend_author, POST_AUDIENCE_PUBLIC)

    def _followed_feed(self, category=None):
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})
        if category:
            url = f'{url}?{Fields.category}={category}'
        response = self.client.get(url, **self.viewer_header)
        self.assertEqual(response.status_code, 200)
        return {p[Fields.post_identifier] for p in response.json()}

    def test_unfiltered_feed_has_both(self):
        ids = self._followed_feed()
        self.assertIn(str(self.family_post.post_identifier), ids)
        self.assertIn(str(self.friend_post.post_identifier), ids)

    def test_family_filter_only_family(self):
        ids = self._followed_feed(FOLLOW_CATEGORY_FAMILY)
        self.assertIn(str(self.family_post.post_identifier), ids)
        self.assertNotIn(str(self.friend_post.post_identifier), ids)

    def test_friend_filter_only_friend(self):
        ids = self._followed_feed(FOLLOW_CATEGORY_FRIEND)
        self.assertIn(str(self.friend_post.post_identifier), ids)
        self.assertNotIn(str(self.family_post.post_identifier), ids)

    def test_invalid_category_filter_rejected(self):
        url = reverse('get_posts_for_followed_users', kwargs={'batch': 0})
        response = self.client.get(f'{url}?{Fields.category}=nope', **self.viewer_header)
        self.assertEqual(response.status_code, 400)
