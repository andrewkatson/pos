package com.example.positiveonlysocial.ui.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign

/** Fraction of a length limit at which the counter starts warning (mirrors web/iOS). */
private const val NEAR_LIMIT_FRACTION = 0.9

/**
 * Counts unicode code points rather than UTF-16 code units, so the count matches
 * Python's len() on the backend (which is what the server enforces). e.g. "💚"
 * is one code point here, like it is one character server-side, even though its
 * String.length is 2.
 */
fun characterCount(text: String): Int = text.codePointCount(0, text.length)

/** Whether [text] is within [max] code points — used to gate submit buttons so
 * the client never sends content the backend would reject for length. */
fun isWithinLength(text: String, max: Int): Boolean = characterCount(text) <= max

/**
 * A live "count / max" indicator mirroring the backend length limits
 * (backend/user_system/constants.py). Turns amber as the user nears the limit
 * and red once over it.
 */
@Composable
fun CharacterCounter(text: String, max: Int, modifier: Modifier = Modifier) {
    val count = characterCount(text)
    val isOver = count > max
    val isNear = !isOver && count >= max * NEAR_LIMIT_FRACTION
    val color = when {
        isOver -> Color(0xFFE5484D)
        isNear -> Color(0xFFE0A106)
        else -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
    }
    Text(
        text = if (isOver) "${count - max} over the $max character limit" else "$count / $max",
        color = color,
        style = MaterialTheme.typography.labelSmall,
        textAlign = TextAlign.End,
        modifier = modifier.fillMaxWidth(),
    )
}
