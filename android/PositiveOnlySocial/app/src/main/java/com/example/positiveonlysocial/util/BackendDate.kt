package com.example.positiveonlysocial.util

import java.time.OffsetDateTime
import java.time.format.DateTimeParseException
import java.util.Date

/**
 * Parses a backend `creation_time` string into a [Date].
 *
 * Handles both formats the app sees:
 * - The real Django backend emits ISO-8601, typically with fractional seconds
 *   and a `+00:00` offset, e.g. "2024-01-15T10:30:45.123456+00:00".
 * - The stubbed API used in debug/UI-test builds emits epoch-millis strings,
 *   e.g. "1718800000000" (see `StatefulStubbedAPI`).
 *
 * Returns null when the string is blank or can't be parsed in either format,
 * so callers can choose their own fallback. This mirrors the iOS `parseDate`
 * helper.
 */
fun parseBackendDate(value: String): Date? {
    val trimmed = value.trim()
    if (trimmed.isEmpty()) return null

    // Epoch-millis (the stubbed API). A bare integer string is never valid
    // ISO-8601, so this is unambiguous.
    trimmed.toLongOrNull()?.let { return Date(it) }

    return try {
        Date.from(OffsetDateTime.parse(trimmed).toInstant())
    } catch (_: DateTimeParseException) {
        null
    }
}
