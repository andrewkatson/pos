package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.CommentRequest
import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Disabling/locking comments (issue #492) against the in-memory stub: a post's
 * author can turn commenting off at creation or lock it afterward, and either
 * way new top-level comments and replies are rejected while existing ones stay
 * visible.
 */
class StatefulStubbedApiCommentsLockTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `a post created with comments_disabled rejects a new comment`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val commenterToken = register(api, "commenter")

        val postId = api.makePost(
            authorToken, CreatePostRequest(caption = "quiet post", commentsDisabled = true)
        ).body()!!.postIdentifier

        assertTrue(api.getPostDetails(authorToken, postId).body()!!.commentsDisabled == true)

        val response = api.commentOnPost(commenterToken, postId, CommentRequest("nice!"))
        assertFalse(response.isSuccessful)
        assertEquals(403, response.code())
    }

    @Test
    fun `lockComments blocks new comments and unlockComments re-allows them`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val commenterToken = register(api, "commenter")
        val postId = api.makePost(authorToken, CreatePostRequest(caption = "open post")).body()!!.postIdentifier

        assertTrue(api.lockComments(authorToken, postId).isSuccessful)
        val blocked = api.commentOnPost(commenterToken, postId, CommentRequest("nice!"))
        assertFalse(blocked.isSuccessful)

        assertTrue(api.unlockComments(authorToken, postId).isSuccessful)
        val allowed = api.commentOnPost(commenterToken, postId, CommentRequest("nice!"))
        assertTrue(allowed.isSuccessful)
    }

    @Test
    fun `locking a post after a thread exists still blocks new replies to it`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val commenterToken = register(api, "commenter")
        val postId = api.makePost(authorToken, CreatePostRequest(caption = "open post")).body()!!.postIdentifier
        val threadId = api.commentOnPost(commenterToken, postId, CommentRequest("first"))
            .body()!!.threadIdentifier!!

        api.lockComments(authorToken, postId)

        val reply = api.replyToThread(commenterToken, postId, threadId, CommentRequest("second"))
        assertFalse(reply.isSuccessful)
        assertEquals(403, reply.code())
    }

    @Test
    fun `only the post author can lock or unlock its comments`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val strangerToken = register(api, "stranger")
        val postId = api.makePost(authorToken, CreatePostRequest(caption = "open post")).body()!!.postIdentifier

        assertFalse(api.lockComments(strangerToken, postId).isSuccessful)
        assertFalse(api.getPostDetails(authorToken, postId).body()!!.commentsDisabled == true)
    }
}
