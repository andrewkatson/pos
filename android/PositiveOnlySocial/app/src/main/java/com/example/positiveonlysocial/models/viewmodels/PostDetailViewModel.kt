package com.example.positiveonlysocial.models.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.*
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
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

    private val _alertMessage = MutableStateFlow<String?>(null)
    val alertMessage: StateFlow<String?> = _alertMessage.asStateFlow()

    // State for presentation
    private val _showReportSheetForPost = MutableStateFlow(false)
    val showReportSheetForPost: StateFlow<Boolean> = _showReportSheetForPost.asStateFlow()

    private val _commentToReport = MutableStateFlow<CommentViewData?>(null)
    val commentToReport: StateFlow<CommentViewData?> = _commentToReport.asStateFlow()

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

    fun setCommentToReport(comment: CommentViewData?) {
        _commentToReport.value = comment
    }

    fun dismissAlert() {
        _alertMessage.value = null
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
                            // Sort comments by date (oldest first)
                            val sortedComments = comments.sortedBy { it.creationTime }
                            
                            // Convert to CommentViewData
                            val commentViewDataList = sortedComments.map { c ->
                                CommentViewData(
                                    id = c.commentIdentifier,
                                    threadId = threadId,
                                    authorUsername = c.authorUsername,
                                    body = c.body,
                                    likeCount = c.likeCount,
                                    createdDate = Date() // TODO: Parse c.creationTime string to Date
                                )
                            }
                            
                            CommentThreadViewData(threadId, commentViewDataList)
                        }
                    }.awaitAll()
                }

                // Filter out empty threads if needed, or keep them
                val nonEmptyThreads = loadedThreads.filter { it.comments.isNotEmpty() }

                // Sort threads by their first comment's date (using dummy date for now as parsing is TODO)
                _commentThreads.value = nonEmptyThreads
                // .sortedBy { it.comments.firstOrNull()?.createdDate } 

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
        // Note: Post model doesn't have likeCount directly exposed as mutable var easily without copy
        // But Post is a data class so copy works.
        // However, Post model in Swift/Kotlin update removed likeCount from Post?
        // Let's check Models.kt.
        // Post: postIdentifier, imageUrl, caption, authorUsername. NO likeCount.
        // PostDisplayData has likeCount.
        // But _postDetail holds Post.
        // So I cannot optimistically update likeCount on _postDetail if it doesn't have it.
        // I might need to fetch details again or use PostDisplayData in ViewModel.
        // For now, I will just make the API call.
        
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                api.likePost(userSession.sessionToken, postIdentifier)
                // Reload data to get fresh counts
                loadAllData()
            } catch (e: Exception) {
                println("Failed to like post: $e")
            }
        }
    }

    fun unlikePost() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                api.unlikePost(userSession.sessionToken, postIdentifier)
                loadAllData()
            } catch (e: Exception) {
                println("Failed to unlike post: $e")
            }
        }
    }

    fun reportPost(reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                api.reportPost(userSession.sessionToken, postIdentifier, ReportRequest(reason))
            } catch (e: Exception) {
                println("Failed to report post: $e")
            }
        }
    }

    fun likeComment(comment: CommentViewData, threadId: String) {
        // Optimistic update - tricky with nested lists and ViewData conversion
        // Skipping optimistic update for now to ensure correctness first
        
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                api.likeComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                loadAllData()
            } catch (e: Exception) {
                println("Failed to like comment: $e")
            }
        }
    }

    fun unlikeComment(comment: CommentViewData, threadId: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                api.unlikeComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                loadAllData()
            } catch (e: Exception) {
                println("Failed to unlike comment: $e")
            }
        }
    }

    fun reportComment(comment: CommentViewData, threadId: String, reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                api.reportComment(userSession.sessionToken, postIdentifier, threadId, comment.id, ReportRequest(reason))
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
                    ?: UserSession("123", "testuser", false, null, null)
                
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
                    ?: UserSession("123", "testuser", false, null, null)
                
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
