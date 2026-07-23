package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.ReportRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.util.PostEvents
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "PostListActions"

/**
 * Like / report / retract-report / delete for posts shown in a *list* — the feed,
 * the Following feed, and the profile grids — so a post can be acted on without
 * opening it first (issue #267). It offers exactly what the post detail screen
 * offers for a single post, and is shared by every list so they behave
 * identically.
 *
 * The like/report state comes from the listing endpoints themselves
 * (`post_likes` / `is_liked` / `is_reported` / `report_reason`, which they now
 * return alongside the post details endpoint). Actions update the owning list's
 * [posts] flow optimistically and revert that entry on failure, matching
 * [PostDetailViewModel]'s behaviour, so nothing has to be refetched — refetching
 * the feed would reshuffle its weighted ordering under the user.
 *
 * A ViewModel owning a list of posts creates one of these over its own backing
 * flow and exposes it to the screen; the screen renders the shared action bar and
 * the shared dialogs against it.
 */
class PostListActions(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val scope: CoroutineScope,
    private val posts: MutableStateFlow<List<Post>>,
    private val account: String = "userSessionToken"
) {

    private val service = "positive-only-social.Positive-Only-Social"

    // The signed-in user. The backend rejects liking your own post, so the like
    // control is hidden on it and the action menu offers Delete instead of Report.
    private val _currentUsername = MutableStateFlow<String?>(null)
    val currentUsername: StateFlow<String?> = _currentUsername.asStateFlow()

    private val _alertMessage = MutableStateFlow<String?>(null)
    val alertMessage: StateFlow<String?> = _alertMessage.asStateFlow()

    // The post whose action menu (Delete / Retract Report / Report) is showing.
    private val _postForAction = MutableStateFlow<Post?>(null)
    val postForAction: StateFlow<Post?> = _postForAction.asStateFlow()

    // The post whose report dialog / retract-report confirmation is showing.
    private val _postToReport = MutableStateFlow<Post?>(null)
    val postToReport: StateFlow<Post?> = _postToReport.asStateFlow()

    private val _postToRetract = MutableStateFlow<Post?>(null)
    val postToRetract: StateFlow<Post?> = _postToRetract.asStateFlow()

    init {
        _currentUsername.value = loadSession()?.username

        // A delete performed anywhere else (the post detail screen, or another
        // list) announces itself through PostEvents; drop the post here too so
        // its now-missing image doesn't linger as an empty black tile (issue #256).
        scope.launch {
            PostEvents.deletedPostIds.collect { deletedId -> removeLocally(deletedId) }
        }
    }

    /** Whether [post] was authored by the signed-in user. */
    fun isOwnPost(post: Post): Boolean {
        val username = _currentUsername.value ?: return false
        return post.authorUsername == username
    }

    fun dismissAlert() {
        _alertMessage.value = null
    }

    fun setPostForAction(post: Post?) {
        // Re-read the post from the list so the menu (and the retract dialog it
        // opens) sees the freshest report state rather than a stale snapshot.
        _postForAction.value = post?.let { currentVersionOf(it) ?: it }
    }

    fun setPostToReport(post: Post?) {
        _postToReport.value = post?.let { currentVersionOf(it) ?: it }
    }

    fun setPostToRetract(post: Post?) {
        _postToRetract.value = post?.let { currentVersionOf(it) ?: it }
    }

    /**
     * Likes or unlikes [post], depending on its current server-backed like state.
     * The count and heart update immediately and revert if the request fails.
     */
    fun toggleLike(post: Post) {
        // The backend rejects liking your own post; the control isn't rendered
        // for it, but guard anyway so a stray call can't desync the count.
        if (isOwnPost(post)) return

        val current = currentVersionOf(post) ?: return
        val wasLiked = current.isLiked
        val previousCount = current.likeCount ?: 0
        val liking = !wasLiked

        applyLike(post.postIdentifier, liking, if (liking) previousCount + 1 else maxOf(0, previousCount - 1))

        scope.launch {
            val token = sessionToken()
            if (token == null) {
                applyLike(post.postIdentifier, wasLiked, previousCount)
                return@launch
            }
            try {
                val response = if (liking) {
                    api.likePost(token, post.postIdentifier)
                } else {
                    api.unlikePost(token, post.postIdentifier)
                }
                if (!response.isSuccessful) {
                    applyLike(post.postIdentifier, wasLiked, previousCount)
                    _alertMessage.value = ApiErrors.messageFor(
                        response,
                        fallback = if (liking) "Failed to like the post. Please try again."
                        else "Failed to unlike the post. Please try again."
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to toggle like on post", e)
                applyLike(post.postIdentifier, wasLiked, previousCount)
                _alertMessage.value =
                    ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    /** Files a report against [post] with [reason]. */
    fun reportPost(post: Post, reason: String) {
        val current = currentVersionOf(post) ?: return
        val wasReported = current.isReported
        val previousReason = current.reportReason

        applyReport(post.postIdentifier, isReported = true, reason = reason)

        scope.launch {
            val token = sessionToken()
            if (token == null) {
                applyReport(post.postIdentifier, wasReported, previousReason)
                return@launch
            }
            try {
                val response = api.reportPost(token, post.postIdentifier, ReportRequest(reason))
                if (!response.isSuccessful) {
                    applyReport(post.postIdentifier, wasReported, previousReason)
                    _alertMessage.value = ApiErrors.messageFor(
                        response,
                        fallback = "Failed to report the post. Please try again."
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to report post", e)
                applyReport(post.postIdentifier, wasReported, previousReason)
                _alertMessage.value =
                    ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    /** Retracts the user's own report against [post] (issue #176). */
    fun retractReport(post: Post) {
        val current = currentVersionOf(post) ?: return
        val wasReported = current.isReported
        val previousReason = current.reportReason

        applyReport(post.postIdentifier, isReported = false, reason = null)

        scope.launch {
            val token = sessionToken()
            if (token == null) {
                applyReport(post.postIdentifier, wasReported, previousReason)
                return@launch
            }
            try {
                val response = api.retractReportPost(token, post.postIdentifier)
                if (!response.isSuccessful) {
                    applyReport(post.postIdentifier, wasReported, previousReason)
                    _alertMessage.value = ApiErrors.messageFor(
                        response,
                        fallback = "Failed to retract the report. Please try again."
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to retract post report", e)
                applyReport(post.postIdentifier, wasReported, previousReason)
                _alertMessage.value =
                    ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    /**
     * Deletes one of the user's own posts and drops it from the list. The list is
     * *not* reloaded: a feed reload would reshuffle the weighted ordering under
     * the user. Other screens learn about the delete through [PostEvents].
     */
    fun deletePost(post: Post) {
        scope.launch {
            val token = sessionToken() ?: return@launch
            try {
                val response = api.deletePost(token, post.postIdentifier)
                if (response.isSuccessful) {
                    removeLocally(post.postIdentifier)
                    PostEvents.postDeleted(post.postIdentifier)
                } else {
                    _alertMessage.value = ApiErrors.messageFor(
                        response,
                        fallback = "Failed to delete the post. Please try again."
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to delete post", e)
                _alertMessage.value =
                    ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    // ------------------------------------------------------------------------
    // Internals
    // ------------------------------------------------------------------------

    private fun loadSession(): UserSession? = try {
        keychainHelper.load(UserSession::class.java, service, account)
    } catch (e: Exception) {
        Log.e(TAG, "Failed to read the stored session", e)
        null
    }

    private fun sessionToken(): String? {
        val session = loadSession()
        if (session == null) {
            Log.e(TAG, "No active session found — cannot perform action")
            _alertMessage.value = "Not logged in."
            return null
        }
        _currentUsername.value = session.username
        return session.sessionToken
    }

    private fun currentVersionOf(post: Post): Post? =
        posts.value.firstOrNull { it.postIdentifier == post.postIdentifier }

    private fun updatePost(postIdentifier: String, transform: (Post) -> Post) {
        posts.value = posts.value.map {
            if (it.postIdentifier == postIdentifier) transform(it) else it
        }
    }

    // Only the like fields are written back, so a concurrent report can't be
    // clobbered by a like reverting (and vice versa).
    private fun applyLike(postIdentifier: String, isLiked: Boolean, likeCount: Int) {
        updatePost(postIdentifier) { it.copy(isLiked = isLiked, likeCount = likeCount) }
    }

    private fun applyReport(postIdentifier: String, isReported: Boolean, reason: String?) {
        updatePost(postIdentifier) { it.copy(isReported = isReported, reportReason = reason) }
    }

    private fun removeLocally(postIdentifier: String) {
        posts.value = posts.value.filterNot { it.postIdentifier == postIdentifier }
        if (_postForAction.value?.postIdentifier == postIdentifier) _postForAction.value = null
        if (_postToReport.value?.postIdentifier == postIdentifier) _postToReport.value = null
        if (_postToRetract.value?.postIdentifier == postIdentifier) _postToRetract.value = null
    }
}
