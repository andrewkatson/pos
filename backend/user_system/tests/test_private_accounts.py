import json
from unittest.mock import patch

from django.urls import reverse

from .test_relationship_categories import RelationshipCategoryTestBase, POSITIVE_CAPTION
from ..constants import (
    BAN_TYPE_SHADOW,
    Fields,
    FOLLOW_CATEGORY_FAMILY,
    FOLLOW_CATEGORY_FOLLOWING,
    FOLLOW_CATEGORY_FRIEND,
    POST_AUDIENCE_FRIENDS,
    POST_AUDIENCE_PUBLIC,
)
from ..models import FollowRequest, PositiveOnlySocialUser, Tag, UserBan, UserFollow
from ..visibility import PUBLIC_VIEWER, can_view_post, privacy_admits, visible_comments, visible_posts


class PrivateAccountTestBase(RelationshipCategoryTestBase):
    """A private author (A) and a viewer (B) who does not follow them, plus
    helpers to drive the follow-request endpoints (issue #96)."""

    def setUp(self):
        super().setUp()
        self.author.is_private = True
        self.author.save(update_fields=['is_private'])

    def _follow(self, username, header, category=None):
        url = reverse('follow_user', kwargs={'username_to_follow': username})
        if category is None:
            return self.client.post(url, **header)
        return self.client.post(
            url, data=json.dumps({Fields.category: category}),
            content_type='application/json', **header)

    def _request_action(self, action, username, header):
        url = reverse(f'{action}_follow_request', kwargs={'username': username})
        return self.client.post(url, **header)

    def _set_private(self, is_private, header):
        return self.client.post(
            reverse('set_account_privacy'), data=json.dumps({Fields.is_private: is_private}),
            content_type='application/json', **header)

    def _profile(self, username, header):
        return self.client.get(
            reverse('get_profile_details', kwargs={'username': username}), **header).json()

    def _profile_post_ids(self, username, header):
        url = reverse('get_posts_for_user', kwargs={'username': username, 'batch': 0})
        return {p[Fields.post_identifier] for p in self.client.get(url, **header).json()}


class FollowPrivateAccountTests(PrivateAccountTestBase):

    def test_following_private_account_files_request_not_edge(self):
        response = self._follow(self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body[Fields.follow_request_pending])
        self.assertIsNone(body[Fields.follow_category])
        self.assertFalse(UserFollow.objects.filter(user_from=self.viewer, user_to=self.author).exists())
        self.assertTrue(FollowRequest.objects.filter(user_from=self.viewer, user_to=self.author).exists())

    def test_following_public_account_is_unchanged(self):
        response = self._follow(self.viewer_username, self.author_header)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()[Fields.follow_request_pending])
        self.assertTrue(UserFollow.objects.filter(user_from=self.author, user_to=self.viewer).exists())
        self.assertFalse(FollowRequest.objects.exists())

    def test_duplicate_request_rejected(self):
        self._follow(self.local_username, self.viewer_header)
        response = self._follow(self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "Follow already requested")
        self.assertEqual(FollowRequest.objects.count(), 1)

    def test_request_from_blocked_user_looks_like_missing_account(self):
        self.author.blocked.add(self.viewer)

        response = self._follow(self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "User does not exist")
        self.assertFalse(FollowRequest.objects.exists())

    def test_decision_uses_fresh_privacy_not_the_stale_lookup(self):
        """The follow-vs-request decision re-reads the target under a row lock
        in the write's transaction, so an account that went private after the
        view first looked it up still gets a request, not an unapproved follow."""
        stale = PositiveOnlySocialUser.objects.get(pk=self.author.pk)
        stale.is_private = False

        with patch('user_system.views.get_user_with_username', return_value=stale):
            response = self._follow(self.local_username, self.viewer_header)

        self.assertTrue(response.json()[Fields.follow_request_pending])
        self.assertFalse(UserFollow.objects.filter(user_from=self.viewer, user_to=self.author).exists())
        self.assertTrue(FollowRequest.objects.filter(user_from=self.viewer, user_to=self.author).exists())

    def test_request_to_an_account_you_blocked_is_refused(self):
        self.viewer.blocked.add(self.author)

        response = self._follow(self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "User does not exist")
        self.assertFalse(FollowRequest.objects.exists())

    def test_existing_follower_is_already_following(self):
        self._label(self.viewer, self.author, FOLLOW_CATEGORY_FOLLOWING)

        response = self._follow(self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "Already following user")
        self.assertFalse(FollowRequest.objects.exists())


