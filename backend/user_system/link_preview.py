"""Open Graph / Twitter Card HTML for a shared post link (issue #381).

The website is a client-only Vite SPA served from S3/CloudFront, so a crawler
that fetches `https://smiling.social/post/<id>` gets an empty `<div id="root">`
and nothing to unfurl. This module renders the small, self-contained HTML
document the crawler is sent instead: nothing but `<meta>` tags plus a human
fallback that bounces a real browser on to the SPA route.

It deliberately does no template loading and no JS: the document is built from
escaped strings so it can be unit tested without a request, and so a crawler
that ignores scripts still sees every tag it needs.
"""

from django.utils.html import escape

# How much of a caption goes into og:description. Facebook/Slack/Twitter all
# truncate somewhere near 200-300 characters anyway; cutting server-side keeps
# the document small and avoids a mid-word cut in the middle of a preview card.
MAX_DESCRIPTION_LENGTH = 200

# Shown when a post has no caption at all (a photo-only post), so the preview
# card never renders with an empty description line.
DEFAULT_DESCRIPTION = "A post on Good Vibes Only, the positivity-only social network."

SITE_NAME = "Good Vibes Only"


def truncate_description(caption):
    """A caption trimmed to preview length, ending at a word boundary.

    Returns DEFAULT_DESCRIPTION for an empty/whitespace-only caption so the
    card always has a description. Long captions are cut at the last space
    before the limit (falling back to a hard cut when a single 'word' is longer
    than the limit) and get a single-character ellipsis.
    """
    text = ' '.join((caption or '').split())
    if not text:
        return DEFAULT_DESCRIPTION
    if len(text) <= MAX_DESCRIPTION_LENGTH:
        return text
    cut = text[:MAX_DESCRIPTION_LENGTH]
    boundary = cut.rfind(' ')
    if boundary > 0:
        cut = cut[:boundary]
    return f"{cut.rstrip()}…"


def _meta(tags):
    """Render `(attribute, name, content)` triples as escaped <meta> tags,
    skipping any whose content is empty."""
    return '\n'.join(
        f'    <meta {attribute}="{escape(name)}" content="{escape(content)}" />'
        for attribute, name, content in tags
        if content
    )


def render_post_preview(*, title, description, canonical_url, image_url=None):
    """The full HTML document served to a crawler for a shared post link.

    `image_url` is optional: a text-only post (#307) has no image, and its card
    degrades from a `summary_large_image` to a plain `summary`. Every value is
    HTML-escaped, so a caption containing markup cannot break out of the meta
    tags or inject script into the document.
    """
    card_type = 'summary_large_image' if image_url else 'summary'
    tags = [
        ('name', 'description', description),
        ('property', 'og:type', 'article'),
        ('property', 'og:site_name', SITE_NAME),
        ('property', 'og:title', title),
        ('property', 'og:description', description),
        ('property', 'og:url', canonical_url),
        ('property', 'og:image', image_url or ''),
        ('name', 'twitter:card', card_type),
        ('name', 'twitter:title', title),
        ('name', 'twitter:description', description),
        ('name', 'twitter:image', image_url or ''),
    ]
    # The refresh sends a human who somehow landed on this URL (a crawler
    # redirect they followed by hand, a copied preview link) on to the real
    # page. Crawlers ignore it and read the meta tags above; the visible link is
    # the no-JS fallback for anything that ignores both.
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{escape(title)}</title>
    <link rel="canonical" href="{escape(canonical_url)}" />
{_meta(tags)}
    <meta http-equiv="refresh" content="0; url={escape(canonical_url)}" />
  </head>
  <body>
    <p><a href="{escape(canonical_url)}">{escape(title)}</a></p>
  </body>
</html>
"""


def render_missing_preview(*, site_url):
    """The document served when a shared link points at a post that is gone,
    hidden, or not public. It is deliberately indistinguishable from the
    never-existed case — a crawler must not be able to probe moderation state —
    and carries no post-specific tags."""
    tags = [
        ('name', 'description', DEFAULT_DESCRIPTION),
        ('property', 'og:type', 'website'),
        ('property', 'og:site_name', SITE_NAME),
        ('property', 'og:title', SITE_NAME),
        ('property', 'og:description', DEFAULT_DESCRIPTION),
        ('property', 'og:url', site_url),
        ('name', 'twitter:card', 'summary'),
    ]
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{escape(SITE_NAME)}</title>
{_meta(tags)}
  </head>
  <body>
    <p>This post is no longer available.</p>
    <p><a href="{escape(site_url)}">{escape(SITE_NAME)}</a></p>
  </body>
</html>
"""
