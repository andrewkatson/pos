"""Hashtag extraction for post captions (issue #379).

A caption may contain `#tags`. We harvest them at post-creation time and store
them normalized (lowercased, deduped) in the shared Tag table so that browsing
by tag is a plain join and #Sunset / #SUNSET / #sunset all resolve to one tag.

Extraction is deliberately forgiving: a caption is free text that already
passed the pre-filter/classifier, so parsing never rejects a post — it just
pulls out whatever `#word` tokens it finds and ignores the rest.
"""
import re

from .constants import MAX_TAG_LENGTH, MAX_TAGS_PER_POST

# A '#' followed by one or more word characters (unicode letters, digits,
# underscore). `\w` is unicode-aware for str in Python's re, so `#café` yields
# "café". The '#' itself and any surrounding punctuation are not captured.
_TAG_RE = re.compile(r'#(\w+)')


def extract_tag_names(caption):
    """The normalized tag names in a caption, in first-seen order.

    Lowercased and deduplicated. Tokens longer than MAX_TAG_LENGTH are skipped
    (they cannot be stored), and at most MAX_TAGS_PER_POST are returned.
    """
    if not caption:
        return []

    names = []
    seen = set()
    for raw in _TAG_RE.findall(caption):
        name = raw.lower()
        if len(name) > MAX_TAG_LENGTH or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= MAX_TAGS_PER_POST:
            break
    return names


def set_post_tags(post, caption):
    """Replace `post`'s tags with the ones parsed from `caption`.

    Idempotent, so it is safe to call on an edit as well as on create. Reuses
    existing Tag rows so the table stays normalized.

    Runs in a constant number of queries rather than one get_or_create per tag:
    fetch the existing rows in bulk, bulk-create the missing ones, then set the
    M2M. This keeps post creation (a hot path) cheap even with the full
    MAX_TAGS_PER_POST tags.
    """
    # Imported here rather than at module load to avoid a models<->tags import
    # cycle (models imports nothing from here, but keep the dependency one-way).
    from .models import Tag

    names = extract_tag_names(caption)
    if not names:
        post.tags.clear()
        return

    existing = {t.name: t for t in Tag.objects.filter(name__in=names)}
    missing = [name for name in names if name not in existing]
    if missing:
        # ignore_conflicts covers a race where a concurrent post created the same
        # tag between the fetch above and this insert; the unique constraint on
        # `name` makes it a no-op rather than an error. Re-fetch afterwards
        # because bulk_create(ignore_conflicts=True) does not reliably populate
        # primary keys on the passed objects.
        Tag.objects.bulk_create([Tag(name=name) for name in missing], ignore_conflicts=True)
        existing = {t.name: t for t in Tag.objects.filter(name__in=names)}

    post.tags.set([existing[name] for name in names])
