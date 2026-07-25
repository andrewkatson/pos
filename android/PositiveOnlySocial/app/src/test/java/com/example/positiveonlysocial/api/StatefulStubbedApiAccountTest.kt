package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.ChangePasswordRequest
import com.example.positiveonlysocial.data.model.LoginRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Exercises the account / contact endpoints (issue #197/#194) against the
 * in-memory stub, mirroring the backend semantics: /me/ returns the signed-in
 * account's own username + email, and changing the password requires the current
 * password, refuses reusing it, and evicts the account's other sessions.
 */
class StatefulStubbedApiAccountTest {

    /** Registers a user and returns their session token. */
    private suspend fun register(api: StatefulStubbedAPI, username: String, password: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", password, "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `getCurrentUser returns the signed-in account's own username and email`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "ada", "Password1")

        val me = api.getCurrentUser(token).body()!!

        assertEquals("ada", me.username)
        assertEquals("ada@test.com", me.email)
    }

    @Test
    fun `getCurrentUser rejects an unknown session`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "grace", "Password1")

        val response = api.getCurrentUser("not-a-real-token")

        assertEquals(401, response.code())
    }

    @Test
    fun `changePassword rejects a wrong current password`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "hopper", "Password1")

        val response = api.changePassword(token, ChangePasswordRequest("WrongPass1", "NewPass123"))

        assertEquals(400, response.code())
    }

    @Test
    fun `changePassword rejects reusing the current password`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "katherine", "Password1")

        val response = api.changePassword(token, ChangePasswordRequest("Password1", "Password1"))

        assertEquals(400, response.code())
    }

    @Test
    fun `changePassword updates the password so only the new one logs in`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "margaret", "Password1")

        val response = api.changePassword(token, ChangePasswordRequest("Password1", "NewPass123"))
        assertTrue(response.isSuccessful)

        assertFalse(api.loginUser(LoginRequest("margaret", "Password1", "false", "127.0.0.1")).isSuccessful)
        assertTrue(api.loginUser(LoginRequest("margaret", "NewPass123", "false", "127.0.0.1")).isSuccessful)
    }

    @Test
    fun `changePassword keeps the current session but evicts the others`() = runTest {
        // A leaked session must not outlive a password change, so every session
        // except the one making the change is invalidated (mirrors the backend).
        val api = StatefulStubbedAPI()
        val token = register(api, "radia", "Password1")
        val other = api.loginUser(LoginRequest("radia", "Password1", "false", "127.0.0.1")).body()!!.sessionToken!!

        api.changePassword(token, ChangePasswordRequest("Password1", "NewPass123"))

        assertTrue(api.getCurrentUser(token).isSuccessful)
        assertEquals(401, api.getCurrentUser(other).code())
    }
}
