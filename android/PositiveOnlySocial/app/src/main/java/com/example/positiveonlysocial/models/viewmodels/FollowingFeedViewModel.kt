package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
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
    fun refreshFollowingFeed() {
        if (_isRefreshing.value || _isLoadingNextPage.value) return

        _isRefreshing.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot refresh following feed")
                    return@launch
                }

                val response = api.getFollowedPosts(userSession.sessionToken, 0)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    _followingPosts.value = newPosts
                    canLoadMore = newPosts.isNotEmpty()
                    currentPage = if (newPosts.isEmpty()) 0 else 1
                } else {
                    Log.e(TAG, "Failed to refresh following feed: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to refresh following feed", e)
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
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch following feed")
                    return@launch
                }

                val response = api.getFollowedPosts(userSession.sessionToken, currentPage)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        _followingPosts.value += newPosts
                        currentPage += 1
                    }
                } else {
                    Log.e(TAG, "Failed to fetch following feed: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch following feed", e)
            } finally {
                _isLoadingNextPage.value = false
            }
        }
    }
}
