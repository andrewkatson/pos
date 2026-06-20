//
//  Positive_Only_SocialTests_RelativeTime.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// Tests for `RelativeTime.string`, which formats comment timestamps in the
/// post detail view. Sub-minute durations must collapse to "< 1 min" (so the
/// label doesn't tick every second) and larger durations round down to the
/// largest whole unit.
struct Positive_Only_SocialTests_RelativeTime {

    // Fixed reference point so assertions don't depend on the wall clock.
    private let now = Date(timeIntervalSince1970: 1_780_000_000)

    private func ago(_ seconds: TimeInterval) -> Date {
        now.addingTimeInterval(-seconds)
    }

    private let minute: TimeInterval = 60
    private var hour: TimeInterval { 60 * minute }
    private var day: TimeInterval { 24 * hour }
    private var week: TimeInterval { 7 * day }
    private var year: TimeInterval { 365 * day }

    @Test func subMinuteCollapsesToLessThanOneMin() {
        #expect(RelativeTime.string(from: ago(0), now: now) == "< 1 min")
        #expect(RelativeTime.string(from: ago(1), now: now) == "< 1 min")
        #expect(RelativeTime.string(from: ago(59), now: now) == "< 1 min")
    }

    @Test func futureTimestampsReadLessThanOneMin() {
        #expect(RelativeTime.string(from: now.addingTimeInterval(5), now: now) == "< 1 min")
    }

    @Test func roundsDownToWholeMinutes() {
        #expect(RelativeTime.string(from: ago(minute), now: now) == "1 min")
        #expect(RelativeTime.string(from: ago(minute + 59), now: now) == "1 min")
        #expect(RelativeTime.string(from: ago(59 * minute), now: now) == "59 min")
    }

    @Test func roundsDownToWholeHours() {
        #expect(RelativeTime.string(from: ago(hour), now: now) == "1 hr")
        #expect(RelativeTime.string(from: ago(23 * hour), now: now) == "23 hr")
    }

    @Test func roundsDownToWholeDaysWithPluralization() {
        #expect(RelativeTime.string(from: ago(day), now: now) == "1 day")
        #expect(RelativeTime.string(from: ago(6 * day), now: now) == "6 days")
    }

    @Test func roundsDownToWholeWeeksWithPluralization() {
        #expect(RelativeTime.string(from: ago(week), now: now) == "1 week")
        #expect(RelativeTime.string(from: ago(8 * week), now: now) == "8 weeks")
        // 364 days is still under a year, so it stays in weeks.
        #expect(RelativeTime.string(from: ago(364 * day), now: now) == "52 weeks")
    }

    @Test func roundsDownToWholeYearsWithPluralization() {
        #expect(RelativeTime.string(from: ago(year), now: now) == "1 year")
        #expect(RelativeTime.string(from: ago(2 * year + 5 * day), now: now) == "2 years")
    }
}
