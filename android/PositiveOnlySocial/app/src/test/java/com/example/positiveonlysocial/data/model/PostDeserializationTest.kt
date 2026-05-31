package com.example.positiveonlysocial.data.model

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Locks in the JSON mapping for the [Post] DTO. The post-details endpoint returns
 * the like count under "post_likes" (not "likeCount"), so without the
 * @SerializedName the like count silently deserialized to its default and the
 * detail screen always showed 0.
 */
class PostDeserializationTest {

    private val gson = Gson()

    @Test
    fun `post details json maps post_likes to likeCount and is_liked to isLiked`() {
        val json = """
            {
              "post_identifier": "p1",
              "image_url": "https://example.com/a.jpg",
              "caption": "hi",
              "post_likes": 7,
              "is_liked": true,
              "author_username": "alice"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertEquals("p1", post.postIdentifier)
        assertEquals("alice", post.authorUsername)
        assertEquals(7, post.likeCount)
        assertTrue(post.isLiked)
    }

    @Test
    fun `feed json without like fields leaves isLiked false`() {
        // Feed endpoints omit post_likes / is_liked entirely.
        val json = """
            {
              "post_identifier": "p2",
              "image_url": "https://example.com/b.jpg",
              "caption": "yo",
              "author_username": "bob"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertEquals("p2", post.postIdentifier)
        assertEquals(false, post.isLiked)
    }
}
