package com.example.positiveonlysocial.ui.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The username length rule must match the backend's Patterns.username: 10-150,
 * where 150 is the username column's max_length. A looser client bound lets a
 * 151-500 character name through to a database failure at registration.
 */
class AuthRequirementsTest {

    private fun lengthMet(username: String): Boolean =
        AuthRequirements.username(username).first().didMeetRequirement

    @Test
    fun usernameLengthBoundsMatchTheBackend() {
        assertEquals(10, AuthRequirements.MIN_USERNAME_LENGTH)
        assertEquals(150, AuthRequirements.MAX_USERNAME_LENGTH)
    }

    @Test
    fun usernameLengthAcceptsTenThroughOneFifty() {
        assertFalse(lengthMet("a".repeat(9)))
        assertTrue(lengthMet("a".repeat(10)))
        assertTrue(lengthMet("a".repeat(150)))
        assertFalse(lengthMet("a".repeat(151)))
        assertFalse(lengthMet("a".repeat(500)))
    }

    @Test
    fun usernameLengthCountsCodePointsLikeTheBackend() {
        // U+1D400 is one letter to Python's len() but two UTF-16 Chars.
        val mathBold = String(Character.toChars(0x1D400))
        assertTrue(lengthMet(mathBold.repeat(150)))
        assertFalse(lengthMet(mathBold.repeat(151)))
    }

    @Test
    fun usernameLabelNamesTheBounds() {
        assertEquals(
            "Between 10 and 150 characters",
            AuthRequirements.username("").first().label,
        )
    }

    @Test
    fun overLongUsernameIsNotAllMet() {
        assertFalse(AuthRequirements.allMet(AuthRequirements.username("a".repeat(151))))
        assertTrue(AuthRequirements.allMet(AuthRequirements.username("a".repeat(150))))
    }
}
