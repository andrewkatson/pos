from django.contrib.auth import get_user_model
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from ..constants import Fields


class AgeSegregationTests(PositiveOnlySocialTestCase):
    """
    Adults and verified underage accounts (16-17) are mutually invisible: an
    adult never sees an underage account's posts, comments, profile, or search
    results, and vice versa (issue #329). Unverified accounts have an unknown
    age and sit in the general (adult) pool.

    Two accounts per band exist because the main feed never returns the
    viewer's own posts, so same-band visibility is proven via a second account
    in the same band.
    """

    def setUp(self):
        super().setUp()

        # Prefixes are chosen so istartswith search fragments are unambiguous:
        # "adult" matches only the two adults, "minor" only the two minors.
        self.adult_a = self.make_user_with_prefix(prefix='adulta')
        self.adult_b = self.make_user_with_prefix(prefix='adultb')
        self.minor_a = self.make_user_with_prefix(prefix='minora')
        self.minor_b = self.make_user_with_prefix(prefix='minorb')
        self.unverified = self.make_user_with_prefix(prefix='unverified')

        for user in (self.adult_a, self.adult_b):
            self._set_band(user['username'], verified=True, adult=True)
        for user in (self.minor_a, self.minor_b):
            self._set_band(user['username'], verified=True, adult=False)
        # self.unverified keeps the registration default (unverified, non-adult).

        self.adult_a_post = self._post_for(self.adult_a)
        self.adult_b_post = self._post_for(self.adult_b)
        self.minor_a_post = self._post_for(self.minor_a)
        self.minor_b_post = self._post_for(self.minor_b)
        self.unverified_post = self._post_for(self.unverified)

    def _set_band(self, username, *, verified, adult):
        get_user_model().objects.filter(username=username).update(
            identity_is_verified=verified, is_adult=adult)

    def _header(self, user):
        return {'HTTP_AUTHORIZATION': f"Bearer {user[Fields.session_management_token]}"}

    def _post_for(self, user):
        return self._make_post(user[Fields.session_management_token])[Fields.post_identifier]

    def _feed_post_ids(self, user):
        url = reverse('get_posts_in_feed', kwargs={'batch': 0})
        response = self.client.get(url, **self._header(user))
        self.assertEqual(response.status_code, 200)
        return [entry[Fields.post_identifier] for entry in response.json()]

    def _post_details_status(self, viewer, post_identifier):
        url = reverse('get_post_details', kwargs={'post_identifier': post_identifier})
        return self.client.get(url, **self._header(viewer)).status_code

    def _search(self, viewer, fragment):
        url = reverse('get_users_matching_fragment', kwargs={'username_fragment': fragment})
        response = self.client.get(url, **self._header(viewer))
        self.assertEqual(response.status_code, 200)
        return [u[Fields.username] for u in response.json()]

    def _profile_status(self, viewer, username):
        url = reverse('get_profile_details', kwargs={'username': username})
        return self.client.get(url, **self._header(viewer)).status_code

    def _follow_status(self, follower, username_to_follow):
        url = reverse('follow_user', kwargs={'username_to_follow': username_to_follow})
        return self.client.post(url, **self._header(follower)).status_code

    def _like_post(self, viewer, post_identifier):
        url = reverse('like_post', kwargs={'post_identifier': post_identifier})
        return self.client.post(url, **self._header(viewer))

    def _report_post(self, viewer, post_identifier):
        url = reverse('report_post', kwargs={'post_identifier': post_identifier})
        return self.client.post(url, data={'reason': 'because'},
                                content_type='application/json', **self._header(viewer))

    # =========================================================================
    # FEED
    # =========================================================================

    def test_adult_feed_shows_adult_pool_and_hides_minors(self):
        ids = self._feed_post_ids(self.adult_a)
        self.assertIn(self.adult_b_post, ids)
        self.assertIn(self.unverified_post, ids)  # unverified is in the adult pool
        self.assertNotIn(self.minor_a_post, ids)
        self.assertNotIn(self.minor_b_post, ids)

    def test_minor_feed_shows_only_minors(self):
        ids = self._feed_post_ids(self.minor_a)
        self.assertIn(self.minor_b_post, ids)
        self.assertNotIn(self.adult_a_post, ids)
        self.assertNotIn(self.adult_b_post, ids)
        self.assertNotIn(self.unverified_post, ids)

    # =========================================================================
    # POST DETAILS
    # =========================================================================

    def test_adult_cannot_open_minor_post_details(self):
        self.assertEqual(self._post_details_status(self.adult_a, self.minor_a_post), 400)

    def test_minor_cannot_open_adult_post_details(self):
        self.assertEqual(self._post_details_status(self.minor_a, self.adult_a_post), 400)

    def test_same_band_post_details_visible(self):
        self.assertEqual(self._post_details_status(self.adult_a, self.adult_b_post), 200)
        self.assertEqual(self._post_details_status(self.adult_a, self.unverified_post), 200)
        self.assertEqual(self._post_details_status(self.minor_a, self.minor_b_post), 200)

    def test_author_can_open_own_post_details(self):
        self.assertEqual(self._post_details_status(self.minor_a, self.minor_a_post), 200)

    # =========================================================================
    # SEARCH
    # =========================================================================

    def test_adult_search_excludes_minors(self):
        names = self._search(self.adult_a, 'minor')
        self.assertNotIn(self.minor_a['username'], names)
        self.assertNotIn(self.minor_b['username'], names)

    def test_minor_search_excludes_adults_and_unverified(self):
        self.assertNotIn(self.adult_a['username'], self._search(self.minor_a, 'adult'))
        self.assertNotIn(self.unverified['username'], self._search(self.minor_a, 'unverified'))

    def test_search_finds_same_band(self):
        self.assertIn(self.adult_b['username'], self._search(self.adult_a, 'adult'))
        self.assertIn(self.minor_b['username'], self._search(self.minor_a, 'minor'))

    # =========================================================================
    # PROFILE
    # =========================================================================

    def test_adult_cannot_view_minor_profile(self):
        self.assertEqual(self._profile_status(self.adult_a, self.minor_a['username']), 400)

    def test_minor_cannot_view_adult_profile(self):
        self.assertEqual(self._profile_status(self.minor_a, self.adult_a['username']), 400)

    def test_account_can_view_own_profile(self):
        self.assertEqual(self._profile_status(self.minor_a, self.minor_a['username']), 200)

    def test_same_band_profile_visible(self):
        self.assertEqual(self._profile_status(self.adult_a, self.adult_b['username']), 200)
        self.assertEqual(self._profile_status(self.adult_a, self.unverified['username']), 200)

    # =========================================================================
    # FOLLOW
    # =========================================================================

    def test_adult_cannot_follow_minor(self):
        self.assertEqual(self._follow_status(self.adult_a, self.minor_a['username']), 400)

    def test_minor_cannot_follow_adult(self):
        self.assertEqual(self._follow_status(self.minor_a, self.adult_a['username']), 400)

    def test_same_band_follow_allowed(self):
        self.assertEqual(self._follow_status(self.adult_a, self.adult_b['username']), 200)

    # =========================================================================
    # LIKE / REPORT (cross-band interaction blocked even with a known id)
    # =========================================================================

    def test_adult_cannot_like_or_report_minor_post(self):
        like = self._like_post(self.adult_a, self.minor_a_post)
        self.assertEqual(like.status_code, 400)
        self.assertEqual(like.json()['error'], "No post with that identifier")

        report = self._report_post(self.adult_a, self.minor_a_post)
        self.assertEqual(report.status_code, 400)
        self.assertEqual(report.json()['error'], "No post with that identifier")

    def test_same_band_like_allowed(self):
        self.assertEqual(self._like_post(self.adult_a, self.adult_b_post).status_code, 200)

    def test_adult_cannot_unlike_or_retract_minor_post(self):
        # The "undo" endpoints must not leak a cross-band post's existence via a
        # distinct "not liked/reported yet" response.
        unlike = self.client.post(
            reverse('unlike_post', kwargs={'post_identifier': self.minor_a_post}),
            **self._header(self.adult_a))
        self.assertEqual(unlike.status_code, 400)
        self.assertEqual(unlike.json()['error'], "No post with that identifier")

        retract = self.client.post(
            reverse('retract_report_post', kwargs={'post_identifier': self.minor_a_post}),
            **self._header(self.adult_a))
        self.assertEqual(retract.status_code, 400)
        self.assertEqual(retract.json()['error'], "No post with that identifier")

    def test_adult_cannot_like_or_report_minor_comment(self):
        # A minor comments on another minor's post; an adult with the ids must
        # not be able to touch the comment.
        comment = self._comment_on_post(
            self.minor_a[Fields.session_management_token], self.minor_b_post)
        thread_id = comment[Fields.comment_thread_identifier]
        comment_id = comment[Fields.comment_identifier]

        like_url = reverse('like_comment', kwargs={
            'post_identifier': self.minor_b_post,
            'comment_thread_identifier': thread_id,
            'comment_identifier': comment_id})
        like = self.client.post(like_url, **self._header(self.adult_a))
        self.assertEqual(like.status_code, 400)
        self.assertEqual(like.json()['error'], "Comment not found")

        report_url = reverse('report_comment', kwargs={
            'post_identifier': self.minor_b_post,
            'comment_thread_identifier': thread_id,
            'comment_identifier': comment_id})
        report = self.client.post(report_url, data={'reason': 'because'},
                                  content_type='application/json', **self._header(self.adult_a))
        self.assertEqual(report.status_code, 400)
        self.assertEqual(report.json()['error'], "Comment not found")

        # The comment "undo" endpoints must not leak existence either.
        unlike_url = reverse('unlike_comment', kwargs={
            'post_identifier': self.minor_b_post,
            'comment_thread_identifier': thread_id,
            'comment_identifier': comment_id})
        unlike = self.client.post(unlike_url, **self._header(self.adult_a))
        self.assertEqual(unlike.status_code, 400)
        self.assertEqual(unlike.json()['error'], "Comment not found")

        retract_url = reverse('retract_report_comment', kwargs={
            'post_identifier': self.minor_b_post,
            'comment_thread_identifier': thread_id,
            'comment_identifier': comment_id})
        retract = self.client.post(retract_url, **self._header(self.adult_a))
        self.assertEqual(retract.status_code, 400)
        self.assertEqual(retract.json()['error'], "Comment not found")
