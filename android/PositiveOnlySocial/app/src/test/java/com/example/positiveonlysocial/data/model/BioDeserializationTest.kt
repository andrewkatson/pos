package com.example.positiveonlysocial.data.model

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Locks in the JSON mapping for the profile bio (issue #380). The profile-details
 * endpoint returns it under "bio"; without the @SerializedName it would silently
 * fail to map, and a server that predates the field must still deserialize.
 */
class BioDeserializationTest {

    private val gson = Gson()

    @Test
    fun `profile details json maps bio`() {
        val json = """
            {
              "username": "ada",
              "post_count": 3,
              "follower_count": 5,
              "following_count": 2,
              "is_following": false,
              "bio": "Aspiring gardener and dog lover."
            }
        """.trimIndent()

        val profile = gson.fromJson(json, ProfileDetailsResponse::class.java)

        assertEquals("ada", profile.username)
        assertEquals("Aspiring gardener and dog lover.", profile.bio)
    }

    @Test
    fun `profile details json from an older server without bio parses to null`() {
        // A server that predates the field omits it entirely; the profile must
        // still deserialize (Gson leaves the missing field null) rather than
        // failing. Callers treat null and "" alike.
        val json = """
            {
              "username": "grace",
              "post_count": 1,
              "follower_count": 0,
              "following_count": 0,
              "is_following": true
            }
        """.trimIndent()

        val profile = gson.fromJson(json, ProfileDetailsResponse::class.java)

        assertEquals("grace", profile.username)
        assertNull(profile.bio)
    }
}
