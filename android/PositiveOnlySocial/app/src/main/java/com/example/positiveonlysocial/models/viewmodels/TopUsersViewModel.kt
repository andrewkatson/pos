package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.TopUser
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "TopUsersViewModel"

/**
 * The Top feed's "People" board: who has the most followers right now
 * (issue #562).
 */
class TopUsersViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _topUsers = MutableStateFlow<List<TopUser>>(emptyList())
    val topUsers: StateFlow<List<TopUser>> = _topUsers.asStateFlow()

    private val _isLoadingNextPage = MutableStateFlow(false)
    val isLoadingNextPage: StateFlow<Boolean> = _isLoadingNextPage.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    private val _loadError = MutableStateFlow<String?>(null)
    val loadError: StateFlow<String?> = _loadError.asStateFlow()

    private var canLoadMore = true
    private var currentPage = 0
    private val service = "positive-only-social.Positive-Only-Social"

    /** Your own row opens the Profile tab rather than a pushed copy of it. */
    val currentUsername: String? get() = loadSession()?.username

    /** Pull-to-refresh: reloads the board from the first page. */
    fun refreshTopUsers() {
        if (_isRefreshing.value || _isLoadingNextPage.value) return
        _isRefreshing.value = true

        viewModelScope.launch {
            try {
                val session = loadSession() ?: run {
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }
                val response = api.getTopUsers(session.sessionToken, 0)
                if (response.isSuccessful) {
                    val rows = response.body() ?: emptyList()
                    _topUsers.value = rows
                    canLoadMore = rows.isNotEmpty()
                    currentPage = if (rows.isEmpty()) 0 else 1
                    _loadError.value = null
                } else {
                    _loadError.value = ApiErrors.messageFor(response, fallback = TOP_USERS_LOAD_FAILED)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to refresh top users", e)
                _loadError.value = ApiErrors.messageFor(e, fallback = TOP_USERS_LOAD_FAILED)
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    fun fetchTopUsers() {
        if (_isLoadingNextPage.value || _isRefreshing.value || !canLoadMore) return
        _isLoadingNextPage.value = true

        viewModelScope.launch {
            try {
                val session = loadSession() ?: run {
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }
                while (true) {
                    val response = api.getTopUsers(session.sessionToken, currentPage)
                    if (!response.isSuccessful) {
                        _loadError.value = ApiErrors.messageFor(response, fallback = TOP_USERS_LOAD_FAILED)
                        break
                    }
                    _loadError.value = null
                    val rows = response.body() ?: emptyList()
                    if (rows.isEmpty()) {
                        canLoadMore = false
                        break
                    }
                    // Live OFFSET paging can repeat someone whose count moved
                    // between requests; drop repeats so rows stay unique, and keep
                    // going past a page of nothing but repeats so the list changes
                    // and the pagination effect restarts.
                    val seen = _topUsers.value.mapTo(HashSet()) { it.username }
                    val unseen = rows.filterNot { it.username in seen }
                    currentPage += 1
                    if (unseen.isNotEmpty()) {
                        _topUsers.value += unseen
                        break
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch top users", e)
                _loadError.value = ApiErrors.messageFor(e, fallback = TOP_USERS_LOAD_FAILED)
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

private const val TOP_USERS_LOAD_FAILED =
    "We couldn't load this board. Pull down to try again."
