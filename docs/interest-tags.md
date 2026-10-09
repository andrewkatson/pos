# Positive interest tags (issues #446 / #35)

The discovery feed (`get_posts_in_feed`) is a "hot" ranking —
`score = (likes + 1) / (age_hours + 2)^G` — and now personalizes that ranking to
what each user has told us they find positive.

**The vocabulary.** A curated, closed set of interest *buckets* (nature, animals,
sports, music, food, …) lives in `INTEREST_CATEGORY_CHOICES`
(`backend/user_system/constants.py`) and is seeded into the `InterestCategory`
table by a data migration. It is the single source of truth: the picker options,
the buckets posts are tagged with, and the buckets users pick all come from it.
It is deliberately separate from the open-vocabulary `#hashtag` `Tag` table — a
hashtag is whatever a user typed in a caption, whereas an interest bucket is a
controlled label the feed-weighting join relies on being finite and stable.
`GET /interests/options/` returns the vocabulary and is **public**, because the
registration screen (which has no session yet) renders the picker from it.

**Choosing interests.** A user sets interests both **during registration** (the
values ride along in the register payload, since the account has no usable
session until email verification) and any time from the **Settings** picker. Two
inputs feed it:

- **Preset buckets** — multi-select from the vocabulary.
- **Freeform** — terms the user types (repeatedly, or as a comma-separated list).
  Each term is checked by the positive text classifier (`is_text_positive`,
  synchronously, exactly like a bio/username); a term that is not positive is
  rejected and reported back, never stored. Each accepted term is then mapped to
  the nearest preset bucket(s) by an interest categorizer, so "hiking" can pull
  in *nature*/*outdoors*. The term itself is kept (lowercased, deduped) so the
  picker can show it and let the user remove it; a term that maps to no bucket is
  still stored and shown, it just adds nothing to ranking.

`POST /interests/set/` (auth) has **full-replace/set semantics**: the payload is
the user's complete desired state, so anything omitted is removed. That is what
powers *removal* in Settings — deselect a bucket or delete a freeform term and
save, and it is gone; empty arrays clear everything. `GET /interests/` returns
the current selection so the picker prefills. A term already stored is kept
without re-running the classifier. The user's `interest_categories` M2M is stored
denormalized as the union of picked presets and every bucket their freeform terms
mapped to, so ranking never has to walk the freeform rows.

**Tagging posts.** An offline job assigns up to `MAX_INTEREST_TAGS_PER_POST`
buckets to each post from its **caption and image**
(`tasks.categorize_post`, using the interest categorizer over both the text and
the S3 image). It is best-effort — a post has already passed moderation by the
time it is categorized, so a provider failure just yields no buckets, never
blocking anything — and idempotent. It runs automatically the moment a post is
approved (enqueued from the approval branch of `classify_post`), and the
`categorize_posts` management command backfills existing posts and any the
approval hook missed (safe to run from cron alongside `sweep_classifications`).

**Weighting the feed.** In `calculate_weights`
(`backend/user_system/feed_algorithm/feed_algorithm.py`), the hot score is
multiplied by `(1 + INTEREST_BOOST × overlap)`, where `overlap` is the number of
interest buckets the post shares with the viewer. The boost is **linear** in the
overlap (not `(1 + INTEREST_BOOST)` per bucket), so it *scales* the hot rank
rather than replacing it: a fresh, liked,
on-topic post rises, but an ancient on-topic post still decays. When the viewer
has no interests the branch is skipped entirely, so no boost is applied and the
score is the plain hot rank — though not identical to what the feed returned
before this feature, since the distinct like count described below corrects
scores that were previously inflated. The match count is computed with a correlated subquery over the
post↔bucket join (not a second aggregate) so it can never corrupt the like count.
Interest weighting composes on top of the existing `visible_posts` and block
filters — it only reorders posts the viewer was already allowed to see.

The like count itself is counted `distinct`. `visible_posts`' audience filter
LEFT JOINs the author's follow edges and deliberately fans out (see
`visibility._audience_q`), so a plain count would tally each like once per edge
— scoring a post by an author who follows 200 people as though it had 200× the
likes. The `.distinct()` that filter applies collapses duplicate rows but does
not undo an aggregate computed over them.
