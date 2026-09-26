package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
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
    fun `performSearch hides view all when second batch repeats first batch`() = runTest {
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
        assertEquals(false, viewModel.hasMoreResults.value)

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
        assertEquals(false, viewModel.hasMoreResults.value)

        verify(api).searchUsers("token123", "query", 0)
        verify(api).searchUsers("token123", "query", 1)
    }

    @Test
    fun `loadAllSearchResults exposes an error when loading another batch fails`() = runTest {
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

        whenever(
            api.searchUsers("token123", "query", 2)
        ).thenThrow(RuntimeException("Network error"))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)

        assertTrue(viewModel.hasMoreResults.value)

        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        assertTrue(viewModel.errorMessage.value != null)
        assertTrue(viewModel.allSearchResults.value.isEmpty())
        assertEquals(false, viewModel.isLoadingAllResults.value)

        viewModel.clearError()
        assertNull(viewModel.errorMessage.value)

        verify(api).searchUsers("token123", "query", 1)
        verify(api).searchUsers("token123", "query", 2)
    }

    @Test
    fun `loadAllSearchResults combines all batches`() = runTest {
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

        advanceTimeBy(100)

        val expectedResults = firstBatch + secondBatch + thirdBatch

        assertEquals(expectedResults, viewModel.allSearchResults.value)
        assertEquals(false, viewModel.isLoadingAllResults.value)

        verify(api).searchUsers("token123", "query", 1)
        verify(api).searchUsers("token123", "query", 2)
    }

    @Test
    fun `loadAllSearchResults stops when a later batch repeats known users`() = runTest {
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

        // Simulates a broken or stale backend returning batch 1 again.
        whenever(
            api.searchUsers("token123", "query", 2)
        ).thenReturn(Response.success(secondBatch))

        viewModel.updateSearchText("query")
        advanceTimeBy(600)

        assertTrue(viewModel.hasMoreResults.value)

        viewModel.loadAllSearchResults()
        advanceUntilIdle()

        assertEquals(
            firstBatch + secondBatch,
            viewModel.allSearchResults.value
        )
        assertEquals(false, viewModel.isLoadingAllResults.value)

        verify(api).searchUsers("token123", "query", 2)
        verify(api, org.mockito.kotlin.never())
            .searchUsers("token123", "query", 3)
    }
}