class FollowRequestDecisionTests(PrivateAccountTestBase):

    def test_approve_creates_edge_with_requested_category(self):
        self._follow(self.local_username, self.viewer_header, category=FOLLOW_CATEGORY_FAMILY)

        response = self._request_action('approve', self.viewer_username, self.author_header)

        self.assertEqual(response.status_code, 200)
        edge = UserFollow.objects.get(user_from=self.viewer, user_to=self.author)
        self.assertEqual(edge.category, FOLLOW_CATEGORY_FAMILY)
        self.assertFalse(FollowRequest.objects.exists())

    def test_block_before_approval_leaves_nothing_to_approve(self):
        self._follow(self.local_username, self.viewer_header)
        self.client.post(
            reverse('toggle_block', kwargs={'username_to_toggle_block': self.viewer_username}),
            **self.author_header)

        response = self._request_action('approve', self.viewer_username, self.author_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "No follow request from user")
        self.assertFalse(UserFollow.objects.exists())

    def test_approve_without_request_fails(self):
        response = self._request_action('approve', self.viewer_username, self.author_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "No follow request from user")
        self.assertFalse(UserFollow.objects.exists())

    def test_requester_cannot_approve_own_request(self):
        """Approval acts on requests *to* the caller, so the requester naming the
        private account finds nothing to approve."""
        self._follow(self.local_username, self.viewer_header)

        response = self._request_action('approve', self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(UserFollow.objects.exists())
        self.assertTrue(FollowRequest.objects.exists())

    def test_deny_drops_request_without_edge(self):
        self._follow(self.local_username, self.viewer_header)

        response = self._request_action('deny', self.viewer_username, self.author_header)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FollowRequest.objects.exists())
        self.assertFalse(UserFollow.objects.exists())
        # The requester may ask again.
        self.assertEqual(self._follow(self.local_username, self.viewer_header).status_code, 200)

    def test_cancel_withdraws_own_request(self):
        self._follow(self.local_username, self.viewer_header)

        response = self._request_action('cancel', self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FollowRequest.objects.exists())

    def test_cancel_without_request_fails(self):
        response = self._request_action('cancel', self.local_username, self.viewer_header)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "No follow request to cancel")

    def test_decision_endpoints_require_auth(self):
        bad = {'HTTP_AUTHORIZATION': 'Bearer notarealtoken'}
        for action in ('approve', 'deny', 'cancel'):
            self.assertEqual(self._request_action(action, self.viewer_username, bad).status_code, 401)
        self.assertEqual(self.client.get(reverse('get_follow_requests'), **bad).status_code, 401)


class FollowRequestListTests(PrivateAccountTestBase):

    def _list(self, header):
        response = self.client.get(reverse('get_follow_requests'), **header)
        self.assertEqual(response.status_code, 200)
        return [row[Fields.username] for row in response.json()]

    def test_lists_incoming_requests_newest_first(self):
        other = self.make_user_with_prefix(prefix='other')
        other_header = {'HTTP_AUTHORIZATION': f'Bearer {other[Fields.session_management_token]}'}
        self._follow(self.local_username, self.viewer_header)
        self._follow(self.local_username, other_header)

        self.assertEqual(self._list(self.author_header), [other[Fields.username], self.viewer_username])

    def test_requester_does_not_see_outgoing_requests_in_list(self):
        self._follow(self.local_username, self.viewer_header)

        self.assertEqual(self._list(self.viewer_header), [])

    def test_unrelated_requests_do_not_duplicate_rows(self):
        """A requester who has also asked to follow other private accounts is
        listed once, not once per request they ever sent."""
        second = PositiveOnlySocialUser.objects.get(
            username=self.make_user_with_prefix(prefix='second')[Fields.username])
        second.is_private = True
        second.save(update_fields=['is_private'])
        self._follow(second.username, self.viewer_header)
        self._follow(self.local_username, self.viewer_header)

        self.assertEqual(self._list(self.author_header), [self.viewer_username])

    def test_shadow_banned_requester_hidden_from_list_and_count(self):
        self._follow(self.local_username, self.viewer_header)
        UserBan.objects.create(user=self.viewer, ban_type=BAN_TYPE_SHADOW)

        self.assertEqual(self._list(self.author_header), [])
        self.assertEqual(self._profile(self.local_username, self.author_header)[Fields.follow_request_count], 0)

    def test_owner_profile_carries_request_count(self):
        self._follow(self.local_username, self.viewer_header)

        self.assertEqual(self._profile(self.local_username, self.author_header)[Fields.follow_request_count], 1)
        # Never exposed on someone else's profile.
        self.assertNotIn(Fields.follow_request_count, self._profile(self.local_username, self.viewer_header))


