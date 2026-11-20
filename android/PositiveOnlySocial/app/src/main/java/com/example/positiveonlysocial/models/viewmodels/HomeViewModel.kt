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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch

private const val TAG = "HomeViewModel"
// Bound requests even if a server keeps returning full pages indefinitely.
private const val MAX_SEARCH_BATCHES = 100

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
    private var prefetchedSecondBatchRawSize: Int? = null
    private var loadAllJob: Job? = null

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
        loadAllJob?.cancel()
        loadAllJob = null
        _isLoadingAllResults.value = false
        val trimmedText = text.trim()

        _searchText.value = text
        _searchedUsers.value = emptyList()
        _errorMessage.value = null
        _hasMoreResults.value = false
        _allSearchResults.value = emptyList()
        _isSearching.value = trimmedText.length >= 3
        prefetchedSecondBatch = emptyList()
        prefetchedSecondBatchQuery = null
        prefetchedSecondBatchRawSize = null
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

            if (_searchText.value.trim() != trimmedQuery) return

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
                prefetchedSecondBatchRawSize = null
                _hasMoreResults.value = false
                return
            }

            try {
                val nextResponse = api.searchUsers(
                    userSession.sessionToken,
                    trimmedQuery,
                    1
                )

                if (_searchText.value.trim() != trimmedQuery) return

                if (!nextResponse.isSuccessful) {
                    prefetchedSecondBatch = emptyList()
                    prefetchedSecondBatchQuery = null
                    prefetchedSecondBatchRawSize = null
                    _hasMoreResults.value = true // Let View All retry this page.
                    return
                }

                val rawNextBatch = nextResponse.body() ?: emptyList()

                val firstBatchUsernames =
                    results.mapTo(mutableSetOf()) { it.username }

                val nextBatch = rawNextBatch.filter { user ->
                    firstBatchUsernames.add(user.username)
                }

                prefetchedSecondBatch = nextBatch
                prefetchedSecondBatchQuery = trimmedQuery
                prefetchedSecondBatchRawSize = rawNextBatch.size
                _hasMoreResults.value = rawNextBatch.isNotEmpty()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (_searchText.value.trim() != trimmedQuery) return
                prefetchedSecondBatch = emptyList()
                prefetchedSecondBatchQuery = null
                prefetchedSecondBatchRawSize = null
                _hasMoreResults.value = true // Retry when View All opens.
                Log.e(
                    TAG,
                    "Error checking for additional search results",
                    e
                )
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            if (_searchText.value.trim() != trimmedQuery) return
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

        loadAllJob = viewModelScope.launch {
            _isLoadingAllResults.value = true

            try {
                val userSession = keychainHelper.load(
                    UserSession::class.java,
                    service,
                    account
                )

                if (userSession == null) {
                    if (_searchText.value.trim() == query) _errorMessage.value = Constants.SESSION_MISSING_MESSAGE
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
                        prefetchedSecondBatchRawSize == 10

                while (shouldLoadAnotherBatch && _searchText.value.trim() == query) {
                    val response = api.searchUsers(
                        userSession.sessionToken,
                        query,
                        batch
                    )

                    if (_searchText.value.trim() != query) return@launch
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

                    // Only the raw page size indicates the end of pagination;
                    // a full page of known users can precede more new users.
                    if (nextBatch.size < 10) {
                        break
                    }

                    if (batch + 1 >= MAX_SEARCH_BATCHES) {
                        _errorMessage.value =
                            "Unable to finish loading all search results. Try a more specific search."
                        return@launch
                    }

                    batch++
                }

                // Don't publish old results if the user changed the query
                // while the remaining batches were loading.
                if (_searchText.value.trim() == query) {
                    _allSearchResults.value = results
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (_searchText.value.trim() != query) return@launch
                _errorMessage.value = ApiErrors.messageFor(
                    e,
                    fallback =
                        "Unable to load all search results. Try again."
                )
                Log.e(TAG, "Error loading all search results", e)
            } finally {
                if (_searchText.value.trim() == query) _isLoadingAllResults.value = false
            }
        }
    }

    fun clearError() {
        _errorMessage.value = null
    }
}
