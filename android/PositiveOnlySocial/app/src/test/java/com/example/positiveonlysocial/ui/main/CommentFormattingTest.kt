package com.example.positiveonlysocial.ui.main

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Unit tests for the editor-side comment formatting model (issue #318). */
class CommentFormattingTest {

    @Test
    fun `toggleBold turns a style on then off over the range`() {
        var styles = CommentFormatting.emptyStyles(4)
        styles = CommentFormatting.toggleBold(styles, 0, 4)
        assertTrue(styles.all { it.bold })
        styles = CommentFormatting.toggleBold(styles, 0, 4)
        assertTrue(styles.none { it.bold })
    }

    @Test
    fun `toggleBold turns on when only part of the range is bold`() {
        var styles = CommentFormatting.emptyStyles(4)
        styles = CommentFormatting.toggleBold(styles, 0, 2)
        styles = CommentFormatting.toggleBold(styles, 0, 4)
        assertTrue(styles.all { it.bold })
    }

    @Test
    fun `toSpans compresses contiguous equal runs and drops plain text`() {
        var styles = CommentFormatting.emptyStyles(6)
        styles = CommentFormatting.toggleBold(styles, 0, 2)
        styles = CommentFormatting.setSize(styles, 4, 6, "large")
        val spans = CommentFormatting.toSpans(styles)!!
        assertEquals(2, spans.size)
        assertEquals(0, spans[0].start)
        assertEquals(2, spans[0].end)
        assertTrue(spans[0].bold)
        assertEquals("large", spans[1].size)
    }

    @Test
    fun `toSpans returns null when nothing is styled`() {
        assertNull(CommentFormatting.toSpans(CommentFormatting.emptyStyles(5)))
    }

    @Test
    fun `reconcile keeps styling when text is inserted in the middle`() {
        // "ab" both bold; type "X" between them -> "aXb".
        var styles = CommentFormatting.emptyStyles(2)
        styles = CommentFormatting.toggleBold(styles, 0, 2)
        val next = CommentFormatting.reconcile(styles, "ab", "aXb")
        assertEquals(listOf(true, false, true), next.map { it.bold })
    }

    @Test
    fun `reconcile drops styling for deleted characters`() {
        var styles = CommentFormatting.emptyStyles(3)
        styles = CommentFormatting.toggleBold(styles, 0, 3)
        val next = CommentFormatting.reconcile(styles, "abc", "ac")
        assertEquals(2, next.size)
        assertTrue(next.all { it.bold })
    }
}
