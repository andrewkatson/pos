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

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

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

    @Test
    fun `refreshFeed replaces feedPosts with fresh data`() = runTest {
        val initialPosts = listOf(Post("1", "url1", "caption1", "user1", 0))
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(initialPosts))

        viewModel.fetchFeed()
        assertEquals(initialPosts, viewModel.feedPosts.value)

        val refreshedPosts = listOf(
            Post("2", "url2", "caption2", "user2", 0),
            Post("3", "url3", "caption3", "user3", 0)
        )
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(refreshedPosts))

        viewModel.refreshFeed()

        assertEquals(refreshedPosts, viewModel.feedPosts.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun `refreshFeed resets pagination after it was exhausted`() = runTest {
        // Exhaust pagination so canLoadMore becomes false.
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(emptyList()))
        viewModel.fetchFeed()
        assertTrue(viewModel.feedPosts.value.isEmpty())

        // Backend now has posts again; refresh should pull them in.
        val refreshedPosts = listOf(Post("1", "url1", "caption1", "user1", 0))
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(refreshedPosts))
        viewModel.refreshFeed()
        assertEquals(refreshedPosts, viewModel.feedPosts.value)

        // And the next page can be fetched again (page 1).
        val nextPage = listOf(Post("2", "url2", "caption2", "user2", 0))
        whenever(api.getPostsInFeed("token123", 1)).thenReturn(Response.success(nextPage))
        viewModel.fetchFeed()
        assertEquals(refreshedPosts + nextPage, viewModel.feedPosts.value)
    }

    @Test
    fun `refreshFeed failure keeps existing posts`() = runTest {
        val initialPosts = listOf(Post("1", "url1", "caption1", "user1", 0))
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(initialPosts))
        viewModel.fetchFeed()

        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.error(400, "error".toResponseBody()))
        viewModel.refreshFeed()

        assertEquals(initialPosts, viewModel.feedPosts.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    // ---- The "you finished!" banner (issue #528) ----

    @Test
    fun `reachedEnd turns on once a page comes back empty`() = runTest {
        val page0 = listOf(Post("1", "url1", "caption1", "user1", 0))
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(page0))
        whenever(api.getPostsInFeed("token123", 1)).thenReturn(Response.success(emptyList()))

        viewModel.fetchFeed()
        // More may exist until a page comes back empty.
        assertFalse(viewModel.reachedEnd.value)

        viewModel.fetchFeed()
        assertTrue(viewModel.reachedEnd.value)
        assertEquals(page0, viewModel.feedPosts.value)
    }

    @Test
    fun `a failed page does not mark the feed finished`() = runTest {
        val page0 = listOf(Post("1", "url1", "caption1", "user1", 0))
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(page0))
        whenever(api.getPostsInFeed("token123", 1)).thenReturn(Response.error(500, "error".toResponseBody()))

        viewModel.fetchFeed()
        viewModel.fetchFeed()

        assertFalse(viewModel.reachedEnd.value)
    }

    @Test
    fun `refreshing a finished feed clears reachedEnd`() = runTest {
        val page0 = listOf(Post("1", "url1", "caption1", "user1", 0))
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(page0))
        whenever(api.getPostsInFeed("token123", 1)).thenReturn(Response.success(emptyList()))
        viewModel.fetchFeed()
        viewModel.fetchFeed()
        assertTrue(viewModel.reachedEnd.value)

        viewModel.refreshFeed()

        assertFalse(viewModel.reachedEnd.value)
    }
}
