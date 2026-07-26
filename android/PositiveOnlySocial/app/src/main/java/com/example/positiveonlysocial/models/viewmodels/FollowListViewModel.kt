package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.Response

private const val TAG = "FollowListViewModel"

/** Which of the two own-lists a [FollowListViewModel] loads. */
enum class FollowListMode(val route: String, val title: String, val emptyMessage: String) {
    FOLLOWERS("followers", "Followers", "You don't have any followers yet."),
    FOLLOWING("following", "Following", "You aren't following anyone yet.");

    companion object {
        /** Parses the navigation `mode` argument, defaulting to followers. */
        fun fromRoute(route: String?): FollowListMode =
            entries.firstOrNull { it.route == route } ?: FOLLOWERS
    }
}

/**
 * Loads the signed-in user's own followers or following list. Only your own
 * lists are ever fetched — the endpoints take no username — so nobody else's
 * followers/following can be viewed (issue #8). Reached by tapping the
 * Followers / Following counts on your own profile.
 */
class FollowListViewModel(
    val mode: FollowListMode,
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _users = MutableStateFlow<List<User>>(emptyList())
    val users: StateFlow<List<User>> = _users.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    /** The signed-in user, so tapping their own row selects the Profile tab
     * rather than pushing a second copy of their profile (issue #347). */
    val currentUsername: String? get() = session()?.username

    fun clearError() {
        _errorMessage.value = null
    }

    private fun session(): UserSession? =
        keychainHelper.load(UserSession::class.java, service, account)

    private fun errorOf(response: Response<*>): String =
        ApiErrors.messageFor(response, fallback = "Request failed. Please try again.")

    /** Loads (or reloads) the list for this mode. */
    fun load() {
        _isLoading.value = true
        _errorMessage.value = null // drop any stale error from a previous load
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot load ${mode.title}")
                    return@launch
                }
                val response = when (mode) {
                    FollowListMode.FOLLOWERS -> api.getFollowers(userSession.sessionToken)
                    FollowListMode.FOLLOWING -> api.getFollowing(userSession.sessionToken)
                }
                if (response.isSuccessful) {
                    _users.value = response.body() ?: emptyList()
                } else {
                    _errorMessage.value = errorOf(response)
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Request failed. Please try again.")
                Log.e(TAG, "Error loading ${mode.title}", e)
            } finally {
                _isLoading.value = false
            }
        }
    }
}
