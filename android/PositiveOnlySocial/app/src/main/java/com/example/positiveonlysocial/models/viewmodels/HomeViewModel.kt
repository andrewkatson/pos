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
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

private const val TAG = "HomeViewModel"
private const val SEARCH_BATCH_SIZE = 10
// Bound requests even if a server keeps returning full pages indefinitely.
private const val MAX_SEARCH_BATCHES = 100

/**
 * Backs the first bottom-nav destination, which is now the signed-in user's own
 * profile (issue #347). The profile itself — stats and post grid — is rendered by
 * the shared profile body against [ProfileViewModel]; this view model owns only
 * the user-search bar above it, plus [currentUsername] so the screen knows whose
 * profile to show.
 *
 * The search endpoint is rate-limited (30 requests per minute per user), so
 * "View all results" never loops over every batch: it shows what is already
 * fetched and [loadMoreSearchResults] pages one further batch per press.
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

    // Whether the "View all results" dialog can page in another batch.
    private val _canLoadMoreResults = MutableStateFlow(false)
    val canLoadMoreResults: StateFlow<Boolean> =
        _canLoadMoreResults.asStateFlow()

    private val _searchText = MutableStateFlow("")
    val searchText: StateFlow<String> = _searchText.asStateFlow()

    // The signed-in user, i.e. whose profile this destination shows.
    private val _currentUsername = MutableStateFlow<String?>(null)
    val currentUsername: StateFlow<String?> = _currentUsername.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    // Bumped whenever the effective (trimmed) query changes. Requests capture it
    // and only touch state while it is unchanged, so a cancelled or superseded
    // request can never clear a newer query's loading state or results.
    private var searchGeneration = 0

    private var prefetchedSecondBatch: List<User> = emptyList()
    private var prefetchedSecondBatchQuery: String? = null
    private var prefetchedSecondBatchRawSize: Int? = null
    private var nextResultsBatch = 1
    private var loadMoreJob: Job? = null

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
                .map { it.trim() }
                // Trim-equivalent edits (e.g. a trailing space) keep the
                // in-flight search instead of restarting it.
                .distinctUntilChanged()
                .debounce(500) // Wait 500ms after user stops typing.
                .collectLatest { query ->
                    performSearch(query)
                }
        }
    }

    fun updateSearchText(text: String) {
        val trimmedText = text.trim()
        val queryChanged = trimmedText != _searchText.value.trim()
        _searchText.value = text

        if (!queryChanged) return

        searchGeneration++
        loadMoreJob?.cancel()
        loadMoreJob = null
        _isLoadingAllResults.value = false
        _canLoadMoreResults.value = false
        _searchedUsers.value = emptyList()
        _errorMessage.value = null
        _hasMoreResults.value = false
        _allSearchResults.value = emptyList()
        _isSearching.value = trimmedText.length >= 3
        prefetchedSecondBatch = emptyList()
        prefetchedSecondBatchQuery = null
        prefetchedSecondBatchRawSize = null
        nextResultsBatch = 1
    }

    private suspend fun performSearch(trimmedQuery: String) {
        // A newer query is already on its way through the debounce.
        if (_searchText.value.trim() != trimmedQuery) return

        val generation = searchGeneration
        fun isCurrent() = generation == searchGeneration

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

            if (!isCurrent()) return

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
            // Show the first batch now; the check for more results below must
            // not hold it back.
            _isSearching.value = false

            if (results.size != SEARCH_BATCH_SIZE) {
                _hasMoreResults.value = false
                return
            }

            try {
                val nextResponse = api.searchUsers(
                    userSession.sessionToken,
                    trimmedQuery,
                    1
                )

                if (!isCurrent()) return

                if (!nextResponse.isSuccessful) {
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
                if (!isCurrent()) return
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
            if (!isCurrent()) return
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
            if (isCurrent()) {
                _isSearching.value = false
            }
        }
    }

    /**
     * Opens "View all results": shows the batches already fetched (the inline
     * first batch plus the prefetched second one). Only when that prefetch
     * failed does it request a batch, to retry it. Reopening the dialog for the
     * same query keeps everything already paged in.
     */
    fun loadAllSearchResults() {
        val query = _searchText.value.trim()

        if (query.length < 3 || _isLoadingAllResults.value) return
        if (_allSearchResults.value.isNotEmpty()) return

        val results = _searchedUsers.value.toMutableList()
        val cachedSecondBatch =
            if (prefetchedSecondBatchQuery == query) prefetchedSecondBatch else null

        if (cachedSecondBatch != null) {
            results.addAll(cachedSecondBatch)
            nextResultsBatch = 2
            _allSearchResults.value = results
            _canLoadMoreResults.value =
                prefetchedSecondBatchRawSize == SEARCH_BATCH_SIZE
        } else {
            nextResultsBatch = 1
            _allSearchResults.value = results
            _canLoadMoreResults.value = false
            loadNextResultsBatch(query)
        }
    }

    /** Pages one further batch into the "View all results" list. */
    fun loadMoreSearchResults() {
        val query = _searchText.value.trim()

        if (
            query.length < 3 ||
            _isLoadingAllResults.value ||
            !_canLoadMoreResults.value
        ) {
            return
        }

        loadNextResultsBatch(query)
    }

    private fun loadNextResultsBatch(query: String) {
        val generation = searchGeneration
        fun isCurrent() = generation == searchGeneration
        val batch = nextResultsBatch

        _isLoadingAllResults.value = true

        loadMoreJob = viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(
                    UserSession::class.java,
                    service,
                    account
                )

                if (userSession == null) {
                    if (isCurrent()) {
                        _errorMessage.value = Constants.SESSION_MISSING_MESSAGE
                    }
                    Log.e(
                        TAG,
                        "No active session found — cannot load search results"
                    )
                    return@launch
                }

                val response = api.searchUsers(
                    userSession.sessionToken,
                    query,
                    batch
                )

                if (!isCurrent()) return@launch

                if (!response.isSuccessful) {
                    // Keep the pages already shown; Load more retries this one.
                    _canLoadMoreResults.value = true
                    _errorMessage.value = ApiErrors.messageFor(
                        response,
                        fallback =
                            "Unable to load more search results. Please try again."
                    )
                    return@launch
                }

                val rawBatch = response.body() ?: emptyList()
                val seenUsernames =
                    _allSearchResults.value.mapTo(mutableSetOf()) { it.username }
                val newUsers = rawBatch.filter { user ->
                    seenUsernames.add(user.username)
                }

                _allSearchResults.value = _allSearchResults.value + newUsers
                nextResultsBatch = batch + 1

                // Only the raw page size indicates the end of pagination; a
                // full page of known users can precede more new users.
                val pageWasFull = rawBatch.size == SEARCH_BATCH_SIZE
                if (pageWasFull && nextResultsBatch >= MAX_SEARCH_BATCHES) {
                    _canLoadMoreResults.value = false
                    _errorMessage.value =
                        "Unable to load more search results. Try a more specific search."
                } else {
                    _canLoadMoreResults.value = pageWasFull
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (!isCurrent()) return@launch
                _canLoadMoreResults.value = true
                _errorMessage.value = ApiErrors.messageFor(
                    e,
                    fallback = "Unable to load more search results. Try again."
                )
                Log.e(TAG, "Error loading more search results", e)
            } finally {
                if (isCurrent()) _isLoadingAllResults.value = false
            }
        }
    }

    fun clearError() {
        _errorMessage.value = null
    }
}
