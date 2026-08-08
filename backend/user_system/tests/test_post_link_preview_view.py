import re
import uuid

from django.test import override_settings
from django.urls import reverse

from .test_parent_case import PositiveOnlySocialTestCase
from .. import link_preview
from ..constants import BAN_TYPE_SHADOW, Fields, HIDDEN_REASON_CLASSIFIER, POST_AUDIENCE_FRIENDS
from ..models import Post, UserBan
from ..views import get_user_with_username


def meta_content(html, attribute, name):
    """The `content` of a <meta {attribute}="{name}"> tag, or None."""
    match = re.search(
        rf'<meta {attribute}="{re.escape(name)}" content="([^"]*)"', html)
    return match.group(1) if match else None


class TruncateDescriptionTests(PositiveOnlySocialTestCase):
    """Caption -> og:description, the one place a preview shows user text."""

    def test_empty_caption_falls_back_to_the_site_blurb(self):
        for caption in (None, '', '   ', '\n\t'):
            with self.subTest(caption=caption):
                self.assertEqual(link_preview.truncate_description(caption),
                                 link_preview.DEFAULT_DESCRIPTION)

    def test_short_caption_is_passed_through_with_whitespace_collapsed(self):
        self.assertEqual(link_preview.truncate_description('  what a\n\n lovely  day  '),
                         'what a lovely day')

    def test_long_caption_is_cut_at_a_word_boundary(self):
        caption = 'sunshine ' * 60
        result = link_preview.truncate_description(caption)

        self.assertLessEqual(len(result), link_preview.MAX_DESCRIPTION_LENGTH + 1)
        self.assertTrue(result.endswith('…'))
        # The cut lands between words, so no half-word is shown.
        self.assertTrue(result[:-1].endswith('sunshine'))

    def test_single_long_word_is_hard_cut(self):
        """A caption with no spaces has no boundary to cut at; it must still be
        truncated rather than passed through whole."""
        result = link_preview.truncate_description('a' * 500)

        self.assertEqual(result, 'a' * link_preview.MAX_DESCRIPTION_LENGTH + '…')


