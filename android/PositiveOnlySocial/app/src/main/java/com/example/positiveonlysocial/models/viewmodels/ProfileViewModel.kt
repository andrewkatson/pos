package com.example.positiveonlysocial.models.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.ProfileDetailsResponse
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ProfileViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    // Published properties
    private val _profileDetails = MutableStateFlow<ProfileDetailsResponse?>(null)
    val profileDetails: StateFlow<ProfileDetailsResponse?> = _profileDetails.asStateFlow()

    private val _userPosts = MutableStateFlow<List<Post>>(emptyList())
    val userPosts: StateFlow<List<Post>> = _userPosts.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _isFollowing = MutableStateFlow(false)
    val isFollowing: StateFlow<Boolean> = _isFollowing.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    // Pagination state
    private var currentPage = 0
    private var canLoadMore = true

    fun fetchProfile(username: String) {
        _isLoading.value = true
        _errorMessage.value = null

        // Reset pagination state when loading a new profile
        currentPage = 0
        canLoadMore = true
        _userPosts.value = emptyList() // Clear old posts immediately

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)

                // Fetch Profile Details
                val profileResponse = api.getProfileDetails(userSession.sessionToken, username)
                if (profileResponse.isSuccessful) {
                    _profileDetails.value = profileResponse.body()
                } else {
                    _errorMessage.value = "Failed to load profile: ${profileResponse.errorBody()?.string()}"
                }

                // Fetch Initial User Posts (Page 0)
                val postsResponse = api.getPostsForUser(userSession.sessionToken, username, 0)
                if (postsResponse.isSuccessful) {
                    val newPosts = postsResponse.body() ?: emptyList()
                    _userPosts.value = newPosts

                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        currentPage += 1
                    }
                } else {
                    if (_errorMessage.value == null) {
                        _errorMessage.value = "Failed to load posts: ${postsResponse.errorBody()?.string()}"
                    }
                }

            } catch (e: Exception) {
                _errorMessage.value = "Error: ${e.localizedMessage}"
                println(e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun fetchUserPosts(username: String) {
        // Guard against multiple fetches or if end is reached
        if (_isLoading.value || !canLoadMore) return

        _isLoading.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)

                val response = api.getPostsForUser(userSession.sessionToken, username, currentPage)

                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()

                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        // Append new posts to existing list
                        _userPosts.value += newPosts
                        currentPage += 1
                    }
                } else {
                    println("Failed to fetch more posts: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                println("Error fetching more posts: ${e.localizedMessage}")
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun toggleFollow(username: String) {
        val currentProfile = _profileDetails.value ?: return
        val isFollowing = currentProfile.isFollowing

        // Optimistic Update
        _profileDetails.value = currentProfile.copy(
            isFollowing = !isFollowing,
            followerCount = if (isFollowing) currentProfile.followerCount - 1 else currentProfile.followerCount + 1
        )

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)

                val response = if (isFollowing) {
                    api.unfollowUser(userSession.sessionToken, username)
                } else {
                    api.followUser(userSession.sessionToken, username)
                }

                if (!response.isSuccessful) {
                    // Revert on failure
                    _profileDetails.value = currentProfile
                    _errorMessage.value = "Failed to update follow status"
                }
            } catch (e: Exception) {
                // Revert on error
                _profileDetails.value = currentProfile
                _errorMessage.value = "Error: ${e.localizedMessage}"
            }
        }
    }
}