package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.IdentityVerificationRequest
import com.example.positiveonlysocial.data.model.PostAudience
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.SetAccountPrivacyRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import java.time.LocalDate

/** The Top posts scoreboard (issue #558) against the in-memory stub. */
class StatefulStubbedApiTopPostsTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `top posts rank public posts by likes and skip restricted ones`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val quiet = api.makePost(authorToken, CreatePostRequest(imageUrl = "q.jpg", caption = "quiet")).body()!!.postIdentifier
        val loved = api.makePost(authorToken, CreatePostRequest(imageUrl = "l.jpg", caption = "loved")).body()!!.postIdentifier
        api.makePost(authorToken, CreatePostRequest(caption = "family", audience = PostAudience.FAMILY.value))

        val viewerToken = register(api, "viewer")
        api.likePost(viewerToken, loved)

        val top = api.getTopPosts(viewerToken, 0, "week").body()!!.map { it.postIdentifier }
        assertEquals(listOf(loved, quiet), top)
    }

    @Test
    fun `an unknown period is rejected`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "viewer")

        assertFalse(api.getTopPosts(token, 0, "decade").isSuccessful)
    }

    @Test
    fun `top posts stay within the viewer's age band`() = runTest {
        val api = StatefulStubbedAPI()
        val teenToken = register(api, "teen")
        api.verifyIdentity(teenToken, IdentityVerificationRequest(LocalDate.now().minusYears(16).toString()))
        val teenPost = api.makePost(teenToken, CreatePostRequest(imageUrl = "t.jpg", caption = "teen")).body()!!.postIdentifier

        val adultToken = register(api, "adult")
        val adultPost = api.makePost(adultToken, CreatePostRequest(imageUrl = "a.jpg", caption = "adult")).body()!!.postIdentifier

        assertEquals(listOf(adultPost), api.getTopPosts(adultToken, 0, "week").body()!!.map { it.postIdentifier })
        assertEquals(listOf(teenPost), api.getTopPosts(teenToken, 0, "week").body()!!.map { it.postIdentifier })
    }

    @Test
    fun `top users rank by followers and leave out the unfollowed`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "quiet")
        register(api, "star")
        register(api, "rising")
        val fan1 = register(api, "fan1")
        api.followUser(fan1, "star")
        api.followUser(fan1, "rising")
        val fan2 = register(api, "fan2")
        api.followUser(fan2, "star")

        val top = api.getTopUsers(fan2, 0).body()!!.map { it.username to it.followerCount }
        assertEquals(listOf("star" to 2, "rising" to 1), top)
    }

    @Test
    fun `top posts leave out private accounts`() = runTest {
        val api = StatefulStubbedAPI()
        val secretToken = register(api, "secret")
        api.setAccountPrivacy(secretToken, SetAccountPrivacyRequest(true))
        api.makePost(secretToken, CreatePostRequest(imageUrl = "s.jpg", caption = "private"))
        val openToken = register(api, "open")
        val openPost = api.makePost(openToken, CreatePostRequest(imageUrl = "o.jpg", caption = "public")).body()!!.postIdentifier

        val viewerToken = register(api, "viewer")
        assertEquals(listOf(openPost), api.getTopPosts(viewerToken, 0, "week").body()!!.map { it.postIdentifier })
    }

    @Test
    fun `top users leave out private accounts`() = runTest {
        val api = StatefulStubbedAPI()
        val secretToken = register(api, "secret")
        api.setAccountPrivacy(secretToken, SetAccountPrivacyRequest(true))
        register(api, "open")
        val fanToken = register(api, "fan")
        api.followUser(fanToken, "open")
        api.followUser(fanToken, "secret")
        api.approveFollowRequest(secretToken, "fan")

        assertEquals(listOf("open"), api.getTopUsers(fanToken, 0).body()!!.map { it.username })
    }

    @Test
    fun `a follower who verifies into the other age band drops from board and profile alike`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "star")
        val fan1 = register(api, "fan1")
        api.followUser(fan1, "star")
        val fan2 = register(api, "fan2")
        api.followUser(fan2, "star")
        api.verifyIdentity(fan2, IdentityVerificationRequest(LocalDate.now().minusYears(16).toString()))

        val viewer = register(api, "viewer")
        val row = api.getTopUsers(viewer, 0).body()!!.single()
        assertEquals("star" to 1, row.username to row.followerCount)
        assertEquals(row.followerCount, api.getProfileDetails(viewer, "star").body()!!.followerCount)
    }
}
