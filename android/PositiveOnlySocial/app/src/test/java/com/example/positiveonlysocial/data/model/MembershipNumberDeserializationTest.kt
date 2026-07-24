package com.example.positiveonlysocial.data.model

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Locks in the JSON mapping for the membership number (issue #198). The
 * profile-details and register endpoints return the join number under
 * "membership_number"; without the @SerializedName it would silently
 * deserialize to null and no member number would ever show.
 */
class MembershipNumberDeserializationTest {

    private val gson = Gson()

    @Test
    fun `profile details json maps membership_number to membershipNumber`() {
        val json = """
            {
              "username": "ada",
              "post_count": 3,
              "follower_count": 5,
              "following_count": 2,
              "is_following": false,
              "membership_number": 42
            }
        """.trimIndent()

        val profile = gson.fromJson(json, ProfileDetailsResponse::class.java)

        assertEquals("ada", profile.username)
        assertEquals(42, profile.membershipNumber)
    }

    @Test
    fun `profile details json from an older server without membership_number parses to null`() {
        // A server that predates the field omits it entirely; the profile must
        // still deserialize with a null membership number rather than failing.
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
        assertNull(profile.membershipNumber)
    }

    @Test
    fun `register response json maps membership_number to membershipNumber`() {
        val json = """
            {
              "session_management_token": "tok",
              "user_id": "abc",
              "membership_number": 7
            }
        """.trimIndent()

        val response = gson.fromJson(json, AuthResponse::class.java)

        assertEquals("tok", response.sessionToken)
        assertEquals(7, response.membershipNumber)
    }
}
