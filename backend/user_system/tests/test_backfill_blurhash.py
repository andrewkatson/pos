"""Tests for the backfill_blurhash management command (issue #438)."""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ..models import Post

COMMAND = 'backfill_blurhash'
COMPUTE = 'user_system.management.commands.backfill_blurhash.compute_blurhash_for_image_url'


def _url(key):
    return f'https://test-bucket.s3.amazonaws.com/{key}'


def _hash_for(image_url):
    """Deterministic stand-in hash so tests can assert which URL was encoded."""
    return f'hash::{image_url}'


class BackfillBlurhashCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username='backfill_user')

    def _make_post(self, key=None, image_url=None, image_blurhash=None):
        if image_url is None and key is not None:
            image_url = _url(key)
        return Post.objects.create(
            author=self.user, image_url=image_url,
            image_blurhash=image_blurhash, caption='hi',
        )

    def test_backfills_only_posts_missing_a_hash(self):
        missing = self._make_post(key='1/a.jpeg')
        already = self._make_post(key='1/b.jpeg', image_blurhash='kept')
        text_only = self._make_post(image_url=None)

        out = StringIO()
        with patch(COMPUTE, side_effect=_hash_for) as compute:
            call_command(COMMAND, stdout=out)

        # Only the hash-less image post is fetched and encoded.
        compute.assert_called_once_with(missing.image_url)

        missing.refresh_from_db()
        already.refresh_from_db()
        text_only.refresh_from_db()
        self.assertEqual(missing.image_blurhash, _hash_for(missing.image_url))
        self.assertEqual(already.image_blurhash, 'kept')   # never overwritten
        self.assertIsNone(text_only.image_blurhash)        # no image, untouched
        self.assertIn('Backfilled 1 post(s)', out.getvalue())

    def test_dry_run_writes_nothing(self):
        post = self._make_post(key='1/a.jpeg')

        out = StringIO()
        with patch(COMPUTE, side_effect=_hash_for) as compute:
            call_command(COMMAND, '--dry-run', stdout=out)

        compute.assert_not_called()
        post.refresh_from_db()
        self.assertIsNone(post.image_blurhash)
        self.assertIn('[dry-run] 1 post(s)', out.getvalue())

    def test_uncomputable_post_is_skipped_and_does_not_loop(self):
        """A post whose image can't be encoded stays null and is not retried
        forever (the pk cursor advances past it)."""
        good = self._make_post(key='1/good.jpeg')
        bad = self._make_post(key='1/bad.jpeg')

        def compute(image_url):
            return None if image_url == bad.image_url else _hash_for(image_url)

        out = StringIO()
        with patch(COMPUTE, side_effect=compute):
            call_command(COMMAND, '--batch-size', '1', stdout=out)

        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertEqual(good.image_blurhash, _hash_for(good.image_url))
        self.assertIsNone(bad.image_blurhash)
        self.assertIn('Backfilled 1 post(s); skipped 1', out.getvalue())

    def test_limit_caps_posts_examined(self):
        for i in range(3):
            self._make_post(key=f'1/p{i}.jpeg')

        with patch(COMPUTE, side_effect=_hash_for) as compute:
            call_command(COMMAND, '--limit', '2', '--batch-size', '1', stdout=StringIO())

        self.assertEqual(compute.call_count, 2)
        self.assertEqual(
            Post.objects.filter(image_blurhash__isnull=False).count(), 2
        )

    def test_rejects_nonpositive_flags(self):
        post = self._make_post(key='1/a.jpeg')

        with patch(COMPUTE, side_effect=_hash_for) as compute:
            for args in (['--batch-size', '0'], ['--batch-size', '-5'],
                         ['--limit', '0'], ['--limit', '-1']):
                with self.assertRaises(CommandError):
                    call_command(COMMAND, *args, stdout=StringIO())

        # Nothing ran: no encode attempted and no hash written.
        compute.assert_not_called()
        post.refresh_from_db()
        self.assertIsNone(post.image_blurhash)


