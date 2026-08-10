package com.example.positiveonlysocial.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
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

    // ---- App Link parsing (issue #382) ----

    @Test
    fun parseReadsBackTheLinksTheBuildersProduce() {
        // Round trip: whatever we hand the share sheet, Android can hand back.
        assertEquals(
            SharedPostLink("abc123", null),
            ShareLinks.parseSharedPostLink(ShareLinks.postUrl("abc123"))
        )
        assertEquals(
            SharedPostLink("abc123", "c789"),
            ShareLinks.parseSharedPostLink(ShareLinks.commentUrl("abc123", "c789"))
        )
    }

    @Test
    fun parseAcceptsTheWwwHost() {
        // Both hosts are claimed by the manifest's autoVerify intent-filter.
        assertEquals(
            SharedPostLink("abc123", null),
            ShareLinks.parseSharedPostLink("https://www.smiling.social/post/abc123")
        )
    }

    @Test
    fun parseIsCaseInsensitiveAboutSchemeAndHost() {
        assertEquals(
            SharedPostLink("abc123", null),
            ShareLinks.parseSharedPostLink("HTTPS://SMILING.social/post/abc123")
        )
    }

    @Test
    fun parseToleratesATrailingSlash() {
        // Chat apps and shorteners add one freely.
        assertEquals(
            SharedPostLink("abc123", null),
            ShareLinks.parseSharedPostLink("https://smiling.social/post/abc123/")
        )
    }

    @Test
    fun parseKeepsThePostWhenTheFragmentIsNotAComment() {
        // An unrecognized fragment shouldn't cost the user the post.
        assertEquals(
            SharedPostLink("abc123", null),
            ShareLinks.parseSharedPostLink("https://smiling.social/post/abc123#top")
        )
        assertEquals(
            SharedPostLink("abc123", null),
            ShareLinks.parseSharedPostLink("https://smiling.social/post/abc123#comment-")
        )
    }

    @Test
    fun parseIgnoresAQueryString() {
        // Links pasted from a browser or a campaign tracker carry one.
        assertEquals(
            SharedPostLink("abc123", "c789"),
            ShareLinks.parseSharedPostLink("https://smiling.social/post/abc123?utm=x#comment-c789")
        )
    }

    @Test
    fun parseRejectsUrlsThatAreNotOurs() {
        // A VIEW intent can be sent by any app, not only by the verified-link
        // path, so a URL that merely looks similar must not navigate anywhere.
        val rejected = listOf(
            "https://smiling.social.evil.example/post/abc123",  // suffix, not our host
            "https://evil.example/post/abc123",                 // wrong host entirely
            "http://smiling.social/post/abc123",                // not https
            "https://smiling.social/posts/abc123",              // different route
            "https://smiling.social/post/",                     // no identifier
            "https://smiling.social/post/abc123/extra",         // deeper path
            "https://smiling.social/profile/ada",               // another route
            "https://smiling.social/",                          // the site root
            "not a url at all",
            "",
            null
        )
        for (url in rejected) {
            assertNull("expected $url to be rejected", ShareLinks.parseSharedPostLink(url))
        }
    }
}
