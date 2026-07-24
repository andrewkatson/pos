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

    // --- Profile photos (issue #7) ---

    @Test
    fun `post json carries the author profile image fields`() {
        // The author's approved profile photo is threaded next to author_username
        // through every list/detail payload, compressed variant plus original
        // fallback (mirroring image_url/original_image_url).
        val json = """
            {
              "post_identifier": "p5",
              "image_url": "https://example.com/e.jpg",
              "caption": "hi",
              "author_username": "alice",
              "author_profile_image_url": "https://example.com/avatar-small.jpg",
              "author_profile_image_original_url": "https://example.com/avatar-full.jpg"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertEquals("https://example.com/avatar-small.jpg", post.authorProfileImageUrl)
        assertEquals("https://example.com/avatar-full.jpg", post.authorProfileImageOriginalUrl)
    }

    @Test
    fun `post json without avatar fields leaves them null`() {
        // A post whose author has no approved photo (or an older server that
        // predates the field) omits them, so they default to null.
        val json = """
            {
              "post_identifier": "p6",
              "image_url": "https://example.com/f.jpg",
              "caption": "hi",
              "author_username": "bob"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertNull(post.authorProfileImageUrl)
        assertNull(post.authorProfileImageOriginalUrl)
    }

    @Test
    fun `comment json carries the author profile image fields`() {
        val json = """
            {
              "comment_identifier": "c1",
              "body": "nice",
              "author_username": "alice",
              "creation_time": "2026-07-21T10:11:12Z",
              "updated_time": "2026-07-21T10:11:12Z",
              "comment_likes": 3,
              "author_profile_image_url": "https://example.com/avatar-small.jpg",
              "author_profile_image_original_url": "https://example.com/avatar-full.jpg"
            }
        """.trimIndent()

        val comment = gson.fromJson(json, CommentDto::class.java)

        assertEquals("https://example.com/avatar-small.jpg", comment.authorProfileImageUrl)
        assertEquals("https://example.com/avatar-full.jpg", comment.authorProfileImageOriginalUrl)
    }

    @Test
    fun `profile details json maps the avatar and owner-only photo fields`() {
        // getProfileDetails now returns the approved photo (compressed + original
        // fallback) plus, for the owner only, the moderation state.
        val json = """
            {
              "username": "alice",
              "post_count": 2,
              "follower_count": 5,
              "following_count": 3,
              "is_following": false,
              "profile_image_url": "https://example.com/avatar-small.jpg",
              "profile_image_original_url": "https://example.com/avatar-full.jpg",
              "profile_image_status": "pending",
              "profile_image_reason_code": null,
              "pending_profile_image_url": "https://example.com/pending.jpg"
            }
        """.trimIndent()

        val profile = gson.fromJson(json, ProfileDetailsResponse::class.java)

        assertEquals("https://example.com/avatar-small.jpg", profile.profileImageUrl)
        assertEquals("https://example.com/avatar-full.jpg", profile.profileImageOriginalUrl)
        assertEquals("pending", profile.profileImageStatus)
        assertNull(profile.profileImageReasonCode)
        assertEquals("https://example.com/pending.jpg", profile.pendingProfileImageUrl)
    }

    @Test
    fun `profile details json without owner-only fields leaves them null`() {
        // Viewing someone else's profile: the backend omits the owner-only
        // moderation fields entirely, so they default to null.
        val json = """
            {
              "username": "bob",
              "post_count": 0,
              "follower_count": 0,
              "following_count": 0,
              "is_following": true,
              "profile_image_url": "https://example.com/bob.jpg",
              "profile_image_original_url": "https://example.com/bob.jpg"
            }
        """.trimIndent()

        val profile = gson.fromJson(json, ProfileDetailsResponse::class.java)

        assertEquals("https://example.com/bob.jpg", profile.profileImageUrl)
        assertNull(profile.profileImageStatus)
        assertNull(profile.pendingProfileImageUrl)
    }

    @Test
    fun `set profile photo request serializes image_url and response maps status`() {
        val body = gson.toJson(SetProfilePhotoRequest(imageUrl = "https://example.com/a.jpg"))
        assertTrue(body.contains("image_url"))
        assertTrue(body.contains("https://example.com/a.jpg"))

        val response = gson.fromJson(
            """{ "profile_image_status": "pending", "message": "reviewing" }""",
            SetProfilePhotoResponse::class.java
        )
        assertEquals("pending", response.profileImageStatus)
        assertEquals("reviewing", response.message)

        val removed = gson.fromJson(
            """{ "profile_image_status": "none", "message": "removed" }""",
            RemoveProfilePhotoResponse::class.java
        )
        assertEquals("none", removed.profileImageStatus)
    }

    // --- Text formatting (issue #318) ---

    @Test
    fun `post json maps caption_font and background_color (issue 318)`() {
        val json = """
            {
              "post_identifier": "p5",
              "image_url": null,
              "caption": "styled",
              "author_username": "dee",
              "caption_font": "serif",
              "background_color": "mint"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertEquals("serif", post.captionFont)
        assertEquals("mint", post.backgroundColor)
    }

    @Test
    fun `post json without style fields leaves them null, rendered as default (issue 318)`() {
        // Gson does not apply Kotlin default values for absent JSON fields, so a
        // response that predates the style fields deserializes them to null; the
        // render layer (TextFormatting) treats null as the default rendering.
        val json = """
            {
              "post_identifier": "p6",
              "caption": "plain",
              "author_username": "dee"
            }
        """.trimIndent()

        val post = gson.fromJson(json, Post::class.java)

        assertNull(post.captionFont)
        assertNull(post.backgroundColor)
    }

    @Test
    fun `comment json maps body_formatting spans (issue 318)`() {
        val json = """
            {
              "comment_identifier": "c1",
              "body": "love this",
              "author_username": "dee",
              "creation_time": "t",
              "updated_time": "t",
              "comment_likes": 0,
              "body_formatting": [
                {"start": 0, "end": 4, "bold": true, "italic": false, "size": "normal"},
                {"start": 5, "end": 9, "bold": false, "italic": true, "size": "large"}
              ]
            }
        """.trimIndent()

        val comment = gson.fromJson(json, CommentDto::class.java)

        assertEquals(2, comment.bodyFormatting?.size)
        assertEquals(0, comment.bodyFormatting?.get(0)?.start)
        assertTrue(comment.bodyFormatting?.get(0)?.bold == true)
        assertEquals("large", comment.bodyFormatting?.get(1)?.size)
    }

    @Test
    fun `comment json without body_formatting is null (issue 318)`() {
        val json = """
            {
              "comment_identifier": "c2",
              "body": "plain",
              "author_username": "dee",
              "creation_time": "t",
              "updated_time": "t",
              "comment_likes": 0
            }
        """.trimIndent()

        val comment = gson.fromJson(json, CommentDto::class.java)

        assertNull(comment.bodyFormatting)
    }
}
