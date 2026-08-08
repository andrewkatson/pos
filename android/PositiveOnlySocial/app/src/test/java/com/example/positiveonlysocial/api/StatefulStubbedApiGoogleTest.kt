package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.ConfirmTotpRequest
import com.example.positiveonlysocial.data.model.GoogleLoginRequest
import com.example.positiveonlysocial.data.model.LoginRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Base64

/**
 * Exercises Google sign-in (issue #10) against the in-memory stub. The stub has
 * to make the same decisions as `login_user_google` in
 * backend/user_system/views.py — link by verified email, key on Google's `sub`,
 * still demand a second factor — or the offline build and the real one diverge.
 */
class StatefulStubbedApiGoogleTest {

    /** An unsigned token carrying the claims the stub reads. Not a credential. */
    private fun idToken(sub: String, email: String, emailVerified: Boolean = true): String {
        val encoder = Base64.getUrlEncoder().withoutPadding()
        val header = encoder.encodeToString("""{"alg":"none"}""".toByteArray())
        val claims = """{"sub":"$sub","email":"$email","email_verified":$emailVerified}"""
        return "$header.${encoder.encodeToString(claims.toByteArray())}.sig"
    }

    private suspend fun signIn(
        api: StatefulStubbedAPI,
        sub: String = "sub-1",
        email: String = "hopefulperson@example.com",
        emailVerified: Boolean = true,
        rememberMe: String = "false",
    ) = api.loginWithGoogle(
        GoogleLoginRequest(idToken(sub, email, emailVerified), rememberMe, "127.0.0.1")
    )

    @Test
    fun `first sign-in creates an account and a session`() = runTest {
        val api = StatefulStubbedAPI()
        val body = signIn(api).body()!!

        assertEquals(true, body.createdAccount)
        assertNotNull(body.membershipNumber)
        assertNotNull(body.sessionToken)
        assertEquals("hopefulperson", body.username)
    }

    @Test
    fun `a short email local part is padded into a valid username`() = runTest {
        // Usernames need at least 10 word characters, matching the backend.
        val api = StatefulStubbedAPI()
        val username = signIn(api, email = "amy@example.com").body()!!.username!!

        assertTrue(username.startsWith("amy"))
        assertTrue(username.length >= 10)
    }

    @Test
    fun `non-word characters are stripped from the generated username`() = runTest {
        val api = StatefulStubbedAPI()
        assertEquals(
            "hopefulperson42",
            signIn(api, email = "hopeful.person-42@example.com").body()!!.username
        )
    }

    @Test
    fun `a taken username gets a suffix instead of failing`() = runTest {
        val api = StatefulStubbedAPI()
        api.register(
            RegisterRequest("hopefulperson", "someoneelse@example.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        )

        val username = signIn(api).body()!!.username!!
        assertNotEquals("hopefulperson", username)
        assertTrue(username.startsWith("hopefulperson"))
    }

    @Test
    fun `signing in again reuses the same account`() = runTest {
        val api = StatefulStubbedAPI()
        val first = signIn(api).body()!!
        val second = signIn(api).body()!!

        assertEquals(first.userId, second.userId)
        assertEquals(false, second.createdAccount)
        // Only a freshly created account is greeted with its join number.
        assertNull(second.membershipNumber)
        assertNotEquals(first.sessionToken, second.sessionToken)
    }

    @Test
    fun `a changed email still finds the account by its google sub`() = runTest {
        // `sub` is the join key precisely because an address can change.
        val api = StatefulStubbedAPI()
        val first = signIn(api).body()!!
        val second = signIn(api, email = "renamedmailbox@example.com").body()!!

        assertEquals(first.userId, second.userId)
    }

    @Test
    fun `a matching email links to the existing password account`() = runTest {
        val api = StatefulStubbedAPI()
        val registered = api.register(
            RegisterRequest("existingperson", "sharedaddress@example.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!

        // Matched case-insensitively: accounts carry whatever case the user
        // typed, while Google normalizes what it asserts.
        val google = signIn(api, email = "SharedAddress@Example.com").body()!!

        assertEquals(registered.userId, google.userId)
        assertEquals(false, google.createdAccount)
    }

    @Test
    fun `the password still works after linking`() = runTest {
        // Linking adds a way in; it never takes the original one away.
        val api = StatefulStubbedAPI()
        api.register(
            RegisterRequest("existingperson", "sharedaddress@example.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        )
        signIn(api, email = "sharedaddress@example.com")

        val login = api.loginUser(LoginRequest("existingperson", "pw12345", "false", "127.0.0.1"))
        assertTrue(login.isSuccessful)
    }

    @Test
    fun `a google account cannot be signed into with a password`() = runTest {
        val api = StatefulStubbedAPI()
        val username = signIn(api).body()!!.username!!

        // There is no password behind a Google account, so none can be guessed.
        val login = api.loginUser(LoginRequest(username, "anything", "false", "127.0.0.1"))
        assertFalse(login.isSuccessful)
    }

    @Test
    fun `remember me returns cookie tokens`() = runTest {
        val api = StatefulStubbedAPI()
        val body = signIn(api, rememberMe = "true").body()!!

        assertNotNull(body.seriesIdentifier)
        assertNotNull(body.loginCookieToken)
    }

    @Test
    fun `an enrolled account still has to supply its second factor`() = runTest {
        // Holding the Google account is a first factor, not a bypass of the
        // second. Built from a password account so enrollment can prove the
        // password the way the real confirm step demands.
        val api = StatefulStubbedAPI()
        val registered = api.register(
            RegisterRequest("enrolledperson", "enrolled@example.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!
        api.setupTotp(registered.sessionToken)
        api.confirmTotp(registered.sessionToken, ConfirmTotpRequest("pw12345", StatefulStubbedAPI.STUB_TOTP_CODE))

        val google = signIn(api, email = "enrolled@example.com").body()!!

        assertTrue(google.twoFactorRequired)
        assertNotNull(google.challengeToken)
        assertNull(google.sessionToken)
    }

    @Test
    fun `an unverified google email is refused`() = runTest {
        val api = StatefulStubbedAPI()
        val response = signIn(api, emailVerified = false)

        assertFalse(response.isSuccessful)
        assertEquals(
            Constants.GOOGLE_EMAIL_UNVERIFIED,
            ApiErrors.messageFor(response, fallback = "fallback")
        )
    }

    @Test
    fun `tokens decode at every payload length, padded or not`() = runTest {
        // java.util.Base64 treats '=' as optional, unlike the browser's atob
        // which rejects a length of 4n+1. Walk the claim set through every
        // length mod 4 so a future "let's pad it like the web stub" change has
        // something to answer to.
        val api = StatefulStubbedAPI()
        repeat(6) { extra ->
            val email = "a".repeat(extra) + "person$extra@example.com"
            val response = signIn(api, sub = "sub-$extra", email = email)
            assertTrue("failed at extra=$extra", response.isSuccessful)
        }
    }

    @Test
    fun `a malformed token is refused`() = runTest {
        val api = StatefulStubbedAPI()
        val response = api.loginWithGoogle(GoogleLoginRequest("not-a-jwt", "false", "127.0.0.1"))

        assertFalse(response.isSuccessful)
        assertEquals(
            Constants.INVALID_GOOGLE_TOKEN,
            ApiErrors.messageFor(response, fallback = "fallback")
        )
    }
}
