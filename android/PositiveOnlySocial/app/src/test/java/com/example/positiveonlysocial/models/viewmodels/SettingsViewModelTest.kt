package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: SettingsViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var authManager: AuthenticationManager
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", false, null, null)

    @Before
    fun setup() {
        api = mock()
        authManager = mock()
        keychainHelper = mock()
        
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(mockUserSession)
        
        viewModel = SettingsViewModel(api, authManager, keychainHelper)
    }

    @Test
    fun `logout success calls api and authManager`() = runTest {
        whenever(api.logout("token123")).thenReturn(Response.success(GenericResponse("Success", "None")))

        viewModel.logout()

        verify(api).logout("token123")
        verify(authManager).logout()
        assertNull(viewModel.errorMessage.value)
    }

    @Test
    fun `logout failure sets errorMessage but still logs out locally`() = runTest {
        whenever(api.logout("token123")).thenThrow(RuntimeException("Network error"))

        viewModel.logout()

        verify(authManager).logout()
        assertEquals("Logout failed: Network error", viewModel.errorMessage.value)
    }

    @Test
    fun `deleteAccount success calls api and logs out`() = runTest {
        whenever(api.deleteUser("token123")).thenReturn(Response.success(GenericResponse("Success", "None")))

        viewModel.deleteAccount()

        verify(api).deleteUser("token123")
        verify(authManager).logout()
    }

    @Test
    fun `deleteAccount failure sets errorMessage`() = runTest {
        whenever(api.deleteUser("token123")).thenReturn(Response.error(400, "error".toResponseBody()))

        viewModel.deleteAccount()

        verify(api).deleteUser("token123")
        verify(authManager, org.mockito.kotlin.never()).logout()
        assertEquals("Failed to delete account: error", viewModel.errorMessage.value)
    }
}
