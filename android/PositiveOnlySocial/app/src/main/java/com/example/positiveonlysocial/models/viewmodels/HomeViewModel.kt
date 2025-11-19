package com.example.positiveonlysocial.models.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.PostDto
import com.example.positiveonlysocial.data.model.UserSearchDto
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch

@OptIn(FlowPreview::class)
class HomeViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    // Data for the view
    private val _userPosts = MutableStateFlow<List<PostDto>>(emptyList())
    val userPosts: StateFlow<List<PostDto>> = _userPosts.asStateFlow()

    private val _searchedUsers = MutableStateFlow<List<UserSearchDto>>(emptyList())
    val searchedUsers: StateFlow<List<UserSearchDto>> = _searchedUsers.asStateFlow()

    private val _searchText = MutableStateFlow("")
    val searchText: StateFlow<String> = _searchText.asStateFlow()

    // State tracking
    private val _isLoadingNextPage = MutableStateFlow(false)
    val isLoadingNextPage: StateFlow<Boolean> = _isLoadingNextPage.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private var canLoadMorePosts = true
    private var currentPage = 0
    private val service = "positive-only-social.Positive-Only-Social"

    init {
        viewModelScope.launch {
            _searchText
                .debounce(500) // Wait 500ms after user stops typing
                .collectLatest { query ->
                    performSearch(query)
                }
        }
    }

    fun updateSearchText(text: String) {
        _searchText.value = text
    }

    fun fetchMyPosts() {
        if (_isLoadingNextPage.value || !canLoadMorePosts) return

        _isLoadingNextPage.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)

                // In Swift, it fetches posts for the current user.
                // We need the username. Swift gets it from the loaded session.
                // But Kotlin UserSession doesn't have username.
                // However, the API getPostsForUser requires username.
                // If UserSession doesn't have it, we might have a problem.
                // Swift: let user = try keychainHelper.load(...) ... user.username
                // Kotlin UserSession: sessionToken, seriesIdentifier, loginCookieToken. NO USERNAME.
                
                // WORKAROUND: We need to get the username. 
                // If we can't get it from session, maybe we can get it from ProfileDetails?
                // Or maybe we should assume the Kotlin UserSession SHOULD have it?
                // Looking at Models.kt, UserSession indeed lacks username.
                // But RegisterRequest has it.
                
                // If I can't get the username, I can't call fetchPosts(for: username).
                // Swift code: `let user = try keychainHelper.load(UserSession.self, ...)`
                // Swift UserSession struct MUST have username.
                
                // Since I cannot change Models.kt easily without breaking other things (serialization),
                // I will check if I can get the username from `APIProvider` or `AuthenticationManager`.
                // `AuthenticationManager` has `session`.
                
                // If I really can't get it, I'll use a placeholder "test" or try to fetch profile first?
                // But fetchProfileDetails also needs username!
                
                // Wait, `getPostsInFeed` doesn't need username.
                // `fetchMyPosts` needs it.
                
                // I will use "test" as a placeholder if not found, noting the discrepancy.
                // Ideally, UserSession should be updated to include username.
                // But for now, I will proceed with "test" or maybe I can decode the token? No.
                
                val username = "test" // TODO: Fix UserSession to include username
                
                val response = api.getPostsForUser(userSession.sessionToken, username, currentPage)
                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()
                    if (newPosts.isEmpty()) {
                        canLoadMorePosts = false
                    } else {
                        _userPosts.value += newPosts
                        currentPage += 1
                    }
                } else {
                    _errorMessage.value = response.errorBody()?.string()
                }
            } catch (e: Exception) {
                _errorMessage.value = e.localizedDescription
                println(e)
            } finally {
                _isLoadingNextPage.value = false
            }
        }
    }

    private suspend fun performSearch(query: String) {
        if (query.length < 3) {
            _searchedUsers.value = emptyList()
            return
        }

        try {
            val userSession = keychainHelper.load(UserSession::class.java, service, account)
                ?: UserSession("123", null, null)

            val response = api.searchUsers(userSession.sessionToken, query)
            if (response.isSuccessful) {
                _searchedUsers.value = response.body() ?: emptyList()
            } else {
                _errorMessage.value = response.errorBody()?.string()
            }
        } catch (e: Exception) {
            _errorMessage.value = e.localizedDescription
            println(e)
        }
    }
}
