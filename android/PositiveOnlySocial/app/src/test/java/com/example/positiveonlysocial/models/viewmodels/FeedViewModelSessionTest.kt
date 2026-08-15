package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response
import java.security.GeneralSecurityException

/**
 * The feed's reasons for being empty (issue #503).
 *
 * A feed with no readable session used to log a line and render an empty list,
 * which on screen is indistinguishable from a feed that loaded fine and had
 * nothing in it. These pin the distinction to [FeedViewModel.loadError] and to
 * [FollowingFeedViewModel.loadError], which is what the screens now show.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class FeedViewModelSessionTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val session = UserSession("token123", "testuser", "1", false, null, null)

    private fun keychainReturning(value: UserSession?): KeychainHelperProtocol = mock {
        whenever(it.load(any<Class<UserSession>>(), any(), any())).thenReturn(value)
    }

    private fun keychainThrowing(): KeychainHelperProtocol = mock {
        whenever(it.load(any<Class<UserSession>>(), any(), any()))
            .thenThrow(GeneralSecurityException("secure storage is unreadable"))
    }

    // --- For You feed ---

    @Test
    fun `fetchFeed with no stored session explains itself and skips the request`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        val viewModel = FeedViewModel(api, keychainReturning(null))

        viewModel.fetchFeed()

        assertEquals(Constants.SESSION_MISSING_MESSAGE, viewModel.loadError.value)
        assertTrue(viewModel.feedPosts.value.isEmpty())
        verify(api, never()).getPostsInFeed(any(), any())
    }

    @Test
    fun `fetchFeed when secure storage is unreadable explains itself`() = runTest {
        // The tablet case from issue #503: the keychain read doesn't return null,
        // it throws. That used to escape as a generic failure (or nothing at all).
        val api: PositiveOnlySocialAPI = mock()
        val viewModel = FeedViewModel(api, keychainThrowing())

        viewModel.fetchFeed()

        assertEquals(Constants.SESSION_MISSING_MESSAGE, viewModel.loadError.value)
        verify(api, never()).getPostsInFeed(any(), any())
    }

    @Test
    fun `fetchFeed reports a backend failure`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        whenever(api.getPostsInFeed("token123", 0))
            .thenReturn(Response.error(500, "boom".toResponseBody()))
        val viewModel = FeedViewModel(api, keychainReturning(session))

        viewModel.fetchFeed()

        assertNotNull(viewModel.loadError.value)
    }

    @Test
    fun `a successful fetch clears a previous error`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        whenever(api.getPostsInFeed("token123", 0))
            .thenReturn(Response.error(500, "boom".toResponseBody()))
        val viewModel = FeedViewModel(api, keychainReturning(session))

        viewModel.fetchFeed()
        assertNotNull(viewModel.loadError.value)

        val posts = listOf(Post("1", "url1", "caption1", "user1", 0))
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(posts))
        viewModel.refreshFeed()

        assertNull(viewModel.loadError.value)
        assertEquals(posts, viewModel.feedPosts.value)
    }

    @Test
    fun `an empty but successful feed is not an error`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        whenever(api.getPostsInFeed("token123", 0)).thenReturn(Response.success(emptyList()))
        val viewModel = FeedViewModel(api, keychainReturning(session))

        viewModel.fetchFeed()

        assertTrue(viewModel.feedPosts.value.isEmpty())
        assertNull(viewModel.loadError.value)
    }

    // --- Following feed ---

    @Test
    fun `fetchFollowingFeed with no stored session explains itself`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        val viewModel = FollowingFeedViewModel(api, keychainReturning(null))

        viewModel.fetchFollowingFeed()

        assertEquals(Constants.SESSION_MISSING_MESSAGE, viewModel.loadError.value)
        verify(api, never()).getFollowedPosts(any(), any(), any())
    }

    @Test
    fun `fetchFollowingFeed when secure storage is unreadable explains itself`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        val viewModel = FollowingFeedViewModel(api, keychainThrowing())

        viewModel.fetchFollowingFeed()

        assertEquals(Constants.SESSION_MISSING_MESSAGE, viewModel.loadError.value)
        verify(api, never()).getFollowedPosts(any(), any(), any())
    }

    @Test
    fun `a successful following fetch clears a previous error`() = runTest {
        val api: PositiveOnlySocialAPI = mock()
        whenever(api.getFollowedPosts("token123", 0, null))
            .thenReturn(Response.error(500, "boom".toResponseBody()))
        val viewModel = FollowingFeedViewModel(api, keychainReturning(session))

        viewModel.fetchFollowingFeed()
        assertNotNull(viewModel.loadError.value)

        val posts = listOf(Post("3", "url3", "caption3", "user3", 0))
        whenever(api.getFollowedPosts("token123", 0, null)).thenReturn(Response.success(posts))
        viewModel.refreshFollowingFeed()

        assertNull(viewModel.loadError.value)
        assertEquals(posts, viewModel.followingPosts.value)
    }
}
