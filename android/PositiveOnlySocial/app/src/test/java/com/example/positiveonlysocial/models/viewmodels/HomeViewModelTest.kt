package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
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
class HomeViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: HomeViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        
        viewModel = HomeViewModel(api, keychainHelper)
    }

    @Test
    fun `fetchMyPosts success updates userPosts`() = runTest {
        val mockPosts = listOf(
            Post("1", "url1", "caption1", "testuser", 1)
        )
        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.success(mockPosts))

        viewModel.fetchMyPosts()

        assertEquals(mockPosts, viewModel.userPosts.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `fetchMyPosts failure updates errorMessage`() = runTest {
        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.error(400, "error".toResponseBody()))

        viewModel.fetchMyPosts()

        assertTrue(viewModel.userPosts.value.isEmpty())
        assertEquals("error", viewModel.errorMessage.value)
    }

    @Test
    fun `refreshMyPosts replaces userPosts with fresh data`() = runTest {
        val initialPosts = listOf(Post("1", "url1", "caption1", "testuser", 1))
        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.success(initialPosts))

        viewModel.fetchMyPosts()
        assertEquals(initialPosts, viewModel.userPosts.value)

        val refreshedPosts = listOf(
            Post("2", "url2", "caption2", "testuser", 1),
            Post("3", "url3", "caption3", "testuser", 1)
        )
        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.success(refreshedPosts))

        viewModel.refreshMyPosts()

        assertEquals(refreshedPosts, viewModel.userPosts.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun `refreshMyPosts resets pagination after it was exhausted`() = runTest {
        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.success(emptyList()))
        viewModel.fetchMyPosts()
        assertTrue(viewModel.userPosts.value.isEmpty())

        val refreshedPosts = listOf(Post("1", "url1", "caption1", "testuser", 1))
        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.success(refreshedPosts))
        viewModel.refreshMyPosts()
        assertEquals(refreshedPosts, viewModel.userPosts.value)

        val nextPage = listOf(Post("2", "url2", "caption2", "testuser", 1))
        whenever(api.getPostsForUser("token123", "testuser", 1)).thenReturn(Response.success(nextPage))
        viewModel.fetchMyPosts()
        assertEquals(refreshedPosts + nextPage, viewModel.userPosts.value)
    }

    @Test
    fun `refreshMyPosts failure keeps existing posts and sets errorMessage`() = runTest {
        val initialPosts = listOf(Post("1", "url1", "caption1", "testuser", 1))
        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.success(initialPosts))
        viewModel.fetchMyPosts()

        whenever(api.getPostsForUser("token123", "testuser", 0)).thenReturn(Response.error(400, "error".toResponseBody()))
        viewModel.refreshMyPosts()

        assertEquals(initialPosts, viewModel.userPosts.value)
        assertEquals("error", viewModel.errorMessage.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun `performSearch with valid query updates searchedUsers`() = runTest {
        val mockUsers = listOf(User("user1", true))
        whenever(api.searchUsers("token123", "query")).thenReturn(Response.success(mockUsers))

        viewModel.updateSearchText("query")
        
        // Advance time to trigger debounce
        advanceTimeBy(600)

        assertEquals(mockUsers, viewModel.searchedUsers.value)
    }

    @Test
    fun `performSearch with short query clears searchedUsers`() = runTest {
        viewModel.updateSearchText("qu")
        
        advanceTimeBy(600)

        assertTrue(viewModel.searchedUsers.value.isEmpty())
        // Should not call API
        verify(api, org.mockito.kotlin.never()).searchUsers(any(), any())
    }
}
