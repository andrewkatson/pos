package com.example.positiveonlysocial.ui.components

import android.provider.Settings
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.positiveonlysocial.data.model.TopPostPeriod
import kotlinx.coroutines.flow.first
import kotlin.math.pow
import kotlin.math.sin

/** The lazy-list key of the banner item, so visibility can be checked by key. */
const val FEED_END_BANNER_KEY = "feed-end-banner"

/** How long a confetti burst lasts; covers the slowest piece's fall. */
private const val CONFETTI_DURATION_MS = 4200

/**
 * What the "you finished!" banner (issue #528) says the viewer just finished;
 * the same wording as the website and iOS.
 */
object FeedEndMessage {
    const val FOR_YOU = "You've seen every post in your feed. Check back soon for more good vibes!"
    const val FOLLOWING = "You've seen every post from the people you follow."
    const val OWN_PROFILE = "That's every post you've shared."

    fun top(period: TopPostPeriod): String {
        val span = when (period) {
            TopPostPeriod.DAY -> "today"
            TopPostPeriod.WEEK -> "this week"
            TopPostPeriod.MONTH -> "this month"
            TopPostPeriod.YEAR -> "this year"
        }
        return "That's the whole Top board for $span."
    }

    fun profile(username: String) = "You've seen all of $username's posts."
}

/**
 * Decides when the end-of-list confetti plays, for one feed or profile.
 *
 * It plays once, the first time the banner scrolls into view — and only when
 * the viewer scrolled to get there, so a profile with a handful of posts that
 * fits on one screen just shows the banner rather than throwing confetti every
 * time it opens — and never with animations turned off. [reset] (when the list
 * reloads) lets finishing it again celebrate again.
 */
@Stable
class EndOfListCelebration(hasCelebrated: Boolean = false) {
    var isPlaying by mutableStateOf(false)
        private set

    /** Whether this finish has been seen. Saved across configuration changes
     * (see [Saver]): a rotation restores the scroll position and the view
     * model's reachedEnd, and must not replay the burst for the same finish. */
    var hasCelebrated = hasCelebrated
        private set

    /** The banner came on screen. */
    fun bannerShown(listScrolled: Boolean, reduceMotion: Boolean) {
        // Seen once is enough, whether or not it earned confetti.
        if (hasCelebrated) return
        hasCelebrated = true
        if (listScrolled && !reduceMotion) isPlaying = true
    }

    /** The burst has fallen off screen. */
    fun finished() {
        isPlaying = false
    }

    /** The list reloaded, so reaching its end again is a fresh finish. */
    fun reset() {
        hasCelebrated = false
        isPlaying = false
    }

    companion object {
        /** Keeps only whether the finish was seen; a burst cut off by the
         * configuration change is not restarted. */
        val Saver: Saver<EndOfListCelebration, Boolean> = Saver(
            save = { it.hasCelebrated },
            restore = { EndOfListCelebration(hasCelebrated = it) }
        )
    }
}

/** A celebration for a feed's [LazyListState]. */
@Composable
fun rememberEndOfListCelebration(reachedEnd: Boolean, listState: LazyListState): EndOfListCelebration =
    rememberEndOfListCelebration(
        reachedEnd,
        bannerVisible = { listState.layoutInfo.visibleItemsInfo.any { it.key == FEED_END_BANNER_KEY } },
        listScrolled = { listState.canScrollBackward },
    )

/** A celebration for a profile grid's [LazyGridState]. */
@Composable
fun rememberEndOfListCelebration(reachedEnd: Boolean, gridState: LazyGridState): EndOfListCelebration =
    rememberEndOfListCelebration(
        reachedEnd,
        bannerVisible = { gridState.layoutInfo.visibleItemsInfo.any { it.key == FEED_END_BANNER_KEY } },
        listScrolled = { gridState.canScrollBackward },
    )

@Composable
private fun rememberEndOfListCelebration(
    reachedEnd: Boolean,
    bannerVisible: () -> Boolean,
    listScrolled: () -> Boolean,
): EndOfListCelebration {
    val celebration = rememberSaveable(saver = EndOfListCelebration.Saver) { EndOfListCelebration() }
    val reduceMotion = rememberReduceMotion()
    LaunchedEffect(reachedEnd) {
        if (!reachedEnd) {
            celebration.reset()
            return@LaunchedEffect
        }
        // Checked against what is actually laid out on screen, not when the
        // item composes: a lazy list may compose the next item ahead of time.
        snapshotFlow(bannerVisible).first { it }
        celebration.bannerShown(listScrolled(), reduceMotion)
    }
    return celebration
}

