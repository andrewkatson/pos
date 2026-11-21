package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.ChangeUsernameRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.RequestEmailChangeRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The stub's username and email change endpoints (issue #594). */
class StatefulStubbedApiAccountChangeTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "Password1", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `me reports the account change fields`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "ada_lovelace")

        val me = api.getCurrentUser(token).body()!!

        assertEquals(true, me.hasPassword)
        assertNull(me.pendingEmail)
        assertNull(me.nextUsernameChangeTime)
    }

    @Test
    fun `changeUsername renames once and then enforces the cooldown`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "ada_lovelace")

        val renamed = api.changeUsername(token, ChangeUsernameRequest("ada_renamed_1"))
        assertTrue(renamed.isSuccessful)
        assertNotNull(renamed.body()!!.nextUsernameChangeTime)
        assertEquals("ada_renamed_1", api.getCurrentUser(token).body()!!.username)

        val again = api.changeUsername(token, ChangeUsernameRequest("ada_renamed_2"))
        assertEquals(400, again.code())
        assertTrue(again.errorBody()!!.string().contains(ApiErrors.USERNAME_CHANGE_TOO_SOON))
    }

    @Test
    fun `changeUsername refuses invalid and taken names`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "grace_hopper")
        val token = register(api, "ada_lovelace")

        assertEquals(400, api.changeUsername(token, ChangeUsernameRequest("short")).code())
        val taken = api.changeUsername(token, ChangeUsernameRequest("grace_hopper"))
        assertTrue(taken.errorBody()!!.string().contains(ApiErrors.USERNAME_TAKEN))
    }

    @Test
    fun `email change waits for its link then swaps the address`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "grace_hopper")
        val token = register(api, "ada_lovelace")

        val wrong = api.requestEmailChange(token, RequestEmailChangeRequest("new@test.com", password = "nope"))
        assertTrue(wrong.errorBody()!!.string().contains(ApiErrors.REAUTHENTICATION_REQUIRED))
        val clash = api.requestEmailChange(token, RequestEmailChangeRequest("GRACE_HOPPER@test.com", password = "Password1"))
        assertTrue(clash.errorBody()!!.string().contains(ApiErrors.EMAIL_IN_USE))

        assertTrue(api.requestEmailChange(token, RequestEmailChangeRequest("new@test.com", password = "Password1")).isSuccessful)
        var me = api.getCurrentUser(token).body()!!
        assertEquals("ada_lovelace@test.com", me.email)
        assertEquals("new@test.com", me.pendingEmail)

        assertTrue(api.confirmEmailChange("stub_email_change_token_ada_lovelace"))
        me = api.getCurrentUser(token).body()!!
        assertEquals("new@test.com", me.email)
        assertNull(me.pendingEmail)
    }

    @Test
    fun `a cancelled email change can no longer be confirmed`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "ada_lovelace")
        api.requestEmailChange(token, RequestEmailChangeRequest("new@test.com", password = "Password1"))

        assertTrue(api.cancelEmailChange(token).isSuccessful)

        assertFalse(api.confirmEmailChange("stub_email_change_token_ada_lovelace"))
        assertEquals("ada_lovelace@test.com", api.getCurrentUser(token).body()!!.email)
    }
}
