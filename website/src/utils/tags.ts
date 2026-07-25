/**
 * Hashtag helpers for captions (issue #379).
 *
 * These mirror the backend's extraction (`backend/user_system/tags.py`): a
 * `#word` token, normalized to lowercase, where "word" is unicode letters,
 * digits, and underscore. Kept in one place so caption linkification and the
 * stubbed API agree on what a tag is.
 */

// A '#' followed by one or more "word" characters, defined explicitly as
// unicode letters, numbers, or underscore (\p{L}\p{N}_) with the `u` flag —
// JS's `\w` is ASCII-only even under `u`, so this spells the class out to
// tokenize #café the same way Python's unicode-aware `\w` does on the backend.
const TAG_RE = /#([\p{L}\p{N}_]+)/gu

/** Longest tag we store, matching the backend's MAX_TAG_LENGTH. */
export const MAX_TAG_LENGTH = 100

/** Most tags a single post keeps, matching the backend's MAX_TAGS_PER_POST. */
export const MAX_TAGS_PER_POST = 30

/** The normalized tag names in a caption, lowercased and de-duplicated,
 * in first-seen order — the same set the backend stores (length- and
 * count-capped), so the two never disagree. */
export function extractTags(caption: string): string[] {
  if (!caption) return []
  const seen = new Set<string>()
  const names: string[] = []
  for (const match of caption.matchAll(TAG_RE)) {
    const name = match[1].toLowerCase()
    if (name.length > MAX_TAG_LENGTH || seen.has(name)) continue
    seen.add(name)
    names.push(name)
    if (names.length >= MAX_TAGS_PER_POST) break
  }
  return names
}

/** The route for a tag's feed page. */
export function tagPathFor(tag: string): string {
  return `/tags/${encodeURIComponent(tag)}`
}

/** A caption split into plain-text and tag segments, so a renderer can turn the
 * tag segments into links while leaving the rest as text. `tag` is the
 * normalized name to link to; `text` is the original matched text (with '#'). */
export type CaptionSegment =
  | { type: 'text'; text: string }
  | { type: 'tag'; text: string; tag: string }

export function splitCaptionByTags(caption: string): CaptionSegment[] {
  if (!caption) return []
  const segments: CaptionSegment[] = []
  // Only linkify a #token the backend would actually store: within the length
  // cap and among the first MAX_TAGS_PER_POST unique tags. A repeat of an
  // already-linkable tag stays linkable; anything else is left as plain text so
  // a tapped tag always resolves and the caption still reads verbatim.
  const linkable = new Set<string>()
  let lastIndex = 0
  for (const match of caption.matchAll(TAG_RE)) {
    const name = match[1].toLowerCase()
    const canLink =
      name.length <= MAX_TAG_LENGTH &&
      (linkable.has(name) || linkable.size < MAX_TAGS_PER_POST)
    if (!canLink) continue
    linkable.add(name)
    const start = match.index ?? 0
    if (start > lastIndex) {
      segments.push({ type: 'text', text: caption.slice(lastIndex, start) })
    }
    segments.push({ type: 'tag', text: match[0], tag: name })
    lastIndex = start + match[0].length
  }
  if (lastIndex < caption.length) {
    segments.push({ type: 'text', text: caption.slice(lastIndex) })
  }
  return segments
}
