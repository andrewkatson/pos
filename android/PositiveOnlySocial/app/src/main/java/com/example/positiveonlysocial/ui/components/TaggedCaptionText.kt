package com.example.positiveonlysocial.ui.components

import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withLink

/**
 * A post caption whose #hashtags are tappable, opening the tag feed (issue
 * #379). The tags wrap inline with the caption; tapping one calls `onTagClick`
 * with the normalized tag name.
 */
@Composable
fun TaggedCaptionText(
    caption: String,
    onTagClick: (String) -> Unit,
    modifier: Modifier = Modifier,
    style: TextStyle = LocalTextStyle.current,
) {
    val linkColor = MaterialTheme.colorScheme.primary
    val annotated = buildAnnotatedString {
        for (segment in captionSegments(caption)) {
            when (segment) {
                is CaptionSegment.Text -> append(segment.text)
                is CaptionSegment.Tag -> {
                    val link = LinkAnnotation.Clickable(
                        tag = segment.name,
                        styles = TextLinkStyles(style = SpanStyle(color = linkColor)),
                    ) { onTagClick(segment.name) }
                    withLink(link) { append(segment.text) }
                }
            }
        }
    }
    Text(text = annotated, style = style, modifier = modifier)
}
