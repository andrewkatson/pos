package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
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
class FeedViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: FeedViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        
        viewModel = FeedViewModel(api, keychainHelper)
    }

    @Test
    fun `fetchFeed success updates feedPosts`() = runTest {
        val mockPosts = listOf(
            Post("1", "url1", "caption1", "user1", 0),
            Post("2", "url2", "caption2", "user2", 2)
        )
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(mockPosts))

        viewModel.fetchFeed()

        assertEquals(mockPosts, viewModel.feedPosts.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `fetchFeed failure does not update feedPosts`() = runTest {
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.error(400, "error".toResponseBody()))

        viewModel.fetchFeed()

        assertTrue(viewModel.feedPosts.value.isEmpty())
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `fetchFeed empty list stops pagination`() = runTest {
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(emptyList()))

        viewModel.fetchFeed()

        assertTrue(viewModel.feedPosts.value.isEmpty())
        
        // Try fetching again, should not call API because canLoadMore is false
        viewModel.fetchFeed()
        verify(api).getPostsInFeed("token123", 0) // Verified called once
    }
}
