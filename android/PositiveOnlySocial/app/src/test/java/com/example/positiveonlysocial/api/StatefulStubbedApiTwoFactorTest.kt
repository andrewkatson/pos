package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.ConfirmTotpRequest
import com.example.positiveonlysocial.data.model.DisableTotpRequest
import com.example.positiveonlysocial.data.model.LoginRequest
import com.example.positiveonlysocial.data.model.LoginTwoFactorRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Exercises the two-factor login flow (issue #348) against the in-memory stub,
 * mirroring the backend semantics: enrolled accounts get a challenge instead of
 * a session, challenges and recovery codes are single-use, and remember-me is
 * carried through the second step.
 */
class StatefulStubbedApiTwoFactorTest {

    /** Registers a user, enables 2FA, and returns their (token, recoveryCodes). */
    private suspend fun registerAndEnroll(api: StatefulStubbedAPI, username: String): Pair<String, List<String>> {
        val token = api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken
        api.setupTotp(token)
        val confirm = api.confirmTotp(token, ConfirmTotpRequest("pw12345", StatefulStubbedAPI.STUB_TOTP_CODE))
        return token to confirm.body()!!.recoveryCodes
    }

    @Test
    fun `confirm rejects a wrong password so a stolen session cannot enrol`() = runTest {
        // Enrolling with a session alone would let a session thief bind their own
        // authenticator, read the recovery codes, and lock the owner out for good.
        val api = StatefulStubbedAPI()
        val token = api.register(
            RegisterRequest("grace", "grace@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken
        api.setupTotp(token)

        val wrong = api.confirmTotp(token, ConfirmTotpRequest("wrong", StatefulStubbedAPI.STUB_TOTP_CODE))
        assertEquals(400, wrong.code())

        val right = api.confirmTotp(token, ConfirmTotpRequest("pw12345", StatefulStubbedAPI.STUB_TOTP_CODE))
        assertEquals(200, right.code())
        assertEquals(10, right.body()!!.recoveryCodes.size)
    }

    @Test
    fun `enrolled login returns challenge then a code yields a session`() = runTest {
        val api = StatefulStubbedAPI()
        registerAndEnroll(api, "ada")

        val loginResponse = api.loginUser(LoginRequest("ada", "pw12345", "false", "127.0.0.1"))
        val body = loginResponse.body()!!
        assertTrue(body.twoFactorRequired)
        assertNotNull(body.challengeToken)
        assertNull(body.sessionToken)

        val session = api.loginUser2FA(
            LoginTwoFactorRequest(challengeToken = body.challengeToken!!, totpCode = StatefulStubbedAPI.STUB_TOTP_CODE)
        )
        assertTrue(session.isSuccessful)
        assertEquals("ada", session.body()!!.username)

        // The challenge is single-use.
        val replay = api.loginUser2FA(
            LoginTwoFactorRequest(challengeToken = body.challengeToken, totpCode = StatefulStubbedAPI.STUB_TOTP_CODE)
        )
        assertFalse(replay.isSuccessful)
    }

    @Test
    fun `wrong code is rejected`() = runTest {
        val api = StatefulStubbedAPI()
        registerAndEnroll(api, "grace")

        val login = api.loginUser(LoginRequest("grace", "pw12345", "false", "127.0.0.1")).body()!!
        val bad = api.loginUser2FA(LoginTwoFactorRequest(challengeToken = login.challengeToken!!, totpCode = "000000"))
        assertFalse(bad.isSuccessful)
    }

    @Test
    fun `recovery code works once`() = runTest {
        val api = StatefulStubbedAPI()
        val (_, codes) = registerAndEnroll(api, "hopper")
        val recovery = codes.first()

        val firstLogin = api.loginUser(LoginRequest("hopper", "pw12345", "false", "127.0.0.1")).body()!!
        val ok = api.loginUser2FA(LoginTwoFactorRequest(challengeToken = firstLogin.challengeToken!!, recoveryCode = recovery))
        assertTrue(ok.isSuccessful)

        // The same code is refused on the next login.
        val secondLogin = api.loginUser(LoginRequest("hopper", "pw12345", "false", "127.0.0.1")).body()!!
        val reused = api.loginUser2FA(LoginTwoFactorRequest(challengeToken = secondLogin.challengeToken!!, recoveryCode = recovery))
        assertFalse(reused.isSuccessful)
    }

    @Test
    fun `remember me is carried through the second step`() = runTest {
        val api = StatefulStubbedAPI()
        registerAndEnroll(api, "margaret")

        val login = api.loginUser(LoginRequest("margaret", "pw12345", "true", "127.0.0.1")).body()!!
        val session = api.loginUser2FA(
            LoginTwoFactorRequest(challengeToken = login.challengeToken!!, totpCode = StatefulStubbedAPI.STUB_TOTP_CODE)
        ).body()!!
        assertNotNull(session.seriesIdentifier)
        assertNotNull(session.loginCookieToken)
    }

    @Test
    fun `disable turns two factor off and login is single-step again`() = runTest {
        val api = StatefulStubbedAPI()
        val (token, _) = registerAndEnroll(api, "katherine")

        val disable = api.disableTotp(
            token,
            DisableTotpRequest(password = "pw12345", totpCode = StatefulStubbedAPI.STUB_TOTP_CODE)
        )
        assertTrue(disable.isSuccessful)
        assertFalse(disable.body()!!.totpEnabled)

        val login = api.loginUser(LoginRequest("katherine", "pw12345", "false", "127.0.0.1")).body()!!
        assertFalse(login.twoFactorRequired)
        assertNotNull(login.sessionToken)
    }
}
