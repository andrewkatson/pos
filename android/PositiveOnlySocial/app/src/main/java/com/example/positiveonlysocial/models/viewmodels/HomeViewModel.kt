package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
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

@OptIn(FlowPreview::class)
class HomeViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    // Data for the view
    private val _userPosts = MutableStateFlow<List<Post>>(emptyList())
    val userPosts: StateFlow<List<Post>> = _userPosts.asStateFlow()

    private val _searchedUsers = MutableStateFlow<List<User>>(emptyList())
    val searchedUsers: StateFlow<List<User>> = _searchedUsers.asStateFlow()

    private val _searchText = MutableStateFlow("")
    val searchText: StateFlow<String> = _searchText.asStateFlow()

    // State tracking
    private val _isLoadingNextPage = MutableStateFlow(false)
    val isLoadingNextPage: StateFlow<Boolean> = _isLoadingNextPage.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    private var canLoadMorePosts = true
    private var currentPage = 0
    private val service = "positive-only-social.Positive-Only-Social"

    init {
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

    /**
     * Pull-to-refresh: resets pagination and reloads the user's posts from the
     * first page, replacing the existing posts with the newest ones from the backend.
     */
    fun refreshMyPosts() {
        if (_isRefreshing.value || _isLoadingNextPage.value) return

        _isRefreshing.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot refresh posts")
                    return@launch
                }

                val username = userSession.username

                val response = api.getPostsForUser(userSession.sessionToken, username, 0)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    _userPosts.value = newPosts
                    canLoadMorePosts = newPosts.isNotEmpty()
                    currentPage = if (newPosts.isEmpty()) 0 else 1
                } else {
                    _errorMessage.value = response.errorBody()?.string()
                }
            } catch (e: Exception) {
                _errorMessage.value = e.localizedMessage
                Log.e(TAG, "Error refreshing my posts", e)
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    fun fetchMyPosts() {
        // Also short-circuit during a pull-to-refresh so pagination can't race
        // the refresh's reset of _userPosts/currentPage/canLoadMorePosts.
        if (_isLoadingNextPage.value || _isRefreshing.value || !canLoadMorePosts) return

        _isLoadingNextPage.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch posts")
                    return@launch
                }

                val username = userSession.username

                val response = api.getPostsForUser(userSession.sessionToken, username, currentPage)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        canLoadMorePosts = false
                    } else {
                        _userPosts.value += newPosts
                        currentPage += 1
                    }
                } else {
                    _errorMessage.value = response.errorBody()?.string()
                }
            } catch (e: Exception) {
                _errorMessage.value = e.localizedMessage
                Log.e(TAG, "Error fetching my posts", e)
            } finally {
                _isLoadingNextPage.value = false
            }
        }
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
                _errorMessage.value = response.errorBody()?.string()
            }
        } catch (e: Exception) {
            _errorMessage.value = e.localizedMessage
            Log.e(TAG, "Error performing search", e)
        }
    }
}
