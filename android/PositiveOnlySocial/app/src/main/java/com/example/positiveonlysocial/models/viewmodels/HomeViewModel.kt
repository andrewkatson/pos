package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch

private const val TAG = "HomeViewModel"

/**
 * Backs the first bottom-nav destination, which is now the signed-in user's own
 * profile (issue #347). The profile itself — stats and post grid — is rendered by
 * the shared profile body against [ProfileViewModel]; this view model owns only
 * the user-search bar above it, plus [currentUsername] so the screen knows whose
 * profile to show.
 */
@OptIn(FlowPreview::class)
class HomeViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _searchedUsers = MutableStateFlow<List<User>>(emptyList())
    val searchedUsers: StateFlow<List<User>> = _searchedUsers.asStateFlow()

    private val _searchText = MutableStateFlow("")
    val searchText: StateFlow<String> = _searchText.asStateFlow()

    // The signed-in user, i.e. whose profile this destination shows.
    private val _currentUsername = MutableStateFlow<String?>(null)
    val currentUsername: StateFlow<String?> = _currentUsername.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    init {
        _currentUsername.value = try {
            keychainHelper.load(UserSession::class.java, service, account)?.username
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read the stored session", e)
            null
        }

        viewModelScope.launch {
            _searchText
                .debounce(500) // Wait 500ms after user stops typing
                .collectLatest { query ->
                    performSearch(query)
                }
        }
    }

    fun updateSearchText(text: String) {
        _searchText.value = text
    }

    private suspend fun performSearch(query: String) {
        if (query.length < 3) {
            _searchedUsers.value = emptyList()
            return
        }

        try {
            val userSession = keychainHelper.load(UserSession::class.java, service, account)
            if (userSession == null) {
                Log.e(TAG, "No active session found — cannot search users")
                return
            }

            val response = api.searchUsers(userSession.sessionToken, query)
            if (response.isSuccessful) {
                _searchedUsers.value = response.body() ?: emptyList()
            } else {
                _errorMessage.value = ApiErrors.messageFor(response, fallback = "Something went wrong. Please try again.")
            }
        } catch (e: Exception) {
            _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            Log.e(TAG, "Error performing search", e)
        }
    }
}
