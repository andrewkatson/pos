package com.example.positiveonlysocial.ui.components

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Caption hashtag parsing (issue #379). */
class CaptionSegmentsTest {

    @Test
    fun `no tags is a single text segment`() {
        assertEquals(listOf(CaptionSegment.Text("just a caption")), captionSegments("just a caption"))
    }

    @Test
    fun `empty caption has no segments`() {
        assertTrue(captionSegments("").isEmpty())
    }

    @Test
    fun `splits text and tag`() {
        assertEquals(
            listOf(
                CaptionSegment.Text("a "),
                CaptionSegment.Tag(text = "#sun", name = "sun"),
                CaptionSegment.Text(" b"),
            ),
            captionSegments("a #sun b"),
        )
    }

    @Test
    fun `tag name is lowercased but text keeps casing`() {
        assertEquals(
            listOf(CaptionSegment.Tag(text = "#SunSet", name = "sunset")),
            captionSegments("#SunSet"),
        )
    }

    @Test
    fun `punctuation terminates a tag`() {
        assertEquals(
            listOf(CaptionSegment.Tag(text = "#day", name = "day"), CaptionSegment.Text("!")),
            captionSegments("#day!"),
        )
    }
}