class AccountPrivacySettingTests(PrivateAccountTestBase):

    def test_set_private_round_trips_through_me(self):
        response = self._set_private(False, self.author_header)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()[Fields.is_private])
        me = self.client.get(reverse('get_current_user'), **self.author_header).json()
        self.assertFalse(me[Fields.is_private])

        self._set_private(True, self.author_header)
        me = self.client.get(reverse('get_current_user'), **self.author_header).json()
        self.assertTrue(me[Fields.is_private])

    def test_non_boolean_rejected(self):
        for bad in ("true", 1, None):
            response = self.client.post(
                reverse('set_account_privacy'), data=json.dumps({Fields.is_private: bad}),
                content_type='application/json', **self.author_header)
            self.assertEqual(response.status_code, 400)
        self.author.refresh_from_db()
        self.assertTrue(self.author.is_private)

    def test_going_public_approves_pending_requests(self):
        self._follow(self.local_username, self.viewer_header, category=FOLLOW_CATEGORY_FRIEND)

        self._set_private(False, self.author_header)

        edge = UserFollow.objects.get(user_from=self.viewer, user_to=self.author)
        self.assertEqual(edge.category, FOLLOW_CATEGORY_FRIEND)
        self.assertFalse(FollowRequest.objects.exists())

    def test_going_private_keeps_existing_followers(self):
        self._set_private(False, self.author_header)
        self._label(self.viewer, self.author, FOLLOW_CATEGORY_FOLLOWING)
        post = self._make_visible_post(self.author)

        self._set_private(True, self.author_header)

        self.assertTrue(UserFollow.objects.filter(user_from=self.viewer, user_to=self.author).exists())
        self.assertIn(str(post.post_identifier), self._profile_post_ids(self.local_username, self.viewer_header))

    def test_block_clears_requests_both_ways(self):
        self._follow(self.local_username, self.viewer_header)
        url = reverse('toggle_block', kwargs={'username_to_toggle_block': self.viewer_username})

        self.client.post(url, **self.author_header)

        self.assertFalse(FollowRequest.objects.exists())


