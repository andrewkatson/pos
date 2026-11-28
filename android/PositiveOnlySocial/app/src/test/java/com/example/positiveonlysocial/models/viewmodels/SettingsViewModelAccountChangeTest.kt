package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.ChangeUsernameRequest
import com.example.positiveonlysocial.data.model.ChangeUsernameResponse
import com.example.positiveonlysocial.data.model.CurrentUserResponse
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.RequestEmailChangeRequest
import com.example.positiveonlysocial.data.model.RequestEmailChangeResponse
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.eq
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

/** Changing the username and email from Settings (issue #594). */
@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelAccountChangeTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: SettingsViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var authManager: AuthenticationManager
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val session = UserSession("token123", "testuser_one", "1", false, null, null)

    @Before
    fun setup() {
        api = mock()
        authManager = mock()
        keychainHelper = mock()
        whenever(keychainHelper.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        viewModel = SettingsViewModel(api, authManager, keychainHelper)
    }

    private suspend fun loadUser(user: CurrentUserResponse) {
        whenever(api.getCurrentUser("token123")).thenReturn(Response.success(user))
        viewModel.loadCurrentUser()
    }

    private fun errorBody(code: String) = "{\"error\":\"$code\"}".toResponseBody()

    @Test
    fun `changeUsername success updates the stored session and current user`() = runTest {
        loadUser(CurrentUserResponse("testuser_one", "t@example.com", hasPassword = true))
        whenever(api.changeUsername("token123", ChangeUsernameRequest("renamed_user"))).thenReturn(
            Response.success(ChangeUsernameResponse("renamed_user", "2099-01-01T00:00:00Z")))

        viewModel.changeUsername("renamed_user")

        val renamed = session.copy(username = "renamed_user")
        verify(keychainHelper).save(eq(renamed), any(), any())
        // A rename keeps the privacy policy answer (#620).
        verify(authManager).login(renamed, true)
        assertEquals("renamed_user", viewModel.currentUser.value?.username)
        assertEquals("2099-01-01T00:00:00Z", viewModel.currentUser.value?.nextUsernameChangeTime)
        assertTrue(viewModel.accountChangeDone.value)
        assertEquals("Your username is now renamed_user.", viewModel.accountChangeMessage.value)
        assertFalse(viewModel.isChangingAccountDetails.value)
    }

    @Test
    fun `changeUsername taken shows the client copy and keeps the session`() = runTest {
        whenever(api.changeUsername(eq("token123"), any())).thenReturn(
            Response.error(400, errorBody(ApiErrors.USERNAME_TAKEN)))

        viewModel.changeUsername("someone_else")

        assertEquals("That username is already taken.", viewModel.accountChangeError.value)
        assertFalse(viewModel.accountChangeDone.value)
        verify(authManager, never()).login(any(), any())
    }

    @Test
    fun `requestEmailChange success records the pending address`() = runTest {
        loadUser(CurrentUserResponse("testuser_one", "t@example.com", hasPassword = true))
        val request = RequestEmailChangeRequest(email = "new@example.com", password = "Password1")
        whenever(api.requestEmailChange("token123", request)).thenReturn(
            Response.success(RequestEmailChangeResponse("new@example.com")))

        viewModel.requestEmailChange("new@example.com", password = "Password1", idToken = null)

        assertEquals("new@example.com", viewModel.currentUser.value?.pendingEmail)
        // The confirmed address stays until the emailed link is followed.
        assertEquals("t@example.com", viewModel.currentUser.value?.email)
        assertTrue(viewModel.accountChangeDone.value)
    }

    @Test
    fun `requestEmailChange wrong password shows the client copy`() = runTest {
        whenever(api.requestEmailChange(eq("token123"), any())).thenReturn(
            Response.error(400, errorBody(ApiErrors.REAUTHENTICATION_REQUIRED)))

        viewModel.requestEmailChange("new@example.com", password = "wrong", idToken = null)

        assertEquals(ApiErrors.codeMessages[ApiErrors.REAUTHENTICATION_REQUIRED], viewModel.accountChangeError.value)
        assertFalse(viewModel.accountChangeDone.value)
    }

    @Test
    fun `requestEmailChange with a Google token sends no password`() = runTest {
        val request = RequestEmailChangeRequest(email = "new@example.com", idToken = "google-id-token")
        whenever(api.requestEmailChange("token123", request)).thenReturn(
            Response.success(RequestEmailChangeResponse("new@example.com")))

        viewModel.requestEmailChange("new@example.com", password = null, idToken = "google-id-token")

        verify(api).requestEmailChange("token123", request)
        assertTrue(viewModel.accountChangeDone.value)
    }

    @Test
    fun `cancelEmailChange clears the pending address`() = runTest {
        loadUser(CurrentUserResponse("testuser_one", "t@example.com", pendingEmail = "new@example.com", hasPassword = true))
        whenever(api.cancelEmailChange("token123")).thenReturn(Response.success(GenericResponse("ok", null)))

        viewModel.cancelEmailChange()

        assertNull(viewModel.currentUser.value?.pendingEmail)
        assertEquals("Your email change was cancelled.", viewModel.accountChangeMessage.value)
    }

    @Test
    fun `resetAccountChangeDialog clears the done flag and error`() = runTest {
        whenever(api.changeUsername(eq("token123"), any())).thenReturn(
            Response.error(400, errorBody(ApiErrors.USERNAME_TAKEN)))
        viewModel.changeUsername("someone_else")

        viewModel.resetAccountChangeDialog()

        assertNull(viewModel.accountChangeError.value)
        assertFalse(viewModel.accountChangeDone.value)
    }
}
