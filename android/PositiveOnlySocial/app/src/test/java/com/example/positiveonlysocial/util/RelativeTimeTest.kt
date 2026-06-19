package com.example.positiveonlysocial.util

import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.Date

class RelativeTimeTest {

    // Fixed reference point so assertions don't depend on the wall clock.
    private val now = Date(1_780_000_000_000L)

    private fun ago(seconds: Long): Date = Date(now.time - seconds * 1000)

    private val minute = 60L
    private val hour = 60 * minute
    private val day = 24 * hour
    private val week = 7 * day
    private val year = 365 * day

    @Test
    fun collapsesSubMinuteToLessThanOneMin() {
        assertEquals("< 1 min", RelativeTime.format(ago(0), now))
        assertEquals("< 1 min", RelativeTime.format(ago(1), now))
        assertEquals("< 1 min", RelativeTime.format(ago(59), now))
    }

    @Test
    fun futureTimestampsReadLessThanOneMin() {
        assertEquals("< 1 min", RelativeTime.format(Date(now.time + 5000), now))
    }

    @Test
    fun roundsDownToWholeMinutes() {
        assertEquals("1 min", RelativeTime.format(ago(minute), now))
        assertEquals("1 min", RelativeTime.format(ago(minute + 59), now))
        assertEquals("59 min", RelativeTime.format(ago(59 * minute), now))
    }

    @Test
    fun roundsDownToWholeHours() {
        assertEquals("1 hr", RelativeTime.format(ago(hour), now))
        assertEquals("23 hr", RelativeTime.format(ago(23 * hour), now))
    }

    @Test
    fun roundsDownToWholeDaysWithPluralization() {
        assertEquals("1 day", RelativeTime.format(ago(day), now))
        assertEquals("6 days", RelativeTime.format(ago(6 * day), now))
    }

    @Test
    fun roundsDownToWholeWeeksWithPluralization() {
        assertEquals("1 week", RelativeTime.format(ago(week), now))
        assertEquals("8 weeks", RelativeTime.format(ago(8 * week), now))
        // 364 days is still under a year, so it stays in weeks.
        assertEquals("52 weeks", RelativeTime.format(ago(364 * day), now))
    }

    @Test
    fun roundsDownToWholeYearsWithPluralization() {
        assertEquals("1 year", RelativeTime.format(ago(year), now))
        assertEquals("2 years", RelativeTime.format(ago(2 * year + 5 * day), now))
    }
}
