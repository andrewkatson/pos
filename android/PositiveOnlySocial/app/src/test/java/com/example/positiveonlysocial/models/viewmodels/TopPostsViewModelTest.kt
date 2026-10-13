package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.TopPostPeriod
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
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
import org.mockito.kotlin.mock
import org.mockito.kotlin.stub
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

/** The Top posts scoreboard (issue #558). */
@OptIn(ExperimentalCoroutinesApi::class)
class TopPostsViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: TopPostsViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()

        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)

        viewModel = TopPostsViewModel(api, keychainHelper)
    }

    @Test
    fun `fetchTopPosts loads this week's board by default`() = runTest {
        val mockPosts = listOf(
            Post("1", "url1", "caption1", "user1", 5),
            Post("2", "url2", "caption2", "user2", 2)
        )
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.success(mockPosts))

        viewModel.fetchTopPosts()

        assertEquals(TopPostPeriod.WEEK, viewModel.selectedPeriod.value)
        assertEquals(mockPosts, viewModel.topPosts.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `selectPeriod reloads the board for the new period`() = runTest {
        val weekPosts = listOf(Post("1", "url1", "caption1", "user1", 5))
        val yearPosts = listOf(Post("9", "url9", "caption9", "user9", 50))
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.success(weekPosts))
        whenever(api.getTopPosts("token123", 0, "year")).thenReturn(Response.success(yearPosts))

        viewModel.fetchTopPosts()
        viewModel.selectPeriod(TopPostPeriod.YEAR)

        assertEquals(TopPostPeriod.YEAR, viewModel.selectedPeriod.value)
        assertEquals(yearPosts, viewModel.topPosts.value)
    }

    @Test
    fun `switching period mid-load reloads and drops the stale response`() = runTest {
        // Park the week load in flight, then switch to the yearly board.
        val weekPosts = listOf(Post("1", "url1", "caption1", "user1", 5))
        val yearPosts = listOf(Post("9", "url9", "caption9", "user9", 50))
        val gate = CompletableDeferred<Unit>()
        api.stub {
            onBlocking { getTopPosts("token123", 0, "week") } doSuspendableAnswer {
                gate.await()
                Response.success(weekPosts)
            }
        }
        whenever(api.getTopPosts("token123", 0, "year")).thenReturn(Response.success(yearPosts))

        viewModel.fetchTopPosts()
        viewModel.selectPeriod(TopPostPeriod.YEAR)
        gate.complete(Unit)
        advanceUntilIdle()

        assertEquals(yearPosts, viewModel.topPosts.value)
        assertFalse(viewModel.isLoadingNextPage.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun `switching period clears the old board and pages the new one`() = runTest {
        val weekPosts = listOf(Post("1", "url1", "caption1", "user1", 5))
        val yearPage0 = listOf(Post("9", "url9", "caption9", "user9", 50))
        val yearPage1 = listOf(Post("8", "url8", "caption8", "user8", 40))
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.success(weekPosts))
        val gate = CompletableDeferred<Unit>()
        api.stub {
            onBlocking { getTopPosts("token123", 0, "year") } doSuspendableAnswer {
                gate.await()
                Response.success(yearPage0)
            }
        }
        whenever(api.getTopPosts("token123", 1, "year")).thenReturn(Response.success(yearPage1))

        viewModel.fetchTopPosts()
        viewModel.selectPeriod(TopPostPeriod.YEAR)

        // While the yearly board loads, the weekly rows are gone rather than
        // sitting under the new chip.
        assertTrue(viewModel.topPosts.value.isEmpty())

        gate.complete(Unit)
        advanceUntilIdle()
        viewModel.fetchTopPosts()

        assertEquals(yearPage0 + yearPage1, viewModel.topPosts.value)
    }

    @Test
    fun `reselecting the current period does not refetch`() = runTest {
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.success(emptyList()))

        viewModel.selectPeriod(TopPostPeriod.WEEK)

        verify(api, times(0)).getTopPosts(any(), any(), any())
    }

    @Test
    fun `fetchTopPosts appends the next page and stops at an empty one`() = runTest {
        val page0 = listOf(Post("1", "url1", "caption1", "user1", 5))
        val page1 = listOf(Post("2", "url2", "caption2", "user2", 3))
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.success(page0))
        whenever(api.getTopPosts("token123", 1, "week")).thenReturn(Response.success(page1))
        whenever(api.getTopPosts("token123", 2, "week")).thenReturn(Response.success(emptyList()))

        viewModel.fetchTopPosts()
        viewModel.fetchTopPosts()
        viewModel.fetchTopPosts()
        viewModel.fetchTopPosts()

        assertEquals(page0 + page1, viewModel.topPosts.value)
        verify(api, times(3)).getTopPosts(any(), any(), any())
    }

    @Test
    fun `a post repeated across pages is only listed once`() = runTest {
        val a = Post("a", "urlA", "a", "userA", 9)
        val b = Post("b", "urlB", "b", "userB", 8)
        val c = Post("c", "urlC", "c", "userC", 7)
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.success(listOf(a, b)))
        whenever(api.getTopPosts("token123", 1, "week")).thenReturn(Response.success(listOf(b, c)))

        viewModel.fetchTopPosts()
        viewModel.fetchTopPosts()

        assertEquals(listOf(a, b, c), viewModel.topPosts.value)
    }

    @Test
    fun `a page of nothing but repeats does not stall pagination`() = runTest {
        val a = Post("a", "urlA", "a", "userA", 9)
        val b = Post("b", "urlB", "b", "userB", 8)
        val c = Post("c", "urlC", "c", "userC", 7)
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.success(listOf(a, b)))
        whenever(api.getTopPosts("token123", 1, "week")).thenReturn(Response.success(listOf(a, b)))
        whenever(api.getTopPosts("token123", 2, "week")).thenReturn(Response.success(listOf(c)))

        viewModel.fetchTopPosts()
        // One fetch reaches page 2 instead of stopping on the repeat-only page 1,
        // which would leave the list (and so the pagination trigger) unchanged.
        viewModel.fetchTopPosts()

        assertEquals(listOf(a, b, c), viewModel.topPosts.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `fetchTopPosts failure surfaces a load error`() = runTest {
        whenever(api.getTopPosts("token123", 0, "week")).thenReturn(Response.error(500, "error".toResponseBody()))

        viewModel.fetchTopPosts()

        assertTrue(viewModel.topPosts.value.isEmpty())
        assertNotNull(viewModel.loadError.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }
}
