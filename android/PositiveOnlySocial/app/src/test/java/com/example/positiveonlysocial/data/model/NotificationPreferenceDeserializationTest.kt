package com.example.positiveonlysocial.data.model

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Locks in the JSON mapping for the notification-preferences endpoint
 * (#342/#343). Fields are nullable because Gson ignores Kotlin defaults for
 * absent keys, so a partial/older payload must still deserialize.
 */
class NotificationPreferenceDeserializationTest {

    private val gson = Gson()

    @Test
    fun `preferences list maps type, label, and enabled`() {
        val json = """
            {
              "preferences": [
                { "type": "post_rejected", "label": "Post moderation", "enabled": false }
              ]
            }
        """.trimIndent()

        val response = gson.fromJson(json, NotificationPreferencesResponse::class.java)

        val prefs = response.preferences
        assertEquals(1, prefs?.size)
        val pref = prefs!!.first()
        assertEquals("post_rejected", pref.type)
        assertEquals("Post moderation", pref.label)
        assertEquals(false, pref.enabled)
    }

    @Test
    fun `an empty or missing preferences array parses to null or empty`() {
        val response = gson.fromJson("{}", NotificationPreferencesResponse::class.java)
        assertNull(response.preferences)

        val emptyResponse = gson.fromJson("""{ "preferences": [] }""", NotificationPreferencesResponse::class.java)
        assertTrue(emptyResponse.preferences?.isEmpty() == true)
    }

    @Test
    fun `set-preference request serializes type and enabled`() {
        val json = gson.toJson(SetNotificationPreferenceRequest(type = "post_rejected", enabled = true))
        assertTrue(json.contains("\"type\":\"post_rejected\""))
        assertTrue(json.contains("\"enabled\":true"))
    }
}
