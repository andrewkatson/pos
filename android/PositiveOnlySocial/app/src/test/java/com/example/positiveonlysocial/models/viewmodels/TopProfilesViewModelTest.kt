package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.TopProfile
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
import org.mockito.kotlin.whenever
import retrofit2.Response

/** The Top profiles scoreboard (issue #588). */
@OptIn(ExperimentalCoroutinesApi::class)
class TopProfilesViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: TopProfilesViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

    @Before
    fun setup() {
        api = mock()
        keychainHelper = mock()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        viewModel = TopProfilesViewModel(api, keychainHelper)
    }

    @Test
    fun `fetchTopProfiles loads the first page`() = runTest {
        val board = listOf(TopProfile("ada", followerCount = 5), TopProfile("bob", followerCount = 2))
        whenever(api.getTopProfiles("token123", 0)).thenReturn(Response.success(board))

        viewModel.fetchTopProfiles()

        assertEquals(board, viewModel.topProfiles.value)
        assertFalse(viewModel.isLoadingNextPage.value)
        assertFalse(viewModel.reachedEnd.value)
    }

    @Test
    fun `paging drops repeated accounts and stops at an empty page`() = runTest {
        whenever(api.getTopProfiles("token123", 0))
            .thenReturn(Response.success(listOf(TopProfile("ada", followerCount = 5))))
        whenever(api.getTopProfiles("token123", 1)).thenReturn(
            Response.success(listOf(TopProfile("ada", followerCount = 5), TopProfile("cat", followerCount = 3)))
        )
        whenever(api.getTopProfiles("token123", 2)).thenReturn(Response.success(emptyList()))

        viewModel.fetchTopProfiles()
        viewModel.fetchTopProfiles()
        assertEquals(listOf("ada", "cat"), viewModel.topProfiles.value.map { it.username })

        viewModel.fetchTopProfiles()
        assertTrue(viewModel.reachedEnd.value)
    }

    @Test
    fun `a failed load reports an error without claiming the board ended`() = runTest {
        whenever(api.getTopProfiles("token123", 0)).thenReturn(
            Response.error(500, "{}".toResponseBody(null))
        )

        viewModel.fetchTopProfiles()

        assertNotNull(viewModel.loadError.value)
        assertFalse(viewModel.reachedEnd.value)
    }

    @Test
    fun `refresh replaces the board`() = runTest {
        whenever(api.getTopProfiles("token123", 0))
            .thenReturn(Response.success(listOf(TopProfile("ada", followerCount = 1))))
            .thenReturn(Response.success(listOf(TopProfile("bob", followerCount = 9))))

        viewModel.fetchTopProfiles()
        viewModel.refreshTopProfiles()

        assertEquals(listOf("bob"), viewModel.topProfiles.value.map { it.username })
    }

    @Test
    fun `follower count label pluralizes`() {
        assertEquals("1 follower", TopProfile("a", followerCount = 1).followerCountLabel)
        assertEquals("0 followers", TopProfile("a").followerCountLabel)
    }
}
