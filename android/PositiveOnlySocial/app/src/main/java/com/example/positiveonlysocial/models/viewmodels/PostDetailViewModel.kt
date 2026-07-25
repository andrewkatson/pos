package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.*
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.util.PostEvents
import com.example.positiveonlysocial.util.parseBackendDate
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Date

private const val TAG = "PostDetailViewModel"

class PostDetailViewModel(
    private val postIdentifier: String,
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    // Published State
    private val _postDetail = MutableStateFlow<Post?>(null)
    val postDetail: StateFlow<Post?> = _postDetail.asStateFlow()

    // We need a View Model for CommentThread to hold the list of comments
    // Since we don't have a dedicated DTO for the full thread with comments in one go,
    // we'll use the new View Data models we added to Models.kt
    // Actually, we added CommentThreadViewData to Models.kt, so we can use that directly.
    
    private val _commentThreads = MutableStateFlow<List<CommentThreadViewData>>(emptyList())
    val commentThreads: StateFlow<List<CommentThreadViewData>> = _commentThreads.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    private val _alertMessage = MutableStateFlow<String?>(null)
    val alertMessage: StateFlow<String?> = _alertMessage.asStateFlow()

    // State for presentation
    private val _showReportSheetForPost = MutableStateFlow(false)
    val showReportSheetForPost: StateFlow<Boolean> = _showReportSheetForPost.asStateFlow()

    private val _commentToReport = MutableStateFlow<CommentViewData?>(null)
    val commentToReport: StateFlow<CommentViewData?> = _commentToReport.asStateFlow()

    // Drives the long-press action menu for the post. The menu offers either
    // "Report" (others' posts) or "Delete" (the user's own post) — never both,
    // so you can't report your own content.
    private val _showActionSheetForPost = MutableStateFlow(false)
    val showActionSheetForPost: StateFlow<Boolean> = _showActionSheetForPost.asStateFlow()

    // The comment whose long-press action menu is showing, if any.
    private val _commentForAction = MutableStateFlow<CommentViewData?>(null)
    val commentForAction: StateFlow<CommentViewData?> = _commentForAction.asStateFlow()

    // Drives the retract-report confirmation for the post / a comment. The
    // dialog shows the user's original report reason pre-populated (issue #176).
    private val _showRetractDialogForPost = MutableStateFlow(false)
    val showRetractDialogForPost: StateFlow<Boolean> = _showRetractDialogForPost.asStateFlow()

    private val _commentToRetract = MutableStateFlow<CommentViewData?>(null)
    val commentToRetract: StateFlow<CommentViewData?> = _commentToRetract.asStateFlow()

    // Set once the post has been deleted so the screen can pop back — the post
    // no longer exists to display.
    private val _postWasDeleted = MutableStateFlow(false)
    val postWasDeleted: StateFlow<Boolean> = _postWasDeleted.asStateFlow()

    // Ids of comments the user has reported this session, so the reported flag
    // stays shown after a successful report (the backend doesn't echo it back).
    private val _reportedCommentIds = MutableStateFlow<Set<String>>(emptySet())
    val reportedCommentIds: StateFlow<Set<String>> = _reportedCommentIds.asStateFlow()

    private val _newCommentText = MutableStateFlow("")
    val newCommentText: StateFlow<String> = _newCommentText.asStateFlow()

    private val _threadToReplyTo = MutableStateFlow<CommentThreadViewData?>(null)
    val threadToReplyTo: StateFlow<CommentThreadViewData?> = _threadToReplyTo.asStateFlow()

    // Drives the "Add a comment" composer dialog for a brand new comment on the
    // post. Both this and the reply flow go through the same dialog so the
    // character counter is always shown and comments aren't typed inline
    // (issues #266, #289, #290).
    private val _showAddCommentDialog = MutableStateFlow(false)
    val showAddCommentDialog: StateFlow<Boolean> = _showAddCommentDialog.asStateFlow()

    // Ids of comments whose thread below them is collapsed. Tapping a comment's
    // username/time header toggles its presence here (issue #243).
    private val _collapsedCommentIds = MutableStateFlow<Set<String>>(emptySet())
    val collapsedCommentIds: StateFlow<Set<String>> = _collapsedCommentIds.asStateFlow()

    // The signed-in user's username, loaded alongside the post. The backend
    // rejects liking your own post/comment, so the UI hides the like control
    // (and the like actions are guarded) for content this user authored.
    private val _currentUsername = MutableStateFlow<String?>(null)
    val currentUsername: StateFlow<String?> = _currentUsername.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    init {
        loadAllData()
    }

    fun updateNewCommentText(text: String) {
        _newCommentText.value = text
    }

    fun setThreadToReplyTo(thread: CommentThreadViewData?) {
        _threadToReplyTo.value = thread
    }

    fun setShowAddCommentDialog(show: Boolean) {
        _showAddCommentDialog.value = show
    }

    /** Toggles whether the thread below the given comment is collapsed. */
    fun toggleCommentCollapsed(commentId: String) {
        val current = _collapsedCommentIds.value
        _collapsedCommentIds.value =
            if (current.contains(commentId)) current - commentId else current + commentId
    }

    fun setShowReportSheetForPost(show: Boolean) {
        _showReportSheetForPost.value = show
    }

    fun setCommentToReport(comment: CommentViewData?) {
        _commentToReport.value = comment
    }

    fun setShowActionSheetForPost(show: Boolean) {
        _showActionSheetForPost.value = show
    }

    fun setCommentForAction(comment: CommentViewData?) {
        _commentForAction.value = comment
    }

    fun setShowRetractDialogForPost(show: Boolean) {
        _showRetractDialogForPost.value = show
    }

    fun setCommentToRetract(comment: CommentViewData?) {
        _commentToRetract.value = comment
    }

    fun dismissAlert() {
        _alertMessage.value = null
    }

    /** Whether the loaded post was authored by the signed-in user. */
    fun isOwnPost(): Boolean {
        val username = _currentUsername.value ?: return false
        return _postDetail.value?.authorUsername == username
    }

    /** Whether the given comment was authored by the signed-in user. */
    fun isOwnComment(comment: CommentViewData): Boolean {
        return comment.authorUsername == _currentUsername.value
    }

    fun loadAllData() {
        _isLoading.value = true

        viewModelScope.launch {
            try {
                loadAllDataInternal()
            } finally {
                _isLoading.value = false
            }
        }
    }

    /**
     * Pull-to-refresh: reloads the post details and comments from the backend.
     * Uses a separate [isRefreshing] flag so the pull-to-refresh indicator is
     * shown instead of the initial full-screen loading spinner.
     */
    fun refresh() {
        // Don't start a refresh while another load is already in flight (the
        // initial loadAllData() from init or an action-triggered reload). Two
        // concurrent loadAllDataInternal() calls both write _postDetail and
        // _commentThreads, so an older response could otherwise overwrite the
        // fresher refreshed data.
        if (_isRefreshing.value || _isLoading.value) return
        _isRefreshing.value = true

        viewModelScope.launch {
            try {
                loadAllDataInternal()
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    private suspend fun loadAllDataInternal() {
        try {
            // These authenticated GETs need the session token so the backend can
            // report whether the current user has liked the post / each comment.
            val userSession = keychainHelper.load(UserSession::class.java, service, account)
            if (userSession == null) {
                Log.e(TAG, "No active session found — cannot load post details")
                _alertMessage.value = "Not logged in."
                return
            }
            val token = userSession.sessionToken
            _currentUsername.value = userSession.username

            // 1. Fetch the main post details
            val postResponse = api.getPostDetails(token, postIdentifier)
            if (postResponse.isSuccessful) {
                _postDetail.value = postResponse.body()
            } else {
                throw Exception("Failed to load post details")
            }

            // 2. Fetch the list of comment thread IDs for this post
            val threadListResponse = api.getCommentsForPost(token, postIdentifier, 0)
            val threadDtos = threadListResponse.body() ?: emptyList()
            val threadIdentifiers = threadDtos.map { it.threadIdentifier }

            // 3. Fetch all comments for *each* thread in parallel
            val loadedThreads = coroutineScope {
                threadIdentifiers.map { threadId ->
                    async {
                        val commentsResponse = api.getCommentsForThread(token, threadId, 0)
                        val comments = commentsResponse.body() ?: emptyList()
                        // Sort comments by date (oldest first)
                        val sortedComments = comments.sortedBy { it.creationTime }

                        // Convert to CommentViewData
                        val commentViewDataList = sortedComments.map { c ->
                            CommentViewData(
                                id = c.commentIdentifier,
                                threadId = threadId,
                                authorUsername = c.authorUsername,
                                body = c.body,
                                formatting = c.bodyFormatting,
                                likeCount = c.likeCount,
                                isLiked = c.isLiked,
                                isReported = c.isReported,
                                reportReason = c.reportReason,
                                createdDate = parseBackendDate(c.creationTime) ?: Date(),
                                authorProfileImageUrl = c.authorProfileImageUrl,
                                authorProfileImageOriginalUrl = c.authorProfileImageOriginalUrl
                            )
                        }

                        CommentThreadViewData(threadId, commentViewDataList)
                    }
                }.awaitAll()
            }

            // Filter out empty threads if needed, or keep them
            val nonEmptyThreads = loadedThreads.filter { it.comments.isNotEmpty() }

            // Order threads oldest-to-newest by their first comment's date, so the
            // post's comments always read top-to-bottom in chronological order
            // (issue #293). Comments within each thread are already sorted oldest
            // first above.
            _commentThreads.value = nonEmptyThreads.sortedBy { it.comments.firstOrNull()?.createdDate }

        } catch (e: Exception) {
            Log.e(TAG, "Error loading post details", e)
            _alertMessage.value = ApiErrors.messageFor(e, fallback = "Failed to load the post. Please try again.")
        }
    }

    fun likePost() {
        // The backend rejects liking your own post; ignore the request.
        if (isOwnPost()) return
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.likePost(userSession.sessionToken, postIdentifier)
                if (response.isSuccessful) {
                    // Reload data to get fresh counts
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to like the post. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to like post", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    fun unlikePost() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.unlikePost(userSession.sessionToken, postIdentifier)
                if (response.isSuccessful) {
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to unlike the post. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to unlike post", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    fun reportPost(reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.reportPost(userSession.sessionToken, postIdentifier, ReportRequest(reason))
                if (response.isSuccessful) {
                    _alertMessage.value = "Post reported successfully."
                    // Reload so the server-backed isReported/reportReason state
                    // (used by the action menu and retract dialog) refreshes.
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to report the post. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to report post", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    /**
     * Retracts the user's own report against the post (issue #176), then reloads
     * so the isReported/reportReason state refreshes.
     */
    fun retractReportPost() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.retractReportPost(userSession.sessionToken, postIdentifier)
                if (response.isSuccessful) {
                    _alertMessage.value = "Report retracted."
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to retract the report. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to retract post report", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    /**
     * Deletes the user's own post, then signals the screen to pop back since the
     * post no longer exists. Only reachable from the action menu on an own post.
     */
    fun deletePost() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.deletePost(userSession.sessionToken, postIdentifier)
                if (response.isSuccessful) {
                    _postWasDeleted.value = true
                    // Tell the Home grid to drop this post so its now-deleted image
                    // doesn't linger as an empty black tile (issue #256).
                    PostEvents.postDeleted(postIdentifier)
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to delete the post. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to delete post", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    /**
     * Deletes one of the user's own comments, then reloads so it disappears from
     * the thread. Only reachable from the action menu on an own comment.
     */
    fun deleteComment(comment: CommentViewData, threadId: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.deleteComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                if (response.isSuccessful) {
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to delete the comment. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to delete comment", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    fun likeComment(comment: CommentViewData, threadId: String) {
        // The backend rejects liking your own comment; ignore the request.
        if (isOwnComment(comment)) return
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.likeComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                if (response.isSuccessful) {
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to like the comment. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to like comment", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    fun unlikeComment(comment: CommentViewData, threadId: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.unlikeComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                if (response.isSuccessful) {
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to unlike the comment. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to unlike comment", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    fun reportComment(comment: CommentViewData, threadId: String, reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.reportComment(userSession.sessionToken, postIdentifier, threadId, comment.id, ReportRequest(reason))
                if (response.isSuccessful) {
                    _reportedCommentIds.value = _reportedCommentIds.value + comment.id
                    _alertMessage.value = "Comment reported successfully."
                    // Reload so the server-backed isReported/reportReason state
                    // (used by the action menu and retract dialog) refreshes.
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to report the comment. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to report comment", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    /**
     * Retracts the user's own report against a comment (issue #176), then
     * reloads so the isReported/reportReason state refreshes.
     */
    fun retractReportComment(comment: CommentViewData, threadId: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }
                val response = api.retractReportComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                if (response.isSuccessful) {
                    _reportedCommentIds.value = _reportedCommentIds.value - comment.id
                    _alertMessage.value = "Report retracted."
                    loadAllData()
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to retract the report. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to retract comment report", e)
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    fun commentOnPost(commentText: String, formatting: List<CommentFormatSpan>? = null) {
        if (commentText.isEmpty()) return

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }

                val response = api.commentOnPost(
                    userSession.sessionToken,
                    postIdentifier,
                    CommentRequest(commentText, formatting)
                )
                
                if (response.isSuccessful) {
                    _newCommentText.value = ""
                    loadAllData() // Reload to get the new thread
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to post comment. Please try again.")
                }
            } catch (e: Exception) {
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Failed to post comment. Please try again.")
            }
        }
    }

    fun replyToCommentThread(thread: CommentThreadViewData, commentText: String, formatting: List<CommentFormatSpan>? = null) {
        if (commentText.isEmpty()) return

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot perform action")
                    _alertMessage.value = "Not logged in."
                    return@launch
                }

                val response = api.replyToThread(
                    userSession.sessionToken,
                    postIdentifier,
                    thread.id,
                    CommentRequest(commentText, formatting)
                )
                
                if (response.isSuccessful) {
                    loadAllData() // Reload to get the new comment
                } else {
                    _alertMessage.value = ApiErrors.messageFor(response, fallback = "Failed to post reply. Please try again.")
                }
            } catch (e: Exception) {
                _alertMessage.value = ApiErrors.messageFor(e, fallback = "Failed to post reply. Please try again.")
            }
        }
    }
}
