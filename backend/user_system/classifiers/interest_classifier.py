"""Topic → interest-bucket categorization (issues #446 / #35).

This is a *topic tagger*, distinct from the positive/negative safety gate in
text_classifier / image_classifier. It answers "which of the curated interest
buckets is this about?" for two callers:

- the offline post categorizer (tasks.categorize_post), on a post's caption and
  image, to populate Post.interest_categories; and
- the freeform-interest mapper (views.apply_user_interests), on a single term a
  user typed, to map "hiking" → {"nature", "outdoors"} so their freeform
  interests can influence feed weighting.

Both entry points are **best-effort**: categorization runs on content that has
already passed moderation, so a provider failure must never block anything — it
just yields no buckets. A deterministic TESTING short-circuit (keyword match)
lets the whole feature be tested without a live API, mirroring
is_text_positive / is_image_positive.
"""
import os
import re
import logging

from .classifier_constants import (
    INTEREST_CATEGORIZATION_TEXT_PROMPT, INTEREST_CATEGORIZATION_IMAGE_PROMPT,
)
from .classifier_utils import (
    get_available_apis, model_for,
    call_text_openrouter_raw, call_image_openrouter_raw,
)
from .image_classifier import load_image_from_url
from ..constants import INTEREST_CATEGORY_SLUGS, MAX_INTEREST_TAGS_PER_POST
from ..utils import convert_to_bool

logger = logging.getLogger(__name__)

# Splits a model reply (or a comma-separated user list) into candidate tokens on
# commas, newlines, and surrounding whitespace.
_SPLIT_RE = re.compile(r'[,\n]+')
# A word-boundary keyword hit for the deterministic TESTING matcher.
_WORD_RE = re.compile(r'[a-z0-9]+')


def _testing_mode():
    testing = os.environ.get("TESTING", False)
    return testing if isinstance(testing, bool) else convert_to_bool(testing)


def _keep_known(tokens, allowed_slugs, max_tags):
    """Lowercase/strip candidate tokens, keep the ones in the vocabulary, dedupe
    preserving order, and cap at max_tags."""
    kept = []
    seen = set()
    for raw in tokens:
        slug = raw.strip().lower()
        if slug and slug in allowed_slugs and slug not in seen:
            seen.add(slug)
            kept.append(slug)
            if len(kept) >= max_tags:
                break
    return kept


def _parse_reply(reply, allowed_slugs, max_tags):
    """Parse a model reply ("nature, animals" / "none") into known slugs."""
    if not reply:
        return []
    return _keep_known(_SPLIT_RE.split(str(reply)), allowed_slugs, max_tags)


def _keyword_match(text, allowed_slugs, max_tags):
    """Deterministic TESTING matcher: a bucket matches when its slug appears as a
    word in the text. Enough to exercise the categorizer end to end without a
    live model (e.g. a caption "a walk in nature with my dog" -> {"nature"})."""
    if not text:
        return []
    words = set(_WORD_RE.findall(str(text).lower()))
    matched = sorted(slug for slug in allowed_slugs if slug in words)
    return matched[:max_tags]


def _render_options(allowed_slugs):
    return ", ".join(sorted(allowed_slugs))


def categorize_text_interests(text, allowed_slugs=INTEREST_CATEGORY_SLUGS,
                              max_tags=MAX_INTEREST_TAGS_PER_POST):
    """Best-effort: the interest buckets a piece of text is about (<= max_tags).

    Never raises; returns [] on empty input, no available provider, or any
    provider error.
    """
    text = (text or "").strip()
    if not text:
        return []
    allowed_slugs = frozenset(allowed_slugs)

    if _testing_mode():
        return _keyword_match(text, allowed_slugs, max_tags)

    available = get_available_apis()
    if not available:
        logger.info("categorize_text_interests: no provider available; skipping.")
        return []

    prompt = (INTEREST_CATEGORIZATION_TEXT_PROMPT
              .replace("{options}", _render_options(allowed_slugs))
              .replace("{max}", str(max_tags))
              .replace("{text}", text))
    try:
        reply = call_text_openrouter_raw(prompt, model_for(available[0]))
    except Exception:
        logger.exception("categorize_text_interests: provider call failed; returning no buckets.")
        return []
    return _parse_reply(reply, allowed_slugs, max_tags)


def categorize_image_interests(image_url, allowed_slugs=INTEREST_CATEGORY_SLUGS,
                               max_tags=MAX_INTEREST_TAGS_PER_POST):
    """Best-effort: the interest buckets an S3-backed image is about.

    Never raises; returns [] when there is no image, no provider (or TESTING,
    where there is no real image to inspect), or on any fetch/provider error.
    """
    if not image_url:
        return []
    allowed_slugs = frozenset(allowed_slugs)

    if _testing_mode():
        # No real image bytes to inspect in tests; text drives categorization.
        return []

    available = get_available_apis()
    if not available:
        logger.info("categorize_image_interests: no provider available; skipping.")
        return []

    try:
        image = load_image_from_url(image_url)
    except Exception:
        logger.exception("categorize_image_interests: could not fetch image %s; skipping.", image_url)
        return []

    prompt = (INTEREST_CATEGORIZATION_IMAGE_PROMPT
              .replace("{options}", _render_options(allowed_slugs))
              .replace("{max}", str(max_tags)))
    try:
        reply = call_image_openrouter_raw(image, prompt, model_for(available[0]))
    except Exception:
        logger.exception("categorize_image_interests: provider call failed; returning no buckets.")
        return []
    return _parse_reply(reply, allowed_slugs, max_tags)
