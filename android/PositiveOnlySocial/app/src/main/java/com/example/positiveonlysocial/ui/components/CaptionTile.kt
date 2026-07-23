package com.example.positiveonlysocial.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.positiveonlysocial.ui.main.TextFormatting

/**
 * The visual stand-in for a text-only post's image (#307): the caption rendered
 * centered on a themed gradient background. Used wherever posts render as image
 * tiles — grid cells clamp the text via [maxLines], the detail view passes
 * [Int.MAX_VALUE] to show the full caption.
 *
 * The author's chosen caption font and background color (issue #318) are
 * applied here; "default" keeps the original themed gradient and system font.
 */
@Composable
fun CaptionTile(
    caption: String,
    modifier: Modifier = Modifier,
    maxLines: Int = 4,
    captionFont: String? = null,
    backgroundColor: String? = null,
) {
    val paletteColor = TextFormatting.backgroundColor(backgroundColor)
    val backgroundModifier = if (paletteColor != null) {
        modifier.background(paletteColor)
    } else {
        modifier.background(
            Brush.linearGradient(
                colors = listOf(
                    MaterialTheme.colorScheme.primary,
                    MaterialTheme.colorScheme.tertiary
                )
            )
        )
    }
    Box(
        modifier = backgroundModifier,
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = caption,
            modifier = Modifier.padding(12.dp),
            color = TextFormatting.foregroundColor(backgroundColor) ?: MaterialTheme.colorScheme.onPrimary,
            fontFamily = TextFormatting.fontFamily(captionFont),
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            maxLines = maxLines,
            overflow = TextOverflow.Ellipsis
        )
    }
}
