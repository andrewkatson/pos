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
 * Deleting a comment against the in-memory stub (issue #603): the comment's
 * author and the post's author may, nobody else — and owning some other post
 * grants nothing over its comments.
 */
class StatefulStubbedApiDeleteCommentTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `the post's author can delete someone else's comment on it`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val commenterToken = register(api, "commenter")
        val postId = api.makePost(authorToken, CreatePostRequest(caption = "sunny day")).body()!!.postIdentifier
        val created = api.commentOnPost(commenterToken, postId, CommentRequest("lovely")).body()!!

        val response = api.deleteComment(authorToken, postId, created.threadIdentifier!!, created.commentIdentifier)

        assertTrue(response.isSuccessful)
        assertEquals(0, api.getCommentsForThread(authorToken, created.threadIdentifier!!, 0, null).body()!!.size)
    }

    @Test
    fun `pairing a post you own with a thread from someone else's post deletes nothing`() = runTest {
        val api = StatefulStubbedAPI()
        val attackerToken = register(api, "attacker")
        val victimToken = register(api, "victim")
        val commenterToken = register(api, "commenter")
        val ownPostId = api.makePost(attackerToken, CreatePostRequest(caption = "mine")).body()!!.postIdentifier
        val victimPostId = api.makePost(victimToken, CreatePostRequest(caption = "theirs")).body()!!.postIdentifier
        val created = api.commentOnPost(commenterToken, victimPostId, CommentRequest("lovely")).body()!!
        val threadId = created.threadIdentifier!!

        val response = api.deleteComment(attackerToken, ownPostId, threadId, created.commentIdentifier)

        assertFalse(response.isSuccessful)
        assertEquals(1, api.getCommentsForThread(victimToken, threadId, 0, null).body()!!.size)
    }
}
