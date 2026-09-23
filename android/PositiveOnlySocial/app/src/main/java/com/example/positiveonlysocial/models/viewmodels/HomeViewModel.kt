package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
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

    private val _isSearching = MutableStateFlow(false)
    val isSearching: StateFlow<Boolean> = _isSearching.asStateFlow()

    private val _hasMoreResults = MutableStateFlow(false)
    val hasMoreResults: StateFlow<Boolean> = _hasMoreResults.asStateFlow()

    private val _allSearchResults = MutableStateFlow<List<User>>(emptyList())
    val allSearchResults: StateFlow<List<User>> = _allSearchResults.asStateFlow()

    private val _isLoadingAllResults = MutableStateFlow(false)
    val isLoadingAllResults: StateFlow<Boolean> =
        _isLoadingAllResults.asStateFlow()

    private val _searchText = MutableStateFlow("")
    val searchText: StateFlow<String> = _searchText.asStateFlow()

    // The signed-in user, i.e. whose profile this destination shows.
    private val _currentUsername = MutableStateFlow<String?>(null)
    val currentUsername: StateFlow<String?> = _currentUsername.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private var prefetchedSecondBatch: List<User> = emptyList()
    private var prefetchedSecondBatchQuery: String? = null

    private val service = "positive-only-social.Positive-Only-Social"

    init {
        _currentUsername.value = try {
            keychainHelper.load(
                UserSession::class.java,
                service,
                account
            )?.username
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read the stored session", e)
            null
        }

        viewModelScope.launch {
            _searchText
                .debounce(500) // Wait 500ms after user stops typing.
                .collectLatest { query ->
                    performSearch(query)
                }
        }
    }

    fun updateSearchText(text: String) {
        val trimmedText = text.trim()

        _searchText.value = text
        _searchedUsers.value = emptyList()
        _errorMessage.value = null
        _hasMoreResults.value = false
        _allSearchResults.value = emptyList()
        _isSearching.value = trimmedText.length >= 3
        prefetchedSecondBatch = emptyList()
        prefetchedSecondBatchQuery = null
    }

    private suspend fun performSearch(query: String) {
        val trimmedQuery = query.trim()

        if (trimmedQuery.length < 3) {
            _searchedUsers.value = emptyList()
            _hasMoreResults.value = false
            _isSearching.value = false
            return
        }

        try {
            val userSession = keychainHelper.load(
                UserSession::class.java,
                service,
                account
            )

            if (userSession == null) {
                _errorMessage.value = Constants.SESSION_MISSING_MESSAGE
                Log.e(TAG, "No active session found — cannot search users")
                return
            }

            val response = api.searchUsers(
                userSession.sessionToken,
                trimmedQuery,
                0
            )

            if (!response.isSuccessful) {
                _searchedUsers.value = emptyList()
                _hasMoreResults.value = false
                _errorMessage.value = ApiErrors.messageFor(
                    response,
                    fallback = "Something went wrong. Please try again."
                )
                return
            }

            val results = response.body() ?: emptyList()
            _searchedUsers.value = results

            if (results.size != 10) {
                prefetchedSecondBatch = emptyList()
                prefetchedSecondBatchQuery = null
                _hasMoreResults.value = false
                return
            }

            try {
                val nextResponse = api.searchUsers(
                    userSession.sessionToken,
                    trimmedQuery,
                    1
                )

                val firstBatchUsernames =
                    results.mapTo(mutableSetOf()) { it.username }

                val nextBatch = if (nextResponse.isSuccessful) {
                    (nextResponse.body() ?: emptyList()).filter { user ->
                        firstBatchUsernames.add(user.username)
                    }
                } else {
                    emptyList()
                }

                prefetchedSecondBatch = nextBatch
                prefetchedSecondBatchQuery = trimmedQuery
                _hasMoreResults.value = nextBatch.isNotEmpty()
            } catch (e: Exception) {
                prefetchedSecondBatch = emptyList()
                prefetchedSecondBatchQuery = null
                _hasMoreResults.value = false
                Log.e(
                    TAG,
                    "Error checking for additional search results",
                    e
                )
            }
        } catch (e: Exception) {
            _searchedUsers.value = emptyList()
            _hasMoreResults.value = false
            _errorMessage.value = ApiErrors.messageFor(
                e,
                fallback = "Something went wrong. Please try again."
            )
            Log.e(TAG, "Error performing search", e)
        } finally {
            // An older cancelled search must not clear a newer query's
            // loading state.
            if (_searchText.value.trim() == trimmedQuery) {
                _isSearching.value = false
            }
        }
    }

    fun loadAllSearchResults() {
        val query = _searchText.value.trim()

        if (query.length < 3 || _isLoadingAllResults.value) {
            return
        }

        _allSearchResults.value = emptyList()

        viewModelScope.launch {
            _isLoadingAllResults.value = true

            try {
                val userSession = keychainHelper.load(
                    UserSession::class.java,
                    service,
                    account
                )

                if (userSession == null) {
                    _errorMessage.value = Constants.SESSION_MISSING_MESSAGE
                    Log.e(
                        TAG,
                        "No active session found — cannot load search results"
                    )
                    return@launch
                }

                val results = _searchedUsers.value.toMutableList()
                val cachedSecondBatch =
                    if (prefetchedSecondBatchQuery == query) {
                        prefetchedSecondBatch
                    } else {
                        null
                    }

                var batch = 1

                if (cachedSecondBatch != null) {
                    results.addAll(cachedSecondBatch)
                    batch = 2
                }

                val seenUsernames =
                    results.mapTo(mutableSetOf()) { it.username }

                val shouldLoadAnotherBatch =
                    cachedSecondBatch == null ||
                        cachedSecondBatch.size == 10

                while (shouldLoadAnotherBatch) {
                    val response = api.searchUsers(
                        userSession.sessionToken,
                        query,
                        batch
                    )

                    if (!response.isSuccessful) {
                        _errorMessage.value = ApiErrors.messageFor(
                            response,
                            fallback =
                                "Unable to load all search results. Please try again."
                        )
                        return@launch
                    }

                    val nextBatch = response.body() ?: emptyList()
                    val newUsers = nextBatch.filter { user ->
                        seenUsernames.add(user.username)
                    }

                    results.addAll(newUsers)

                    if (nextBatch.size < 10 || newUsers.isEmpty()) {
                        break
                    }

                    batch++
                }

                // Don't publish old results if the user changed the query
                // while the remaining batches were loading.
                if (_searchText.value.trim() == query) {
                    _allSearchResults.value = results
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(
                    e,
                    fallback =
                        "Unable to load all search results. Try again."
                )
                Log.e(TAG, "Error loading all search results", e)
            } finally {
                _isLoadingAllResults.value = false
            }
        }
    }

    fun clearError() {
        _errorMessage.value = null
    }
}