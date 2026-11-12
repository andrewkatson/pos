# Hashtags (#tags)

Captions can carry `#hashtags` (issue #379). When a post is created, the
backend parses every `#word` token out of the caption and stores the tags,
normalized to lowercase, in a shared `Tag` table linked to the post
(`backend/user_system/tags.py`, `Post.tags`). Normalization means `#Sunset`,
`#SUNSET` and `#sunset` are the same tag, and a tag row is shared across every
post that uses it. Parsing is forgiving — a caption is free text that already
passed the pre-filter/classifier, so extraction never rejects a post; it just
harvests what it finds. A tag is at most `MAX_TAG_LENGTH` characters and a post
keeps at most `MAX_TAGS_PER_POST` of them.

Every full post payload the API returns — the feed, followed-feed, profile,
saved-posts, tag-feed, and post-details endpoints — carries a `tags` array
(sorted tag names), so clients render the caption's `#tags` as links. (The
appeals/hidden-content listings return a reduced post shape and omit it.) Tapping a tag opens a **tag
feed**: `GET /tags/<tag>/posts/<batch>/` lists the visible posts carrying that
tag, newest first, batched like the other feeds. The tag feed applies exactly
the same visibility and block rules as every other listing endpoint
(`visible_posts` plus the per-viewer block filters), so a hidden, pending,
shadow-banned, or blocked author's post never surfaces there — the tag is only
an extra filter layered on top of the normal visibility query. Tags are
extracted even for a post still pending classification, but that post stays
author-only until it is approved, so its tags cannot leak into anyone else's
tag feed.
