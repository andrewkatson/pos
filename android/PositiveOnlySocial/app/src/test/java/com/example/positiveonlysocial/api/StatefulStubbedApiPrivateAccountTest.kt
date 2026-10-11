package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.CommentRequest
import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.ReportRequest
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

        assertEquals(listOf("viewer"), api.getFollowRequests(authorToken, null).body()!!.map { it.username })
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
        assertTrue(api.getFollowRequests(authorToken, null).body()!!.isEmpty())
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

        assertTrue(api.getFollowRequests(authorToken, null).body()!!.isEmpty())
    }

    @Test
    fun `a non-follower can't find or interact with a private post`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        api.setAccountPrivacy(authorToken, SetAccountPrivacyRequest(true))
        val postId = api.makePost(authorToken, CreatePostRequest(imageUrl = "a.jpg", caption = "sunny #beach"))
            .body()!!.postIdentifier
        val comment = api.commentOnPost(authorToken, postId, CommentRequest("lovely")).body()!!
        val viewerToken = register(api, "viewer")

        assertTrue(api.getPostsByTag(viewerToken, "beach", 0).body()!!.isEmpty())
        assertFalse(api.likePost(viewerToken, postId).isSuccessful)
        assertFalse(api.reportPost(viewerToken, postId, ReportRequest("not positive")).isSuccessful)
        assertFalse(api.commentOnPost(viewerToken, postId, CommentRequest("hi")).isSuccessful)
        assertFalse(api.likeComment(viewerToken, postId, comment.threadIdentifier!!, comment.commentIdentifier).isSuccessful)
        assertFalse(
            api.reportComment(
                viewerToken, postId, comment.threadIdentifier!!, comment.commentIdentifier, ReportRequest("x")
            ).isSuccessful
        )

        assertFalse(api.savePost(viewerToken, postId).isSuccessful)
        assertFalse(api.getCommentsForPost(viewerToken, postId, 0, null).isSuccessful)
        assertFalse(api.getCommentsForThread(viewerToken, comment.threadIdentifier!!, 0, null).isSuccessful)
        assertFalse(api.replyToThread(viewerToken, postId, comment.threadIdentifier!!, CommentRequest("hi")).isSuccessful)

        api.followUser(viewerToken, "author")
        api.approveFollowRequest(authorToken, "viewer")
        assertEquals(1, api.getPostsByTag(viewerToken, "beach", 0).body()!!.size)
        assertEquals(1, api.getCommentsForThread(viewerToken, comment.threadIdentifier!!, 0, null).body()!!.size)
        assertTrue(api.likePost(viewerToken, postId).isSuccessful)
    }

    @Test
    fun `a request is refused when the requester blocked the private account`() = runTest {
        val api = StatefulStubbedAPI()
        val (_, viewerToken) = privateAuthorAndViewer(api)
        api.toggleBlock(viewerToken, "author")

        assertFalse(api.followUser(viewerToken, "author").isSuccessful)
    }

    @Test
    fun `deleting a requester drops their pending follow request`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")

        api.deleteUser(viewerToken)

        assertTrue(api.getFollowRequests(authorToken, null).body()!!.isEmpty())
        assertEquals(0, api.getProfileDetails(authorToken, "author").body()!!.followRequestCount)
    }

    @Test
    fun `a requester who verified as a minor cannot be approved`() = runTest {
        val api = StatefulStubbedAPI()
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        api.followUser(viewerToken, "author")
        val minorYear = java.time.LocalDate.now().year - 16
        api.verifyIdentity(viewerToken, com.example.positiveonlysocial.data.model.IdentityVerificationRequest("$minorYear-01-01"))

        assertTrue(api.getFollowRequests(authorToken, null).body()!!.isEmpty())
        assertFalse(api.approveFollowRequest(authorToken, "viewer").isSuccessful)
        api.setAccountPrivacy(authorToken, SetAccountPrivacyRequest(false))
        assertEquals(0, api.getProfileDetails(authorToken, "author").body()!!.followerCount)
    }

    @Test
    fun `follow requests page by request-id cursor, unaffected by answering rows`() = runTest {
        val api = StatefulStubbedAPI()
        api.followRequestBatchSize = 1
        val (authorToken, viewerToken) = privateAuthorAndViewer(api)
        val otherToken = register(api, "other")
        api.followUser(viewerToken, "author")
        api.followUser(otherToken, "author")

        val first = api.getFollowRequests(authorToken, null).body()!!
        assertEquals(listOf("other"), first.map { it.username })
        api.approveFollowRequest(authorToken, "other") // answering a row doesn't shift the cursor
        val second = api.getFollowRequests(authorToken, first.last().requestId).body()!!
        assertEquals(listOf("viewer"), second.map { it.username })
        assertTrue(api.getFollowRequests(authorToken, second.last().requestId).body()!!.isEmpty())
    }
}