@override_settings(FRONTEND_BASE_URL='https://smiling.social')
class PostLinkPreviewViewTests(PositiveOnlySocialTestCase):
    """
    The Open Graph document a link-preview crawler is served for a shared post
    (issue #381). It follows exactly the same public-visibility rule as the JSON
    endpoints, and a post it may not show degrades to the generic site card
    rather than an error page.
    """

    def setUp(self):
        super().setUp()

        self.author = self.make_user_with_prefix(prefix='author')
        self.author_user = get_user_with_username(self.author['username'])

        post_data = self._make_post(self.author[Fields.session_management_token])
        self.post_identifier = post_data[Fields.post_identifier]
        self.post = Post.objects.get(post_identifier=self.post_identifier)

        self.url = reverse('get_post_link_preview',
                           kwargs={'post_identifier': str(self.post_identifier)})

    def _html(self, expected_status=200):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, expected_status)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        return response.content.decode('utf-8')

    # =========================================================================
    # A PUBLIC POST
    # =========================================================================

    def test_preview_describes_the_post(self):
        Post.objects.filter(pk=self.post.pk).update(caption='a very good day')
        html = self._html()

        canonical = f'https://smiling.social/post/{self.post_identifier}'
        self.assertEqual(meta_content(html, 'property', 'og:url'), canonical)
        self.assertIn(f'<link rel="canonical" href="{canonical}" />', html)
        self.assertEqual(meta_content(html, 'property', 'og:description'), 'a very good day')
        self.assertEqual(meta_content(html, 'property', 'og:title'),
                         f"{self.author['username']} on {link_preview.SITE_NAME}")
        self.assertEqual(meta_content(html, 'property', 'og:site_name'), link_preview.SITE_NAME)
        self.assertEqual(meta_content(html, 'property', 'og:type'), 'article')

    def test_preview_carries_twitter_card_tags(self):
        html = self._html()

        self.assertEqual(meta_content(html, 'name', 'twitter:card'), 'summary_large_image')
        self.assertEqual(meta_content(html, 'name', 'twitter:title'),
                         meta_content(html, 'property', 'og:title'))
        self.assertEqual(meta_content(html, 'name', 'twitter:description'),
                         meta_content(html, 'property', 'og:description'))
        self.assertEqual(meta_content(html, 'name', 'twitter:image'),
                         meta_content(html, 'property', 'og:image'))

    def test_preview_image_is_the_posts_compressed_image(self):
        html = self._html()

        image = meta_content(html, 'property', 'og:image')
        self.assertTrue(image)
        # The image URL comes off the post, not a placeholder.
        self.assertIn(self.post.image_url.rsplit('/', 1)[-1], image)

    def test_text_only_post_degrades_to_a_summary_card(self):
        """A text-only post (#307) has no image, so there is no large-image card
        to render and no empty og:image tag to emit."""
        Post.objects.filter(pk=self.post.pk).update(image_url=None)

        html = self._html()

        self.assertEqual(meta_content(html, 'name', 'twitter:card'), 'summary')
        self.assertIsNone(meta_content(html, 'property', 'og:image'))

    def test_caption_markup_is_escaped(self):
        """A caption is user text; it must not be able to close the meta tag or
        inject script into the preview document."""
        Post.objects.filter(pk=self.post.pk).update(
            caption='" /><script>alert(1)</script><meta x="')

        html = self._html()

        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        # The description survived as text rather than breaking out of the tag.
        self.assertIn('alert(1)', meta_content(html, 'property', 'og:description'))

    def test_human_landing_on_the_preview_is_bounced_to_the_site(self):
        html = self._html()

        canonical = f'https://smiling.social/post/{self.post_identifier}'
        self.assertIn(f'<meta http-equiv="refresh" content="0; url={canonical}" />', html)
        self.assertIn(f'<a href="{canonical}">', html)

    def test_preview_is_only_briefly_cacheable(self):
        """og:image is a CloudFront-signed URL that expires, so the document
        must not be cached for long."""
        response = self.client.get(self.url)

        self.assertEqual(response['Cache-Control'], 'public, max-age=300')

    # =========================================================================
    # A POST THE CRAWLER MAY NOT SEE
    # =========================================================================

    def _assert_generic_card(self):
        html = self._html(expected_status=404)

        self.assertEqual(meta_content(html, 'property', 'og:title'), link_preview.SITE_NAME)
        self.assertEqual(meta_content(html, 'property', 'og:type'), 'website')
        self.assertIsNone(meta_content(html, 'property', 'og:image'))
        # Nothing about the post leaks — not even its id.
        self.assertNotIn(str(self.post_identifier), html)

    def test_hidden_post_gets_the_generic_card(self):
        Post.objects.filter(pk=self.post.pk).update(
            hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)

        self._assert_generic_card()

    def test_restricted_audience_post_gets_the_generic_card(self):
        Post.objects.filter(pk=self.post.pk).update(audience=POST_AUDIENCE_FRIENDS)

        self._assert_generic_card()

    def test_shadow_banned_authors_post_gets_the_generic_card(self):
        UserBan.objects.create(user=self.author_user, ban_type=BAN_TYPE_SHADOW)

        self._assert_generic_card()

    def test_missing_post_gets_the_generic_card(self):
        url = reverse('get_post_link_preview', kwargs={'post_identifier': str(uuid.uuid4())})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertIn('no longer available', response.content.decode('utf-8'))

    def test_hidden_and_missing_posts_are_indistinguishable(self):
        """A crawler must not be able to tell a moderated post from one that
        never existed."""
        missing = self.client.get(
            reverse('get_post_link_preview', kwargs={'post_identifier': str(uuid.uuid4())}))

        Post.objects.filter(pk=self.post.pk).update(
            hidden=True, hidden_reason=HIDDEN_REASON_CLASSIFIER)
        hidden = self.client.get(self.url)

        self.assertEqual(missing.status_code, hidden.status_code)
        self.assertEqual(missing.content, hidden.content)
