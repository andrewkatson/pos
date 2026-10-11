package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.TopPostPeriod
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "TopPostsViewModel"

/**
 * The "Top" feed: the scoreboard of the most-liked public posts across the app
 * over a chosen period (issue #558). Mirrors [FollowingFeedViewModel], with the
 * time period in place of the group filter.
 */
class TopPostsViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _topPosts = MutableStateFlow<List<Post>>(emptyList())
    val topPosts: StateFlow<List<Post>> = _topPosts.asStateFlow()

    private val _isLoadingNextPage = MutableStateFlow(false)
    val isLoadingNextPage: StateFlow<Boolean> = _isLoadingNextPage.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    /**
     * Why the feed is empty, when it's empty because something went wrong rather
     * than because there is nothing to show (issue #503). Mirrors [FeedViewModel].
     */
    private val _loadError = MutableStateFlow<String?>(null)
    val loadError: StateFlow<String?> = _loadError.asStateFlow()

    private val _selectedPeriod = MutableStateFlow(TopPostPeriod.WEEK)
    val selectedPeriod: StateFlow<TopPostPeriod> = _selectedPeriod.asStateFlow()

    /**
     * Like / report / retract-report / delete for the posts in this feed, so they
     * can be acted on without opening each one.
     */
    val postActions =
        PostListActions(api, keychainHelper, viewModelScope, _topPosts, account)

    private var canLoadMore = true
    private var currentPage = 0
    private val service = "positive-only-social.Positive-Only-Social"

    // Bumped when the period changes, so a load still in flight for the old
    // period can recognise it has been superseded and drop its response rather
    // than fill the list under the new selection.
    private var loadGeneration = 0
    private var loadJob: Job? = null

    /**
     * Switches the time period and reloads from the first page. A no-op when the
     * period is unchanged so re-selecting doesn't refetch.
     */
    fun selectPeriod(period: TopPostPeriod) {
        if (period == _selectedPeriod.value) return
        _selectedPeriod.value = period
        // Supersede any in-flight load: its response belongs to the old period,
        // and its loading flag would otherwise make the refresh below a no-op.
        loadGeneration += 1
        loadJob?.cancel()
        _isLoadingNextPage.value = false
        _isRefreshing.value = false
        // Clear the old board rather than leaving it under the new chip: its
        // rows would otherwise be reused for the new page, so the last row's
        // pagination effect wouldn't fire again and page 1 would never load.
        _topPosts.value = emptyList()
        canLoadMore = true
        currentPage = 0
        refreshTopPosts()
    }

    /**
     * Pull-to-refresh: resets pagination and reloads the scoreboard from the
     * first page, replacing the existing posts.
     */
    fun refreshTopPosts() {
        if (_isRefreshing.value || _isLoadingNextPage.value) return

        _isRefreshing.value = true

        val generation = loadGeneration
        loadJob = viewModelScope.launch {
            try {
                val userSession = loadSession()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot refresh top posts")
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }

                val response = api.getTopPosts(userSession.sessionToken, 0, _selectedPeriod.value.value)
                if (generation != loadGeneration) return@launch
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    _topPosts.value = newPosts
                    canLoadMore = newPosts.isNotEmpty()
                    currentPage = if (newPosts.isEmpty()) 0 else 1
                    _loadError.value = null
                } else {
                    // Resolve the message before logging: the error body is a
                    // one-shot stream, so reading it here would leave ApiErrors
                    // nothing to extract the backend's own wording from.
                    val message = ApiErrors.messageFor(response, fallback = TOP_POSTS_LOAD_FAILED)
                    Log.e(TAG, "Failed to refresh top posts: ${response.code()} $message")
                    _loadError.value = message
                }
            } catch (e: CancellationException) {
                // The scope going away isn't a load failure, and must not leave
                // an error message behind on the way out.
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to refresh top posts", e)
                if (generation == loadGeneration) {
                    _loadError.value = ApiErrors.messageFor(e, fallback = TOP_POSTS_LOAD_FAILED)
                }
            } finally {
                // A superseded load leaves the flags to the load that replaced it.
                if (generation == loadGeneration) _isRefreshing.value = false
            }
        }
    }

    fun fetchTopPosts() {
        // Also short-circuit during a pull-to-refresh so pagination can't race
        // the refresh's reset of the feed and pagination cursor.
        if (_isLoadingNextPage.value || _isRefreshing.value || !canLoadMore) return

        _isLoadingNextPage.value = true

        val generation = loadGeneration
        loadJob = viewModelScope.launch {
            try {
                val userSession = loadSession()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch top posts")
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }

                val response = api.getTopPosts(userSession.sessionToken, currentPage, _selectedPeriod.value.value)
                if (generation != loadGeneration) return@launch
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        // Live OFFSET paging can repeat a post whose rank moved
                        // between requests; drop repeats so rows stay unique.
                        val seen = _topPosts.value.mapTo(HashSet()) { it.postIdentifier }
                        _topPosts.value += newPosts.filterNot { it.postIdentifier in seen }
                        currentPage += 1
                    }
                    _loadError.value = null
                } else {
                    // See refreshTopPosts: the message has to be resolved
                    // before the one-shot error body is read for the log.
                    val message = ApiErrors.messageFor(response, fallback = TOP_POSTS_LOAD_FAILED)
                    Log.e(TAG, "Failed to fetch top posts: ${response.code()} $message")
                    _loadError.value = message
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch top posts", e)
                if (generation == loadGeneration) {
                    _loadError.value = ApiErrors.messageFor(e, fallback = TOP_POSTS_LOAD_FAILED)
                }
            } finally {
                if (generation == loadGeneration) _isLoadingNextPage.value = false
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

private const val TOP_POSTS_LOAD_FAILED =
    "We couldn't load this feed. Pull down to try again."
