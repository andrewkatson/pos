package com.example.positiveonlysocial.ui.main

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.em
import com.example.positiveonlysocial.R
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

    /**
     * The "rounded" caption font. Android has no rounded system family — unlike
     * web (a `ui-rounded`-led stack) and iOS (`.system(design: .rounded)`) — so
     * mapping the key to a generic family made the choice a silent no-op: it
     * rendered exactly like "default". Nunito, bundled in `res/font`, is the
     * closest match: a soft sans with rounded terminals. It is licensed under
     * the SIL Open Font License (`licenses/Nunito-OFL.txt`).
     *
     * One variable font file covers every weight. `minSdk` is 26, which is also
     * where Android gained variable-font support, so the `wght` axis always
     * applies.
     *
     * Captions render at two weights today — CaptionTile uses SemiBold, while
     * the composer preview, the feed row (issue #450) and the detail view all
     * use Normal. Bold is registered anyway: it costs nothing in a variable
     * font, and without it a bold caption would be emboldened synthetically
     * from the 600 instance instead of using the real 700 one. (Comments do
     * carry inline bold spans, but they style weight only — `annotatedComment`
     * sets no family — so a bold comment span never reaches this font.)
     */
    // The variation-settings overload of Font() is still ExperimentalTextApi.
    // Opting in is contained to this one family; if it ever changes, the fix is
    // to register per-weight static Nunito files instead.
    @OptIn(ExperimentalTextApi::class)
    private val roundedFontFamily = FontFamily(
        Font(R.font.nunito_variable, FontWeight.Normal, variationSettings = weightAxis(400)),
        Font(R.font.nunito_variable, FontWeight.SemiBold, variationSettings = weightAxis(600)),
        Font(R.font.nunito_variable, FontWeight.Bold, variationSettings = weightAxis(700))
    )

    private fun weightAxis(weight: Int) =
        FontVariation.Settings(FontVariation.weight(weight))

    /** The caption font for a font key, or null (the default system font).
     * Accepts null (an absent key) and treats it as the default. */
    fun fontFamily(key: String?): FontFamily? = when (key) {
        "serif" -> FontFamily.Serif
        "monospace" -> FontFamily.Monospace
        "rounded" -> roundedFontFamily
        // Compose has no handwriting built-in, but Cursive resolves to the
        // system's script face (Dancing Script on AOSP), which is distinct.
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
