package com.example.positiveonlysocial.ui.main

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.em
import com.example.positiveonlysocial.data.model.CommentFormatSpan

/**
 * Maps the curated text-formatting keys (issue #318) to Compose fonts/colors,
 * and builds an [AnnotatedString] for a comment's inline spans. The curated
 * keys (and the fixed color palette) keep rendering consistent with the web and
 * iOS clients.
 */
object TextFormatting {
    val fontOptions = listOf("default", "serif", "monospace", "rounded", "handwriting")
    val backgroundOptions = listOf("default", "sky", "mint", "blush", "lemon", "lavender")
    val sizeOptions = listOf("small", "normal", "large", "xlarge")

    /** The caption font for a font key, or null (the default system font).
     * Accepts null (an absent key) and treats it as the default. */
    fun fontFamily(key: String?): FontFamily? = when (key) {
        "serif" -> FontFamily.Serif
        "monospace" -> FontFamily.Monospace
        // Compose has no rounded/handwriting built-ins; approximate with the
        // closest generic families so the choice is still visibly distinct.
        "rounded" -> FontFamily.SansSerif
        "handwriting" -> FontFamily.Cursive
        else -> null
    }

    /** The tile background color for a background-color key, or null (default). */
    fun backgroundColor(key: String?): Color? = when (key) {
        "sky" -> Color(0xFFDFF1FF)
        "mint" -> Color(0xFFDCF7E8)
        "blush" -> Color(0xFFFFE4EC)
        "lemon" -> Color(0xFFFFF6CC)
        "lavender" -> Color(0xFFECE3FF)
        else -> null
    }

    /** A legible foreground color for text on the given background, or null. */
    fun foregroundColor(key: String?): Color? = when (key) {
        "sky" -> Color(0xFF10334A)
        "mint" -> Color(0xFF14432B)
        "blush" -> Color(0xFF4A1327)
        "lemon" -> Color(0xFF4A3D0A)
        "lavender" -> Color(0xFF2F1A4A)
        else -> null
    }

    /** Font size for a text-size key as a relative unit, or unspecified (1em). */
    fun sizeUnit(key: String): TextUnit = when (key) {
        "small" -> 0.85f.em
        "large" -> 1.25f.em
        "xlarge" -> 1.5f.em
        else -> TextUnit.Unspecified
    }

    /**
     * Builds an [AnnotatedString] applying inline bold/italic/size spans over
     * [text]. Offsets are UTF-16 code units (matching Kotlin String indexing);
     * they are clamped so a malformed payload degrades to plain text.
     */
    fun annotatedComment(text: String, spans: List<CommentFormatSpan>?): AnnotatedString {
        if (spans.isNullOrEmpty()) return AnnotatedString(text)
        return buildAnnotatedString {
            append(text)
            val length = text.length
            for (span in spans) {
                val start = span.start.coerceIn(0, length)
                val end = span.end.coerceIn(start, length)
                if (start >= end) continue
                addStyle(
                    SpanStyle(
                        fontWeight = if (span.bold) FontWeight.Bold else null,
                        fontStyle = if (span.italic) FontStyle.Italic else null,
                        fontSize = sizeUnit(span.size)
                    ),
                    start,
                    end
                )
            }
        }
    }
}
