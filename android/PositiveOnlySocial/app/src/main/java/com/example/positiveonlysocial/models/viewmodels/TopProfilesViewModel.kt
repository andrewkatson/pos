package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.TopProfile
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "TopProfilesViewModel"

/**
 * The Profiles board in the Feed tab's Top segment: the public accounts with the
 * most followers, all-time (issue #588). Pages like [TopPostsViewModel], minus
 * the period picker.
 */
class TopProfilesViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _topProfiles = MutableStateFlow<List<TopProfile>>(emptyList())
    val topProfiles: StateFlow<List<TopProfile>> = _topProfiles.asStateFlow()

    private val _isLoadingNextPage = MutableStateFlow(false)
    val isLoadingNextPage: StateFlow<Boolean> = _isLoadingNextPage.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    /** Why the board is empty, when a load failed rather than there being no one to rank. */
    private val _loadError = MutableStateFlow<String?>(null)
    val loadError: StateFlow<String?> = _loadError.asStateFlow()

    private val _reachedEnd = MutableStateFlow(false)
    /** True once a page comes back empty: the whole board is loaded. */
    val reachedEnd: StateFlow<Boolean> = _reachedEnd.asStateFlow()

    private var canLoadMore = true
        set(value) {
            field = value
            _reachedEnd.value = !value
        }
    private var currentPage = 0

    private val _refreshRevision = MutableStateFlow(0)
    /**
     * Bumped by every successful refresh. A refresh that returns the same first
     * page leaves the last row and the list size unchanged, so the screen keys
     * its pagination effect on this too, or it would never ask for page 1 again
     * (and a short board would lose its end banner).
     */
    val refreshRevision: StateFlow<Int> = _refreshRevision.asStateFlow()
    private val service = "positive-only-social.Positive-Only-Social"

    /** Pull-to-refresh: reloads the board from the first page. */
    fun refreshTopProfiles() {
        if (_isRefreshing.value || _isLoadingNextPage.value) return
        _isRefreshing.value = true

        viewModelScope.launch {
            try {
                val userSession = loadSession()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot refresh top profiles")
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }
                val response = api.getTopProfiles(userSession.sessionToken, 0)
                if (response.isSuccessful) {
                    val newProfiles = response.body() ?: emptyList()
                    _topProfiles.value = newProfiles
                    canLoadMore = newProfiles.isNotEmpty()
                    currentPage = if (newProfiles.isEmpty()) 0 else 1
                    _refreshRevision.value += 1
                    _loadError.value = null
                } else {
                    // Resolve the message before logging: the error body is a
                    // one-shot stream.
                    val message = ApiErrors.messageFor(response, fallback = TOP_PROFILES_LOAD_FAILED)
                    Log.e(TAG, "Failed to refresh top profiles: ${response.code()} $message")
                    _loadError.value = message
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to refresh top profiles", e)
                _loadError.value = ApiErrors.messageFor(e, fallback = TOP_PROFILES_LOAD_FAILED)
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    fun fetchTopProfiles() {
        if (_isLoadingNextPage.value || _isRefreshing.value || !canLoadMore) return
        _isLoadingNextPage.value = true

        viewModelScope.launch {
            try {
                val userSession = loadSession()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch top profiles")
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }
                while (true) {
                    val response = api.getTopProfiles(userSession.sessionToken, currentPage)
                    if (!response.isSuccessful) {
                        val message = ApiErrors.messageFor(response, fallback = TOP_PROFILES_LOAD_FAILED)
                        Log.e(TAG, "Failed to fetch top profiles: ${response.code()} $message")
                        _loadError.value = message
                        break
                    }
                    _loadError.value = null
                    val newProfiles = response.body() ?: emptyList()
                    if (newProfiles.isEmpty()) {
                        canLoadMore = false
                        break
                    }
                    // Live OFFSET paging can repeat an account whose rank moved
                    // between requests; drop repeats so rows stay unique.
                    val seen = _topProfiles.value.mapTo(HashSet()) { it.username }
                    val unseen = newProfiles.filterNot { it.username in seen }
                    currentPage += 1
                    if (unseen.isNotEmpty()) {
                        _topProfiles.value += unseen
                        break
                    }
                    // A page of nothing but repeats: keep going so the last
                    // row's pagination effect has something new to key on.
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch top profiles", e)
                _loadError.value = ApiErrors.messageFor(e, fallback = TOP_PROFILES_LOAD_FAILED)
            } finally {
                _isLoadingNextPage.value = false
            }
        }
    }

    /** See [FeedViewModel.loadSession] — a read that throws is "no session" too. */
    private fun loadSession(): UserSession? = try {
        keychainHelper.load(UserSession::class.java, service, account)
    } catch (e: Exception) {
        Log.e(TAG, "Failed to read the stored session", e)
        null
    }
}

private const val TOP_PROFILES_LOAD_FAILED =
    "We couldn't load this board. Pull down to try again."
