package com.example.positiveonlysocial.ui.main

import com.example.positiveonlysocial.data.model.CommentFormatSpan

/**
 * Editor-side per-character formatting for composing a comment (issue #318).
 * Mirrors the web/iOS char-attribute model: the toolbar sets attributes over
 * the current selection, and on submit the array is compressed into the sorted,
 * non-overlapping spans the API expects. One entry per UTF-16 code unit (a
 * Kotlin `Char`), so offsets line up with the backend contract.
 */
data class CharStyle(
    val bold: Boolean = false,
    val italic: Boolean = false,
    val size: String = "normal"
) {
    val isPlain: Boolean get() = !bold && !italic && size == "normal"
}

object CommentFormatting {
    fun emptyStyles(count: Int): List<CharStyle> = List(count) { CharStyle() }

    /**
     * Reconcile the style list across a single text edit by diffing the common
     * prefix and suffix. Inserted characters get default (plain) styles;
     * untouched characters keep theirs. The result always has one entry per
     * character in [newText].
     */
    fun reconcile(prev: List<CharStyle>, oldText: String, newText: String): List<CharStyle> {
        if (oldText == newText) return prev
        val styles = if (prev.size == oldText.length) prev else emptyStyles(oldText.length)
        val minLen = minOf(oldText.length, newText.length)
        var prefix = 0
        while (prefix < minLen && oldText[prefix] == newText[prefix]) prefix++
        var suffix = 0
        while (suffix < (minLen - prefix) &&
            oldText[oldText.length - 1 - suffix] == newText[newText.length - 1 - suffix]
        ) {
            suffix++
        }
        val head = styles.subList(0, prefix)
        val tail = styles.subList(oldText.length - suffix, oldText.length)
        val insertedCount = (newText.length - suffix - prefix).coerceAtLeast(0)
        return head + emptyStyles(insertedCount) + tail
    }

    fun applyToRange(
        styles: List<CharStyle>,
        start: Int,
        end: Int,
        transform: (CharStyle) -> CharStyle
    ): List<CharStyle> {
        if (start >= end) return styles
        return styles.mapIndexed { i, style -> if (i in start until end) transform(style) else style }
    }

    /** Toggle bold over [start, end): off if all already bold, else on. */
    fun toggleBold(styles: List<CharStyle>, start: Int, end: Int): List<CharStyle> {
        if (start >= end) return styles
        val allOn = (start until end).all { it < styles.size && styles[it].bold }
        return applyToRange(styles, start, end) { it.copy(bold = !allOn) }
    }

    /** Toggle italic over [start, end): off if all already italic, else on. */
    fun toggleItalic(styles: List<CharStyle>, start: Int, end: Int): List<CharStyle> {
        if (start >= end) return styles
        val allOn = (start until end).all { it < styles.size && styles[it].italic }
        return applyToRange(styles, start, end) { it.copy(italic = !allOn) }
    }

    fun setSize(styles: List<CharStyle>, start: Int, end: Int, size: String): List<CharStyle> =
        applyToRange(styles, start, end) { it.copy(size = size) }

    /** Compress the style list into sorted, non-overlapping spans, dropping
     * unstyled runs. Returns null when there is no formatting. */
    fun toSpans(styles: List<CharStyle>): List<CommentFormatSpan>? {
        val spans = mutableListOf<CommentFormatSpan>()
        var i = 0
        while (i < styles.size) {
            val style = styles[i]
            if (style.isPlain) {
                i++
                continue
            }
            var j = i + 1
            while (j < styles.size && styles[j] == style) j++
            spans.add(CommentFormatSpan(i, j, style.bold, style.italic, style.size))
            i = j
        }
        return spans.ifEmpty { null }
    }
}
