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
