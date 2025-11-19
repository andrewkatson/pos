package com.example.positiveonlysocial.models.viewmodels

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

class FeedViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _feedPosts = MutableStateFlow<List<Post>>(emptyList())
    val feedPosts: StateFlow<List<Post>> = _feedPosts.asStateFlow()

    private val _isLoadingNextPage = MutableStateFlow(false)
    val isLoadingNextPage: StateFlow<Boolean> = _isLoadingNextPage.asStateFlow()

    private var canLoadMore = true
    private var currentPage = 0
    private val service = "positive-only-social.Positive-Only-Social"

    fun fetchFeed() {
        if (_isLoadingNextPage.value || !canLoadMore) return

        _isLoadingNextPage.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)

                val response = api.getPostsInFeed(userSession.sessionToken, currentPage)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        _feedPosts.value += newPosts
                        currentPage += 1
                    }
                } else {
                    println("Failed to fetch feed: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                println("Failed to fetch feed: $e")
            } finally {
                _isLoadingNextPage.value = false
            }
        }
    }
}
