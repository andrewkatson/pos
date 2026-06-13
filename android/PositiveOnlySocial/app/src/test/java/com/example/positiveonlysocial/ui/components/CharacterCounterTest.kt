package com.example.positiveonlysocial.ui.components

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CharacterCounterTest {

    @Test
    fun countsAsciiByCodePoint() {
        assertEquals(5, characterCount("hello"))
        assertEquals(0, characterCount(""))
    }

    @Test
    fun countsEmojiAsSingleCodePointMatchingBackend() {
        // "💚" is two UTF-16 code units but one code point, matching Python's
        // len() on the backend.
        assertEquals(5, characterCount("💚".repeat(5)))
    }

    @Test
    fun withinLimitAtAndBelowMax() {
        assertTrue(isWithinLength("a".repeat(125), 125))
        assertTrue(isWithinLength("a".repeat(124), 125))
    }

    @Test
    fun notWithinLimitOverMax() {
        assertFalse(isWithinLength("a".repeat(126), 125))
    }
}
