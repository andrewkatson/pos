package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.CommentThreadViewData
import com.example.positiveonlysocial.data.model.CommentViewData
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.PostDetailViewModel
import com.example.positiveonlysocial.models.viewmodels.PostDetailViewModelFactory
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

@OptIn(ExperimentalFoundationApi::class, ExperimentalMaterial3Api::class)
@Composable
fun PostDetailScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    postId: String
) {
    PositiveOnlySocialTheme {
        val viewModel: PostDetailViewModel = viewModel(
            factory = PostDetailViewModelFactory(postId, api, keychainHelper)
        )

        val postDetail by viewModel.postDetail.collectAsState()
        val commentThreads by viewModel.commentThreads.collectAsState()
        val isLoading by viewModel.isLoading.collectAsState()
        val isRefreshing by viewModel.isRefreshing.collectAsState()
        val alertMessage by viewModel.alertMessage.collectAsState()
        // The signed-in user; used to hide the like control on their own
        // post/comments since the backend rejects liking your own content.
        val currentUsername by viewModel.currentUsername.collectAsState()
        
        // Local state for interactions
        var isPostReported by remember { mutableStateOf(false) }
        
        // Sheets
        val showReportSheetForPost by viewModel.showReportSheetForPost.collectAsState()
        val commentToReport by viewModel.commentToReport.collectAsState()
        val threadToReplyTo by viewModel.threadToReplyTo.collectAsState()

        if (alertMessage != null) {
            AlertDialog(
                onDismissRequest = { viewModel.dismissAlert() },
                title = { Text("Error") },
                text = { Text(alertMessage ?: "Unknown error") },
                confirmButton = {
                    Button(onClick = { viewModel.dismissAlert() }) {
                        Text("OK")
                    }
                }
            )
        }

        if (showReportSheetForPost) {
            ReportDialog(
                onDismiss = { viewModel.setShowReportSheetForPost(false) },
                onSubmit = {
                    reason -> viewModel.reportPost(reason)
                    isPostReported = true
                }
            )
        }

        commentToReport?.let { comment ->
            ReportDialog(
                onDismiss = { viewModel.setCommentToReport(null) },
                onSubmit = { reason -> viewModel.reportComment(comment, comment.threadId, reason) }
            )
        }

        threadToReplyTo?.let { thread ->
            ReplyDialog(
                thread = thread,
                onDismiss = { viewModel.setThreadToReplyTo(null) },
                onSubmit = { text -> viewModel.replyToCommentThread(thread, text) }
            )
        }

        PullToRefreshBox(
            isRefreshing = isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = 16.dp)
        ) {
            if (isLoading && postDetail == null) {
                item {
                    Box(modifier = Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            } else if (postDetail != null) {
                val post = postDetail!!
                // The backend rejects liking your own post, so the like control
                // is hidden and double-tap-to-like is a no-op on it.
                val isOwnPost = post.authorUsername == currentUsername
                item {
                    Column(modifier = Modifier.fillMaxWidth()) {
                        AsyncImage(
                            model = post.imageUrl,
                            contentDescription = "Post Image",
                            modifier = Modifier
                                .fillMaxWidth()
                                .aspectRatio(1f)
                                .combinedClickable(
                                    onDoubleClick = {
                                        if (isOwnPost) return@combinedClickable
                                        // Drive the action from the server-backed like state
                                        if (post.isLiked) viewModel.unlikePost() else viewModel.likePost()
                                    },
                                    onLongClick = {
                                       viewModel.setShowReportSheetForPost(true)
                                    },
                                    onClick = {}
                                ),
                            contentScale = ContentScale.Crop
                        )

                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (!isOwnPost) {
                                    Icon(if (post.isLiked) Icons.Default.Favorite else Icons.Default.FavoriteBorder, contentDescription = if (post.isLiked) "Liked" else "Like", tint = Color.Red)
                                    Spacer(modifier = Modifier.width(4.dp))
                                }
                                Text("${post.likeCount} likes", fontWeight = FontWeight.Bold)
                                Spacer(modifier = Modifier.weight(1f))
                                if (isPostReported) {
                                    Icon(Icons.Default.Flag, contentDescription = "Reported", tint = Color.Red)
                                }
                            }
                            
                            Spacer(modifier = Modifier.height(8.dp))
                            
                            Text(
                                text = "${post.authorUsername} ${post.caption}",
                                style = MaterialTheme.typography.bodyMedium
                            )
                            
                            Divider(modifier = Modifier.padding(vertical = 16.dp))
                            
                            // Add Comment Section
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                TextField(
                                    value = viewModel.newCommentText.collectAsState().value,
                                    onValueChange = { viewModel.updateNewCommentText(it) },
                                    placeholder = { Text("Add a comment...") },
                                    modifier = Modifier.weight(1f)
                                )
                                Button(
                                    onClick = { viewModel.commentOnPost(viewModel.newCommentText.value) },
                                    enabled = viewModel.newCommentText.collectAsState().value.isNotEmpty(),
                                    modifier = Modifier.padding(start = 8.dp)
                                ) {
                                    Text("Post")
                                }
                            }
                            
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("Comments", fontWeight = FontWeight.Bold)
                        }
                    }
                }
                
                items(commentThreads) { thread ->
                    CommentThreadView(thread = thread, viewModel = viewModel, currentUsername = currentUsername)
                }
            } else {
                item {
                    Text("Post not found.", modifier = Modifier.padding(16.dp))
                }
            }
        }
        }
    }
}

