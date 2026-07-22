package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.PostStatusResponse
import com.example.positiveonlysocial.data.model.ProfileDetailsResponse
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.doSuspendableAnswer
import org.mockito.kotlin.eq
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.stub
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class ProfileViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: ProfileViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        
        viewModel = ProfileViewModel(api, keychainHelper)
    }

    @Test
    fun `fetchProfile success updates profileDetails and userPosts`() = runTest {
        val mockProfile = ProfileDetailsResponse("user1", 1, 1, 2, true)
        val mockPosts = listOf(Post("1", "url", "caption", "user1", 1))
        
        whenever(api.getProfileDetails("token123", "user1")).thenReturn(Response.success(mockProfile))
        whenever(api.getPostsForUser("token123", "user1", 0)).thenReturn(Response.success(mockPosts))

        viewModel.fetchProfile("user1")

        assertEquals(mockProfile, viewModel.profileDetails.value)
        assertEquals(mockPosts, viewModel.userPosts.value)
        assertFalse(viewModel.isLoading.value)
    }

    @Test
    fun `toggleFollow calls api and updates state optimistically`() = runTest {
        val mockProfile = ProfileDetailsResponse("user1", 1, 10, 3, false)
        whenever(api.getProfileDetails("token123", "user1")).thenReturn(Response.success(mockProfile))
        whenever(api.getPostsForUser("token123", "user1", 0)).thenReturn(Response.success(emptyList()))
        
        viewModel.fetchProfile("user1")
        
        whenever(api.followUser("token123", "user1")).thenReturn(Response.success(GenericResponse("Success", "None")))

        viewModel.toggleFollow("user1")

        // Verify optimistic update
        assertTrue(viewModel.profileDetails.value!!.isFollowing)
        assertEquals(11, viewModel.profileDetails.value!!.followerCount)
        
        verify(api).followUser("token123", "user1")
    }

    @Test
    fun testToggleBlock() = runTest {
        // Arrange
        val userId = "testUser"
        var mockProfileDetailsResponse = ProfileDetailsResponse(userId, 1, 10, 3, false, isBlocked = false)
        
        whenever(api.toggleBlock(any(), any())).thenReturn(Response.success(GenericResponse("Success", "None")))
        
        // Initially not blocked, but following
        mockProfileDetailsResponse = mockProfileDetailsResponse.copy(isBlocked = false, isFollowing = true)
        whenever(api.getProfileDetails(any(), eq(userId))).thenReturn(Response.success(mockProfileDetailsResponse))
        whenever(api.getPostsForUser(any(), eq(userId), any())).thenReturn(Response.success(emptyList()))

        viewModel.fetchProfile(userId)

        assertFalse(viewModel.isBlocked.value)
        assertTrue(viewModel.isFollowing.value)

        // Act - Block
        viewModel.toggleBlock(userId)

        // Assert - Blocked & Unfollowed (optimistically)
        verify(api).toggleBlock(eq("token123"), eq(userId))
        assertTrue(viewModel.isBlocked.value)
        assertFalse(viewModel.isFollowing.value)
        
        // Simulate API response for unblocking
        whenever(api.toggleBlock(any(), any())).thenReturn(Response.success(GenericResponse("Success", "None")))
        
        // Act - Unblock
        viewModel.toggleBlock(userId)
        
        // Assert - Unblocked (optimistically)
        assertFalse(viewModel.isBlocked.value)
    }

    @Test
    fun `follow then block then follow does not double-count followers`() = runTest {
        val userId = "user1"
        val mockProfile = ProfileDetailsResponse(userId, 1, 0, 3, isFollowing = false, isBlocked = false)
        whenever(api.getProfileDetails("token123", userId)).thenReturn(Response.success(mockProfile))
        whenever(api.getPostsForUser("token123", userId, 0)).thenReturn(Response.success(emptyList()))
        whenever(api.followUser("token123", userId)).thenReturn(Response.success(GenericResponse("Success", "None")))
        whenever(api.toggleBlock(any(), any())).thenReturn(Response.success(GenericResponse("Success", "None")))

        viewModel.fetchProfile(userId)

        // Follow -> count goes from 0 to 1
        viewModel.toggleFollow(userId)
        assertEquals(1, viewModel.profileDetails.value!!.followerCount)
        assertTrue(viewModel.isFollowing.value)

        // Block -> backend unfollows, so the count must drop back to 0
        viewModel.toggleBlock(userId)
        assertEquals(0, viewModel.profileDetails.value!!.followerCount)
        assertFalse(viewModel.isFollowing.value)

        // Unblock then follow again -> count is 1, not 2
        viewModel.toggleBlock(userId)
        viewModel.toggleFollow(userId)
        assertEquals(1, viewModel.profileDetails.value!!.followerCount)
        assertTrue(viewModel.isFollowing.value)
    }

    @Test
    fun `fetchUserPosts is a no-op while a refresh is in progress`() = runTest {
        val mockProfile = ProfileDetailsResponse("user1", 1, 1, 2, true)
        val page0 = listOf(Post("1", "url", "caption", "user1", 1))

        // Park the refresh inside its first API call so _isRefreshing stays true
        // while we attempt to paginate.
        val gate = CompletableDeferred<Unit>()
        api.stub {
            onBlocking { getProfileDetails("token123", "user1") } doSuspendableAnswer {
                gate.await()
                Response.success(mockProfile)
            }
        }
        whenever(api.getPostsForUser("token123", "user1", 0)).thenReturn(Response.success(page0))

        // Start a refresh (suspends at the gate), then try to paginate concurrently.
        viewModel.refreshProfile("user1")
        viewModel.fetchUserPosts("user1")

        // Let the refresh complete.
        gate.complete(Unit)
        advanceUntilIdle()

        // Pagination must have short-circuited: only the refresh's page-0 load
        // ran, and no page-1 fetch raced it.
        verify(api, times(1)).getPostsForUser("token123", "user1", 0)
        verify(api, never()).getPostsForUser("token123", "user1", 1)
        assertEquals(page0, viewModel.userPosts.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun `refreshProfile surfaces an error when profile details fail to load`() = runTest {
        // Profile details fail, posts succeed. The failure must be surfaced
        // rather than silently leaving follow/block state stale.
        whenever(api.getProfileDetails("token123", "user1"))
            .thenReturn(Response.error(500, "error".toResponseBody()))
        whenever(api.getPostsForUser("token123", "user1", 0))
            .thenReturn(Response.success(emptyList()))

        viewModel.refreshProfile("user1")

        assertNotNull(viewModel.errorMessage.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun testFetchProfileWithBlockedStatus() = runTest {
        // Arrange
        val userId = "testUser"
        val mockProfileDetailsResponse = ProfileDetailsResponse(userId, 1, 10, 3, false, isBlocked = true)
        
        whenever(api.getProfileDetails(any(), eq(userId))).thenReturn(Response.success(mockProfileDetailsResponse))
        whenever(api.getPostsForUser(any(), eq(userId), any())).thenReturn(Response.success(emptyList()))

        // Act
        viewModel.fetchProfile(userId)

        // Assert
        assertTrue(viewModel.isBlocked.value)
    }

    // --- Async classification reconciliation (#282) ---
    //
    // The bounded status poll lives in this view model rather than
    // HomeViewModel because the Profile tab's grid is this view model's
    // (issue #347). Only your own posts ever carry a status.

    private fun stubOwnProfile(posts: List<Post>) {
        whenever(api.getProfileDetails("token123", "testuser"))
            .thenReturn(Response.success(ProfileDetailsResponse("testuser", posts.size, 0, 0, false)))
        whenever(api.getPostsForUser("token123", "testuser", 0))
            .thenReturn(Response.success(posts))
    }

    @Test
    fun `pending post polls status and reloads grid when approved`() = runTest {
        val pendingPost = Post("1", null, "caption", "testuser", status = "pending", hidden = true, hiddenReason = "pending_classification")
        stubOwnProfile(listOf(pendingPost))
        viewModel.fetchUserPosts("testuser")
        advanceUntilIdle()
        assertEquals("pending", viewModel.userPosts.value.first().status)

        // The worker approves it; the bounded poll notices and reloads.
        whenever(api.getPostStatus("token123", "1"))
            .thenReturn(Response.success(PostStatusResponse("1", "approved")))
        val approvedPost = Post("1", null, "caption", "testuser", status = "approved", hidden = false, hiddenReason = "")
        stubOwnProfile(listOf(approvedPost))

        advanceTimeBy(3100)
        advanceUntilIdle()

        assertEquals("approved", viewModel.userPosts.value.first().status)
        assertEquals(null, viewModel.reviewNotice.value)
    }

    @Test
    fun `pending post that resolves to rejected surfaces a review notice`() = runTest {
        val pendingPost = Post("1", null, "caption", "testuser", status = "pending", hidden = true, hiddenReason = "pending_classification")
        stubOwnProfile(listOf(pendingPost))
        viewModel.fetchUserPosts("testuser")
        advanceUntilIdle()

        whenever(api.getPostStatus("token123", "1")).thenReturn(
            Response.success(
                PostStatusResponse(
                    postIdentifier = "1",
                    status = "rejected",
                    reasonCode = "guidelines",
                    appealable = true,
                    hidden = true,
                    hiddenReason = "classifier",
                    message = "Your post did not pass automated review. It is hidden for now but you can appeal the decision."
                )
            )
        )
        val rejectedPost = Post("1", null, "caption", "testuser", status = "rejected", hidden = true, hiddenReason = "classifier", appealable = true)
        stubOwnProfile(listOf(rejectedPost))

        advanceTimeBy(3100)
        advanceUntilIdle()

        assertTrue(viewModel.reviewNotice.value!!.contains("appeal"))
        assertEquals("rejected", viewModel.userPosts.value.first().status)

        viewModel.dismissReviewNotice()
        assertEquals(null, viewModel.reviewNotice.value)
    }

    @Test
    fun `no status poll when no post is pending`() = runTest {
        stubOwnProfile(listOf(Post("1", "url1", "caption1", "testuser", status = "approved")))
        viewModel.fetchUserPosts("testuser")
        advanceUntilIdle()

        advanceTimeBy(60_000)
        advanceUntilIdle()

        verify(api, never()).getPostStatus(any(), any())
    }
}
