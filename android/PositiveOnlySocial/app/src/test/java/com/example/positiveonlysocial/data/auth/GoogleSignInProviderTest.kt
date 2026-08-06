package com.example.positiveonlysocial.data.auth

import android.content.Context
import com.google.gson.JsonParser
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import java.util.Base64

/**
 * Covers the parts of Google sign-in (issue #10) that do not need a real
 * account picker: whether the button is offered at all, and that the UI-test
 * stub produces a token the stubbed API can actually read.
 */
class GoogleSignInProviderTest {

    @Test
    fun `a build with no web client id does not offer google sign-in`() {
        // Unset means the feature is a silent no-op, the same rule the backend
        // and the website follow — the button is hidden rather than shown as
        // one that could only ever fail.
        assertFalse(GoogleSignInProvider(webClientId = "").isConfigured)
        assertFalse(GoogleSignInProvider(webClientId = "   ").isConfigured)
    }

    @Test
    fun `a configured web client id offers google sign-in`() {
        assertTrue(GoogleSignInProvider(webClientId = "web.apps.googleusercontent.com").isConfigured)
    }

    @Test
    fun `an unconfigured provider refuses to start the flow`() = runTest {
        try {
            GoogleSignInProvider(webClientId = "").signIn(mock<Context>())
            throw AssertionError("expected NotConfigured")
        } catch (e: GoogleSignInFailure) {
            assertTrue(e is GoogleSignInFailure.NotConfigured)
        }
    }

    @Test
    fun `the stub returns a token carrying the claims the stubbed api reads`() = runTest {
        val token = StubbedGoogleSignIn(email = "stubperson@example.com").signIn(mock<Context>())

        // Three base64url segments, and the middle one is the claim set the
        // stubbed API decodes (see StatefulStubbedAPI.decodeIdTokenClaims).
        val segments = token.split(".")
        assertEquals(3, segments.size)
        val claims = JsonParser
            .parseString(String(Base64.getUrlDecoder().decode(segments[1])))
            .asJsonObject

        assertEquals("stub-google-sub", claims["sub"].asString)
        assertEquals("stubperson@example.com", claims["email"].asString)
        assertTrue(claims["email_verified"].asBoolean)
    }
}
