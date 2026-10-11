package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.SetAccountPrivacyRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Private accounts & follow requests (issue #96) against the in-memory stub:
 * following a private account files a request, and only approval reveals its
 * posts and counts.
 */
class StatefulStubbedApiPrivateAccountTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    /** A private author with one post; returns (authorToken, viewerToken). */
    private suspend fun privateAuthorAndViewer(api: StatefulStubbedAPI): Pair<String, String> {
        val authorToken = register(api, "author")
        api.setAccountPrivacy(authorToken, SetAccountPrivacyRequest(true))
        api.makePost(authorToken, CreatePostRequest(imageUrl = "a.jpg", caption = "hello"))
        return authorToken to register(api, "viewer")
    }

    @Test
    fun `following a private account files a request and keeps it locked`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)

        val follow = api.followUser(viewerToken, "author").body()!!
        assertEquals(true, follow.followRequestPending)

        val locked = api.getProfileDetails(viewerToken, "author").body()!!
        assertEquals(true, locked.isPrivate)
        assertFalse(locked.isFollowing)
        assertEquals(true, locked.followRequestPending)
        assertEquals(0, locked.postCount)
        assertTrue(api.getPostsForUser(viewerToken, "author", 0).body()!!.isEmpty())
        assertFalse(api.followUser(viewerToken, "author").isSuccessful)

        assertEquals(listOf("viewer"), api.getFollowRequests(authorToken).body()!!.map { it.username })
        assertEquals(1, api.getProfileDetails(authorToken, "author").body()!!.followRequestCount)
    }

    @Test
    fun `approving a request reveals posts and counts`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")

        assertTrue(api.approveFollowRequest(authorToken, "viewer").isSuccessful)

        val unlocked = api.getProfileDetails(viewerToken, "author").body()!!
        assertTrue(unlocked.isFollowing)
        assertEquals(1, unlocked.postCount)
        assertEquals(1, api.getPostsForUser(viewerToken, "author", 0).body()!!.size)
        assertTrue(api.getFollowRequests(authorToken).body()!!.isEmpty())
    }

    @Test
    fun `deny and cancel drop the request without following`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)

        api.followUser(viewerToken, "author")
        assertTrue(api.cancelFollowRequest(viewerToken, "author").isSuccessful)
        assertFalse(api.cancelFollowRequest(viewerToken, "author").isSuccessful)

        api.followUser(viewerToken, "author")
        assertTrue(api.denyFollowRequest(authorToken, "viewer").isSuccessful)
        val profile = api.getProfileDetails(viewerToken, "author").body()!!
        assertFalse(profile.isFollowing)
        assertEquals(false, profile.followRequestPending)
    }

    @Test
    fun `going public approves pending requests`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")

        api.setAccountPrivacy(authorToken, SetAccountPrivacyRequest(false))

        assertTrue(api.getProfileDetails(viewerToken, "author").body()!!.isFollowing)
        assertEquals(false, api.getCurrentUser(authorToken).body()!!.isPrivate)
    }

    @Test
    fun `blocking drops pending requests both ways`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")

        api.toggleBlock(authorToken, "viewer")

        assertTrue(api.getFollowRequests(authorToken).body()!!.isEmpty())
    }
}
