package com.example.positiveonlysocial.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Covers the pure share-URL builders (issue #34). Launching the actual system
 * share sheet needs an Android runtime, so [ShareLinks.shareText] isn't unit
 * tested here — only the URLs it would carry.
 */
class ShareLinksTest {

    @Test
    fun baseUrlPointsAtTheWebsite() {
        assertEquals("https://smiling.social", ShareLinks.WEB_BASE_URL)
    }

    @Test
    fun postUrlIsRootedAtThePostPath() {
        assertEquals("https://smiling.social/post/abc123", ShareLinks.postUrl("abc123"))
    }

    @Test
    fun commentUrlAppendsTheCommentFragment() {
        assertEquals(
            "https://smiling.social/post/abc123#comment-c789",
            ShareLinks.commentUrl("abc123", "c789")
        )
    }

    @Test
    fun commentUrlBuildsOnTopOfThePostUrl() {
        // The comment link is the post link plus the fragment, so a website that
        // ignores the fragment still lands on the right post.
        val postUrl = ShareLinks.postUrl("p1")
        val commentUrl = ShareLinks.commentUrl("p1", "c1")
        assertTrue(commentUrl.startsWith(postUrl))
        assertEquals("$postUrl#comment-c1", commentUrl)
    }
}
