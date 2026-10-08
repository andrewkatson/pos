package com.example.positiveonlysocial.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The author-only audience badge (issue #518): the tier it resolves a raw
 * backend value to, and the text it shows and announces for each tier.
 */
class PostAudienceBadgeTest {

    @Test
    fun `badge tier reads the raw value`() {
        assertEquals(PostAudience.FAMILY, PostAudience.badgeTier("family"))
        assertEquals(PostAudience.FRIENDS, PostAudience.badgeTier("friends"))
        assertEquals(PostAudience.FOLLOWING, PostAudience.badgeTier("following"))
        assertEquals(PostAudience.PUBLIC, PostAudience.badgeTier("public"))
    }

    @Test
    fun `missing or unknown audience is badged public like the backend treats it`() {
        // Older responses omit the field (Gson leaves it null).
        assertEquals(PostAudience.PUBLIC, PostAudience.badgeTier(null))
        // A tier this client does not know falls back rather than showing nothing.
        assertEquals(PostAudience.PUBLIC, PostAudience.badgeTier("coworkers"))
    }

    @Test
    fun `badge names each tier and who it admits`() {
        assertEquals("Public", PostAudience.PUBLIC.badgeLabel)
        assertEquals("Following", PostAudience.FOLLOWING.badgeLabel)
        assertEquals("Friends", PostAudience.FRIENDS.badgeLabel)
        assertEquals("Family", PostAudience.FAMILY.badgeLabel)

        assertEquals("Visible to anyone", PostAudience.PUBLIC.badgeDescription)
        assertEquals("Visible to people you follow", PostAudience.FOLLOWING.badgeDescription)
        assertEquals("Visible to friends and family", PostAudience.FRIENDS.badgeDescription)
        assertEquals("Visible to family only", PostAudience.FAMILY.badgeDescription)
    }
}
