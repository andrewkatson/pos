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
import kotlin.collections.emptyList

private const val TAG = "TagFeedViewModel"

/**
 * Drives the tag feed (issue #379): the posts carrying a given #hashtag,
 * paginated. Mirrors FeedViewModel, swapping the feed fetch for the
 * browse-by-tag endpoint.
 */
class TagFeedViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val tag: String,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _posts = MutableStateFlow<List<Post>>(emptyList())
    val posts: StateFlow<List<Post>> = _posts.asStateFlow()

    private val _isLoadingNextPage = MutableStateFlow(false)
    val isLoadingNextPage: StateFlow<Boolean> = _isLoadingNextPage.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    /** Like / report / retract-report / delete for the posts in this tag feed,
     * so they can be acted on without opening each one (issue #267). */
    val postActions = PostListActions(api, keychainHelper, viewModelScope, _posts, account)

    private var canLoadMore = true
    private var currentPage = 0
    private val service = "positive-only-social.Positive-Only-Social"

    fun refresh() {
        if (_isRefreshing.value || _isLoadingNextPage.value) return

        _isRefreshing.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot refresh tag feed")
                    return@launch
                }

                val response = api.getPostsByTag(userSession.sessionToken, tag, 0)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    _posts.value = newPosts
                    canLoadMore = newPosts.isNotEmpty()
                    currentPage = if (newPosts.isEmpty()) 0 else 1
                } else {
                    Log.e(TAG, "Failed to refresh tag feed: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to refresh tag feed", e)
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    fun fetchNextPage() {
        if (_isLoadingNextPage.value || _isRefreshing.value || !canLoadMore) return

        _isLoadingNextPage.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch tag feed")
                    return@launch
                }

                val response = api.getPostsByTag(userSession.sessionToken, tag, currentPage)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        _posts.value += newPosts
                        currentPage += 1
                    }
                } else {
                    Log.e(TAG, "Failed to fetch tag feed: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch tag feed", e)
            } finally {
                _isLoadingNextPage.value = false
            }
        }
    }
}
