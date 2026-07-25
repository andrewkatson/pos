package com.example.positiveonlysocial.ui.main

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import coil.compose.AsyncImage
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.ui.components.CaptionTile

/**
 * A post thumbnail that loads the compressed [Post.imageUrl] and falls back to
 * the full-resolution [Post.originalImageUrl] when the compressed copy isn't
 * available yet. The compressed copy is produced by an async Lambda, so a
 * just-posted (or recently hidden-pending-appeal) image can 404 in the compressed
 * bucket for a while; without the fallback those tiles render as empty black
 * boxes until the user re-logs in. Shared by the Home, Feed, and Profile grids.
 * See issues #252 and #254.
 */
@Composable
fun PostImageWithFallback(
    post: Post,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
) {
    if (post.imageUrl == null) {
        // A text-only post (#307) has no image; render its caption as the tile,
        // styled with the author's chosen font/background color (issue #318).
        CaptionTile(
            caption = post.caption,
            modifier = modifier,
            captionFont = post.captionFont,
            backgroundColor = post.backgroundColor
        )
        return
    }
    // Once the compressed URL errors, switch to the original. Keyed to the post id
    // so a recycled grid cell resets when it's reused for a different post.
    var useOriginal by remember(post.postIdentifier) { mutableStateOf(false) }
    val model = if (useOriginal) post.originalImageUrl else post.imageUrl
    AsyncImage(
        model = model,
        contentDescription = "Post Image",
        modifier = modifier,
        contentScale = contentScale,
        onError = {
            if (!useOriginal && post.originalImageUrl != null) {
                useOriginal = true
            }
        }
    )
}
