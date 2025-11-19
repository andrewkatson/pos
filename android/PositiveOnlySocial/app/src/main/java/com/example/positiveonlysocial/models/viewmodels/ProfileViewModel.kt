package com.example.positiveonlysocial.models.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.PostDto
import com.example.positiveonlysocial.data.model.ProfileDto
import com.example.positiveonlysocial.data.model.UserSearchDto
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ProfileViewModel(
    private val user: UserSearchDto, // Using UserSearchDto as the basic User model
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    // Published properties
    private val _userPosts = MutableStateFlow<List<PostDto>>(emptyList())
    val userPosts: StateFlow<List<PostDto>> = _userPosts.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _canLoadMore = MutableStateFlow(true)
    val canLoadMore: StateFlow<Boolean> = _canLoadMore.asStateFlow()

    private val _profileDetails = MutableStateFlow<ProfileDto?>(null)
    val profileDetails: StateFlow<ProfileDto?> = _profileDetails.asStateFlow()

    private val _isLoadingProfile = MutableStateFlow(false)
    val isLoadingProfile: StateFlow<Boolean> = _isLoadingProfile.asStateFlow()

    private val _isFollowing = MutableStateFlow(false)
    val isFollowing: StateFlow<Boolean> = _isFollowing.asStateFlow()

    private var batch = 0
    private val service = "positive-only-social.Positive-Only-Social"

    fun fetchUserPosts() {
        if (_isLoading.value || !_canLoadMore.value) return

        _isLoading.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)

                val response = api.getPostsForUser(userSession.sessionToken, user.username, batch)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        _canLoadMore.value = false
                    } else {
                        _userPosts.value += newPosts
                        batch += 1
                    }
                } else {
                    println("Error fetching user posts: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                println("Error fetching user posts: $e")
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun fetchProfileDetails() {
        if (_isLoadingProfile.value) return
        _isLoadingProfile.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)

                val response = api.getProfileDetails(userSession.sessionToken, user.username)
                if (response.isSuccessful) {
                    val details = response.body()
                    _profileDetails.value = details
                    _isFollowing.value = details?.isFollowing == true
                } else {
                    println("Error fetching profile details: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                println("Error fetching profile details: $e")
            } finally {
                _isLoadingProfile.value = false
            }
        }
    }

    fun toggleFollow() {
        if (_isLoadingProfile.value) return
        _isLoadingProfile.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)

                if (_isFollowing.value) {
                    val response = api.unfollowUser(userSession.sessionToken, user.username)
                    if (response.isSuccessful) {
                        _isFollowing.value = false
                        _profileDetails.value = _profileDetails.value?.let {
                            it.copy(followerCount = it.followerCount - 1)
                        }
                    }
                } else {
                    val response = api.followUser(userSession.sessionToken, user.username)
                    if (response.isSuccessful) {
                        _isFollowing.value = true
                        _profileDetails.value = _profileDetails.value?.let {
                            it.copy(followerCount = it.followerCount + 1)
                        }
                    }
                }
            } catch (e: Exception) {
                println("Error toggling follow: $e")
            } finally {
                _isLoadingProfile.value = false
            }
        }
    }
}