@Composable
fun CommentThreadView(thread: CommentThreadViewData, viewModel: PostDetailViewModel, currentUsername: String?) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        thread.comments.firstOrNull()?.let { rootComment ->
            CommentRow(
                comment = rootComment,
                isOwn = rootComment.authorUsername == currentUsername,
                onLike = { viewModel.likeComment(rootComment, rootComment.threadId) },
                onUnlike = { viewModel.unlikeComment(rootComment, rootComment.threadId) },
                onReport = { viewModel.setCommentToReport(rootComment) }
            )
            
            // Reply Input for Thread
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(start = 16.dp, top = 8.dp)) {
                 TextButton(onClick = { viewModel.setThreadToReplyTo(thread) }) {
                     Text("Reply", fontSize = 12.sp)
                 }
            }
        }
        
        if (thread.comments.size > 1) {
            Column(modifier = Modifier.padding(start = 32.dp)) {
                thread.comments.drop(1).forEach { reply ->
                    CommentRow(
                        comment = reply,
                        isOwn = reply.authorUsername == currentUsername,
                        onLike = { viewModel.likeComment(reply, reply.threadId) },
                        onUnlike = { viewModel.unlikeComment(reply, reply.threadId) },
                        onReport = { viewModel.setCommentToReport(reply) }
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun CommentRow(
    comment: CommentViewData,
    isOwn: Boolean,
    onLike: () -> Unit,
    onUnlike: () -> Unit,
    onReport: () -> Unit
) {
    var isReported by remember { mutableStateOf(false) }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
            .combinedClickable(
                onDoubleClick = {
                    // The backend rejects liking your own comment, so double-tap
                    // is a no-op on it.
                    if (isOwn) return@combinedClickable
                    // Drive the action from the server-backed like state
                    if (comment.isLiked) onUnlike() else onLike()
                },
                onLongClick = {
                    isReported = true
                    onReport()
                },
                onClick = {}
            ),
        verticalAlignment = Alignment.Top
    ) {
        // Avatar Placeholder
        Surface(
            shape = MaterialTheme.shapes.small,
            color = Color.Gray,
            modifier = Modifier.size(32.dp)
        ) {}
        
        Spacer(modifier = Modifier.width(8.dp))
        
        Column {
            Row {
                Text(comment.authorUsername, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                Spacer(modifier = Modifier.width(4.dp))
                Text(comment.body, fontSize = 14.sp)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                // TODO Date placeholder - needs formatting logic
                Text("Just now", fontSize = 12.sp, color = Color.Gray)
                Spacer(modifier = Modifier.width(8.dp))
                if (!isOwn) {
                    Icon(
                        if (comment.isLiked) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                        contentDescription = if (comment.isLiked) "Liked" else "Like",
                        tint = Color.Red,
                        modifier = Modifier.size(12.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                }
                Text("${comment.likeCount} likes", fontSize = 12.sp, color = Color.Gray)
                Spacer(modifier = Modifier.width(8.dp))
                if (isReported) {
                    Icon(Icons.Default.Flag, contentDescription = "Reported", tint = Color.Red)
                }
            }
        }
    }
}

@Composable
fun ReportDialog(onDismiss: () -> Unit, onSubmit: (String) -> Unit) {
    var reason by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Report") },
        text = {
            TextField(
                value = reason,
                onValueChange = { reason = it },
                placeholder = { Text("Reason for reporting...") }
            )
        },
        confirmButton = {
            Button(onClick = { 
                if (reason.isNotEmpty()) {
                    onSubmit(reason)
                    onDismiss()
                }
            }) {
                Text("Submit")
            }
        },
        dismissButton = {
            Button(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

@Composable
fun ReplyDialog(thread: CommentThreadViewData, onDismiss: () -> Unit, onSubmit: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Reply to ${thread.comments.firstOrNull()?.authorUsername ?: "Comment"}") },
        text = {
            TextField(
                value = text,
                onValueChange = { text = it },
                placeholder = { Text("Your reply...") }
            )
        },
        confirmButton = {
            Button(onClick = { 
                if (text.isNotEmpty()) {
                    onSubmit(text)
                    onDismiss()
                }
            }) {
                Text("Send")
            }
        },
        dismissButton = {
            Button(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

@Preview(showBackground = true)
@Composable
fun PostDetailScreenPreview() {
    PostDetailScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper,
        postId = "1"
    )
}
