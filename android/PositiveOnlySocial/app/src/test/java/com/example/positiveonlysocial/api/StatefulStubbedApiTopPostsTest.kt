package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.PostAudience
import com.example.positiveonlysocial.data.model.RegisterRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

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
}
