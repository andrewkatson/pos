package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.model.FollowCategory
import com.example.positiveonlysocial.data.model.PostAudience
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.SetCategoryRequest
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Relationship categories & post audience (issue #392) against the in-memory
 * stub: follow categories drive both the feed filter and post visibility.
 */
class StatefulStubbedApiRelationshipTest {

    private suspend fun register(api: StatefulStubbedAPI, username: String): String =
        api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!.sessionToken

    @Test
    fun `follow defaults to following and profile reports the category`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "target")
        val viewerToken = register(api, "viewer")

        api.followUser(viewerToken, "target")
        assertEquals(
            FollowCategory.FOLLOWING.value,
            api.getProfileDetails(viewerToken, "target").body()!!.followCategory
        )
    }

    @Test
    fun `setFollowCategory requires an existing follow then updates it`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "target")
        val viewerToken = register(api, "viewer")

        val notFollowing = api.setFollowCategory(viewerToken, "target", SetCategoryRequest("friend"))
        assertFalse(notFollowing.isSuccessful)

        api.followUser(viewerToken, "target")
        val updated = api.setFollowCategory(viewerToken, "target", SetCategoryRequest("family"))
        assertTrue(updated.isSuccessful)
        assertEquals(
            FollowCategory.FAMILY.value,
            api.getProfileDetails(viewerToken, "target").body()!!.followCategory
        )
    }

    @Test
    fun `profile has a null category when not following`() = runTest {
        val api = StatefulStubbedAPI()
        register(api, "target")
        val viewerToken = register(api, "viewer")

        val profile = api.getProfileDetails(viewerToken, "target").body()!!
        assertFalse(profile.isFollowing)
        assertNull(profile.followCategory)
    }

    @Test
    fun `a family-only post reaches only family-labeled viewers`() = runTest {
        val api = StatefulStubbedAPI()
        val viewerToken = register(api, "viewer")
        val authorToken = register(api, "author")

        // The author labels the viewer a friend, then posts to family only.
        api.followUser(authorToken, "viewer")
        api.setFollowCategory(authorToken, "viewer", SetCategoryRequest("friend"))
        val postId = api.makePost(
            authorToken, CreatePostRequest(caption = "family news", audience = PostAudience.FAMILY.value)
        ).body()!!.postIdentifier

        // A friend is too far out for a family-only post.
        assertFalse(api.getPostDetails(viewerToken, postId).isSuccessful)

        // Promote to family and it becomes visible.
        api.setFollowCategory(authorToken, "viewer", SetCategoryRequest("family"))
        val visible = api.getPostDetails(viewerToken, postId)
        assertTrue(visible.isSuccessful)
        assertEquals(PostAudience.FAMILY.value, visible.body()!!.audience)
    }

    @Test
    fun `the author always sees their own restricted post`() = runTest {
        val api = StatefulStubbedAPI()
        val authorToken = register(api, "author")
        val postId = api.makePost(
            authorToken, CreatePostRequest(caption = "just me", audience = PostAudience.FAMILY.value)
        ).body()!!.postIdentifier

        assertTrue(api.getPostDetails(authorToken, postId).isSuccessful)
    }

    @Test
    fun `the followed feed can be filtered to an exact group`() = runTest {
        // Each user makes a single post, so the default batch size returns them
        // all in batch 0.
        val api = StatefulStubbedAPI()
        val viewerToken = register(api, "viewer")
        val famToken = register(api, "famUser")
        val friToken = register(api, "friUser")

        api.followUser(viewerToken, "famUser")
        api.setFollowCategory(viewerToken, "famUser", SetCategoryRequest("family"))
        api.followUser(viewerToken, "friUser")
        api.setFollowCategory(viewerToken, "friUser", SetCategoryRequest("friend"))

        val famPost = api.makePost(famToken, CreatePostRequest(imageUrl = "f.jpg", caption = "fam")).body()!!.postIdentifier
        val friPost = api.makePost(friToken, CreatePostRequest(imageUrl = "r.jpg", caption = "fri")).body()!!.postIdentifier

        val all = api.getFollowedPosts(viewerToken, 0).body()!!.map { it.postIdentifier }
        assertTrue(all.contains(famPost))
        assertTrue(all.contains(friPost))

        val familyOnly = api.getFollowedPosts(viewerToken, 0, "family").body()!!.map { it.postIdentifier }
        assertEquals(listOf(famPost), familyOnly)

        val friendOnly = api.getFollowedPosts(viewerToken, 0, "friend").body()!!.map { it.postIdentifier }
        assertEquals(listOf(friPost), friendOnly)
    }
}
