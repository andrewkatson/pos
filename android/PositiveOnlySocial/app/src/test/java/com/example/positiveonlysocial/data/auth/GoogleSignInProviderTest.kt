package com.example.positiveonlysocial.data.auth

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import com.google.gson.JsonParser
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
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
    fun `a context with no activity is a reported failure, not a crash`() = runTest {
        // Credential Manager renders the picker over an Activity, but
        // LocalContext.current is only typed as a Context — under a preview or
        // any wrapping it may not be one.
        try {
            GoogleSignInProvider(webClientId = "web.apps.googleusercontent.com")
                .signIn(mock<Context>())
            throw AssertionError("expected NoActivity")
        } catch (e: GoogleSignInFailure) {
            assertTrue(e is GoogleSignInFailure.NoActivity)
        }
    }

    @Test
    fun `an activity is found through a wrapper chain`() {
        // The chain is mocked rather than built from real ContextWrappers:
        // these are JVM unit tests against the mockable android.jar, where
        // getBaseContext() is a stub that returns null
        // (unitTests.isReturnDefaultValues), so a real wrapper would report an
        // empty chain and the test would be measuring the stub, not the walk.
        val activity = mock<Activity>()
        val inner = mock<ContextWrapper>()
        whenever(inner.baseContext).thenReturn(activity)
        val outer = mock<ContextWrapper>()
        whenever(outer.baseContext).thenReturn(inner)

        assertEquals(activity, outer.findActivity())
    }

    @Test
    fun `a plain context has no activity to find`() {
        assertNull(mock<Context>().findActivity())
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
