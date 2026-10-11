package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.Response

private const val TAG = "FollowRequestsViewModel"

/**
 * Fires after the signed-in user approves or denies a follow request, or changes
 * their private account setting (going public approves every pending request) —
 * issue #96. Their own profile listens so its lock badge, "Follow Requests (n)"
 * badge and follower count refresh when they come back to it — the profile's
 * view model outlives the trip, so it would not reload on its own.
 */
object FollowRequestEvents {
    private val _decisions = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val decisions: SharedFlow<Unit> = _decisions

    fun notifyDecision() {
        _decisions.tryEmit(Unit)
    }
}

/**
 * Loads the signed-in private account's incoming follow requests and approves
 * or denies them (issue #96). Reached from Settings and the owner's profile.
 */
class FollowRequestsViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _requests = MutableStateFlow<List<User>>(emptyList())
    val requests: StateFlow<List<User>> = _requests.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    // Set once a load succeeds, so a failed load shows only its error — never
    // the "no one is waiting" empty state for a list that was never fetched.
    private val _hasLoaded = MutableStateFlow(false)
    val hasLoaded: StateFlow<Boolean> = _hasLoaded.asStateFlow()

    // The list is paginated (a popular account's backlog is unbounded): whether
    // another page may exist, and the next one to fetch.
    private val _canLoadMore = MutableStateFlow(false)
    val canLoadMore: StateFlow<Boolean> = _canLoadMore.asStateFlow()
    private val _isLoadingMore = MutableStateFlow(false)
    // Keyset cursor: the oldest request id loaded so far, kept even if that row
    // is answered meanwhile, so answering rows can't shift a later request out
    // of the next page.
    private var nextCursor: Long? = null

    /**
     * Usernames with an approve/deny in flight, so each row's buttons disable
     * independently (several decisions may overlap).
     */
    private val _decidingUsernames = MutableStateFlow<Set<String>>(emptySet())
    val decidingUsernames: StateFlow<Set<String>> = _decidingUsernames.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    fun clearError() {
        _errorMessage.value = null
    }

    private fun session(): UserSession? =
        keychainHelper.load(UserSession::class.java, service, account)

    /** Loads (or reloads) the incoming requests, newest first. */
    fun load() {
        _isLoading.value = true
        _errorMessage.value = null
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot load follow requests")
                    return@launch
                }
                val response = api.getFollowRequests(userSession.sessionToken, null)
                if (response.isSuccessful) {
                    val page = response.body() ?: emptyList()
                    _requests.value = page
                    nextCursor = page.lastOrNull()?.requestId
                    _canLoadMore.value = page.isNotEmpty()
                    _hasLoaded.value = true
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Request failed. Please try again.")
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Request failed. Please try again.")
                Log.e(TAG, "Error loading follow requests", e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    /**
     * Fetches the next page and appends it, skipping anyone already listed
     * (answering rows shifts later pages up). An empty page ends the list.
     */
    fun loadMore() {
        if (!_canLoadMore.value || _isLoadingMore.value || _isLoading.value) return
        _isLoadingMore.value = true
        viewModelScope.launch {
            try {
                val userSession = session() ?: return@launch
                val response = api.getFollowRequests(userSession.sessionToken, nextCursor)
                if (response.isSuccessful) {
                    val page = response.body() ?: emptyList()
                    val shown = _requests.value.map { it.username }.toSet()
                    _requests.value = _requests.value + page.filterNot { it.username in shown }
                    page.lastOrNull()?.requestId?.let { nextCursor = it }
                    _canLoadMore.value = page.isNotEmpty()
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Request failed. Please try again.")
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Request failed. Please try again.")
                Log.e(TAG, "Error loading more follow requests", e)
            } finally {
                _isLoadingMore.value = false
            }
        }
    }

    /** Approves [username]'s request — they become a follower — and drops the row. */
    fun approve(username: String) = decide(username) { token -> api.approveFollowRequest(token, username) }

    /** Denies [username]'s request and drops the row. The requester isn't told. */
    fun deny(username: String) = decide(username) { token -> api.denyFollowRequest(token, username) }

    private fun decide(username: String, call: suspend (String) -> Response<GenericResponse>) {
        _decidingUsernames.value = _decidingUsernames.value + username
        _errorMessage.value = null
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    _errorMessage.value = "You must be logged in to answer a follow request."
                    return@launch
                }
                val response = call(userSession.sessionToken)
                if (response.isSuccessful) {
                    _requests.value = _requests.value.filterNot { it.username == username }
                    FollowRequestEvents.notifyDecision()
                } else {
                    _errorMessage.value = ApiErrors.messageFor(response, fallback = "Request failed. Please try again.")
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Request failed. Please try again.")
                Log.e(TAG, "Error answering follow request", e)
            } finally {
                _decidingUsernames.value = _decidingUsernames.value - username
            }
        }
    }
}
