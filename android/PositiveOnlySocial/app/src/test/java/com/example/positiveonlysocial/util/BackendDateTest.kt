package com.example.positiveonlysocial.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant

class BackendDateTest {

    @Test
    fun parsesDjangoTimestampWithFractionalSecondsAndOffset() {
        val parsed = parseBackendDate("2024-01-15T10:30:45.123456+00:00")
        assertEquals(Instant.parse("2024-01-15T10:30:45.123456Z").toEpochMilli(), parsed?.time)
    }

    @Test
    fun parsesTimestampWithoutFractionalSeconds() {
        val parsed = parseBackendDate("2024-01-15T10:30:45+00:00")
        assertEquals(Instant.parse("2024-01-15T10:30:45Z").toEpochMilli(), parsed?.time)
    }

    @Test
    fun parsesNonUtcOffset() {
        val parsed = parseBackendDate("2024-01-15T10:30:45-05:00")
        assertEquals(Instant.parse("2024-01-15T15:30:45Z").toEpochMilli(), parsed?.time)
    }

    @Test
    fun returnsNullForUnparseableInput() {
        assertNull(parseBackendDate(""))
        assertNull(parseBackendDate("not a date"))
    }
}
