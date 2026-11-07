package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.IdentityVerificationRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.SetAccountPrivacyRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate

/** The Top profiles scoreboard (issue #588) against the in-memory stub. */
class StatefulStubbedApiTopProfilesTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `top profiles rank public accounts by followers and skip those with none`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "popular")
        register(api, "modest")
        register(api, "lonely")
        val fanOne = register(api, "fanone")
        api.followUser(fanOne, "popular")
        api.followUser(fanOne, "modest")
        val viewer = register(api, "viewer")
        api.followUser(viewer, "popular")

        val board = api.getTopProfiles(viewer, 0).body()!!
        assertEquals(listOf("popular" to 2, "modest" to 1), board.map { it.username to it.followerCount })
    }

    @Test
    fun `top profiles leave out private and blocked accounts`() = runTest {
        val api = StatefulStubbedAPI()
        val secret = register(api, "secret")
        api.setAccountPrivacy(secret, SetAccountPrivacyRequest(true))
        register(api, "rude")
        val viewer = register(api, "viewer")
        api.followUser(viewer, "rude")
        api.followUser(viewer, "secret")
        assertEquals(listOf("rude"), api.getTopProfiles(viewer, 0).body()!!.map { it.username })

        api.toggleBlock(viewer, "rude")
        assertEquals(emptyList<String>(), api.getTopProfiles(viewer, 0).body()!!.map { it.username })
    }

    @Test
    fun `top profiles stay within the viewer's age band`() = runTest {
        val api = StatefulStubbedAPI()
        val teen = register(api, "teen")
        api.verifyIdentity(teen, IdentityVerificationRequest(LocalDate.now().minusYears(16).toString()))
        val teenFan = register(api, "teenfan")
        api.verifyIdentity(teenFan, IdentityVerificationRequest(LocalDate.now().minusYears(17).toString()))
        api.followUser(teenFan, "teen")
        register(api, "adult")
        val adultFan = register(api, "adultfan")
        api.followUser(adultFan, "adult")

        assertEquals(listOf("adult"), api.getTopProfiles(adultFan, 0).body()!!.map { it.username })
        assertEquals(listOf("teen"), api.getTopProfiles(teen, 0).body()!!.map { it.username })
    }

    @Test
    fun `top profiles page in batches`() = runTest {
        val api = StatefulStubbedAPI()
        api.topProfilesPageSize = 1
        register(api, "alpha")
        register(api, "beta")
        val viewer = register(api, "viewer")
        api.followUser(viewer, "alpha")
        api.followUser(viewer, "beta")

        assertEquals(listOf("alpha"), api.getTopProfiles(viewer, 0).body()!!.map { it.username })
        assertEquals(listOf("beta"), api.getTopProfiles(viewer, 1).body()!!.map { it.username })
        assertEquals(emptyList<String>(), api.getTopProfiles(viewer, 2).body()!!.map { it.username })
    }
}
