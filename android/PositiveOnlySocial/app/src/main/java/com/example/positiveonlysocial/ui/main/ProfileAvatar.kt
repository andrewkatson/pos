package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.painter.BitmapPainter
import androidx.compose.ui.graphics.painter.ColorPainter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.example.positiveonlysocial.util.BlurHashDecoder

/**
 * A user's profile photo (issue #7), rendered as a circular avatar next to their
 * name everywhere it appears — feed rows, post/comment authors, search results,
 * blocked users and the large profile header.
 *
 * Falls back the same way post images do (see [PostImageWithFallback]): the
 * compressed [imageUrl] first, then the full-resolution [originalImageUrl] if
 * that fails to load (the compressed copy is produced by an async Lambda and can
 * 404 briefly — see issues #252/#254), and finally a neutral gray-circle
 * placeholder when there is no photo at all or both URLs fail.
 *
 * While the photo loads, its [blurHash] preview (issue #460) stands in for the
 * flat gray circle — the same treatment [PostImageWithFallback] gives post
 * images, decoded with the same [BlurHashDecoder].
 */
@Composable
fun ProfileAvatar(
    imageUrl: String?,
    originalImageUrl: String? = null,
    contentDescription: String? = null,
    size: Dp = 32.dp,
    modifier: Modifier = Modifier,
    blurHash: String? = null,
) {
    val circle = modifier.size(size).clip(CircleShape)

    // The compressed→original switch flips at most once each way, so a failing
    // original leaves the placeholder rather than looping. Keyed to BOTH URLs so
    // the fallback resets whenever either changes — a recycled row reused for a
    // different user, or a refreshed signed URL where only the original differs.
    var useOriginal by remember(imageUrl, originalImageUrl) { mutableStateOf(false) }
    var failed by remember(imageUrl, originalImageUrl) { mutableStateOf(false) }

    val model = if (useOriginal) originalImageUrl else imageUrl

    // Shown while the photo loads (and kept as the error image so an avatar whose
    // compressed and original URLs both fail isn't left blank): the decoded
    // BlurHash when the user has one (issue #460), otherwise the same flat gray
    // circle as the no-photo case. Never null, mirroring PostImageWithFallback.
    val blurBitmap = remember(blurHash) { BlurHashDecoder.decode(blurHash)?.asImageBitmap() }
    val placeholderPainter = remember(blurBitmap) {
        blurBitmap?.let { BitmapPainter(it) } ?: ColorPainter(Color.Gray)
    }

    if (model == null || failed) {
        // Both URLs failed: keep the blurred preview rather than dropping to the
        // person icon — it is still a truer stand-in for the photo, and it is
        // what the loading state was already showing. A user with no photo at
        // all has no hash, so they get the neutral circle as before.
        if (failed && blurBitmap != null) {
            Image(
                bitmap = blurBitmap,
                contentDescription = contentDescription,
                modifier = circle,
                contentScale = ContentScale.Crop
            )
            return
        }
        Box(
            modifier = circle.background(Color.Gray),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Person,
                contentDescription = contentDescription,
                tint = Color.White,
                modifier = Modifier.size(size * 0.6f)
            )
        }
        return
    }

    AsyncImage(
        model = model,
        contentDescription = contentDescription,
        modifier = circle,
        contentScale = ContentScale.Crop,
        placeholder = placeholderPainter,
        error = placeholderPainter,
        onError = {
            if (!useOriginal && originalImageUrl != null) {
                useOriginal = true
            } else {
                failed = true
            }
        }
    )
}