/** Animations off in developer options / accessibility ("Remove animations"). */
@Composable
private fun rememberReduceMotion(): Boolean {
    val context = LocalContext.current
    return remember(context) {
        Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
}

/** The banner itself, placed after the last post with [FEED_END_BANNER_KEY]. */
@Composable
fun FeedEndBanner(message: String, modifier: Modifier = Modifier) {
    val accent = MaterialTheme.colorScheme.primary
    val shape = RoundedCornerShape(14.dp)
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
            .clip(shape)
            .background(
                Brush.linearGradient(
                    listOf(accent.copy(alpha = 0.18f), Color(0xFFFF7EB6).copy(alpha = 0.14f))
                )
            )
            .border(1.dp, accent.copy(alpha = 0.45f), shape)
            .padding(16.dp)
            .semantics(mergeDescendants = true) {}
            .testTag("FeedEndBanner"),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text("🎉", fontSize = 32.sp, modifier = Modifier.clearAndSetSemantics {})
        Text(
            "You finished!",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(top = 6.dp, bottom = 2.dp)
        )
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
    }
}

/**
 * One piece of confetti. Its spread is derived from its index rather than
 * random, so the burst is the same every time; multipliers coprime with 100
 * walk every column without bunching.
 */
private class ConfettiPiece(i: Int) {
    val x = ((i * 37) % 100) / 100f
    val delay = ((i * 53) % 40) / 40f
    val duration = 2.2f + ((i * 29) % 10) / 10f
    val drift = ((i * 71) % 17) * 6f - 48f
    val spin = 360f + ((i * 43) % 5) * 180f
    val color = CONFETTI_COLORS[i % CONFETTI_COLORS.size]
    val isRound = i % 4 == 0
}

private val CONFETTI_COLORS = listOf(
    Color(0xFF5BA4DC), Color(0xFFF7C948), Color(0xFFFF7EB6),
    Color(0xFF7EE081), Color(0xFFB28DFF), Color(0xFFFF9F5A),
)

private val CONFETTI_PIECES = List(72) { ConfettiPiece(it) }

/**
 * The confetti burst over the whole list while [celebration] is playing:
 * pieces fall from above the top edge to below the bottom, drifting and
 * spinning. Decorative only — it takes no touches and is hidden from TalkBack.
 */
@Composable
fun ConfettiOverlay(celebration: EndOfListCelebration, modifier: Modifier = Modifier) {
    if (!celebration.isPlaying) return
    val clock = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        clock.animateTo(1f, tween(durationMillis = CONFETTI_DURATION_MS, easing = LinearEasing))
        celebration.finished()
    }
    Canvas(modifier = modifier.fillMaxSize().clearAndSetSemantics {}) {
        val elapsed = clock.value * CONFETTI_DURATION_MS / 1000f
        for (piece in CONFETTI_PIECES) {
            val t = elapsed - piece.delay
            if (t <= 0f || t >= piece.duration) continue
            val progress = t / piece.duration
            val fall = 1f - (1f - progress).pow(1.6f)
            val x = piece.x * size.width + (piece.drift * progress + sin(t * 4f) * 10f).dp.toPx()
            val y = -16.dp.toPx() + fall * (size.height + 32.dp.toPx())
            val alpha = if (progress > 0.85f) (1f - progress) / 0.15f else 1f
            translate(x, y) {
                rotate(piece.spin * progress, pivot = Offset.Zero) {
                    if (piece.isRound) {
                        drawCircle(piece.color, radius = 5.dp.toPx(), center = Offset.Zero, alpha = alpha)
                    } else {
                        drawRoundRect(
                            piece.color,
                            topLeft = Offset(-4.dp.toPx(), -7.dp.toPx()),
                            size = Size(8.dp.toPx(), 14.dp.toPx()),
                            cornerRadius = CornerRadius(2.dp.toPx()),
                            alpha = alpha
                        )
                    }
                }
            }
        }
    }
}