class PrivatePostVisibilityTests(PrivateAccountTestBase):
    """The core rule (issue #96): a private account's posts reach only the
    account itself and its approved followers, everywhere posts are served."""

    def setUp(self):
        super().setUp()
        self.post = self._make_visible_post(self.author)
        self.post_id = str(self.post.post_identifier)

    def _post_details_status(self, header):
        url = reverse('get_post_details', kwargs={'post_identifier': self.post_id})
        return self.client.get(url, **header).status_code

    def test_non_follower_cannot_see_posts(self):
        self.assertFalse(can_view_post(self.post, self.viewer))
        self.assertNotIn(self.post, visible_posts(self.author.post_set.all(), self.viewer))
        self.assertEqual(self._profile_post_ids(self.local_username, self.viewer_header), set())
        self.assertNotEqual(self._post_details_status(self.viewer_header), 200)

    def test_pending_requester_cannot_see_posts(self):
        self._follow(self.local_username, self.viewer_header)

        self.assertFalse(can_view_post(self.post, self.viewer))
        self.assertEqual(self._profile_post_ids(self.local_username, self.viewer_header), set())

    def test_approved_follower_sees_posts(self):
        self._follow(self.local_username, self.viewer_header)
        self._request_action('approve', self.viewer_username, self.author_header)

        self.assertTrue(can_view_post(self.post, self.viewer))
        self.assertEqual(self._profile_post_ids(self.local_username, self.viewer_header), {self.post_id})
        self.assertEqual(self._post_details_status(self.viewer_header), 200)

    def test_author_always_sees_own_posts(self):
        self.assertTrue(can_view_post(self.post, self.author))
        self.assertEqual(self._profile_post_ids(self.local_username, self.author_header), {self.post_id})

    def test_author_following_viewer_is_not_enough(self):
        """Privacy reads the viewer→author edge. The author following the viewer
        (the edge audience reads) does not let the viewer in."""
        self._label(self.author, self.viewer, FOLLOW_CATEGORY_FAMILY)

        self.assertFalse(can_view_post(self.post, self.viewer))
        self.assertNotIn(self.post, visible_posts(self.author.post_set.all(), self.viewer))

    def test_audience_still_applies_to_followers(self):
        """A private author's friends-only post needs both: the viewer follows
        the author (privacy) and the author labeled the viewer a friend (audience)."""
        friends_post = self._make_visible_post(self.author, audience=POST_AUDIENCE_FRIENDS)
        self._label(self.viewer, self.author, FOLLOW_CATEGORY_FOLLOWING)
        self.assertFalse(can_view_post(friends_post, self.viewer))
        self.assertNotIn(friends_post, visible_posts(self.author.post_set.all(), self.viewer))

        self._label(self.author, self.viewer, FOLLOW_CATEGORY_FRIEND)
        self.assertTrue(can_view_post(friends_post, self.viewer))
        self.assertIn(friends_post, visible_posts(self.author.post_set.all(), self.viewer))

    def test_follower_query_does_not_duplicate_posts(self):
        """The privacy subquery must not add fan-out (issue #397)."""
        self._label(self.viewer, self.author, FOLLOW_CATEGORY_FOLLOWING)
        for i in range(3):
            other = PositiveOnlySocialUser.objects.get(
                username=self.make_user_with_prefix(prefix=f'extra{i}')[Fields.username])
            self._label(self.author, other, FOLLOW_CATEGORY_FOLLOWING)
            self._label(self.viewer, other, FOLLOW_CATEGORY_FOLLOWING)

        self.assertEqual(visible_posts(self.author.post_set.all(), self.viewer).count(), 1)
        self.assertEqual(visible_posts(self.author.post_set.all(), self.author).count(), 1)

    def test_hidden_from_discovery_feed_and_tag_feed(self):
        tag, _ = Tag.objects.get_or_create(name='sunshine')
        self.post.tags.add(tag)
        feed_url = reverse('get_posts_in_feed', kwargs={'batch': 0})
        tag_url = reverse('get_posts_for_tag', kwargs={'tag': 'sunshine', 'batch': 0})

        feed_ids = {p[Fields.post_identifier] for p in self.client.get(feed_url, **self.viewer_header).json()}
        tag_ids = {p[Fields.post_identifier] for p in self.client.get(tag_url, **self.viewer_header).json()}
        self.assertNotIn(self.post_id, feed_ids)
        self.assertNotIn(self.post_id, tag_ids)

        self._label(self.viewer, self.author, FOLLOW_CATEGORY_FOLLOWING)
        tag_ids = {p[Fields.post_identifier] for p in self.client.get(tag_url, **self.viewer_header).json()}
        self.assertIn(self.post_id, tag_ids)

    def test_non_follower_cannot_like_or_report(self):
        like = self.client.post(
            reverse('like_post', kwargs={'post_identifier': self.post_id}), **self.viewer_header)
        report = self.client.post(
            reverse('report_post', kwargs={'post_identifier': self.post_id}),
            data=json.dumps({Fields.reason: 'not positive'}),
            content_type='application/json', **self.viewer_header)

        self.assertEqual(like.status_code, 400)
        self.assertEqual(like.json()['error'], "No post with that identifier")
        self.assertEqual(report.status_code, 400)
        self.assertEqual(report.json()['error'], "No post with that identifier")
        self.assertFalse(self.post.postlike_set.exists())

    def test_non_follower_cannot_read_or_like_comments_on_private_post(self):
        thread = self.post.commentthread_set.create()
        comment = thread.comment_set.create(
            author=self.author, body=POSITIVE_CAPTION, hidden=False, audience=POST_AUDIENCE_PUBLIC)

        listing = self.client.get(
            reverse('get_comments_for_post', kwargs={'post_identifier': self.post_id, 'batch': 0}),
            **self.viewer_header)
        like = self.client.post(reverse('like_comment', kwargs={
            'post_identifier': self.post_id,
            'comment_thread_identifier': str(thread.comment_thread_identifier),
            'comment_identifier': str(comment.comment_identifier),
        }), **self.viewer_header)

        self.assertNotEqual(listing.status_code, 200)
        self.assertEqual(like.status_code, 400)
        self.assertFalse(comment.commentlike_set.exists())


