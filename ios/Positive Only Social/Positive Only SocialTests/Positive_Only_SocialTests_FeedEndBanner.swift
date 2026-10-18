//
//  Positive_Only_SocialTests_FeedEndBanner.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// Tests for when the end-of-list confetti plays (issue #528) and what the
/// banner says.
@MainActor
struct Positive_Only_SocialTests_FeedEndBanner {

    @Test func confettiPlaysWhenTheViewerScrolledToTheBanner() {
        let celebration = EndOfListCelebration()
        celebration.isScrolled = true

        celebration.bannerBecameVisible(reduceMotion: false)

        #expect(celebration.confettiStart != nil)
    }

    @Test func aListThatFitsOnScreenGetsNoConfetti() {
        let celebration = EndOfListCelebration()
        celebration.isScrolled = false

        celebration.bannerBecameVisible(reduceMotion: false)

        #expect(celebration.confettiStart == nil)
    }

    @Test func reduceMotionSkipsTheConfetti() {
        let celebration = EndOfListCelebration()
        celebration.isScrolled = true

        celebration.bannerBecameVisible(reduceMotion: true)

        #expect(celebration.confettiStart == nil)
    }

    @Test func confettiPlaysOncePerFinish() {
        let celebration = EndOfListCelebration()
        celebration.isScrolled = true
        celebration.bannerBecameVisible(reduceMotion: false)
        let firstBurst = celebration.confettiStart

        // Scrolling the banner off and back on doesn't replay it.
        celebration.bannerBecameVisible(reduceMotion: false)
        #expect(celebration.confettiStart == firstBurst)
    }

    @Test func aBannerSeenWithoutConfettiDoesNotCelebrateLater() {
        let celebration = EndOfListCelebration()
        // First seen on a list that fit on screen...
        celebration.bannerBecameVisible(reduceMotion: false)
        // ...then seen again after scrolling around.
        celebration.isScrolled = true
        celebration.bannerBecameVisible(reduceMotion: false)

        #expect(celebration.confettiStart == nil)
    }

    @Test func resetLetsTheNextFinishCelebrateAgain() {
        let celebration = EndOfListCelebration()
        celebration.isScrolled = true
        celebration.bannerBecameVisible(reduceMotion: false)

        celebration.reset()
        #expect(celebration.confettiStart == nil)

        celebration.bannerBecameVisible(reduceMotion: false)
        #expect(celebration.confettiStart != nil)
    }

    @Test func confettiClearsAfterItFalls() async {
        let celebration = EndOfListCelebration()
        celebration.isScrolled = true
        celebration.bannerBecameVisible(reduceMotion: false)

        try? await Task.sleep(for: .seconds(EndOfListCelebration.confettiDuration + 0.5))

        #expect(celebration.confettiStart == nil)
    }

    @Test func messagesMatchTheOtherClients() {
        #expect(FeedEndMessage.top(.day) == "That's the whole Top board for today.")
        #expect(FeedEndMessage.top(.week) == "That's the whole Top board for this week.")
        #expect(FeedEndMessage.profile(of: "bob") == "You've seen all of bob's posts.")
        #expect(FeedEndMessage.ownProfile == "That's every post you've shared.")
    }
}
