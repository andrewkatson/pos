package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.TopUser
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
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
import org.mockito.kotlin.mock
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

/** The most-followed people board (issue #562). */
@OptIn(ExperimentalCoroutinesApi::class)
class TopUsersViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: TopUsersViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

    private fun user(name: String, count: Int) = TopUser(name, false, count)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        viewModel = TopUsersViewModel(api, keychainHelper)
    }

    @Test
    fun `fetchTopUsers loads the board`() = runTest {
        val rows = listOf(user("star", 5), user("rising", 2))
        whenever(api.getTopUsers("token123", 0)).thenReturn(Response.success(rows))

        viewModel.fetchTopUsers()

        assertEquals(rows, viewModel.topUsers.value)
        assertFalse(viewModel.isLoadingNextPage.value)
    }

    @Test
    fun `fetchTopUsers appends pages, skips repeats, and stops at an empty page`() = runTest {
        val a = user("a", 9)
        val b = user("b", 8)
        val c = user("c", 7)
        whenever(api.getTopUsers("token123", 0)).thenReturn(Response.success(listOf(a, b)))
        // Page 1 only repeats page 0, so one fetch must walk on to page 2.
        whenever(api.getTopUsers("token123", 1)).thenReturn(Response.success(listOf(a, b)))
        whenever(api.getTopUsers("token123", 2)).thenReturn(Response.success(listOf(c)))
        whenever(api.getTopUsers("token123", 3)).thenReturn(Response.success(emptyList()))

        viewModel.fetchTopUsers()
        viewModel.fetchTopUsers()
        assertEquals(listOf(a, b, c), viewModel.topUsers.value)

        viewModel.fetchTopUsers()
        viewModel.fetchTopUsers()
        verify(api, times(4)).getTopUsers(any(), any())
    }

    @Test
    fun `refreshTopUsers replaces the board`() = runTest {
        whenever(api.getTopUsers("token123", 0)).thenReturn(Response.success(listOf(user("old", 1))))
        viewModel.fetchTopUsers()

        val fresh = listOf(user("new", 3))
        whenever(api.getTopUsers("token123", 0)).thenReturn(Response.success(fresh))
        viewModel.refreshTopUsers()

        assertEquals(fresh, viewModel.topUsers.value)
        assertFalse(viewModel.isRefreshing.value)
    }

    @Test
    fun `fetchTopUsers failure surfaces a load error`() = runTest {
        whenever(api.getTopUsers("token123", 0)).thenReturn(Response.error(500, "error".toResponseBody()))

        viewModel.fetchTopUsers()

        assertTrue(viewModel.topUsers.value.isEmpty())
        assertNotNull(viewModel.loadError.value)
    }
}
