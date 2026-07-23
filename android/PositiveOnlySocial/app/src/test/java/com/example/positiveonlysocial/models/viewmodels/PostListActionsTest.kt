package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.ReportRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.util.PostEvents
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.eq
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

/**
 * Covers the in-place post actions shared by every post list (issue #267). A
 * [FeedViewModel] hosts them here because it owns the list they mutate; the
 * profile grids use the very same [PostListActions] over their own list.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class PostListActionsTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: FeedViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

    private val otherPost = Post(
        postIdentifier = "1",
        imageUrl = "url1",
        caption = "caption1",
        authorUsername = "someone_else",
        likeCount = 3
    )

    private val ownPost = Post(
        postIdentifier = "2",
        imageUrl = "url2",
        caption = "caption2",
        authorUsername = "testuser",
        likeCount = 7
    )

    private val actions: PostListActions get() = viewModel.postActions

    private fun postWithId(id: String): Post =
        viewModel.feedPosts.value.first { it.postIdentifier == id }

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()

        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)

        viewModel = FeedViewModel(api, keychainHelper)
    }

    private suspend fun loadFeed() {
        whenever(api.getPostsInFeed("token123", 0))
            .thenReturn(Response.success(listOf(otherPost, ownPost)))
        viewModel.fetchFeed()
    }

    @Test
    fun `currentUsername comes from the stored session`() = runTest {
        assertEquals("testuser", actions.currentUsername.value)
    }

    @Test
    fun `isOwnPost distinguishes the signed-in user's posts`() = runTest {
        assertTrue(actions.isOwnPost(ownPost))
        assertFalse(actions.isOwnPost(otherPost))
    }

    @Test
    fun `toggleLike likes optimistically and calls the api`() = runTest {
        loadFeed()
        whenever(api.likePost("token123", "1"))
            .thenReturn(Response.success(GenericResponse("Liked", null)))

        actions.toggleLike(otherPost)

        assertTrue(postWithId("1").isLiked)
        assertEquals(4, postWithId("1").likeCount)
        verify(api).likePost("token123", "1")
    }

    @Test
    fun `toggleLike unlikes a post that is already liked`() = runTest {
        whenever(api.getPostsInFeed("token123", 0))
            .thenReturn(Response.success(listOf(otherPost.copy(isLiked = true))))
        viewModel.fetchFeed()
        whenever(api.unlikePost("token123", "1"))
            .thenReturn(Response.success(GenericResponse("Unliked", null)))

        actions.toggleLike(otherPost)

        assertFalse(postWithId("1").isLiked)
        assertEquals(2, postWithId("1").likeCount)
        verify(api).unlikePost("token123", "1")
    }

    @Test
    fun `toggleLike reverts the count when the request fails`() = runTest {
        loadFeed()
        whenever(api.likePost("token123", "1"))
            .thenReturn(Response.error(500, "{\"error\":\"Server error\"}".toResponseBody()))

        actions.toggleLike(otherPost)
        advanceUntilIdle()

        assertFalse(postWithId("1").isLiked)
        assertEquals(3, postWithId("1").likeCount)
        assertEquals("Server error", actions.alertMessage.value)
    }

    @Test
    fun `toggleLike is a no-op on your own post`() = runTest {
        loadFeed()

        actions.toggleLike(ownPost)
        advanceUntilIdle()

        // The backend rejects liking your own post, so no request is made and
        // the count can't drift.
        verify(api, never()).likePost(any(), eq("2"))
        assertEquals(7, postWithId("2").likeCount)
        assertFalse(postWithId("2").isLiked)
    }

    @Test
    fun `reportPost marks the post reported and keeps the reason`() = runTest {
        loadFeed()
        whenever(api.reportPost(eq("token123"), eq("1"), any()))
            .thenReturn(Response.success(GenericResponse("Reported", null)))

        actions.reportPost(otherPost, "spam")

        assertTrue(postWithId("1").isReported)
        assertEquals("spam", postWithId("1").reportReason)
        verify(api).reportPost("token123", "1", ReportRequest("spam"))
    }

    @Test
    fun `reportPost reverts when the request fails`() = runTest {
        loadFeed()
        whenever(api.reportPost(eq("token123"), eq("1"), any()))
            .thenReturn(Response.error(500, "{\"error\":\"Server error\"}".toResponseBody()))

        actions.reportPost(otherPost, "spam")
        advanceUntilIdle()

        assertFalse(postWithId("1").isReported)
        assertNull(postWithId("1").reportReason)
        assertNotNull(actions.alertMessage.value)
    }

    @Test
    fun `retractReport clears the reported state and the reason`() = runTest {
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(
            Response.success(listOf(otherPost.copy(isReported = true, reportReason = "spam")))
        )
        viewModel.fetchFeed()
        whenever(api.retractReportPost("token123", "1"))
            .thenReturn(Response.success(GenericResponse("Retracted", null)))

        actions.retractReport(otherPost)

        assertFalse(postWithId("1").isReported)
        assertNull(postWithId("1").reportReason)
        verify(api).retractReportPost("token123", "1")
    }

    @Test
    fun `retractReport restores the reason when the request fails`() = runTest {
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(
            Response.success(listOf(otherPost.copy(isReported = true, reportReason = "spam")))
        )
        viewModel.fetchFeed()
        whenever(api.retractReportPost("token123", "1"))
            .thenReturn(Response.error(500, "{\"error\":\"Server error\"}".toResponseBody()))

        actions.retractReport(otherPost)
        advanceUntilIdle()

        assertTrue(postWithId("1").isReported)
        assertEquals("spam", postWithId("1").reportReason)
    }

    @Test
    fun `deletePost drops the post from the list without reloading the feed`() = runTest {
        loadFeed()
        whenever(api.deletePost("token123", "2"))
            .thenReturn(Response.success(GenericResponse("Deleted", null)))

        actions.deletePost(ownPost)
        advanceUntilIdle()

        assertEquals(listOf("1"), viewModel.feedPosts.value.map { it.postIdentifier })
        // Reloading would reshuffle the weighted feed ordering under the user, so
        // only the original page-0 load happened.
        verify(api).getPostsInFeed("token123", 0)
    }

    @Test
    fun `deletePost failure leaves the post in place`() = runTest {
        loadFeed()
        whenever(api.deletePost("token123", "2"))
            .thenReturn(Response.error(500, "{\"error\":\"Server error\"}".toResponseBody()))

        actions.deletePost(ownPost)
        advanceUntilIdle()

        assertEquals(2, viewModel.feedPosts.value.size)
        assertEquals("Server error", actions.alertMessage.value)
    }

    @Test
    fun `a delete announced elsewhere removes the post from the list`() = runTest {
        loadFeed()

        // The post detail screen (a different ViewModel entirely) announces its
        // delete through PostEvents; every list drops it (issue #256).
        PostEvents.postDeleted("1")
        advanceUntilIdle()

        assertEquals(listOf("2"), viewModel.feedPosts.value.map { it.postIdentifier })
    }

    @Test
    fun `setPostForAction picks up the freshest report state`() = runTest {
        loadFeed()
        whenever(api.reportPost(eq("token123"), eq("1"), any()))
            .thenReturn(Response.success(GenericResponse("Reported", null)))

        actions.reportPost(otherPost, "spam")
        // The caller still holds the pre-report snapshot; the menu must not.
        actions.setPostForAction(otherPost)

        assertTrue(actions.postForAction.value!!.isReported)
        assertEquals("spam", actions.postForAction.value!!.reportReason)
    }
}
