package com.example.positiveonlysocial.ui.main

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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage

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
 */
@Composable
fun ProfileAvatar(
    imageUrl: String?,
    originalImageUrl: String? = null,
    contentDescription: String? = null,
    size: Dp = 32.dp,
    modifier: Modifier = Modifier,
) {
    val circle = modifier.size(size).clip(CircleShape)

    // The compressed→original switch flips at most once each way, so a failing
    // original leaves the placeholder rather than looping. Keyed to BOTH URLs so
    // the fallback resets whenever either changes — a recycled row reused for a
    // different user, or a refreshed signed URL where only the original differs.
    var useOriginal by remember(imageUrl, originalImageUrl) { mutableStateOf(false) }
    var failed by remember(imageUrl, originalImageUrl) { mutableStateOf(false) }

    val model = if (useOriginal) originalImageUrl else imageUrl

    if (model == null || failed) {
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
        onError = {
            if (!useOriginal && originalImageUrl != null) {
                useOriginal = true
            } else {
                failed = true
            }
        }
    )
}
