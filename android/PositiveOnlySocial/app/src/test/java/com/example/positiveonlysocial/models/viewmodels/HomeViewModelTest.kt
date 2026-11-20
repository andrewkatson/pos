package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.doSuspendableAnswer
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.times
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
    fun `currentUsername comes from the stored session`() = runTest {
        // The first bottom-nav destination shows the signed-in user's own
        // profile (issue #347), so it has to know who that is.
        assertEquals("testuser", viewModel.currentUsername.value)
    }

    @Test
    fun `currentUsername is null when there is no stored session`() = runTest {
        val emptyKeychain = mock<KeychainHelperProtocol>()
        whenever(emptyKeychain.load(any<Class<UserSession>>(), any(), any())).thenReturn(null)

        val signedOut = HomeViewModel(api, emptyKeychain)

        assertNull(signedOut.currentUsername.value)
    }

    @Test
    fun `performSearch with valid query updates searchedUsers`() = runTest {
        val mockUsers = listOf(User("user1", true))
        whenever(api.searchUsers("token123", "query", 0)).thenReturn(Response.success(mockUsers))

        viewModel.updateSearchText("query")

        // Advance time to trigger debounce
        advanceTimeBy(600)

        assertEquals(mockUsers, viewModel.searchedUsers.value)
    }

    @Test
    fun `performSearch with no matches finishes with empty results`() = runTest {
        whenever(
            api.searchUsers("token123", "missing", 0)
        ).thenReturn(Response.success(emptyList()))

        viewModel.updateSearchText("missing")

        assertTrue(viewModel.isSearching.value)

        advanceTimeBy(600)

        assertTrue(viewModel.searchedUsers.value.isEmpty())
        assertEquals(false, viewModel.isSearching.value)

        verify(api).searchUsers("token123", "missing", 0)
    }

    @Test
    fun `performSearch with short query clears searchedUsers`() = runTest {
        viewModel.updateSearchText("qu")

        advanceTimeBy(600)

        assertTrue(viewModel.searchedUsers.value.isEmpty())
        // Should not call API
        verify(api, org.mockito.kotlin.never()).searchUsers(any(), any(), any())
    }

    @Test
    fun `performSearch with fewer than 10 results has no more results`() = runTest {
        val mockUsers = List(5) { index ->
            User("user$index", true)
        }

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(mockUsers))

        viewModel.updateSearchText("query")

        advanceTimeBy(600)

        assertEquals(mockUsers, viewModel.searchedUsers.value)
        assertEquals(false, viewModel.hasMoreResults.value)

        verify(api).searchUsers("token123", "query", 0)
    }

    @Test
    fun `performSearch with full first batch and nonempty second batch has more results`() = runTest {
        val firstBatch = List(10) { index ->
            User("user$index", true)
        }

        val secondBatch = listOf(
            User("user10", true)
        )

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(firstBatch))

        whenever(
            api.searchUsers("token123", "query", 1)
        ).thenReturn(Response.success(secondBatch))

        viewModel.updateSearchText("query")

        advanceTimeBy(600)

        assertEquals(firstBatch, viewModel.searchedUsers.value)
        assertTrue(viewModel.hasMoreResults.value)

        verify(api).searchUsers("token123", "query", 0)
        verify(api).searchUsers("token123", "query", 1)
    }

    @Test
    fun `performSearch with full first batch and empty second batch has no more results`() = runTest {
        val firstBatch = List(10) { index ->
            User("user$index", true)
        }

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(firstBatch))

        whenever(
            api.searchUsers("token123", "query", 1)
        ).thenReturn(Response.success(emptyList()))

        viewModel.updateSearchText("query")

        advanceTimeBy(600)

        assertEquals(firstBatch, viewModel.searchedUsers.value)
        assertEquals(false, viewModel.hasMoreResults.value)

        verify(api).searchUsers("token123", "query", 1)
    }

    @Test
    fun `performSearch retains pagination when second batch repeats first batch`() = runTest {
        val firstBatch = List(10) { index ->
            User("user$index", true)
        }

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(firstBatch))

        // Simulates an older backend that ignores the batch parameter.
        whenever(
            api.searchUsers("token123", "query", 1)
        ).thenReturn(Response.success(firstBatch))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)

        assertEquals(firstBatch, viewModel.searchedUsers.value)
        assertEquals(true, viewModel.hasMoreResults.value)

        verify(api).searchUsers("token123", "query", 0)
        verify(api).searchUsers("token123", "query", 1)
    }

    @Test
    fun `performSearch keeps first batch when second batch check fails`() = runTest {
        val firstBatch = List(10) { index ->
            User("user$index", true)
        }

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(firstBatch))

        whenever(
            api.searchUsers("token123", "query", 1)
        ).thenThrow(RuntimeException("Network error"))

        viewModel.updateSearchText("query")

        advanceTimeBy(600)

        assertEquals(firstBatch, viewModel.searchedUsers.value)
        assertEquals(true, viewModel.hasMoreResults.value)

        verify(api).searchUsers("token123", "query", 0)
        verify(api).searchUsers("token123", "query", 1)
    }

    @Test
    fun `cancelled search does not show an error`() = runTest {
        whenever(api.searchUsers("token123", "old", 0))
            .thenThrow(CancellationException("old request"))

        viewModel.updateSearchText("old")
        advanceTimeBy(600)
        advanceUntilIdle()

        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `changing query cancels old prefetch without changing new results`() = runTest {
        val oldFirst = List(10) { User("old$it", true) }
        val pendingPrefetch = CompletableDeferred<Response<List<User>>>()
        val newResults = listOf(User("newUser", true))
        whenever(api.searchUsers("token123", "old", 0)).thenReturn(Response.success(oldFirst))
        whenever(api.searchUsers("token123", "old", 1))
            .doSuspendableAnswer { pendingPrefetch.await() }
        whenever(api.searchUsers("token123", "new", 0)).thenReturn(Response.success(newResults))

        viewModel.updateSearchText("old")
        advanceTimeBy(600)
        viewModel.updateSearchText("new")
        advanceTimeBy(600)
        advanceUntilIdle()

        assertEquals(newResults, viewModel.searchedUsers.value)
        assertNull(viewModel.errorMessage.value)
        assertEquals(false, viewModel.hasMoreResults.value)
    }

    @Test
    fun `first batch shows while the additional-results check is pending`() = runTest {
        val first = List(10) { User("user$it", true) }
        val pendingPrefetch = CompletableDeferred<Response<List<User>>>()
        whenever(api.searchUsers("token123", "query", 0)).thenReturn(Response.success(first))
        whenever(api.searchUsers("token123", "query", 1))
            .doSuspendableAnswer { pendingPrefetch.await() }

        viewModel.updateSearchText("query")
        advanceTimeBy(600)

        // HomeScreen hides results while isSearching, so it must already be off.
        assertEquals(first, viewModel.searchedUsers.value)
        assertEquals(false, viewModel.isSearching.value)
        assertEquals(false, viewModel.hasMoreResults.value)

        pendingPrefetch.complete(Response.success(listOf(User("user10", true))))
        advanceUntilIdle()

        assertTrue(viewModel.hasMoreResults.value)
    }

    @Test
    fun `trailing space keeps the in-flight search and its loading state`() = runTest {
        val pendingFirst = CompletableDeferred<Response<List<User>>>()
        val results = listOf(User("user1", true))
        whenever(api.searchUsers("token123", "query", 0))
            .doSuspendableAnswer { pendingFirst.await() }

        viewModel.updateSearchText("query")
        advanceTimeBy(600)
        viewModel.updateSearchText("query ")
        advanceTimeBy(600)

        assertTrue(viewModel.isSearching.value)

        pendingFirst.complete(Response.success(results))
        advanceUntilIdle()

        assertEquals(results, viewModel.searchedUsers.value)
        assertEquals(false, viewModel.isSearching.value)
        verify(api, times(1)).searchUsers("token123", "query", 0)
    }

    @Test
    fun `superseded search cannot clear the new query's loading state`() = runTest {
        val pendingOld = CompletableDeferred<Response<List<User>>>()
        val newResults = listOf(User("newUser", true))
        whenever(api.searchUsers("token123", "old", 0))
            .doSuspendableAnswer { pendingOld.await() }
        whenever(api.searchUsers("token123", "new", 0)).thenReturn(Response.success(newResults))

        viewModel.updateSearchText("old")
        advanceTimeBy(600)
        viewModel.updateSearchText("new")
        // The old request finishes while the new query is still debouncing.
        pendingOld.complete(Response.success(listOf(User("oldUser", true))))
        advanceTimeBy(100)

        assertTrue(viewModel.isSearching.value)
        assertTrue(viewModel.searchedUsers.value.isEmpty())

        advanceTimeBy(600)
        advanceUntilIdle()

        assertEquals(newResults, viewModel.searchedUsers.value)
        assertEquals(false, viewModel.isSearching.value)
    }

    @Test
    fun `old pagination failure cannot show an error for new query`() = runTest {
        val first = List(10) { User("old$it", true) }
        val pendingPage = CompletableDeferred<Response<List<User>>>()
        whenever(api.searchUsers("token123", "old", 0)).thenReturn(Response.success(first))
        whenever(api.searchUsers("token123", "old", 1))
            .thenReturn(Response.success(List(10) { User("old${it + 10}", true) }))
        whenever(api.searchUsers("token123", "old", 2))
            .doSuspendableAnswer { pendingPage.await() }
        whenever(api.searchUsers("token123", "new", 0))
            .thenReturn(Response.success(listOf(User("newUser", true))))

        viewModel.updateSearchText("old")
        advanceTimeBy(600)
        viewModel.loadAllSearchResults()
        viewModel.loadMoreSearchResults()
        advanceTimeBy(1)
        viewModel.updateSearchText("new")
        pendingPage.completeExceptionally(RuntimeException("old failure"))
        advanceUntilIdle()

        assertNull(viewModel.errorMessage.value)
        assertTrue(viewModel.allSearchResults.value.isEmpty())
        assertEquals(false, viewModel.isLoadingAllResults.value)
    }

    @Test
    fun `opening all results shows prefetched batches without another request`() = runTest {
        val first = List(10) { User("user$it", true) }
        val second = List(10) { User("user${it + 10}", true) }
        whenever(api.searchUsers("token123", "query", 0)).thenReturn(Response.success(first))
        whenever(api.searchUsers("token123", "query", 1)).thenReturn(Response.success(second))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)
        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        assertEquals(first + second, viewModel.allSearchResults.value)
        assertTrue(viewModel.canLoadMoreResults.value)
        assertEquals(false, viewModel.isLoadingAllResults.value)
        verify(api, never()).searchUsers("token123", "query", 2)
    }

    @Test
    fun `deduplicated full cached page still offers the following page`() = runTest {
        val first = List(10) { User("user$it", true) }
        val second = listOf(first[0]) + List(9) { User("user${it + 10}", true) }
        val third = listOf(User("user19", true))
        whenever(api.searchUsers("token123", "query", 0)).thenReturn(Response.success(first))
        whenever(api.searchUsers("token123", "query", 1)).thenReturn(Response.success(second))
        whenever(api.searchUsers("token123", "query", 2)).thenReturn(Response.success(third))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)
        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        assertTrue(viewModel.canLoadMoreResults.value)

        viewModel.loadMoreSearchResults()
        advanceUntilIdle()

        assertEquals((first + second + third).distinctBy { it.username }, viewModel.allSearchResults.value)
        assertEquals(false, viewModel.canLoadMoreResults.value)
        verify(api).searchUsers("token123", "query", 2)
    }

    @Test
    fun `failed prefetch can be retried when loading all results`() = runTest {
        val first = List(10) { User("user$it", true) }
        val second = listOf(User("user10", true))
        whenever(api.searchUsers("token123", "query", 0)).thenReturn(Response.success(first))
        whenever(api.searchUsers("token123", "query", 1))
            .thenThrow(RuntimeException("temporary failure"))
            .thenReturn(Response.success(second))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)
        assertTrue(viewModel.hasMoreResults.value)
        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        assertEquals(first + second, viewModel.allSearchResults.value)
        assertEquals(false, viewModel.canLoadMoreResults.value)
        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `failed load more keeps the pages already fetched`() = runTest {
        val firstBatch = List(10) { index ->
            User("user$index", true)
        }
        val secondBatch = List(10) { index ->
            User("user${index + 10}", true)
        }
        val thirdBatch = listOf(User("user20", true))

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(firstBatch))

        whenever(
            api.searchUsers("token123", "query", 1)
        ).thenReturn(Response.success(secondBatch))

        whenever(
            api.searchUsers("token123", "query", 2)
        ).thenThrow(RuntimeException("Network error"))
            .thenReturn(Response.success(thirdBatch))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)

        assertTrue(viewModel.hasMoreResults.value)

        viewModel.loadAllSearchResults()
        viewModel.loadMoreSearchResults()
        advanceUntilIdle()

        assertTrue(viewModel.errorMessage.value != null)
        assertEquals(firstBatch + secondBatch, viewModel.allSearchResults.value)
        assertTrue(viewModel.canLoadMoreResults.value)
        assertEquals(false, viewModel.isLoadingAllResults.value)

        viewModel.clearError()
        assertNull(viewModel.errorMessage.value)

        // Load more retries the failed batch.
        viewModel.loadMoreSearchResults()
        advanceUntilIdle()

        assertEquals(firstBatch + secondBatch + thirdBatch, viewModel.allSearchResults.value)
        assertEquals(false, viewModel.canLoadMoreResults.value)
        verify(api, times(2)).searchUsers("token123", "query", 2)
    }

    @Test
    fun `rate-limited load more keeps the pages already fetched`() = runTest {
        val firstBatch = List(10) { User("user$it", true) }
        val secondBatch = List(10) { User("user${it + 10}", true) }
        whenever(api.searchUsers("token123", "query", 0)).thenReturn(Response.success(firstBatch))
        whenever(api.searchUsers("token123", "query", 1)).thenReturn(Response.success(secondBatch))
        whenever(api.searchUsers("token123", "query", 2))
            .thenReturn(Response.error(429, "".toResponseBody(null)))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)
        viewModel.loadAllSearchResults()
        viewModel.loadMoreSearchResults()
        advanceUntilIdle()

        assertEquals(
            "You're doing that too often. Please wait a moment and try again.",
            viewModel.errorMessage.value
        )
        assertEquals(firstBatch + secondBatch, viewModel.allSearchResults.value)
        assertTrue(viewModel.canLoadMoreResults.value)
    }

    @Test
    fun `load more pages exactly one batch per press`() = runTest {
        val firstBatch = List(10) { index ->
            User("user$index", true)
        }

        val secondBatch = List(10) { index ->
            User("user${index + 10}", true)
        }

        val thirdBatch = List(3) { index ->
            User("user${index + 20}", true)
        }

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(firstBatch))

        whenever(
            api.searchUsers("token123", "query", 1)
        ).thenReturn(Response.success(secondBatch))

        whenever(
            api.searchUsers("token123", "query", 2)
        ).thenReturn(Response.success(thirdBatch))

        viewModel.updateSearchText("query")

        advanceTimeBy(600)

        assertTrue(viewModel.hasMoreResults.value)

        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        assertEquals(firstBatch + secondBatch, viewModel.allSearchResults.value)

        viewModel.loadMoreSearchResults()
        advanceUntilIdle()

        val expectedResults = firstBatch + secondBatch + thirdBatch

        assertEquals(expectedResults, viewModel.allSearchResults.value)
        assertEquals(false, viewModel.isLoadingAllResults.value)
        assertEquals(false, viewModel.canLoadMoreResults.value)

        verify(api, times(1)).searchUsers("token123", "query", 1)
        verify(api, times(1)).searchUsers("token123", "query", 2)
        verify(api, never()).searchUsers("token123", "query", 3)
    }

    @Test
    fun `reopening all results keeps pages already loaded`() = runTest {
        val firstBatch = List(10) { User("user$it", true) }
        val secondBatch = List(10) { User("user${it + 10}", true) }
        val thirdBatch = listOf(User("user20", true))
        whenever(api.searchUsers("token123", "query", 0)).thenReturn(Response.success(firstBatch))
        whenever(api.searchUsers("token123", "query", 1)).thenReturn(Response.success(secondBatch))
        whenever(api.searchUsers("token123", "query", 2)).thenReturn(Response.success(thirdBatch))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)
        viewModel.loadAllSearchResults()
        viewModel.loadMoreSearchResults()
        advanceUntilIdle()
        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        assertEquals(firstBatch + secondBatch + thirdBatch, viewModel.allSearchResults.value)
        verify(api, times(1)).searchUsers("token123", "query", 2)
    }

    @Test
    fun `load more continues past full duplicate pages to later users`() = runTest {
        val firstBatch = List(10) { index ->
            User("user$index", true)
        }
        val secondBatch = List(10) { index ->
            User("user${index + 10}", true)
        }

        whenever(
            api.searchUsers("token123", "query", 0)
        ).thenReturn(Response.success(firstBatch))

        whenever(
            api.searchUsers("token123", "query", 1)
        ).thenReturn(Response.success(secondBatch))

        // Consecutive full duplicate pages must not hide later new users.
        whenever(
            api.searchUsers("token123", "query", 2)
        ).thenReturn(Response.success(secondBatch))
        whenever(
            api.searchUsers("token123", "query", 3)
        ).thenReturn(Response.success(firstBatch))
        val finalBatch = listOf(User("user20", true))
        whenever(
            api.searchUsers("token123", "query", 4)
        ).thenReturn(Response.success(finalBatch))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)

        assertTrue(viewModel.hasMoreResults.value)

        viewModel.loadAllSearchResults()
        advanceUntilIdle()
        repeat(3) {
            assertTrue(viewModel.canLoadMoreResults.value)
            viewModel.loadMoreSearchResults()
            advanceUntilIdle()
        }

        assertEquals(
            firstBatch + secondBatch + finalBatch,
            viewModel.allSearchResults.value
        )
        assertEquals(false, viewModel.isLoadingAllResults.value)
        assertEquals(false, viewModel.canLoadMoreResults.value)

        verify(api).searchUsers("token123", "query", 2)
        verify(api).searchUsers("token123", "query", 3)
        verify(api).searchUsers("token123", "query", 4)
        verify(api, never())
            .searchUsers("token123", "query", 5)
    }

    @Test
    fun `endless full duplicate pages stop offering load more at the batch cap`() = runTest {
        val firstBatch = List(10) { User("user$it", true) }
        whenever(api.searchUsers(any(), any(), any()))
            .thenReturn(Response.success(firstBatch))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)
        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        var presses = 0
        while (viewModel.canLoadMoreResults.value && presses < 200) {
            viewModel.loadMoreSearchResults()
            advanceUntilIdle()
            presses++
        }

        assertEquals(firstBatch, viewModel.searchedUsers.value)
        assertEquals(firstBatch, viewModel.allSearchResults.value)
        assertEquals(false, viewModel.canLoadMoreResults.value)
        assertEquals(
            "Unable to load more search results. Try a more specific search.",
            viewModel.errorMessage.value
        )
        assertEquals(false, viewModel.isLoadingAllResults.value)
        verify(api).searchUsers("token123", "query", 99)
        verify(api, never()).searchUsers("token123", "query", 100)
    }
}
