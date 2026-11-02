package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.CommentFormatSpan
import com.example.positiveonlysocial.data.model.CommentRequest
import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.EditCommentRequest
import com.example.positiveonlysocial.data.model.EditPostRequest
import com.example.positiveonlysocial.data.model.RegisterRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Editing a caption or a comment (issue #462) against the in-memory stub: only
 * the author may, a rejected edit keeps the original, and a saved one is
 * marked edited.
 */
class StatefulStubbedApiEditTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `editPost replaces the caption, re-tags it, and marks it edited`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "author")
        val postId = api.makePost(token, CreatePostRequest(caption = "sunny day")).body()!!.postIdentifier
        assertNull(api.getPostDetails(token, postId).body()!!.editedTime)

        val saved = api.editPost(token, postId, EditPostRequest("sunny day #beach")).body()!!

        assertEquals("sunny day #beach", saved.caption)
        assertEquals(listOf("beach"), saved.tags)
        val details = api.getPostDetails(token, postId).body()!!
        assertEquals("sunny day #beach", details.caption)
        assertNotNull(details.editedTime)
    }

    @Test
    fun `post listings carry the edit time`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "author")
        val postId = api.makePost(token, CreatePostRequest(caption = "sunny day")).body()!!.postIdentifier
        api.editPost(token, postId, EditPostRequest("sunny day #beach"))

        val listed = api.getPostsForUser(token, "author", 0).body()!!.single()
        assertEquals("sunny day #beach", listed.caption)
        assertNotNull(listed.editedTime)
    }

    @Test
    fun `editPost refuses negative text and someone else's post`() = runTest {
        val api = StatefulStubbedAPI()
        val token = register(api, "author")
        val otherToken = register(api, "other")
        val postId = api.makePost(token, CreatePostRequest(caption = "sunny day")).body()!!.postIdentifier

        assertEquals(400, api.editPost(token, postId, EditPostRequest("negative")).code())
        assertFalse(api.editPost(otherToken, postId, EditPostRequest("mine now")).isSuccessful)
        assertEquals("sunny day", api.getPostDetails(token, postId).body()!!.caption)
    }

    @Test
    fun `editComment is author-only, frozen by a comments lock, and keeps the original on a rejection`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val commenterToken = register(api, "commenter")
        val postId = api.makePost(authorToken, CreatePostRequest(caption = "sunny day")).body()!!.postIdentifier
        val created = api.commentOnPost(commenterToken, postId, CommentRequest("lovely")).body()!!
        val threadId = created.threadIdentifier!!
        val commentId = created.commentIdentifier

        val bold = listOf(CommentFormatSpan(0, 2, true, false, "normal"))
        val saved = api.editComment(commenterToken, postId, threadId, commentId, EditCommentRequest("so lovely", bold)).body()!!
        assertEquals("so lovely", saved.body)
        assertEquals(bold, saved.bodyFormatting)
        assertNotNull(saved.editedTime)

        assertEquals(400, api.editComment(commenterToken, postId, threadId, commentId, EditCommentRequest("negative")).code())
        assertFalse(api.editComment(authorToken, postId, threadId, commentId, EditCommentRequest("hijacked")).isSuccessful)

        api.lockComments(authorToken, postId)
        assertEquals(403, api.editComment(commenterToken, postId, threadId, commentId, EditCommentRequest("after lock")).code())

        val listed = api.getCommentsForThread(commenterToken, threadId, 0).body()!!.single()
        assertEquals("so lovely", listed.body)
        assertTrue(listed.editedTime != null)
    }
}
