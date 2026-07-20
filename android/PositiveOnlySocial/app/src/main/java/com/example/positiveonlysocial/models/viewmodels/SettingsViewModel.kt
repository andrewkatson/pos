package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.model.IdentityVerificationRequest
import com.example.positiveonlysocial.data.model.ConfirmTotpRequest
import com.example.positiveonlysocial.data.model.DisableTotpRequest
import com.example.positiveonlysocial.data.model.TotpSetupResponse
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "SettingsViewModel"

class SettingsViewModel(
    private val api: PositiveOnlySocialAPI,
    private val authenticationManager: AuthenticationManager,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _showLogoutConfirmation = MutableStateFlow(false)
    val showLogoutConfirmation: StateFlow<Boolean> = _showLogoutConfirmation.asStateFlow()

    private val _showDeleteConfirmation = MutableStateFlow(false)
    val showDeleteConfirmation: StateFlow<Boolean> = _showDeleteConfirmation.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val _showingErrorAlert = MutableStateFlow(false)
    val showingErrorAlert: StateFlow<Boolean> = _showingErrorAlert.asStateFlow()

    private val _verificationMessage = MutableStateFlow<String?>(null)
    val verificationMessage: StateFlow<String?> = _verificationMessage.asStateFlow()

    private val _showingVerificationAlert = MutableStateFlow(false)
    val showingVerificationAlert: StateFlow<Boolean> = _showingVerificationAlert.asStateFlow()

    // Two-factor authentication state (issue #348). `totpSetup` drives the
    // scan/confirm steps of the enrollment dialog; `recoveryCodes` (set once
    // confirm succeeds) drives the final save-your-codes step.
    private val _totpSetup = MutableStateFlow<TotpSetupResponse?>(null)
    val totpSetup: StateFlow<TotpSetupResponse?> = _totpSetup.asStateFlow()

    private val _recoveryCodes = MutableStateFlow<List<String>?>(null)
    val recoveryCodes: StateFlow<List<String>?> = _recoveryCodes.asStateFlow()

    private val _twoFactorStatusMessage = MutableStateFlow<String?>(null)
    val twoFactorStatusMessage: StateFlow<String?> = _twoFactorStatusMessage.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    fun setShowLogoutConfirmation(show: Boolean) {
        _showLogoutConfirmation.value = show
    }

    fun setShowDeleteConfirmation(show: Boolean) {
        _showDeleteConfirmation.value = show
    }

    fun clearError() {
        _errorMessage.value = null
    }

    fun logout() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                
                if (userSession != null) {
                    // Call API to invalidate token on server
                    val response = api.logout(userSession.sessionToken)
                    if (!response.isSuccessful) {
                        Log.w(TAG, "Backend logout failed: ${response.message()}")
                    }
                }
                
                // Clear local session regardless of API success
                authenticationManager.logout()
                
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Logout failed. Please try again.")
                // Force local logout anyway? Usually yes.
                authenticationManager.logout()
            }
        }
    }

    fun deleteAccount() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                
                if (userSession != null) {
                    val response = api.deleteUser(userSession.sessionToken)
                    if (response.isSuccessful) {
                        authenticationManager.logout()
                    } else {
                        _errorMessage.value = ApiErrors.messageFor(response, fallback = "Failed to delete your account. Please try again.")
                    }
                } else {
                    authenticationManager.logout()
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Failed to delete your account. Please try again.")
            }
        }
    }

    // MARK: - Two-Factor Authentication (issue #348)

    /** Starts TOTP enrollment: fetches a fresh secret + otpauth:// URI. */
    fun startTotpSetup() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    _errorMessage.value = "Session not found."
                    _showingErrorAlert.value = true
                    return@launch
                }
                val response = api.setupTotp(userSession.sessionToken)
                if (response.isSuccessful) {
                    _totpSetup.value = response.body()
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Could not start two-factor setup.")
                    _showingErrorAlert.value = true
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Could not start two-factor setup.")
                _showingErrorAlert.value = true
            }
        }
    }

    /**
     * Finishes TOTP enrollment by verifying one code from the authenticator.
     * On success `recoveryCodes` is populated for the one-time display.
     */
    fun confirmTotp(code: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    _errorMessage.value = "Session not found."
                    _showingErrorAlert.value = true
                    return@launch
                }
                val response = api.confirmTotp(userSession.sessionToken, ConfirmTotpRequest(code))
                val codes = response.body()?.recoveryCodes
                if (response.isSuccessful && codes != null) {
                    _recoveryCodes.value = codes
                } else if (response.isSuccessful) {
                    // 2xx with a null/empty body: surface an error rather than
                    // leaving the enrollment dialog stuck on the confirm step.
                    _errorMessage.value = "Two-factor setup did not complete. Please try again."
                    _showingErrorAlert.value = true
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Verification failed. Please try again.")
                    _showingErrorAlert.value = true
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Verification failed. Please try again.")
                _showingErrorAlert.value = true
            }
        }
    }

    /** Dismisses the enrollment flow after the recovery codes have been shown. */
    fun finishTotpEnrollment() {
        // Only report success if confirm actually produced recovery codes, so an
        // accidental call while still mid-enrollment can't fake an enabled state.
        val wasEnrolled = _recoveryCodes.value != null
        _totpSetup.value = null
        _recoveryCodes.value = null
        if (wasEnrolled) {
            _twoFactorStatusMessage.value = "Two-factor authentication is now enabled."
        }
    }

    /** Abandons a not-yet-confirmed enrollment (the pending secret is inert). */
    fun cancelTotpEnrollment() {
        _totpSetup.value = null
        _recoveryCodes.value = null
    }

    fun clearTwoFactorStatusMessage() {
        _twoFactorStatusMessage.value = null
    }

    /**
     * Turns two-factor authentication off. Requires the account password plus
     * a current authenticator code or an unused recovery code.
     */
    fun disableTotp(password: String, code: String, isRecoveryCode: Boolean) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    _errorMessage.value = "Session not found."
                    _showingErrorAlert.value = true
                    return@launch
                }
                // Recovery codes are sent lowercased to match the backend pattern.
                val request = DisableTotpRequest(
                    password = password,
                    totpCode = if (isRecoveryCode) null else code,
                    recoveryCode = if (isRecoveryCode) code.lowercase() else null
                )
                val response = api.disableTotp(userSession.sessionToken, request)
                if (response.isSuccessful) {
                    _twoFactorStatusMessage.value = "Two-factor authentication has been disabled."
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Could not disable two-factor authentication.")
                    _showingErrorAlert.value = true
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Could not disable two-factor authentication.")
                _showingErrorAlert.value = true
            }
        }
    }

    fun verifyIdentity(dateOfBirth: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                
                if (userSession != null) {
                    val request = IdentityVerificationRequest(dateOfBirth)
                    val response = api.verifyIdentity(userSession.sessionToken, request)
                    
                    if (response.isSuccessful) {
                        // Update local session to verified
                        val newSession = userSession.copy(isIdentityVerified = true)
                        keychainHelper.save(newSession, service, account)
                        authenticationManager.login(newSession)
                        
                        _verificationMessage.value = "Identity verified successfully!"
                        _showingVerificationAlert.value = true
                    } else {
                        _errorMessage.value = ApiErrors.messageFor(response, fallback = "Verification failed. Please try again.")
                        _showingErrorAlert.value = true
                    }
                } else {
                    _errorMessage.value = "Session not found."
                    _showingErrorAlert.value = true
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Verification failed. Please try again.")
                _showingErrorAlert.value = true
            }
        }
    }
}
