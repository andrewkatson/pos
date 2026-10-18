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
    fun `parent maps when present and is null when absent`() {
        val json = """
            {
              "preferences": [
                { "type": "all", "label": "Push notifications", "parent": null, "enabled": true },
                { "type": "new_like", "label": "Likes", "parent": "all", "enabled": true },
                { "type": "legacy", "label": "Legacy", "enabled": true }
              ]
            }
        """.trimIndent()

        val prefs = gson.fromJson(json, NotificationPreferencesResponse::class.java).preferences!!

        assertEquals(listOf(null, "all", null), prefs.map { it.parent })
    }

    private fun tree(vararg off: String) = listOf(
        "all" to null, "post_rejected" to "all", "new_post" to "all",
        "new_post_friend" to "new_post", "new_like" to "all", "new_like_other" to "new_like"
    ).map { (type, parent) ->
        NotificationPreference(type = type, label = type, enabled = type !in off, parent = parent)
    }

    private fun shown(prefs: List<NotificationPreference>) =
        visibleNotificationRows(prefs).map { "${it.depth}:${it.pref.type}" }

    @Test
    fun `rows indent under their parent (#444)`() {
        assertEquals(
            listOf("0:all", "1:post_rejected", "1:new_post", "2:new_post_friend", "1:new_like", "2:new_like_other"),
            shown(tree()))
    }

    @Test
    fun `an off parent hides its subtree`() {
        assertEquals(
            listOf("0:all", "1:post_rejected", "1:new_post", "1:new_like", "2:new_like_other"),
            shown(tree("new_post")))
        assertEquals(listOf("0:all"), shown(tree("all")))
    }

    @Test
    fun `rows without a known parent stay at the top level`() {
        val prefs = listOf(
            NotificationPreference(type = "post_rejected", label = "Post moderation", enabled = true),
            NotificationPreference(type = "x", label = "X", enabled = true, parent = "missing"))
        assertEquals(listOf("0:post_rejected", "0:x"), shown(prefs))
    }

    @Test
    fun `set-preference request serializes type and enabled`() {
        val json = gson.toJson(SetNotificationPreferenceRequest(type = "post_rejected", enabled = true))
        assertTrue(json.contains("\"type\":\"post_rejected\""))
        assertTrue(json.contains("\"enabled\":true"))
    }
}
