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

    // ---- Profile links (issue #510) ----

    @Test
    fun profileUrlIsRootedAtTheProfilePath() {
        assertEquals(
            "https://smiling.social/profile/sunny_side_up",
            ShareLinks.profileUrl("sunny_side_up")
        )
    }

    @Test
    fun parseReadsBackTheProfileLinkTheBuilderProduces() {
        // Round trip, like the post links: the manifest claims /profile/ too.
        assertEquals(
            SharedLink.Profile("sunny_side_up"),
            ShareLinks.parseSharedLink(ShareLinks.profileUrl("sunny_side_up"))
        )
        assertEquals(
            SharedLink.Profile("sunny_side_up"),
            ShareLinks.parseSharedLink("https://www.smiling.social/profile/sunny_side_up/")
        )
    }

    @Test
    fun parseAcceptsAUnicodeUsername() {
        // The backend's username rule admits Unicode letters, so the parser
        // must too — Java's ASCII-only `\w` would have rejected this.
        assertEquals(
            SharedLink.Profile("sonn\u00e9_\u00fcber_\u65e5\u672c_x"),
            ShareLinks.parseSharedLink("https://smiling.social/profile/sonn%C3%A9_%C3%BCber_%E6%97%A5%E6%9C%AC_x")
        )
    }

    @Test
    fun parseAcceptsASupplementaryPlaneUsername() {
        // Deseret letters sit outside the BMP, so each is a surrogate pair;
        // validating per UTF-16 Char would reject this valid 10-letter name.
        val name = "𐐀".repeat(10)
        assertEquals(
            SharedLink.Profile(name),
            ShareLinks.parseSharedLink("https://smiling.social/profile/" + "%F0%90%90%80".repeat(10))
        )
    }

    @Test
    fun parseAcceptsNumberCategoryUsernames() {
        // Python's `\w` (the backend's rule) admits letter numbers (U+216B, Ⅻ)
        // and other numbers (U+2460, ①), not just letters and decimal digits.
        for ((name, encoded) in listOf(
            "Ⅻ".repeat(10) to "%E2%85%AB".repeat(10),
            "①".repeat(10) to "%E2%91%A0".repeat(10),
        )) {
            assertEquals(
                SharedLink.Profile(name),
                ShareLinks.parseSharedLink("https://smiling.social/profile/$encoded")
            )
        }
    }

    @Test
    fun parseRejectsProfileLinksThatCouldNotBeAUsername() {
        // The segment becomes a navigation argument, so only a well-formed
        // username (10-150 word characters, the backend's rule) is ever routed.
        for (url in listOf(
            "https://smiling.social/profile/",
            "https://smiling.social/profile/some%20one",
            "https://smiling.social/profile/a-b",
            "https://smiling.social/profile/ada/posts",
            "https://smiling.social/profile/tooshort9",
            "https://smiling.social/profile/" + "a".repeat(151)
        )) {
            assertNull("expected $url to be rejected", ShareLinks.parseSharedLink(url))
        }
    }

    // ---- App Link parsing (issue #382) ----

    @Test
    fun parseReadsBackTheLinksTheBuildersProduce() {
        // Round trip: whatever we hand the share sheet, Android can hand back.
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", null)),
            ShareLinks.parseSharedLink(ShareLinks.postUrl("abc123"))
        )
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", "c789")),
            ShareLinks.parseSharedLink(ShareLinks.commentUrl("abc123", "c789"))
        )
    }

    @Test
    fun parseAcceptsTheWwwHost() {
        // Both hosts are claimed by the manifest's autoVerify intent-filter.
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", null)),
            ShareLinks.parseSharedLink("https://www.smiling.social/post/abc123")
        )
    }

    @Test
    fun parseIsCaseInsensitiveAboutSchemeAndHost() {
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", null)),
            ShareLinks.parseSharedLink("HTTPS://SMILING.social/post/abc123")
        )
    }

    @Test
    fun parseToleratesATrailingSlash() {
        // Chat apps and shorteners add one freely.
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", null)),
            ShareLinks.parseSharedLink("https://smiling.social/post/abc123/")
        )
    }

    @Test
    fun parseKeepsThePostWhenTheFragmentIsNotAComment() {
        // An unrecognized fragment shouldn't cost the user the post.
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", null)),
            ShareLinks.parseSharedLink("https://smiling.social/post/abc123#top")
        )
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", null)),
            ShareLinks.parseSharedLink("https://smiling.social/post/abc123#comment-")
        )
    }

    @Test
    fun parseIgnoresAQueryString() {
        // Links pasted from a browser or a campaign tracker carry one.
        assertEquals(
            SharedLink.Post(SharedPostLink("abc123", "c789")),
            ShareLinks.parseSharedLink("https://smiling.social/post/abc123?utm=x#comment-c789")
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
            "https://smiling.social/tags/sunset",               // another route
            "https://smiling.social/",                          // the site root
            "not a url at all",
            "",
            null
        )
        for (url in rejected) {
            assertNull("expected $url to be rejected", ShareLinks.parseSharedLink(url))
        }
    }
}
