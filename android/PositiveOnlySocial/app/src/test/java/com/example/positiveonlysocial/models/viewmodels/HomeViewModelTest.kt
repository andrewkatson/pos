package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
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
        whenever(api.searchUsers("token123", "query")).thenReturn(Response.success(mockUsers))

        viewModel.updateSearchText("query")

        // Advance time to trigger debounce
        advanceTimeBy(600)

        assertEquals(mockUsers, viewModel.searchedUsers.value)
    }

    @Test
    fun `performSearch with short query clears searchedUsers`() = runTest {
        viewModel.updateSearchText("qu")

        advanceTimeBy(600)

        assertTrue(viewModel.searchedUsers.value.isEmpty())
        // Should not call API
        verify(api, org.mockito.kotlin.never()).searchUsers(any(), any())
    }
}
