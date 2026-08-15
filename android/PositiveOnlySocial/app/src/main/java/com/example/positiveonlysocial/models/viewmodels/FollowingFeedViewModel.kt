package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.FollowCategory
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "FollowingFeedViewModel"

class FollowingFeedViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _followingPosts = MutableStateFlow<List<Post>>(emptyList())
    val followingPosts: StateFlow<List<Post>> = _followingPosts.asStateFlow()

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

    // Optional group filter (issue #392): null is the whole following feed.
    private val _selectedCategory = MutableStateFlow<FollowCategory?>(null)
    val selectedCategory: StateFlow<FollowCategory?> = _selectedCategory.asStateFlow()

    /**
     * Like / report / retract-report / delete for the posts in this feed, so they
     * can be acted on without opening each one (issue #267).
     */
    val postActions =
        PostListActions(api, keychainHelper, viewModelScope, _followingPosts, account)

    private var canLoadMore = true
    private var currentPage = 0
    private val service = "positive-only-social.Positive-Only-Social"

    /**
     * Pull-to-refresh: resets pagination and reloads the following feed from the
     * first page, replacing the existing posts with the newest ones from the backend.
     */
    /**
     * Switches the group filter and reloads from the first page (issue #392). A
     * no-op when the category is unchanged so re-selecting doesn't refetch.
     */
    fun selectCategory(category: FollowCategory?) {
        if (category == _selectedCategory.value) return
        _selectedCategory.value = category
        refreshFollowingFeed()
    }

    fun refreshFollowingFeed() {
        if (_isRefreshing.value || _isLoadingNextPage.value) return

        _isRefreshing.value = true

        viewModelScope.launch {
            try {
                val userSession = loadSession()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot refresh following feed")
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }

                val response = api.getFollowedPosts(userSession.sessionToken, 0, _selectedCategory.value?.value)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    _followingPosts.value = newPosts
                    canLoadMore = newPosts.isNotEmpty()
                    currentPage = if (newPosts.isEmpty()) 0 else 1
                    _loadError.value = null
                } else {
                    // Resolve the message before logging: the error body is a
                    // one-shot stream, so reading it here would leave ApiErrors
                    // nothing to extract the backend's own wording from.
                    val message = ApiErrors.messageFor(response, fallback = FOLLOWING_FEED_LOAD_FAILED)
                    Log.e(TAG, "Failed to refresh following feed: ${response.code()} $message")
                    _loadError.value = message
                }
            } catch (e: CancellationException) {
                // The scope going away isn't a load failure, and must not leave
                // an error message behind on the way out.
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to refresh following feed", e)
                _loadError.value = ApiErrors.messageFor(e, fallback = FOLLOWING_FEED_LOAD_FAILED)
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    fun fetchFollowingFeed() {
        // Also short-circuit during a pull-to-refresh so pagination can't race
        // the refresh's reset of the feed and pagination cursor.
        if (_isLoadingNextPage.value || _isRefreshing.value || !canLoadMore) return

        _isLoadingNextPage.value = true

        viewModelScope.launch {
            try {
                val userSession = loadSession()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch following feed")
                    _loadError.value = Constants.SESSION_MISSING_MESSAGE
                    return@launch
                }

                val response = api.getFollowedPosts(userSession.sessionToken, currentPage, _selectedCategory.value?.value)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        _followingPosts.value += newPosts
                        currentPage += 1
                    }
                    _loadError.value = null
                } else {
                    // See refreshFollowingFeed: the message has to be resolved
                    // before the one-shot error body is read for the log.
                    val message = ApiErrors.messageFor(response, fallback = FOLLOWING_FEED_LOAD_FAILED)
                    Log.e(TAG, "Failed to fetch following feed: ${response.code()} $message")
                    _loadError.value = message
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch following feed", e)
                _loadError.value = ApiErrors.messageFor(e, fallback = FOLLOWING_FEED_LOAD_FAILED)
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

private const val FOLLOWING_FEED_LOAD_FAILED =
    "We couldn't load this feed. Pull down to try again."
