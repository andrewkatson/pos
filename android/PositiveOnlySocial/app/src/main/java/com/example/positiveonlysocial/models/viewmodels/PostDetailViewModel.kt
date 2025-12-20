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
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                val response = api.likePost(userSession.sessionToken, postIdentifier)
                if (response.isSuccessful) {
                    // Reload data to get fresh counts
                    loadAllData()
                } else {
                    _alertMessage.value = "Failed to like post: ${response.message()}"
                }
            } catch (e: Exception) {
                println("Failed to like post: $e")
                _alertMessage.value = "Error: ${e.localizedMessage}"
            }
        }
    }

    fun unlikePost() {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                val response = api.unlikePost(userSession.sessionToken, postIdentifier)
                if (response.isSuccessful) {
                    loadAllData()
                } else {
                    _alertMessage.value = "Failed to unlike post: ${response.message()}"
                }
            } catch (e: Exception) {
                println("Failed to unlike post: $e")
                _alertMessage.value = "Error: ${e.localizedMessage}"
            }
        }
    }

    fun reportPost(reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                val response = api.reportPost(userSession.sessionToken, postIdentifier, ReportRequest(reason))
                if (response.isSuccessful) {
                    _alertMessage.value = "Post reported successfully."
                } else {
                    _alertMessage.value = "Failed to report post: ${response.message()}"
                }
            } catch (e: Exception) {
                println("Failed to report post: $e")
                _alertMessage.value = "Error: ${e.localizedMessage}"
            }
        }
    }

    fun likeComment(comment: CommentViewData, threadId: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                val response = api.likeComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                if (response.isSuccessful) {
                    loadAllData()
                } else {
                    _alertMessage.value = "Failed to like comment: ${response.message()}"
                }
            } catch (e: Exception) {
                println("Failed to like comment: $e")
                _alertMessage.value = "Error: ${e.localizedMessage}"
            }
        }
    }

    fun unlikeComment(comment: CommentViewData, threadId: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                val response = api.unlikeComment(userSession.sessionToken, postIdentifier, threadId, comment.id)
                if (response.isSuccessful) {
                    loadAllData()
                } else {
                    _alertMessage.value = "Failed to unlike comment: ${response.message()}"
                }
            } catch (e: Exception) {
                println("Failed to unlike comment: $e")
                _alertMessage.value = "Error: ${e.localizedMessage}"
            }
        }
    }

    fun reportComment(comment: CommentViewData, threadId: String, reason: String) {
        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                    ?: UserSession("123", "testuser", false, null, null)
                val response = api.reportComment(userSession.sessionToken, postIdentifier, threadId, comment.id, ReportRequest(reason))
                if (response.isSuccessful) {
                    _alertMessage.value = "Comment reported successfully."
                } else {
                    _alertMessage.value = "Failed to report comment: ${response.message()}"
                }
            } catch (e: Exception) {
                println("Failed to report comment: $e")
                _alertMessage.value = "Error: ${e.localizedMessage}"
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
                    val errorBody = response.errorBody()?.string()
                    val errorMsg = try {
                        org.json.JSONObject(errorBody).getString("error")
                    } catch (e: Exception) {
                        "Failed to post comment"
                    }
                    _alertMessage.value = errorMsg
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
                    val errorBody = response.errorBody()?.string()
                    val errorMsg = try {
                        org.json.JSONObject(errorBody).getString("error")
                    } catch (e: Exception) {
                        "Failed to post reply"
                    }
                    _alertMessage.value = errorMsg
                }
            } catch (e: Exception) {
                _alertMessage.value = "Failed to post reply: ${e.localizedMessage}"
            }
        }
    }
}
