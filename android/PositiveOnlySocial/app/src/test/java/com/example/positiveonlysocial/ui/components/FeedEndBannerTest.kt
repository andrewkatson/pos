package com.example.positiveonlysocial.ui.components

import androidx.compose.runtime.saveable.SaverScope
import com.example.positiveonlysocial.data.model.TopPostPeriod
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** When the end-of-list confetti plays (issue #528), and what the banner says. */
class FeedEndBannerTest {

    @Test
    fun confettiPlaysWhenTheViewerScrolledToTheBanner() {
        val celebration = EndOfListCelebration()
        celebration.bannerShown(listScrolled = true, reduceMotion = false)
        assertTrue(celebration.isPlaying)

        celebration.finished()
        assertFalse(celebration.isPlaying)
    }

    @Test
    fun aListThatFitsOnScreenGetsNoConfetti() {
        val celebration = EndOfListCelebration()
        celebration.bannerShown(listScrolled = false, reduceMotion = false)
        assertFalse(celebration.isPlaying)
    }

    @Test
    fun removedAnimationsSkipTheConfetti() {
        val celebration = EndOfListCelebration()
        celebration.bannerShown(listScrolled = true, reduceMotion = true)
        assertFalse(celebration.isPlaying)
    }

    @Test
    fun confettiPlaysOncePerFinish() {
        val celebration = EndOfListCelebration()
        celebration.bannerShown(listScrolled = true, reduceMotion = false)
        celebration.finished()

        // Seeing the banner again doesn't replay it...
        celebration.bannerShown(listScrolled = true, reduceMotion = false)
        assertFalse(celebration.isPlaying)

        // ...until the list reloads and is finished again.
        celebration.reset()
        celebration.bannerShown(listScrolled = true, reduceMotion = false)
        assertTrue(celebration.isPlaying)
    }

    @Test
    fun aBannerSeenWithoutConfettiDoesNotCelebrateLater() {
        val celebration = EndOfListCelebration()
        celebration.bannerShown(listScrolled = false, reduceMotion = false)
        celebration.bannerShown(listScrolled = true, reduceMotion = false)
        assertFalse(celebration.isPlaying)
    }

    @Test
    fun resetStopsAPlayingBurst() {
        val celebration = EndOfListCelebration()
        celebration.bannerShown(listScrolled = true, reduceMotion = false)
        celebration.reset()
        assertFalse(celebration.isPlaying)
    }

    @Test
    fun aRestoredFinishDoesNotReplayTheConfetti() {
        val celebration = EndOfListCelebration()
        celebration.bannerShown(listScrolled = true, reduceMotion = false)

        // A rotation saves and restores the celebration...
        val restored = with(EndOfListCelebration.Saver) {
            restore(SaverScope { true }.save(celebration)!!)!!
        }

        // ...without restarting the burst, or playing it again when the
        // restored list shows the banner.
        assertFalse(restored.isPlaying)
        restored.bannerShown(listScrolled = true, reduceMotion = false)
        assertFalse(restored.isPlaying)

        // A list that starts over can still celebrate.
        restored.reset()
        restored.bannerShown(listScrolled = true, reduceMotion = false)
        assertTrue(restored.isPlaying)
    }

    @Test
    fun anUnseenFinishStillCelebratesAfterARestore() {
        val restored = with(EndOfListCelebration.Saver) {
            restore(SaverScope { true }.save(EndOfListCelebration())!!)!!
        }
        restored.bannerShown(listScrolled = true, reduceMotion = false)
        assertTrue(restored.isPlaying)
    }

    @Test
    fun messagesMatchTheOtherClients() {
        assertEquals("That's the whole Top board for today.", FeedEndMessage.top(TopPostPeriod.DAY))
        assertEquals("That's the whole Top board for this year.", FeedEndMessage.top(TopPostPeriod.YEAR))
        assertEquals("You've seen all of bob's posts.", FeedEndMessage.profile("bob"))
        assertEquals("That's every post you've shared.", FeedEndMessage.OWN_PROFILE)
    }
}
