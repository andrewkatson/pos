package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
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
import com.example.positiveonlysocial.ui.navigation.Screen
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.dismissKeyboardOnTap
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

        val focusManager = LocalFocusManager.current

        // Long-press action menus (Report vs Delete, depending on ownership).
        val showActionSheetForPost by viewModel.showActionSheetForPost.collectAsState()
        val commentForAction by viewModel.commentForAction.collectAsState()
        val postWasDeleted by viewModel.postWasDeleted.collectAsState()

        // The post was deleted out from under this screen; pop back to the feed.
        LaunchedEffect(postWasDeleted) {
            if (postWasDeleted) {
                navController.popBackStack()
            }
        }

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

        // The post's long-press action menu: Delete on the user's own post,
        // Report on everyone else's — so you can never report your own post.
        if (showActionSheetForPost) {
            val isOwnPost = postDetail?.authorUsername == currentUsername
            ActionSheetDialog(
                isOwn = isOwnPost,
                itemLabel = "Post",
                onDismiss = { viewModel.setShowActionSheetForPost(false) },
                onReport = { viewModel.setShowReportSheetForPost(true) },
                onDelete = { viewModel.deletePost() }
            )
        }

        // The comment's long-press action menu mirrors the post's.
        commentForAction?.let { comment ->
            val isOwnComment = comment.authorUsername == currentUsername
            ActionSheetDialog(
                isOwn = isOwnComment,
                itemLabel = "Comment",
                onDismiss = { viewModel.setCommentForAction(null) },
                onReport = { viewModel.setCommentToReport(comment) },
                onDelete = { viewModel.deleteComment(comment, comment.threadId) }
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
            modifier = Modifier.fillMaxSize().dismissKeyboardOnTap(),
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
                                       viewModel.setShowActionSheetForPost(true)
                                    },
                                    onClick = {}
                                ),
                            contentScale = ContentScale.Crop
                        )

                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (!isOwnPost) {
                                    IconButton(onClick = {
                                        if (post.isLiked) viewModel.unlikePost() else viewModel.likePost()
                                    }) {
                                        Icon(
                                            if (post.isLiked) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                                            contentDescription = if (post.isLiked) "Unlike post" else "Like post",
                                            tint = Color.Red
                                        )
                                    }
                                }
                                Text("${post.likeCount} likes", fontWeight = FontWeight.Bold)
                                Spacer(modifier = Modifier.weight(1f))
                                if (isPostReported) {
                                    Icon(Icons.Default.Flag, contentDescription = "Reported", tint = Color.Red)
                                }
                            }
                            
                            Spacer(modifier = Modifier.height(8.dp))
                            
                            Row {
                                // Tap the author's name to open their profile,
                                // same as in the feed.
                                Text(
                                    text = post.authorUsername,
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyMedium,
                                    modifier = Modifier.clickable {
                                        navController.navigate(Screen.Profile.createRoute(post.authorUsername))
                                    }
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    text = post.caption,
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                            
                            Divider(modifier = Modifier.padding(vertical = 16.dp))
                            
                            // Add Comment Section
                            val newCommentText by viewModel.newCommentText.collectAsState()
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                TextField(
                                    value = newCommentText,
                                    onValueChange = { viewModel.updateNewCommentText(it) },
                                    placeholder = { Text("Add a comment...") },
                                    modifier = Modifier.weight(1f),
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                                    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
                                )
                                Button(
                                    onClick = { viewModel.commentOnPost(newCommentText) },
                                    enabled = newCommentText.isNotEmpty(),
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
                    CommentThreadView(
                        thread = thread,
                        viewModel = viewModel,
                        currentUsername = currentUsername,
                        onAuthorClick = { username ->
                            navController.navigate(Screen.Profile.createRoute(username))
                        }
                    )
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
fun CommentThreadView(
    thread: CommentThreadViewData,
    viewModel: PostDetailViewModel,
    currentUsername: String?,
    onAuthorClick: (String) -> Unit
) {
    val reportedCommentIds by viewModel.reportedCommentIds.collectAsState()
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        thread.comments.firstOrNull()?.let { rootComment ->
            CommentRow(
                comment = rootComment,
                isOwn = rootComment.authorUsername == currentUsername,
                isReported = reportedCommentIds.contains(rootComment.id),
                onLike = { viewModel.likeComment(rootComment, rootComment.threadId) },
                onUnlike = { viewModel.unlikeComment(rootComment, rootComment.threadId) },
                onLongPress = { viewModel.setCommentForAction(rootComment) },
                onAuthorClick = onAuthorClick
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
                        isReported = reportedCommentIds.contains(reply.id),
                        onLike = { viewModel.likeComment(reply, reply.threadId) },
                        onUnlike = { viewModel.unlikeComment(reply, reply.threadId) },
                        onLongPress = { viewModel.setCommentForAction(reply) },
                        onAuthorClick = onAuthorClick
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
    isReported: Boolean,
    onLike: () -> Unit,
    onUnlike: () -> Unit,
    onLongPress: () -> Unit,
    onAuthorClick: (String) -> Unit
) {
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
                    // Open the action menu (Report or Delete, by ownership).
                    onLongPress()
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
                // Tap the author's name to open their profile, same as the
                // post author above. combinedClickable (not clickable) so the
                // row's double-tap (like) and long-press (report/delete)
                // gestures keep working over the username instead of being
                // consumed by this inner handler.
                Text(
                    comment.authorUsername,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    modifier = Modifier.combinedClickable(
                        onDoubleClick = {
                            if (isOwn) return@combinedClickable
                            if (comment.isLiked) onUnlike() else onLike()
                        },
                        onLongClick = { onLongPress() },
                        onClick = { onAuthorClick(comment.authorUsername) }
                    )
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(comment.body, fontSize = 14.sp)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                // TODO Date placeholder - needs formatting logic
                Text("Just now", fontSize = 12.sp, color = Color.Gray)
                Spacer(modifier = Modifier.width(8.dp))
                if (!isOwn) {
                    IconButton(
                        onClick = { if (comment.isLiked) onUnlike() else onLike() },
                        // IconButton enforces a minimum 48dp touch target while
                        // keeping the visible icon small.
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            if (comment.isLiked) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                            contentDescription = if (comment.isLiked) "Unlike comment" else "Like comment",
                            tint = Color.Red,
                            modifier = Modifier.size(12.dp)
                        )
                    }
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

/**
 * The mini action menu shown on long-press. Offers a single action — Delete for
 * the user's own content, Report for everyone else's — so you can never report
 * your own post or comment. More options can be added here later.
 */
@Composable
fun ActionSheetDialog(
    isOwn: Boolean,
    itemLabel: String,
    onDismiss: () -> Unit,
    onReport: () -> Unit,
    onDelete: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(itemLabel) },
        // The primary action lives in the confirmButton slot so it's laid out and
        // announced as the dialog's main action; more options can be added later.
        confirmButton = {
            if (isOwn) {
                TextButton(onClick = { onDelete(); onDismiss() }) {
                    Text("Delete $itemLabel")
                }
            } else {
                TextButton(onClick = { onReport(); onDismiss() }) {
                    Text("Report $itemLabel")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

@Composable
fun ReportDialog(onDismiss: () -> Unit, onSubmit: (String) -> Unit) {
    var reason by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Report") },
        text = {
            TextField(
                value = reason,
                onValueChange = { reason = it },
                placeholder = { Text("Reason for reporting...") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
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
            // A reply can span multiple lines, so this stays multiline (Enter
            // inserts a newline). The dialog's Send/Cancel buttons remain
            // reachable above the keyboard, so no Done-to-dismiss is needed.
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
