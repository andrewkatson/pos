package com.example.positiveonlysocial.fcm

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PushNotificationKeysTest {

    @Test
    fun rejectionsAndUnknownKindsShareOneSlot() {
        assertNull(PushNotificationKeys.tagFor("post_rejected", "post-1", null))
        assertNull(PushNotificationKeys.tagFor("future_kind", "post-1", "sam"))
        assertNull(PushNotificationKeys.tagFor(null, "post-1", null))
    }

    @Test
    fun postActivityIsKeyedByKindAndPost() {
        assertEquals("new_like:post-1", PushNotificationKeys.tagFor("new_like", "post-1", null))
        assertNotEquals(
            PushNotificationKeys.tagFor("new_like", "post-1", null),
            PushNotificationKeys.tagFor("new_comment", "post-1", null))
    }

    @Test
    fun followActivityIsKeyedByWhoActed() {
        assertEquals("new_follower:sam", PushNotificationKeys.tagFor("new_follower", null, "sam"))
        assertEquals("follow_request:sam", PushNotificationKeys.tagFor("follow_request", null, "sam"))
        assertEquals("follow_accepted:sam", PushNotificationKeys.tagFor("follow_accepted", null, "sam"))
    }

    @Test
    fun usernamesWithCollidingHashCodesGetDistinctTags() {
        // "Aa" and "BB" share a String.hashCode, so a hashed id would collide.
        assertEquals("followuserAa".hashCode(), "followuserBB".hashCode())
        assertNotEquals(
            PushNotificationKeys.tagFor("new_follower", null, "followuserAa"),
            PushNotificationKeys.tagFor("new_follower", null, "followuserBB"))
    }
}
