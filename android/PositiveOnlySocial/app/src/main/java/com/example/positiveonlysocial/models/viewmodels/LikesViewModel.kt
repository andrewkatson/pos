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

private const val TAG = "LikesViewModel"

/**
 * What a [LikesViewModel] is listing the likers of (issue #478). Carries the
 * identifiers rather than a fetch lambda, so the view model owns the paging.
 */
sealed class LikesTarget {
    abstract val title: String

    data class Post(val postIdentifier: String) : LikesTarget() {
        override val title: String get() = "Likes"
    }

    data class Comment(
        val postIdentifier: String,
        val commentThreadIdentifier: String,
        val commentIdentifier: String
    ) : LikesTarget() {
        override val title: String get() = "Comment likes"
    }
}

/**
 * Loads "who liked this" for one of the signed-in user's own posts or comments
 * (issue #478), a batch at a time. Only your own content is ever asked about —
 * the backend answers for nobody else's — so the like count is only tappable on
 * your own post/comment.
 */
class LikesViewModel(
    val target: LikesTarget,
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

    /**
     * Whether another batch might exist. False once a batch comes back empty,
     * or after a failure — the list then stands as "here is what we have"
     * rather than paging into the same error again.
     */
    private val _canLoadMore = MutableStateFlow(false)
    val canLoadMore: StateFlow<Boolean> = _canLoadMore.asStateFlow()

    /** The next batch index to request. 0 until the first batch lands. */
    private var nextBatch = 0

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

    private suspend fun fetch(token: String, batch: Int): Response<List<User>> = when (target) {
        is LikesTarget.Post -> api.getPostLikers(token, target.postIdentifier, batch)
        is LikesTarget.Comment -> api.getCommentLikers(
            token, target.postIdentifier, target.commentThreadIdentifier, target.commentIdentifier, batch
        )
    }

    /** Loads (or reloads) the first batch, discarding anything already listed. */
    fun load() = load(batch = 0, replacing = true)

    /** Appends the next batch, if there is one. */
    fun loadMore() {
        if (!_canLoadMore.value || _isLoading.value) return
        load(batch = nextBatch, replacing = false)
    }

    private fun load(batch: Int, replacing: Boolean) {
        _isLoading.value = true
        _errorMessage.value = null // drop any stale error from a previous load
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot load likes")
                    return@launch
                }
                val response = fetch(userSession.sessionToken, batch)
                if (response.isSuccessful) {
                    val page = response.body() ?: emptyList()
                    _users.value = if (replacing) page else _users.value + page
                    // An empty batch is the end of the list, not an error.
                    _canLoadMore.value = page.isNotEmpty()
                    nextBatch = if (page.isEmpty()) batch else batch + 1
                } else {
                    _errorMessage.value = errorOf(response)
                    _canLoadMore.value = false
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Request failed. Please try again.")
                _canLoadMore.value = false
                Log.e(TAG, "Error loading likes", e)
            } finally {
                _isLoading.value = false
            }
        }
    }
}
