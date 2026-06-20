package com.example.positiveonlysocial.util

import java.util.Date

/**
 * Formats how long ago [from] happened, relative to [now] (defaults to the
 * current time).
 *
 * Sub-minute durations collapse to "< 1 min" so the label never shows a
 * second-level granularity that ticks on every recomposition. Larger durations
 * round down to the largest whole unit: minutes, hours, days, weeks, then
 * years. This mirrors the same helper on iOS (`RelativeTime`) and the website
 * (`formatRelativeTime`) so the three clients read identically.
 */
object RelativeTime {
    fun format(from: Date, now: Date = Date()): String {
        val seconds = ((now.time - from.time) / 1000).coerceAtLeast(0)
        if (seconds < 60) return "< 1 min"

        val minutes = seconds / 60
        if (minutes < 60) return "$minutes min"

        val hours = minutes / 60
        if (hours < 24) return "$hours hr"

        val days = hours / 24
        if (days < 7) return "$days ${if (days == 1L) "day" else "days"}"

        if (days < 365) {
            val weeks = days / 7
            return "$weeks ${if (weeks == 1L) "week" else "weeks"}"
        }

        val years = days / 365
        return "$years ${if (years == 1L) "year" else "years"}"
    }
}
