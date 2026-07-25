package com.example.positiveonlysocial.ui.components

/** A caption segment: literal text, or a #hashtag with its normalized name. */
sealed interface CaptionSegment {
    data class Text(val text: String) : CaptionSegment
    data class Tag(val text: String, val name: String) : CaptionSegment
}

private val TAG_REGEX = Regex("#([\\p{L}\\p{N}_]+)")

/**
 * Splits a caption into text and #hashtag segments, mirroring the backend's
 * extraction (`backend/user_system/tags.py`): a '#' followed by unicode word
 * characters. The tag `name` is lowercased; `text` keeps the original casing.
 */
fun captionSegments(caption: String): List<CaptionSegment> {
    if (caption.isEmpty()) return emptyList()
    val segments = mutableListOf<CaptionSegment>()
    var lastEnd = 0
    for (match in TAG_REGEX.findAll(caption)) {
        val range = match.range
        if (range.first > lastEnd) {
            segments.add(CaptionSegment.Text(caption.substring(lastEnd, range.first)))
        }
        segments.add(CaptionSegment.Tag(text = match.value, name = match.groupValues[1].lowercase()))
        lastEnd = range.last + 1
    }
    if (lastEnd < caption.length) {
        segments.add(CaptionSegment.Text(caption.substring(lastEnd)))
    }
    return segments
}
