package com.example.positiveonlysocial.data.model

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
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
    fun `listing json carries the interaction state and feed details`() {
        // The three post-listing endpoints now return the same interaction state
        // the details endpoint does (issue #267), plus the comment count and
        // creation time the feed rows show (issue #249).
        val json = """
            {
              "post_identifier": "p2",
              "image_url": "https://example.com/b.jpg",
              "caption": "yo",
              "author_username": "bob",
              "post_likes": 4,
              "is_liked": true,
              "is_reported": true,
              "report_reason": "spam",
              "comment_count": 12,
              "creation_time": "2026-07-21T10:11:12Z"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertEquals("p2", post.postIdentifier)
        assertEquals(4, post.likeCount)
        assertTrue(post.isLiked)
        assertTrue(post.isReported)
        assertEquals("spam", post.reportReason)
        assertEquals(12, post.commentCount)
        assertEquals("2026-07-21T10:11:12Z", post.creationTime)
    }

    @Test
    fun `listing json from an older server without the new fields still parses`() {
        // A server that predates the extra listing fields omits them entirely;
        // the post must still deserialize with harmless defaults rather than
        // failing, so an out-of-date backend doesn't break the feed.
        val json = """
            {
              "post_identifier": "p4",
              "image_url": "https://example.com/d.jpg",
              "caption": "yo",
              "author_username": "bob"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertEquals("p4", post.postIdentifier)
        assertEquals(false, post.isLiked)
        assertEquals(false, post.isReported)
        assertNull(post.reportReason)
        assertNull(post.creationTime)
    }

    @Test
    fun `text-only post json with null image_url deserializes to null imageUrl`() {
        // A text-only post (#307): the backend serializes image_url as null.
        val json = """
            {
              "post_identifier": "p3",
              "image_url": null,
              "original_image_url": null,
              "caption": "words only",
              "author_username": "carol"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertEquals("p3", post.postIdentifier)
        assertNull(post.imageUrl)
        assertNull(post.originalImageUrl)
        assertEquals("words only", post.caption)
    }

    @Test
    fun `text-only create request omits image_url from the body`() {
        // The wire convention for #307: clients omit image_url rather than
        // sending null (Gson drops null fields by default).
        val body = gson.toJson(CreatePostRequest(caption = "words only"))

        assertFalse(body.contains("image_url"))
        assertTrue(body.contains("words only"))
    }
}
