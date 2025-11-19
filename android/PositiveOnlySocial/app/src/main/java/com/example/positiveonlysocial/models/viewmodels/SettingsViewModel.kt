package com.example.positiveonlysocial.models.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SettingsViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    // Published properties
    private val _showingLogoutConfirm = MutableStateFlow(false)
    val showingLogoutConfirm: StateFlow<Boolean> = _showingLogoutConfirm.asStateFlow()

    private val _showingDeleteConfirm = MutableStateFlow(false)
    val showingDeleteConfirm: StateFlow<Boolean> = _showingDeleteConfirm.asStateFlow()

    private val _showingErrorAlert = MutableStateFlow(false)
    val showingErrorAlert: StateFlow<Boolean> = _showingErrorAlert.asStateFlow()

    private val _errorMessage = MutableStateFlow("")
    val errorMessage: StateFlow<String> = _errorMessage.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    fun setShowingLogoutConfirm(show: Boolean) {
        _showingLogoutConfirm.value = show
    }

    fun setShowingDeleteConfirm(show: Boolean) {
        _showingDeleteConfirm.value = show
    }

    fun setShowingErrorAlert(show: Boolean) {
        _showingErrorAlert.value = show
    }

    fun logout(authManager: AuthenticationManager) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                
                if (userSession != null) {
                    api.logout(userSession.sessionToken)
                    println("✅ Backend logout successful.")
                } else {
                    authManager.logout()
                    return@launch
                }
            } catch (e: Exception) {
                println("🔴 Backend logout failed: ${e.localizedMessage}. Proceeding with local logout.")
            }

            authManager.logout()
        }
    }

    fun deleteAccount(authManager: AuthenticationManager) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                
                if (userSession == null) {
                    _errorMessage.value = "Session not found. Cannot delete account."
                    _showingErrorAlert.value = true
                    return@launch
                }

                val response = api.deleteUser(userSession.sessionToken)
                if (response.isSuccessful) {
                    println("✅ Account deletion successful.")
                    authManager.logout()
                } else {
                    throw Exception("Failed to delete account")
                }

            } catch (e: Exception) {
                _errorMessage.value = "Failed to delete account. Please try again."
                _showingErrorAlert.value = true
                println("🔴 Account deletion failed: ${e.localizedMessage}")
            }
        }
    }
}
