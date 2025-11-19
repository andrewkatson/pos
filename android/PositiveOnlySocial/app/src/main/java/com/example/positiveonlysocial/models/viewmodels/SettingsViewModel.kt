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

    private val service = "positive-only-social.Positive-Only-Social"

    fun setShowLogoutConfirmation(show: Boolean) {
        _showLogoutConfirmation.value = show
    }

    fun setShowDeleteConfirmation(show: Boolean) {
        _showDeleteConfirmation.value = show
    }

    fun logout() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                
                if (userSession != null) {
                    // Call API to invalidate token on server
                    api.logout(userSession.sessionToken)
                }
                
                // Clear local session regardless of API success
                authenticationManager.logout()
                
            } catch (e: Exception) {
                _errorMessage.value = "Logout failed: ${e.localizedMessage}"
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
                        _errorMessage.value = "Failed to delete account: ${response.errorBody()?.string()}"
                    }
                } else {
                    authenticationManager.logout()
                }
            } catch (e: Exception) {
                _errorMessage.value = "Error deleting account: ${e.localizedMessage}"
            }
        }
    }
}
