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
import org.mockito.kotlin.whenever
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class FollowingFeedViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: FollowingFeedViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        
        viewModel = FollowingFeedViewModel(api, keychainHelper)
    }

    @Test
    fun `fetchFollowingFeed success updates followingPosts`() = runTest {
        val mockPosts = listOf(
            Post("1", "url1", "caption1", "user1", 0),
            Post("2", "url2", "caption2", "user2", 2)
        )
        whenever(api.getFollowedPosts("token123", 0)).thenReturn(Response.success(mockPosts))

        viewModel.fetchFollowingFeed()

        assertEquals(mockPosts, viewModel.followingPosts.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `fetchFollowingFeed failure does not update followingPosts`() = runTest {
        whenever(api.getFollowedPosts("token123", 0)).thenReturn(Response.error(400, "error".toResponseBody()))

        viewModel.fetchFollowingFeed()

        assertTrue(viewModel.followingPosts.value.isEmpty())
        assertFalse(viewModel.isLoadingNextPage.value)
    }
}
