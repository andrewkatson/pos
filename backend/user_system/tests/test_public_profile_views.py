import os
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .test_parent_case import PositiveOnlySocialTestCase
from .. import link_preview
from ..constants import (
    BAN_TYPE_OUTRIGHT,
    BAN_TYPE_SHADOW,
    Fields,
    HIDDEN_REASON_CLASSIFIER,
    HIDDEN_REASON_CLASSIFIER_FINAL,
    POST_AUDIENCE_FRIENDS,
    POST_BATCH_SIZE,
    PROFILE_IMAGE_STATUS_APPROVED,
    PROFILE_IMAGE_STATUS_PENDING,
)
from ..models import Post, PositiveOnlySocialUser, UserBan
from ..utils import get_compressed_image_url
from ..views import get_user_with_username


AVATAR_BLURHASH = 'LEHV6nWB2yk8pyo0adR*.7kCMdnj'


def _meta_content(html, attribute, name):
    """The `content` of a <meta {attribute}="{name}"> tag, or None."""
    match = re.search(rf'<meta {attribute}="{re.escape(name)}" content="([^"]*)"', html)
    return match.group(1) if match else None


@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
@override_settings(FRONTEND_BASE_URL='https://smiling.social')
class PublicProfileViewTests(PositiveOnlySocialTestCase):
    """
    The signed-out half of sharing a profile (issue #510): a recipient with no
    account can read a shared profile's header and post grid, and a crawler can
    unfurl the link — but only when the account is genuinely public. A shadow
    banned account or a verified minor's account is reported as a 404 that is
    indistinguishable from a username that was never registered, and the grid
    holds exactly the posts the public post endpoint would serve individually.
    """

    def setUp(self):
        super().setUp()

        self.owner = self.make_user_with_prefix(prefix='owner')
        self.owner_user = get_user_with_username(self.owner['username'])
        self.owner_header = {
            'HTTP_AUTHORIZATION': f"Bearer {self.owner[Fields.session_management_token]}"}

        post_data = self._make_post(self.owner[Fields.session_management_token])
        self.post_identifier = post_data[Fields.post_identifier]
        self.post = Post.objects.get(post_identifier=self.post_identifier)

        self.details_url = self._details_url(self.owner['username'])
        self.posts_url = self._posts_url(self.owner['username'])
        self.preview_url = self._preview_url(self.owner['username'])

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _details_url(self, username):
        return reverse('get_public_profile_details', kwargs={'username': username})

    def _posts_url(self, username, batch=0):
        return reverse('get_public_posts_for_user', kwargs={'username': username, 'batch': batch})

    def _preview_url(self, username):
        return reverse('get_profile_link_preview', kwargs={'username': username})

    def _assert_profile_hidden(self, message):
        """Every public endpoint for this profile reports it as not found."""
        for url in (self.details_url, self.posts_url, self.preview_url):
            self.assertEqual(self.client.get(url).status_code, 404, msg=f"{message}: {url}")

    def _assert_profile_visible(self, message):
        for url in (self.details_url, self.posts_url, self.preview_url):
            self.assertEqual(self.client.get(url).status_code, 200, msg=f"{message}: {url}")

    def _set_avatar(self, user):
        url = f'https://test-bucket.s3.amazonaws.com/{user.id}/avatar.jpeg'
        PositiveOnlySocialUser.objects.filter(pk=user.pk).update(
            profile_image_url=url, profile_image_status=PROFILE_IMAGE_STATUS_APPROVED,
            profile_image_blurhash=AVATAR_BLURHASH)
        return url

    def _follow(self, follower, username_to_follow):
        url = reverse('follow_user', kwargs={'username_to_follow': username_to_follow})
        header = {'HTTP_AUTHORIZATION': f"Bearer {follower[Fields.session_management_token]}"}
        self.assertEqual(self.client.post(url, **header).status_code, 200)

    def _preview_html(self, expected_status=200):
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, expected_status)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        return response.content.decode('utf-8')

    # =========================================================================
    # THE HAPPY PATH
    # =========================================================================

    def test_public_profile_is_served_without_a_token(self):
        PositiveOnlySocialUser.objects.filter(pk=self.owner_user.pk).update(
            bio='Collector of small joys.')

        response = self.client.get(self.details_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[Fields.username], self.owner['username'])
        self.assertEqual(data[Fields.post_count], 1)
        self.assertEqual(data[Fields.follower_count], 0)
        self.assertEqual(data[Fields.following_count], 0)
        self.assertEqual(data[Fields.bio], 'Collector of small joys.')
        self.assertEqual(data[Fields.membership_number], self.owner_user.membership_number)
        self.assertIn(Fields.identity_is_verified, data)

    def test_public_profile_omits_per_viewer_and_owner_only_state(self):
        """There is no viewer, so no follow/block flags; and the owner-only
        photo-review fields must not leak to the open internet."""
        PositiveOnlySocialUser.objects.filter(pk=self.owner_user.pk).update(
            pending_profile_image_url=f'https://test-bucket.s3.amazonaws.com/{self.owner_user.id}/new.jpeg',
            profile_image_status=PROFILE_IMAGE_STATUS_PENDING)

        data = self.client.get(self.details_url).json()

        for field in (Fields.is_following, Fields.follow_category, 'is_blocked',
                      Fields.profile_image_status, Fields.profile_image_reason_code,
                      Fields.pending_profile_image_url):
            self.assertNotIn(field, data)

    def test_public_profile_carries_the_approved_avatar(self):
        avatar = self._set_avatar(self.owner_user)

        data = self.client.get(self.details_url).json()

        # Without CloudFront configured the URLs degrade exactly as they do for a
        # signed-in viewer: compressed-bucket swap plus the raw original.
        self.assertEqual(data[Fields.profile_image_url], get_compressed_image_url(avatar))
        self.assertEqual(data[Fields.profile_image_original_url], avatar)
        self.assertEqual(data[Fields.profile_image_blurhash], AVATAR_BLURHASH)

    def test_public_profile_without_a_photo_has_null_avatar_fields(self):
        data = self.client.get(self.details_url).json()

        self.assertIsNone(data[Fields.profile_image_url])
        self.assertIsNone(data[Fields.profile_image_original_url])
        self.assertIsNone(data[Fields.profile_image_blurhash])

    def test_public_grid_serves_the_users_public_posts(self):
        posts = self.client.get(self.posts_url).json()

        self.assertEqual(len(posts), 1)
        row = posts[0]
        self.assertEqual(row[Fields.post_identifier], str(self.post_identifier))
        self.assertEqual(row[Fields.caption], self.post.caption)
        self.assertEqual(row[Fields.author_username], self.owner['username'])
        self.assertEqual(row[Fields.image_url], get_compressed_image_url(self.post.image_url))
        self.assertEqual(row[Fields.original_image_url], self.post.image_url)
        self.assertEqual(row[Fields.post_likes], 0)

    def test_public_grid_omits_per_viewer_and_author_only_state(self):
        row = self.client.get(self.posts_url).json()[0]

        for field in (Fields.is_liked, Fields.is_saved, Fields.is_reported, Fields.report_reason,
                      Fields.status, Fields.hidden, Fields.hidden_reason, Fields.appealable):
            self.assertNotIn(field, row)

    def test_public_grid_like_count_reflects_real_likes(self):
        """The grouped like-count query is keyed on the post's primary key, which
        for Post is post_identifier. A non-zero count is what proves the key
        resolves — a test that only ever sees 0 would pass with a broken key."""
        liker = self.make_user_with_prefix(prefix='liker')
        like_url = reverse('like_post', kwargs={'post_identifier': str(self.post_identifier)})
        header = {'HTTP_AUTHORIZATION': f"Bearer {liker[Fields.session_management_token]}"}
        self.assertEqual(self.client.post(like_url, **header).status_code, 200)

        row = self.client.get(self.posts_url).json()[0]

        self.assertEqual(row[Fields.post_likes], 1)

    def test_public_grid_like_counts_are_one_grouped_query(self):
        """The batch's like counts come from one grouped query handed to the
        serializer, not a COUNT per tile: the number of queries must not grow
        with the number of posts in the batch."""
        with CaptureQueriesContext(connection) as one_post:
            self.assertEqual(len(self.client.get(self.posts_url).json()), 1)

        for _ in range(3):
            self._make_post(self.owner[Fields.session_management_token])
        with CaptureQueriesContext(connection) as four_posts:
            self.assertEqual(len(self.client.get(self.posts_url).json()), 4)

        self.assertEqual(len(four_posts.captured_queries), len(one_post.captured_queries))

    def test_public_grid_is_batched(self):
        for _ in range(POST_BATCH_SIZE):
            self._make_post(self.owner[Fields.session_management_token])

        first = self.client.get(self._posts_url(self.owner['username'], 0)).json()
        second = self.client.get(self._posts_url(self.owner['username'], 1)).json()
        third = self.client.get(self._posts_url(self.owner['username'], 2)).json()

        self.assertEqual(len(first), POST_BATCH_SIZE)
        self.assertEqual(len(second), 1)
        self.assertEqual(third, [])
        # No post appears in two batches.
        self.assertEqual(len({p[Fields.post_identifier] for p in first + second}), POST_BATCH_SIZE + 1)

    # =========================================================================
    # THE GRID AND THE COUNTS SHOW ONLY WHAT IS PUBLIC
    # =========================================================================

    def test_hidden_post_is_dropped_from_the_grid_and_the_count(self):
        Post.objects.filter(pk=self.post.pk).update(hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)

        self.assertEqual(self.client.get(self.posts_url).json(), [])
        self.assertEqual(self.client.get(self.details_url).json()[Fields.post_count], 0)

    def test_final_rejection_tombstone_is_dropped_from_the_grid(self):
        Post.objects.filter(pk=self.post.pk).update(
            hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER_FINAL)

        self.assertEqual(self.client.get(self.posts_url).json(), [])
        self.assertEqual(self.client.get(self.details_url).json()[Fields.post_count], 0)

    def test_restricted_audience_post_is_dropped_from_the_grid(self):
        """A friends-only post is never public, so the shared profile must not
        show it even though its author's profile is."""
        Post.objects.filter(pk=self.post.pk).update(audience=POST_AUDIENCE_FRIENDS)

        self.assertEqual(self.client.get(self.details_url).status_code, 200)
        self.assertEqual(self.client.get(self.posts_url).json(), [])
        self.assertEqual(self.client.get(self.details_url).json()[Fields.post_count], 0)

    def test_grid_matches_what_the_public_post_endpoint_serves(self):
        """Invariant: every post the grid lists is one whose own shared link
        resolves, and vice versa — the two views share one visibility rule."""
        self._make_post(self.owner[Fields.session_management_token])
        second = Post.objects.filter(author=self.owner_user).exclude(pk=self.post.pk).get()
        Post.objects.filter(pk=second.pk).update(audience=POST_AUDIENCE_FRIENDS)

        listed = {p[Fields.post_identifier] for p in self.client.get(self.posts_url).json()}

        for post in (self.post, second):
            url = reverse('get_public_post_details', kwargs={'post_identifier': str(post.post_identifier)})
            individually_public = self.client.get(url).status_code == 200
            self.assertEqual(str(post.post_identifier) in listed, individually_public)

    def test_follower_counts_exclude_accounts_that_are_not_public(self):
        """The counts must agree with what the public could see (issue #398): a
        shadow-banned follower and a verified minor follower are hidden from the
        open internet, so neither may inflate the number."""
        visible_follower = self.make_user_with_prefix(prefix='visible')
        banned_follower = self.make_user_with_prefix(prefix='banned')
        minor_follower = self.make_user_with_prefix(prefix='young')
        for follower in (visible_follower, banned_follower, minor_follower):
            self._follow(follower, self.owner['username'])
        UserBan.objects.create(
            user=get_user_with_username(banned_follower['username']), ban_type=BAN_TYPE_SHADOW)
        get_user_model().objects.filter(username=minor_follower['username']).update(
            identity_is_verified=True, is_adult=False)

        data = self.client.get(self.details_url).json()

        self.assertEqual(data[Fields.follower_count], 1)

    # =========================================================================
    # WHAT IS NOT PUBLIC LOOKS EXACTLY LIKE WHAT DOES NOT EXIST
    # =========================================================================

    def test_shadow_banned_account_is_not_public(self):
        UserBan.objects.create(user=self.owner_user, ban_type=BAN_TYPE_SHADOW)

        self._assert_profile_hidden("a shadow-banned account")

    def test_expired_shadow_ban_makes_the_profile_public_again(self):
        UserBan.objects.create(
            user=self.owner_user, ban_type=BAN_TYPE_SHADOW,
            expires=timezone.now() - timedelta(days=1))

        self._assert_profile_visible("an expired shadow ban")

    def test_outright_ban_does_not_hide_the_profile(self):
        """An outright ban stops the account from acting; it is not a takedown,
        so the profile stays up — matching what signed-in viewers see."""
        UserBan.objects.create(user=self.owner_user, ban_type=BAN_TYPE_OUTRIGHT)

        self._assert_profile_visible("an outright-banned account")

    def test_verified_minors_profile_is_not_public(self):
        """An anonymous visitor's age is unknown, which puts it in the adult
        band — and the two bands are mutually invisible (issue #329)."""
        get_user_model().objects.filter(pk=self.owner_user.pk).update(
            identity_is_verified=True, is_adult=False)

        self._assert_profile_hidden("a verified minor's profile")

    def test_verified_adults_profile_stays_public(self):
        get_user_model().objects.filter(pk=self.owner_user.pk).update(
            identity_is_verified=True, is_adult=True)

        self._assert_profile_visible("a verified adult's profile")

    def test_unregistered_username_is_not_found(self):
        for url in (self._details_url('nobody_here_at_all'),
                    self._posts_url('nobody_here_at_all'),
                    self._preview_url('nobody_here_at_all')):
            self.assertEqual(self.client.get(url).status_code, 404, msg=url)

    def test_hidden_and_missing_profiles_are_indistinguishable(self):
        """Neither a shadow ban nor a minor's account can be confirmed by name."""
        missing = self.client.get(self._details_url('nobody_here_at_all'))
        UserBan.objects.create(user=self.owner_user, ban_type=BAN_TYPE_SHADOW)
        banned = self.client.get(self.details_url)

        self.assertEqual(missing.status_code, banned.status_code)
        self.assertEqual(missing.content, banned.content)

    def test_malformed_username_is_not_found_rather_than_rejected(self):
        """A name that could never have been registered is just not found, so
        the response shape cannot be used to tell 'invalid' from 'unknown'."""
        self.assertEqual(self.client.get(self._details_url('a-b')).status_code, 404)

    # =========================================================================
    # THE ANSWER DOES NOT DEPEND ON WHO IS ASKING
    # =========================================================================

    def test_owner_gets_the_same_public_answer_for_their_own_hidden_post(self):
        """The signed-in grid shows an author their own hidden posts. The public
        grid resolves against a fixed anonymous viewer instead, so the owner's
        own browser sees what a stranger would."""
        Post.objects.filter(pk=self.post.pk).update(hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)

        self.assertEqual(self.client.get(self.posts_url, **self.owner_header).json(), [])

        # ...while the authenticated grid still shows it to its author.
        private_url = reverse('get_posts_for_user',
                              kwargs={'username': self.owner['username'], 'batch': 0})
        private = self.client.get(private_url, **self.owner_header).json()
        self.assertEqual([p[Fields.post_identifier] for p in private], [str(self.post_identifier)])

    def test_owner_gets_no_review_state_on_the_public_profile(self):
        PositiveOnlySocialUser.objects.filter(pk=self.owner_user.pk).update(
            pending_profile_image_url=f'https://test-bucket.s3.amazonaws.com/{self.owner_user.id}/new.jpeg',
            profile_image_status=PROFILE_IMAGE_STATUS_PENDING)

        data = self.client.get(self.details_url, **self.owner_header).json()

        self.assertNotIn(Fields.pending_profile_image_url, data)
        self.assertNotIn(Fields.profile_image_status, data)

    # =========================================================================
    # THE LINK PREVIEW
    # =========================================================================

    def test_preview_describes_the_profile(self):
        PositiveOnlySocialUser.objects.filter(pk=self.owner_user.pk).update(bio='Sunsets and soup.')
        html = self._preview_html()

        canonical = f"https://smiling.social/profile/{self.owner['username']}"
        self.assertEqual(_meta_content(html, 'property', 'og:url'), canonical)
        self.assertIn(f'<link rel="canonical" href="{canonical}" />', html)
        self.assertEqual(_meta_content(html, 'property', 'og:title'),
                         f"{self.owner['username']} on {link_preview.SITE_NAME}")
        self.assertEqual(_meta_content(html, 'property', 'og:description'), 'Sunsets and soup.')
        self.assertEqual(_meta_content(html, 'property', 'og:type'), 'profile')
        self.assertEqual(_meta_content(html, 'property', 'og:site_name'), link_preview.SITE_NAME)

    def test_preview_without_a_bio_uses_the_site_blurb(self):
        html = self._preview_html()

        self.assertEqual(_meta_content(html, 'property', 'og:description'),
                         link_preview.DEFAULT_DESCRIPTION)

    def test_preview_image_is_the_profile_photo(self):
        avatar = self._set_avatar(self.owner_user)
        html = self._preview_html()

        self.assertEqual(_meta_content(html, 'property', 'og:image'), get_compressed_image_url(avatar))
        self.assertEqual(_meta_content(html, 'name', 'twitter:card'), 'summary_large_image')

    def test_preview_without_a_photo_degrades_to_a_summary_card(self):
        html = self._preview_html()

        self.assertIsNone(_meta_content(html, 'property', 'og:image'))
        self.assertEqual(_meta_content(html, 'name', 'twitter:card'), 'summary')

    def test_preview_escapes_bio_markup(self):
        PositiveOnlySocialUser.objects.filter(pk=self.owner_user.pk).update(
            bio='<script>alert(1)</script> & friends')
        html = self._preview_html()

        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_preview_is_only_briefly_cacheable(self):
        response = self.client.get(self.preview_url)

        self.assertEqual(response['Cache-Control'], 'public, max-age=300')

    def test_non_public_profile_gets_the_generic_card(self):
        UserBan.objects.create(user=self.owner_user, ban_type=BAN_TYPE_SHADOW)

        html = self._preview_html(expected_status=404)

        self.assertEqual(_meta_content(html, 'property', 'og:type'), 'website')
        self.assertEqual(_meta_content(html, 'property', 'og:title'), link_preview.SITE_NAME)
        # Nothing about the account leaks — not even its name.
        self.assertNotIn(self.owner['username'], html)

    # =========================================================================
    # INPUT VALIDATION
    # =========================================================================

    def test_below_zero_batch_does_not_route(self):
        self.assertEqual(
            self.client.get(f"/user_index/public/profiles/{self.owner['username']}/posts/-1/").status_code,
            404)

    def test_post_method_not_allowed(self):
        """These are read-only endpoints."""
        self.assertEqual(self.client.post(self.details_url).status_code, 405)
        self.assertEqual(self.client.post(self.posts_url).status_code, 405)
        self.assertEqual(self.client.post(self.preview_url).status_code, 405)