class BackfillProfilePhotoBlurhashTests(TestCase):
    """The profile-photo half of the backfill (issue #460)."""

    def _make_user(self, name, profile_image_url=None, profile_image_blurhash=None):
        return get_user_model().objects.create(
            username=name, profile_image_url=profile_image_url,
            profile_image_blurhash=profile_image_blurhash,
        )

    def test_backfills_only_approved_photos_missing_a_hash(self):
        missing = self._make_user('blur_missing', profile_image_url=_url('1/a.jpeg'))
        already = self._make_user('blur_already', profile_image_url=_url('1/b.jpeg'),
                                  profile_image_blurhash='kept')
        # A user with only a *pending* upload is never shown to anyone else, so
        # it needs no placeholder and must not be fetched or encoded.
        pending_only = self._make_user('blur_pending')
        pending_only.pending_profile_image_url = _url('1/c.jpeg')
        pending_only.save(update_fields=['pending_profile_image_url'])

        out = StringIO()
        with patch(COMPUTE, side_effect=_hash_for) as compute:
            call_command(COMMAND, '--target', 'profiles', stdout=out)

        compute.assert_called_once_with(missing.profile_image_url)

        for user in (missing, already, pending_only):
            user.refresh_from_db()
        self.assertEqual(missing.profile_image_blurhash,
                         _hash_for(missing.profile_image_url))
        self.assertEqual(already.profile_image_blurhash, 'kept')  # never overwritten
        self.assertIsNone(pending_only.profile_image_blurhash)
        self.assertIn('Backfilled 1 profile photo(s)', out.getvalue())

    def test_dry_run_writes_nothing(self):
        user = self._make_user('blur_dry', profile_image_url=_url('1/a.jpeg'))

        out = StringIO()
        with patch(COMPUTE, side_effect=_hash_for) as compute:
            call_command(COMMAND, '--target', 'profiles', '--dry-run', stdout=out)

        compute.assert_not_called()
        user.refresh_from_db()
        self.assertIsNone(user.profile_image_blurhash)
        self.assertIn('[dry-run] 1 profile photo(s)', out.getvalue())

    def test_uncomputable_photo_is_skipped_and_does_not_loop(self):
        good = self._make_user('blur_good', profile_image_url=_url('1/good.jpeg'))
        bad = self._make_user('blur_bad', profile_image_url=_url('1/bad.jpeg'))

        def compute(image_url):
            return None if image_url == bad.profile_image_url else _hash_for(image_url)

        out = StringIO()
        with patch(COMPUTE, side_effect=compute):
            call_command(COMMAND, '--target', 'profiles', '--batch-size', '1', stdout=out)

        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertEqual(good.profile_image_blurhash, _hash_for(good.profile_image_url))
        self.assertIsNone(bad.profile_image_blurhash)
        self.assertIn('Backfilled 1 profile photo(s); skipped 1', out.getvalue())

    def test_default_target_covers_posts_and_profiles(self):
        author = self._make_user('blur_both', profile_image_url=_url('1/avatar.jpeg'))
        post = Post.objects.create(author=author, image_url=_url('1/post.jpeg'), caption='hi')

        out = StringIO()
        with patch(COMPUTE, side_effect=_hash_for):
            call_command(COMMAND, stdout=out)

        author.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(post.image_blurhash, _hash_for(post.image_url))
        self.assertEqual(author.profile_image_blurhash, _hash_for(author.profile_image_url))
        self.assertIn('Backfilled 1 post(s)', out.getvalue())
        self.assertIn('Backfilled 1 profile photo(s)', out.getvalue())

    def test_posts_target_leaves_profiles_alone(self):
        author = self._make_user('blur_posts_only', profile_image_url=_url('1/avatar.jpeg'))
        post = Post.objects.create(author=author, image_url=_url('1/post.jpeg'), caption='hi')

        with patch(COMPUTE, side_effect=_hash_for):
            call_command(COMMAND, '--target', 'posts', stdout=StringIO())

        author.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(post.image_blurhash, _hash_for(post.image_url))
        self.assertIsNone(author.profile_image_blurhash)
