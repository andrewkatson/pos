package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.ProfileDetailsResponse
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
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

    private val mockUserSession = UserSession("token123", "testuser", false, null, null)

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
}
```
