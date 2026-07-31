import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from ..constants import (
    HIDDEN_REASON_NONE, HIDDEN_REASON_PENDING_CLASSIFICATION,
    HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_CLASSIFIER_FINAL, HIDDEN_REASON_REPORTS,
    MAX_INTEREST_TAGS_PER_POST,
)
from ..models import Post, InterestCategory
from .. import tasks


@override_settings(RATELIMIT_ENABLE=False)
@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class CategorizePostTaskTests(TestCase):
    """tasks.categorize_post assigns interest buckets to approved posts. In
    TESTING the categorizer keyword-matches captions against bucket slugs, so a
    caption naming buckets is tagged with them."""

    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user(username='author', email='a@t.com')

    def _post(self, caption, hidden_reason=HIDDEN_REASON_NONE, image_url=None):
        return Post.objects.create(
            author=self.author, caption=caption, image_url=image_url,
            hidden=(hidden_reason != HIDDEN_REASON_NONE), hidden_reason=hidden_reason)

    def _slugs(self, post):
        return sorted(post.interest_categories.values_list('slug', flat=True))

    def test_assigns_buckets_from_caption(self):
        post = self._post("A walk in nature with some music")
        tasks.categorize_post(post.post_identifier)
        self.assertEqual(self._slugs(post), ['music', 'nature'])

    def test_caps_at_max_tags(self):
        post = self._post("nature music art food travel science")
        tasks.categorize_post(post.post_identifier)
        self.assertEqual(len(self._slugs(post)), MAX_INTEREST_TAGS_PER_POST)

    def test_no_match_leaves_no_buckets(self):
        post = self._post("just some ordinary words here")
        tasks.categorize_post(post.post_identifier)
        self.assertEqual(self._slugs(post), [])

    def test_idempotent(self):
        post = self._post("nature")
        tasks.categorize_post(post.post_identifier)
        tasks.categorize_post(post.post_identifier)
        self.assertEqual(self._slugs(post), ['nature'])

    def test_skips_pending_post(self):
        post = self._post("nature", hidden_reason=HIDDEN_REASON_PENDING_CLASSIFICATION)
        tasks.categorize_post(post.post_identifier)
        self.assertEqual(self._slugs(post), [])

    def test_skips_rejected_posts(self):
        for reason in (HIDDEN_REASON_CLASSIFIER, HIDDEN_REASON_CLASSIFIER_FINAL):
            post = self._post("nature", hidden_reason=reason)
            tasks.categorize_post(post.post_identifier)
            self.assertEqual(self._slugs(post), [])

    def test_report_hidden_post_is_still_categorized(self):
        # A report-hidden post already passed classification and may return to
        # the feed, so it is categorizable.
        post = self._post("nature", hidden_reason=HIDDEN_REASON_REPORTS)
        tasks.categorize_post(post.post_identifier)
        self.assertEqual(self._slugs(post), ['nature'])

    def test_provider_outage_does_not_clear_existing_buckets(self):
        # The categorizer returns [] both when nothing matches and when it could
        # not run (no provider, provider down). A redelivered job during an
        # outage must not strip buckets an earlier run found.
        post = self._post("nature and animals")
        tasks.categorize_post(post.post_identifier)
        self.assertEqual(self._slugs(post), ['animals', 'nature'])

        with patch('user_system.tasks.interest_classifier_class.categorize_text_interests',
                   return_value=[]), \
             patch('user_system.tasks.interest_classifier_class.categorize_image_interests',
                   return_value=[]):
            tasks.categorize_post(post.post_identifier)

        self.assertEqual(self._slugs(post), ['animals', 'nature'])

    def test_missing_post_is_noop(self):
        # Should not raise for a post that no longer exists.
        tasks.categorize_post("00000000-0000-0000-0000-000000000000")


@override_settings(RATELIMIT_ENABLE=False)
@patch.dict(os.environ, {"TESTING": "True"}, clear=True)
class CategorizePostsCommandTests(TestCase):
    """The categorize_posts backfill command tags approved, uncategorized posts."""

    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user(username='author', email='a@t.com')

    def test_backfills_uncategorized_approved_posts(self):
        post = Post.objects.create(author=self.author, caption="nature and animals",
                                   hidden=False, hidden_reason=HIDDEN_REASON_NONE)
        call_command('categorize_posts')
        self.assertEqual(sorted(post.interest_categories.values_list('slug', flat=True)),
                         ['animals', 'nature'])

    def test_dry_run_changes_nothing(self):
        post = Post.objects.create(author=self.author, caption="nature",
                                   hidden=False, hidden_reason=HIDDEN_REASON_NONE)
        call_command('categorize_posts', '--dry-run')
        self.assertEqual(post.interest_categories.count(), 0)

    def test_skips_already_categorized(self):
        post = Post.objects.create(author=self.author, caption="nature",
                                   hidden=False, hidden_reason=HIDDEN_REASON_NONE)
        # Pre-tag with an unrelated bucket; backfill only targets posts with none,
        # so this post is left untouched.
        post.interest_categories.add(InterestCategory.objects.get(slug='sports'))
        call_command('categorize_posts')
        self.assertEqual(sorted(post.interest_categories.values_list('slug', flat=True)),
                         ['sports'])
