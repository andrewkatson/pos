package com.example.positiveonlysocial.models.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.*
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Date

class PostDetailViewModel(
    private val postIdentifier: String,
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    // Published State
    private val _postDetail = MutableStateFlow<PostDto?>(null)
    val postDetail: StateFlow<PostDto?> = _postDetail.asStateFlow()

    // We need a View Model for CommentThread to hold the list of comments
    // Since we don't have a dedicated DTO for the full thread with comments in one go,
    // we'll use a data class to hold it.
    data class CommentThreadViewData(
        val id: String,
        val comments: List<CommentDto>
    )

    private val _commentThreads = MutableStateFlow<List<CommentThreadViewData>>(emptyList())
    val commentThreads: StateFlow<List<CommentThreadViewData>> = _commentThreads.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _alertMessage = MutableStateFlow<String?>(null)
    val alertMessage: StateFlow<String?> = _alertMessage.asStateFlow()

    // State for presentation
    private val _showReportSheetForPost = MutableStateFlow(false)
    val showReportSheetForPost: StateFlow<Boolean> = _showReportSheetForPost.asStateFlow()

    private val _commentToReport = MutableStateFlow<CommentDto?>(null)
    val commentToReport: StateFlow<CommentDto?> = _commentToReport.asStateFlow()

    private val _newCommentText = MutableStateFlow("")
    val newCommentText: StateFlow<String> = _newCommentText.asStateFlow()

    private val _threadToReplyTo = MutableStateFlow<CommentThreadViewData?>(null)
    val threadToReplyTo: StateFlow<CommentThreadViewData?> = _threadToReplyTo.asStateFlow()

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

    fun setShowReportSheetForPost(show: Boolean) {
        _showReportSheetForPost.value = show
    }

    fun setCommentToReport(comment: CommentDto?) {
        _commentToReport.value = comment
    }

    fun loadAllData() {
        _isLoading.value = true

        viewModelScope.launch {
            try {
                // 1. Fetch the main post details
                val postResponse = api.getPostDetails(postIdentifier)
                if (postResponse.isSuccessful) {
                    _postDetail.value = postResponse.body()
                } else {
                    throw Exception("Failed to load post details")
                }

                // 2. Fetch the list of comment thread IDs for this post
                val threadListResponse = api.getCommentsForPost(postIdentifier, 0)
                val threadDtos = threadListResponse.body() ?: emptyList()
                val threadIdentifiers = threadDtos.map { it.threadIdentifier }

                // 3. Fetch all comments for *each* thread in parallel
                val loadedThreads = coroutineScope {
                    threadIdentifiers.map { threadId ->
                        async {
                            val commentsResponse = api.getCommentsForThread(threadId, 0)
                            val comments = commentsResponse.body() ?: emptyList()
                            // Sort comments by date (oldest first) - assuming creationTime is comparable string or we parse it
                            // For simplicity, using string comparison as in Swift it used Date() conversion
                            val sortedComments = comments.sortedBy { it.creationTime }
                            CommentThreadViewData(threadId, sortedComments)
                        }
                    }.map { it.await() }
                }

                // Filter out empty threads if needed, or keep them
                val nonEmptyThreads = loadedThreads.filter { it.comments.isNotEmpty() }

                // Sort threads by their first comment's date
                _commentThreads.value = nonEmptyThreads.sortedBy {
                    it.comments.firstOrNull()?.creationTime
                }

            } catch (e: Exception) {
                println("Error loading post details: $e")
                _alertMessage.value = "Failed to load post: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun likePost() {
        // Optimistic update
        _postDetail.value?.let { post ->
            val currentLikes = post.likeCount ?: 0
            _postDetail.value = post.copy(likeCount = currentLikes + 1)
        }

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                api.likePost(userSession.sessionToken, postIdentifier)
            } catch (e: Exception) {
                println("Failed to like post: $e")
            }
        }
    }

    fun unlikePost() {
        // Optimistic update
        _postDetail.value?.let { post ->
            val currentLikes = post.likeCount ?: 0
            _postDetail.value = post.copy(likeCount = maxOf(0, currentLikes - 1))
        }

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                api.unlikePost(userSession.sessionToken, postIdentifier)
            } catch (e: Exception) {
                println("Failed to unlike post: $e")
            }
        }
    }

    fun reportPost(reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                api.reportPost(userSession.sessionToken, postIdentifier, ReportRequest(reason))
            } catch (e: Exception) {
                println("Failed to report post: $e")
            }
        }
    }

    fun likeComment(comment: CommentDto, threadId: String) {
        // Optimistic update
        updateCommentLikes(threadId, comment.commentIdentifier, 1)

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                api.likeComment(userSession.sessionToken, postIdentifier, threadId, comment.commentIdentifier)
            } catch (e: Exception) {
                println("Failed to like comment: $e")
            }
        }
    }

    fun unlikeComment(comment: CommentDto, threadId: String) {
        // Optimistic update
        updateCommentLikes(threadId, comment.commentIdentifier, -1)

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                api.unlikeComment(userSession.sessionToken, postIdentifier, threadId, comment.commentIdentifier)
            } catch (e: Exception) {
                println("Failed to unlike comment: $e")
            }
        }
    }

    private fun updateCommentLikes(threadId: String, commentId: String, delta: Int) {
        val currentThreads = _commentThreads.value.toMutableList()
        val threadIndex = currentThreads.indexOfFirst { it.id == threadId }
        if (threadIndex != -1) {
            val thread = currentThreads[threadIndex]
            val comments = thread.comments.toMutableList()
            val commentIndex = comments.indexOfFirst { it.commentIdentifier == commentId }
            if (commentIndex != -1) {
                val comment = comments[commentIndex]
                val newLikeCount = maxOf(0, comment.likeCount + delta)
                comments[commentIndex] = comment.copy(likeCount = newLikeCount)
                currentThreads[threadIndex] = thread.copy(comments = comments)
                _commentThreads.value = currentThreads
            }
        }
    }

    fun reportComment(comment: CommentDto, threadId: String, reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                api.reportComment(userSession.sessionToken, postIdentifier, threadId, comment.commentIdentifier, ReportRequest(reason))
            } catch (e: Exception) {
                println("Failed to report comment: $e")
            }
        }
    }

    fun commentOnPost(commentText: String) {
        if (commentText.isEmpty()) return

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                
                val response = api.commentOnPost(
                    userSession.sessionToken,
                    postIdentifier,
                    CommentRequest(commentText)
                )
                
                if (response.isSuccessful) {
                    _newCommentText.value = ""
                    loadAllData() // Reload to get the new thread
                } else {
                    _alertMessage.value = "Failed to post comment"
                }
            } catch (e: Exception) {
                _alertMessage.value = "Failed to post comment: ${e.localizedMessage}"
            }
        }
    }

    fun replyToCommentThread(thread: CommentThreadViewData, commentText: String) {
        if (commentText.isEmpty()) return

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", null, null)
                
                val response = api.replyToThread(
                    userSession.sessionToken,
                    postIdentifier,
                    thread.id,
                    CommentRequest(commentText)
                )
                
                if (response.isSuccessful) {
                    loadAllData() // Reload to get the new comment
                } else {
                    _alertMessage.value = "Failed to post reply"
                }
            } catch (e: Exception) {
                _alertMessage.value = "Failed to post reply: ${e.localizedMessage}"
            }
        }
    }
}
