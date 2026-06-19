package com.example.positiveonlysocial.util

import java.time.OffsetDateTime
import java.time.format.DateTimeParseException
import java.util.Date

/**
 * Parses an ISO-8601 timestamp produced by the Django backend — typically with
 * fractional seconds and a `+00:00` offset, e.g.
 * "2024-01-15T10:30:45.123456+00:00" — into a [Date].
 *
 * Returns null when the string is blank or can't be parsed, so callers can
 * choose their own fallback. This mirrors the iOS `parseDate` helper.
 */
fun parseBackendDate(value: String): Date? = try {
    Date.from(OffsetDateTime.parse(value).toInstant())
} catch (_: DateTimeParseException) {
    null
}
