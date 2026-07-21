package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.Response

private const val TAG = "BlockedUsersViewModel"

/**
 * Loads the signed-in user's blocked users and unblocks them on demand
 * (toggle_block). Reached from Settings.
 */
class BlockedUsersViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _blockedUsers = MutableStateFlow<List<User>>(emptyList())
    val blockedUsers: StateFlow<List<User>> = _blockedUsers.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    /**
     * The usernames with an unblock request in flight, so each row's button
     * can be disabled independently (several unblocks may overlap).
     */
    private val _unblockingUsernames = MutableStateFlow<Set<String>>(emptySet())
    val unblockingUsernames: StateFlow<Set<String>> = _unblockingUsernames.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    fun clearError() {
        _errorMessage.value = null
    }

    private fun session(): UserSession? =
        keychainHelper.load(UserSession::class.java, service, account)

    /**
     * Extracts the backend's `error` message from a failed response body so the
     * UI shows the message rather than the raw `{"error": ...}` JSON.
     */
    private fun errorOf(response: Response<*>): String {
        return ApiErrors.messageFor(response, fallback = "Request failed. Please try again.")
    }

    /** Loads (or reloads) the full list of blocked users. */
    fun load() {
        _isLoading.value = true
        _errorMessage.value = null // drop any stale error from a previous load/unblock
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot load blocked users")
                    return@launch
                }
                val response = api.getBlockedUsers(userSession.sessionToken)
                if (response.isSuccessful) {
                    _blockedUsers.value = response.body() ?: emptyList()
                } else {
                    _errorMessage.value = errorOf(response)
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Request failed. Please try again.")
                Log.e(TAG, "Error loading blocked users", e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    /** Unblocks a user via toggle_block and removes them from the list. */
    fun unblock(username: String) {
        _unblockingUsernames.value = _unblockingUsernames.value + username
        _errorMessage.value = null
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    _errorMessage.value = "You must be logged in to unblock a user."
                    return@launch
                }
                val response = api.toggleBlock(userSession.sessionToken, username)
                if (response.isSuccessful) {
                    _blockedUsers.value = _blockedUsers.value.filterNot { it.username == username }
                } else {
                    _errorMessage.value = errorOf(response)
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Request failed. Please try again.")
                Log.e(TAG, "Error unblocking user", e)
            } finally {
                _unblockingUsernames.value = _unblockingUsernames.value - username
            }
        }
    }
}
