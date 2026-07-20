package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.util.PostEvents
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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

    // Reconciling async post classification (issue #282): a short bounded poll
    // runs while any of the user's own posts is pending, then stops; the
    // ordinary mount/pull-to-refresh reload is the backstop after that. A
    // rejection surfaces once through `reviewNotice`.
    private val _reviewNotice = MutableStateFlow<String?>(null)
    val reviewNotice: StateFlow<String?> = _reviewNotice.asStateFlow()

    private var statusPollJob: Job? = null
    private var statusPollAttempts = 0
    // ~30s of checks, 3s apart. Internal so tests can shorten the interval.
    var statusPollIntervalMs = 3000L
    private val statusPollMaxAttempts = 10
    /** At most this many pending posts are polled per round (see
     * startStatusPollIfNeeded for the rate-limit math). */
    private val statusPollMaxPosts = 3

    fun dismissReviewNotice() {
        _reviewNotice.value = null
    }

    init {
        viewModelScope.launch {
            _searchText
                .debounce(500) // Wait 500ms after user stops typing
                .collectLatest { query ->
                    performSearch(query)
                }
        }

        // When a post is deleted (from its detail screen, which lives in a
        // different nav entry), drop it from the grid so its now-missing image
        // doesn't linger as an empty black tile until logout (issue #256).
        viewModelScope.launch {
            PostEvents.deletedPostIds.collect { deletedId ->
                _userPosts.value = _userPosts.value.filterNot { it.postIdentifier == deletedId }
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
                    // A fresh first page grants a fresh reconcile-poll budget (#282).
                    statusPollAttempts = 0
                    startStatusPollIfNeeded()
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Something went wrong. Please try again.")
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
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
                    startStatusPollIfNeeded()
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Something went wrong. Please try again.")
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
                Log.e(TAG, "Error fetching my posts", e)
            } finally {
                _isLoadingNextPage.value = false
            }
        }
    }

    /**
     * Starts (or continues) the short bounded status poll (#282) when any of
     * the user's own posts is still pending classification. No-op when nothing
     * is pending, a poll is already scheduled, or the budget is spent.
     */
    private fun startStatusPollIfNeeded() {
        // The grid is newest-first, so this polls the most recent pending
        // posts; the cap keeps the worst case (3 posts every 3s = 60
        // requests/min) inside the status endpoint's 120/m per-user rate
        // limit, and older pending posts reconcile on refresh.
        val pendingIds = _userPosts.value.filter { it.status == "pending" }
            .take(statusPollMaxPosts)
            .map { it.postIdentifier }
        if (pendingIds.isEmpty() || statusPollJob != null || statusPollAttempts >= statusPollMaxAttempts) return

        statusPollJob = viewModelScope.launch {
            delay(statusPollIntervalMs)
            // Clear before polling so the poll round itself can re-arm the
            // next round (directly or via the reload it triggers).
            statusPollJob = null
            statusPollAttempts += 1
            pollPendingStatuses(pendingIds)
        }
    }

    /**
     * One poll round (#282): check each pending post's status. When any has
     * resolved, reload the grid (approved posts lose their badge; final
     * rejections drop out) and surface a rejection notice; otherwise re-arm
     * the timer within the budget.
     */
    private suspend fun pollPendingStatuses(pendingIds: List<String>) {
        val userSession = keychainHelper.load(UserSession::class.java, service, account) ?: return

        var anyResolved = false
        for (postId in pendingIds) {
            try {
                val response = api.getPostStatus(userSession.sessionToken, postId)
                val body = response.body()
                if (response.isSuccessful && body != null && body.status != "pending") {
                    anyResolved = true
                    if (body.status == "rejected" || body.status == "rejected_final") {
                        _reviewNotice.value = body.message
                            ?: "One of your recent posts did not pass automated review."
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error polling post status for $postId", e)
            }
        }

        if (anyResolved) {
            refreshMyPosts()
        } else {
            startStatusPollIfNeeded()
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
                _errorMessage.value = ApiErrors.messageFor(response, fallback = "Something went wrong. Please try again.")
            }
        } catch (e: Exception) {
            _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            Log.e(TAG, "Error performing search", e)
        }
    }
}
