package com.example.positiveonlysocial.ui.components

/** A caption segment: literal text, or a #hashtag with its normalized name. */
sealed interface CaptionSegment {
    data class Text(val text: String) : CaptionSegment
    data class Tag(val text: String, val name: String) : CaptionSegment
}

private val TAG_REGEX = Regex("#([\\p{L}\\p{N}_]+)")

// Caps mirroring the backend (backend/user_system/constants.py), so a #token is
// only linkified when the backend would actually store it as a tag.
private const val MAX_TAG_LENGTH = 100
private const val MAX_TAGS_PER_POST = 30

/**
 * Splits a caption into text and #hashtag segments, mirroring the backend's
 * extraction (`backend/user_system/tags.py`): a '#' followed by unicode
 * letters, numbers, or underscore (\p{L}\p{N}_). That class is exactly
 * equivalent to the backend's Python `\w` on a `str` (both are alphanumerics
 * plus underscore and exclude combining marks / connector punctuation), so the
 * two tokenize a caption identically. Kotlin's `lowercase()` uses the invariant
 * (root) locale — locale-independent, matching the backend's str.lower() — so
 * casing never diverges. The tag `name` is lowercased; `text` keeps its casing.
 * Only tags the backend would store are emitted as [CaptionSegment.Tag] —
 * overlong tags and anything past the first [MAX_TAGS_PER_POST] unique names
 * stay as plain text, so a tapped tag always resolves and the caption still
 * reads verbatim.
 */
fun captionSegments(caption: String): List<CaptionSegment> {
    if (caption.isEmpty()) return emptyList()
    val segments = mutableListOf<CaptionSegment>()
    val linkable = mutableSetOf<String>()
    var lastEnd = 0
    for (match in TAG_REGEX.findAll(caption)) {
        val name = match.groupValues[1].lowercase()
        val canLink = name.length <= MAX_TAG_LENGTH &&
            (name in linkable || linkable.size < MAX_TAGS_PER_POST)
        if (!canLink) continue
        linkable.add(name)
        val range = match.range
        if (range.first > lastEnd) {
            segments.add(CaptionSegment.Text(caption.substring(lastEnd, range.first)))
        }
        segments.add(CaptionSegment.Tag(text = match.value, name = name))
        lastEnd = range.last + 1
    }
    if (lastEnd < caption.length) {
        segments.add(CaptionSegment.Text(caption.substring(lastEnd)))
    }
    return segments
}
