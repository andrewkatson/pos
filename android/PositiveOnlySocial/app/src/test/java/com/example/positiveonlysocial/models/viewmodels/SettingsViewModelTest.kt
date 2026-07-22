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
import com.example.positiveonlysocial.data.model.IdentityVerificationRequest
import com.example.positiveonlysocial.data.model.ConfirmTotpRequest
import com.example.positiveonlysocial.data.model.ConfirmTotpResponse
import com.example.positiveonlysocial.data.model.DisableTotpRequest
import com.example.positiveonlysocial.data.model.DisableTotpResponse
import com.example.positiveonlysocial.data.model.TotpSetupResponse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: SettingsViewModel
    private lateinit var api: PositiveOnlySocialAPI
    private lateinit var authManager: AuthenticationManager
    private lateinit var keychainHelper: KeychainHelperProtocol

    private val mockUserSession = UserSession("token123", "testuser", "1", false, null, null)

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
        assertEquals("Logout failed. Please try again.", viewModel.errorMessage.value)
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
        whenever(api.deleteUser("token123")).thenReturn(Response.error(400, "{\"error\":\"Account deletion failed\"}".toResponseBody()))

        viewModel.deleteAccount()

        verify(api).deleteUser("token123")
        verify(authManager, org.mockito.kotlin.never()).logout()
        assertEquals("Account deletion failed", viewModel.errorMessage.value)
    }
    @Test
    fun `verifyIdentity success calls api and updates state`() = runTest {
        whenever(api.verifyIdentity(
            "token123",
            IdentityVerificationRequest("1990-01-01")
        )).thenReturn(Response.success(GenericResponse("Success", "None")))

        viewModel.verifyIdentity("1990-01-01")

        verify(api).verifyIdentity("token123", IdentityVerificationRequest("1990-01-01"))
        // authManager.login IS called in the implementation
        verify(authManager).login(any())
        assertEquals("Identity verified successfully!", viewModel.verificationMessage.value)
    }

    // --- Two-Factor Authentication Tests (issue #348) ---

    @Test
    fun `startTotpSetup populates secret and uri`() = runTest {
        whenever(api.setupTotp("token123")).thenReturn(
            Response.success(TotpSetupResponse("SECRETBASE32", "otpauth://totp/x?secret=SECRETBASE32"))
        )

        viewModel.startTotpSetup()

        verify(api).setupTotp("token123")
        val setup = viewModel.totpSetup.value
        assertNotNull(setup)
        assertEquals("SECRETBASE32", setup?.totpSecret)
        assertEquals("otpauth://totp/x?secret=SECRETBASE32", setup?.otpauthUri)
        assertEquals(false, viewModel.showingErrorAlert.value)
    }

    @Test
    fun `confirmTotp success exposes recovery codes`() = runTest {
        val codes = (0 until 10).map { "code$it" }
        whenever(api.confirmTotp("token123", ConfirmTotpRequest("pw12345", "123456"))).thenReturn(
            Response.success(ConfirmTotpResponse(totpEnabled = true, recoveryCodes = codes))
        )

        viewModel.confirmTotp("pw12345", "123456")

        verify(api).confirmTotp("token123", ConfirmTotpRequest("pw12345", "123456"))
        assertEquals(10, viewModel.recoveryCodes.value?.size)
        // The in-flight flag is cleared once the request settles, so the UI can
        // block a duplicate submission while it runs and re-enable Verify after.
        assertEquals(false, viewModel.isConfirmingTotp.value)
    }

    @Test
    fun `confirmTotp failure clears the in-flight confirm flag`() = runTest {
        whenever(api.confirmTotp(any(), any())).thenReturn(
            Response.error(400, "{\"error\":\"Invalid password\"}".toResponseBody())
        )

        viewModel.confirmTotp("wrongpw", "123456")

        // A failed confirm must not leave Verify stuck disabled on retry.
        assertEquals(false, viewModel.isConfirmingTotp.value)
    }

    @Test
    fun `confirmTotp failure surfaces error and no codes`() = runTest {
        whenever(api.confirmTotp("token123", ConfirmTotpRequest("pw12345", "000000"))).thenReturn(
            Response.error(400, "{\"error\":\"Invalid two-factor code\"}".toResponseBody())
        )

        viewModel.confirmTotp("pw12345", "000000")

        assertNull(viewModel.recoveryCodes.value)
        assertTrue(viewModel.showingErrorAlert.value)
    }

    @Test
    fun `finishTotpEnrollment clears state and sets status message`() = runTest {
        whenever(api.setupTotp("token123")).thenReturn(
            Response.success(TotpSetupResponse("SECRET", "otpauth://totp/x"))
        )
        whenever(api.confirmTotp("token123", ConfirmTotpRequest("pw12345", "123456"))).thenReturn(
            Response.success(ConfirmTotpResponse(totpEnabled = true, recoveryCodes = listOf("a", "b")))
        )
        // Enroll fully so recovery codes exist — finishTotpEnrollment only
        // reports success when confirm actually produced them.
        viewModel.startTotpSetup()
        viewModel.confirmTotp("pw12345", "123456")

        viewModel.finishTotpEnrollment()

        assertNull(viewModel.totpSetup.value)
        assertNull(viewModel.recoveryCodes.value)
        assertEquals("Two-factor authentication is now enabled.", viewModel.twoFactorStatusMessage.value)
    }

    @Test
    fun `finishTotpEnrollment without recovery codes does not claim enabled`() = runTest {
        // Called with no confirmed enrollment (recoveryCodes still null): must
        // not fake a success state.
        viewModel.finishTotpEnrollment()

        assertNull(viewModel.twoFactorStatusMessage.value)
    }

    @Test
    fun `disableTotp with authenticator code sends totp_code and reports status`() = runTest {
        whenever(api.disableTotp("token123", DisableTotpRequest(password = "pw", totpCode = "123456", recoveryCode = null)))
            .thenReturn(Response.success(DisableTotpResponse(totpEnabled = false)))

        viewModel.disableTotp(password = "pw", code = "123456", isRecoveryCode = false)

        verify(api).disableTotp("token123", DisableTotpRequest(password = "pw", totpCode = "123456", recoveryCode = null))
        assertEquals("Two-factor authentication has been disabled.", viewModel.twoFactorStatusMessage.value)
    }

    @Test
    fun `disableTotp with recovery code lowercases it and sends recovery_code`() = runTest {
        whenever(api.disableTotp("token123", DisableTotpRequest(password = "pw", totpCode = null, recoveryCode = "abcdef0123")))
            .thenReturn(Response.success(DisableTotpResponse(totpEnabled = false)))

        viewModel.disableTotp(password = "pw", code = "ABCDEF0123", isRecoveryCode = true)

        verify(api).disableTotp("token123", DisableTotpRequest(password = "pw", totpCode = null, recoveryCode = "abcdef0123"))
    }

    @Test
    fun `disableTotp failure surfaces error`() = runTest {
        whenever(api.disableTotp(org.mockito.kotlin.eq("token123"), any())).thenReturn(
            Response.error(400, "{\"error\":\"Invalid password\"}".toResponseBody())
        )

        viewModel.disableTotp(password = "wrong", code = "123456", isRecoveryCode = false)

        assertTrue(viewModel.showingErrorAlert.value)
    }
}
