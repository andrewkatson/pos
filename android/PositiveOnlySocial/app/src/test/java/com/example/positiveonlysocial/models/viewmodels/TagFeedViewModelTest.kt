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
class TagFeedViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: TagFeedViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        viewModel = TagFeedViewModel(api, keychainHelper, "sunset")
    }

    @Test
    fun `fetchNextPage success updates posts`() = runTest {
        val mockPosts = listOf(
            Post("1", "url1", "a #sunset", "user1", 0, tags = listOf("sunset")),
            Post("2", "url2", "another #sunset", "user2", 0, tags = listOf("sunset"))
        )
        whenever(api.getPostsByTag("token123", "sunset", 0)).thenReturn(Response.success(mockPosts))

        viewModel.fetchNextPage()

        assertEquals(mockPosts, viewModel.posts.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `fetchNextPage empty list stops pagination`() = runTest {
        whenever(api.getPostsByTag("token123", "sunset", 0)).thenReturn(Response.success(emptyList()))

        viewModel.fetchNextPage()
        assertTrue(viewModel.posts.value.isEmpty())

        // A second fetch must not hit the API again, because canLoadMore is false.
        viewModel.fetchNextPage()
        verify(api).getPostsByTag("token123", "sunset", 0)
    }

    @Test
    fun `fetchNextPage failure keeps posts empty`() = runTest {
        whenever(api.getPostsByTag("token123", "sunset", 0))
            .thenReturn(Response.error(400, "error".toResponseBody()))

        viewModel.fetchNextPage()

        assertTrue(viewModel.posts.value.isEmpty())
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `refresh replaces posts with fresh data`() = runTest {
        val initial = listOf(Post("1", "url1", "a #sunset", "user1", 0, tags = listOf("sunset")))
        whenever(api.getPostsByTag("token123", "sunset", 0)).thenReturn(Response.success(initial))
        viewModel.fetchNextPage()
        assertEquals(initial, viewModel.posts.value)

        val refreshed = listOf(
            Post("2", "url2", "b #sunset", "user2", 0, tags = listOf("sunset")),
            Post("3", "url3", "c #sunset", "user3", 0, tags = listOf("sunset"))
        )
        whenever(api.getPostsByTag("token123", "sunset", 0)).thenReturn(Response.success(refreshed))
        viewModel.refresh()

        assertEquals(refreshed, viewModel.posts.value)
        assertFalse(viewModel.isRefreshing.value)
    }
}
