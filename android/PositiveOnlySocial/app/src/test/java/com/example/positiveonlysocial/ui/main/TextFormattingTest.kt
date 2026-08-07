package com.example.positiveonlysocial.ui.main

import androidx.compose.ui.text.font.FontFamily
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The caption-font half of the curated formatting keys (issue #318). The point
 * of these tests is that every offered key renders *differently*: a key that
 * maps to the same family as the default is a picker option that does nothing.
 */
class TextFormattingTest {

    @Test
    fun `offers the curated caption font keys`() {
        assertEquals(
            listOf("default", "serif", "monospace", "rounded", "handwriting"),
            TextFormatting.fontOptions
        )
    }

    @Test
    fun `default and unknown keys render with the system font`() {
        assertNull(TextFormatting.fontFamily("default"))
        assertNull(TextFormatting.fontFamily(null))
        assertNull(TextFormatting.fontFamily("not-a-font"))
    }

    @Test
    fun `built-in families map to their Compose counterparts`() {
        assertEquals(FontFamily.Serif, TextFormatting.fontFamily("serif"))
        assertEquals(FontFamily.Monospace, TextFormatting.fontFamily("monospace"))
        assertEquals(FontFamily.Cursive, TextFormatting.fontFamily("handwriting"))
    }

    @Test
    fun `rounded resolves to a real rounded face, not the default sans`() {
        val rounded = TextFormatting.fontFamily("rounded")
        assertNotNull(rounded)
        // The bug this guards: "rounded" used to map to FontFamily.SansSerif,
        // which renders identically to the default — selecting it did nothing.
        assertNotEquals(FontFamily.SansSerif, rounded)
        assertNotEquals(FontFamily.Default, rounded)
    }

    @Test
    fun `no offered font key silently renders as the default`() {
        // Comparing families pairwise is not enough: null (no override),
        // FontFamily.Default and FontFamily.SansSerif are distinct objects that
        // all *render* as the theme's sans face, so a key mapped to any of them
        // is a picker option that does nothing.
        val rendersAsDefault = setOf(null, FontFamily.Default, FontFamily.SansSerif)
        for (key in TextFormatting.fontOptions.filter { it != "default" }) {
            assertFalse(
                "\"$key\" renders identically to the default font",
                TextFormatting.fontFamily(key) in rendersAsDefault
            )
        }
    }

    @Test
    fun `every offered font key maps to a different family`() {
        val families = TextFormatting.fontOptions.map { TextFormatting.fontFamily(it) }
        assertEquals(TextFormatting.fontOptions.size, families.distinct().size)
    }
}