class PrivateAuthorCommentTests(PrivateAccountTestBase):
    """Privacy gates posts only. A private account's comment on someone else's
    public post follows that comment's own audience, like anyone's."""

    def test_public_comment_by_private_account_visible_to_non_followers(self):
        public_post = self._make_visible_post(self.viewer)
        thread = public_post.commentthread_set.create()
        comment = thread.comment_set.create(
            author=self.author, body=POSITIVE_CAPTION, hidden=False, audience=POST_AUDIENCE_PUBLIC)
        stranger = PositiveOnlySocialUser.objects.get(
            username=self.make_user_with_prefix(prefix='stranger')[Fields.username])

        self.assertIn(comment, visible_comments(thread.comment_set.all(), stranger))
        self.assertIn(comment, visible_comments(thread.comment_set.all(), PUBLIC_VIEWER))


class PrivateProfileDetailsTests(PrivateAccountTestBase):

    def setUp(self):
        super().setUp()
        self._make_visible_post(self.author)
        other = PositiveOnlySocialUser.objects.get(
            username=self.make_user_with_prefix(prefix='fan')[Fields.username])
        self._label(other, self.author, FOLLOW_CATEGORY_FOLLOWING)

    def test_non_follower_sees_no_counts(self):
        profile = self._profile(self.local_username, self.viewer_header)

        self.assertTrue(profile[Fields.is_private])
        self.assertEqual(profile[Fields.post_count], 0)
        self.assertEqual(profile[Fields.follower_count], 0)
        self.assertEqual(profile[Fields.following_count], 0)
        self.assertFalse(profile[Fields.follow_request_pending])
        # The header itself is still there.
        self.assertEqual(profile[Fields.username], self.local_username)

    def test_pending_flag_reflects_request(self):
        self._follow(self.local_username, self.viewer_header)

        profile = self._profile(self.local_username, self.viewer_header)

        self.assertTrue(profile[Fields.follow_request_pending])
        self.assertFalse(profile[Fields.is_following])

    def test_follower_and_owner_see_counts(self):
        self._label(self.viewer, self.author, FOLLOW_CATEGORY_FOLLOWING)

        for header in (self.viewer_header, self.author_header):
            profile = self._profile(self.local_username, header)
            self.assertEqual(profile[Fields.post_count], 1)
            self.assertEqual(profile[Fields.follower_count], 2)

    def test_public_profile_reports_not_private(self):
        profile = self._profile(self.viewer_username, self.author_header)

        self.assertFalse(profile[Fields.is_private])


class PrivateAccountShareLinkTests(PrivateAccountTestBase):
    """A shared link to a private account shows the header but no counts or
    posts; its posts' own links 404 for a signed-out visitor."""

    def setUp(self):
        super().setUp()
        self.post = self._make_visible_post(self.author)
        self.author.bio = "sunny days"
        self.author.save(update_fields=['bio'])

    def test_public_profile_shows_header_without_counts(self):
        response = self.client.get(
            reverse('get_public_profile_details', kwargs={'username': self.local_username}))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body[Fields.is_private])
        self.assertEqual(body[Fields.bio], "sunny days")
        self.assertEqual(body[Fields.post_count], 0)
        self.assertEqual(body[Fields.follower_count], 0)
        self.assertEqual(body[Fields.following_count], 0)

    def test_public_grid_empty_and_post_link_404s(self):
        grid = self.client.get(
            reverse('get_public_posts_for_user', kwargs={'username': self.local_username, 'batch': 0}))
        details = self.client.get(
            reverse('get_public_post_details', kwargs={'post_identifier': str(self.post.post_identifier)}))

        self.assertEqual(grid.status_code, 200)
        self.assertEqual(grid.json(), [])
        self.assertEqual(details.status_code, 404)
        self.assertFalse(privacy_admits(self.author, PUBLIC_VIEWER))
