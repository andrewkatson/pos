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
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.MoreHoriz
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
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.CommentThreadViewData
import com.example.positiveonlysocial.ui.components.CaptionTile
import com.example.positiveonlysocial.ui.components.CharacterCounter
import com.example.positiveonlysocial.ui.components.isWithinLength
import com.example.positiveonlysocial.data.model.CommentViewData
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.PostDetailViewModel
import com.example.positiveonlysocial.models.viewmodels.PostDetailViewModelFactory
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.util.RelativeTime
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

        // Sheets
        val showReportSheetForPost by viewModel.showReportSheetForPost.collectAsState()
        val commentToReport by viewModel.commentToReport.collectAsState()
        val threadToReplyTo by viewModel.threadToReplyTo.collectAsState()

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

        // The post's action menu (three-dots button or long-press): Delete on
        // the user's own post, Report on everyone else's — or Retract Report
        // when they already reported it (issues #304, #176).
        if (showActionSheetForPost) {
            val isOwnPost = postDetail?.authorUsername == currentUsername
            ActionSheetDialog(
                isOwn = isOwnPost,
                isReported = postDetail?.isReported == true,
                itemLabel = "Post",
                onDismiss = { viewModel.setShowActionSheetForPost(false) },
                onReport = { viewModel.setShowReportSheetForPost(true) },
                onRetract = { viewModel.setShowRetractDialogForPost(true) },
                onDelete = { viewModel.deletePost() }
            )
        }

        // The comment's action menu mirrors the post's.
        val reportedCommentIds by viewModel.reportedCommentIds.collectAsState()
        commentForAction?.let { comment ->
            val isOwnComment = comment.authorUsername == currentUsername
            ActionSheetDialog(
                isOwn = isOwnComment,
                isReported = comment.isReported || reportedCommentIds.contains(comment.id),
                itemLabel = "Comment",
                onDismiss = { viewModel.setCommentForAction(null) },
                onReport = { viewModel.setCommentToReport(comment) },
                onRetract = { viewModel.setCommentToRetract(comment) },
                onDelete = { viewModel.deleteComment(comment, comment.threadId) }
            )
        }

        // Retract-report confirmations, pre-populated with the user's original
        // reason (issue #176).
        val showRetractDialogForPost by viewModel.showRetractDialogForPost.collectAsState()
        if (showRetractDialogForPost) {
            RetractReportDialog(
                reason = postDetail?.reportReason ?: "",
                onDismiss = { viewModel.setShowRetractDialogForPost(false) },
                onRetract = { viewModel.retractReportPost() }
            )
        }

        val commentToRetract by viewModel.commentToRetract.collectAsState()
        commentToRetract?.let { comment ->
            RetractReportDialog(
                reason = comment.reportReason ?: "",
                onDismiss = { viewModel.setCommentToRetract(null) },
                onRetract = { viewModel.retractReportComment(comment, comment.threadId) }
            )
        }

        if (showReportSheetForPost) {
            ReportDialog(
                onDismiss = { viewModel.setShowReportSheetForPost(false) },
                onSubmit = { reason -> viewModel.reportPost(reason) }
            )
        }

        commentToReport?.let { comment ->
            ReportDialog(
                onDismiss = { viewModel.setCommentToReport(null) },
                onSubmit = { reason -> viewModel.reportComment(comment, comment.threadId, reason) }
            )
        }

        // "Add a comment" on the post and "Reply" on a thread share the same
        // composer dialog (title aside), so the character counter is always shown
        // and the dialog closes the moment the comment is submitted (issue #291).
        val showAddCommentDialog by viewModel.showAddCommentDialog.collectAsState()
        if (showAddCommentDialog) {
            CommentComposerDialog(
                title = "Add a comment",
                onDismiss = { viewModel.setShowAddCommentDialog(false) },
                onSubmit = { text -> viewModel.commentOnPost(text) }
            )
        }

        threadToReplyTo?.let { thread ->
            CommentComposerDialog(
                title = "Reply to ${thread.comments.firstOrNull()?.authorUsername ?: "Comment"}",
                onDismiss = { viewModel.setThreadToReplyTo(null) },
                onSubmit = { text -> viewModel.replyToCommentThread(thread, text) }
            )
        }

        // Top bar with a back button, since this screen is always pushed onto
        // the root nav stack with no other way back (issue #260). Title matches
        // iOS's PostDetailView navigationTitle.
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("Post") },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                )
            }
        ) { scaffoldPadding ->
        PullToRefreshBox(
            isRefreshing = isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize().padding(scaffoldPadding)
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
                        val mediaModifier = Modifier
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
                            )
                        if (post.imageUrl == null) {
                            // A text-only post (#307): the caption is the tile;
                            // double-tap-to-like and long-press still work on it.
                            CaptionTile(
                                caption = post.caption,
                                modifier = mediaModifier,
                                maxLines = Int.MAX_VALUE
                            )
                        } else {
                            // Falls back to the full-res original while the async
                            // Lambda-generated compressed copy is still missing
                            // (#252/#254), same as the grids.
                            PostImageWithFallback(
                                post = post,
                                modifier = mediaModifier,
                                contentScale = ContentScale.Crop
                            )
                        }

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
                                if (post.isReported) {
                                    Icon(Icons.Default.Flag, contentDescription = "Reported", tint = Color.Red)
                                }
                                // Three-dots menu: the discoverable alternative to
                                // long-pressing the image (issue #304).
                                IconButton(onClick = { viewModel.setShowActionSheetForPost(true) }) {
                                    Icon(Icons.Default.MoreHoriz, contentDescription = "Post options")
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

                            // Add Comment Section. Tapping this opens the shared
                            // comment composer dialog (which shows the character
                            // counter) rather than typing inline, so commenting on
                            // a post and replying to a thread work the same way
                            // (issues #266, #289, #290).
                            OutlinedButton(
                                onClick = { viewModel.setShowAddCommentDialog(true) },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text("Add a comment...", modifier = Modifier.weight(1f))
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
}

@Composable
fun CommentThreadView(
    thread: CommentThreadViewData,
    viewModel: PostDetailViewModel,
    currentUsername: String?,
    onAuthorClick: (String) -> Unit
) {
    val reportedCommentIds by viewModel.reportedCommentIds.collectAsState()
    val collapsedCommentIds by viewModel.collapsedCommentIds.collectAsState()

    // Hide every comment that sits below the first collapsed one in the thread,
    // so tapping a comment's header folds away the comments under it (issue #243).
    val collapseIndex = thread.comments.indexOfFirst { collapsedCommentIds.contains(it.id) }
    val visibleComments =
        if (collapseIndex == -1) thread.comments else thread.comments.take(collapseIndex + 1)

    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        visibleComments.firstOrNull()?.let { rootComment ->
            CommentRow(
                comment = rootComment,
                isOwn = rootComment.authorUsername == currentUsername,
                isReported = rootComment.isReported || reportedCommentIds.contains(rootComment.id),
                isCollapsed = collapsedCommentIds.contains(rootComment.id),
                onToggleCollapse = { viewModel.toggleCommentCollapsed(rootComment.id) },
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

        if (visibleComments.size > 1) {
            Column(modifier = Modifier.padding(start = 32.dp)) {
                visibleComments.drop(1).forEach { reply ->
                    CommentRow(
                        comment = reply,
                        isOwn = reply.authorUsername == currentUsername,
                        isReported = reply.isReported || reportedCommentIds.contains(reply.id),
                        isCollapsed = collapsedCommentIds.contains(reply.id),
                        onToggleCollapse = { viewModel.toggleCommentCollapsed(reply.id) },
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
    isCollapsed: Boolean,
    onToggleCollapse: () -> Unit,
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
                // A single tap collapses/expands the thread below this comment
                // (issue #243). Tapping the author's name still opens their
                // profile — that inner handler wins over this one. This lives on
                // the row's own combinedClickable (rather than a nested
                // clickable) so it can't swallow the long-press that opens the
                // action menu.
                onClick = { onToggleCollapse() }
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

        Column(modifier = Modifier.weight(1f)) {
            // Username + time header. Tapping the comment (this header or the
            // body) collapses the thread below it (issue #243) via the row's
            // combinedClickable above; tapping the name itself still opens the
            // author's profile.
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
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
                Spacer(modifier = Modifier.width(8.dp))
                Text(RelativeTime.format(comment.createdDate), fontSize = 12.sp, color = Color.Gray)
                Spacer(modifier = Modifier.width(4.dp))
                // Three-dots menu next to the timestamp: the discoverable
                // alternative to long-pressing the comment (issue #304). Opens
                // the same action menu (Report / Retract Report / Delete).
                IconButton(
                    onClick = { onLongPress() },
                    modifier = Modifier.size(24.dp)
                ) {
                    Icon(
                        Icons.Default.MoreHoriz,
                        contentDescription = "Options for comment by ${comment.authorUsername}",
                        tint = Color.Gray,
                        modifier = Modifier.size(16.dp)
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
                // Chevron hint for the collapse state of the thread below.
                Text(if (isCollapsed) "▸" else "▾", fontSize = 12.sp, color = Color.Gray)
            }
            // The comment body sits below the username/time header line.
            Text(comment.body, fontSize = 14.sp)
            Row(verticalAlignment = Alignment.CenterVertically) {
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
 * The mini action menu shown by the three-dots button or a long-press. Offers a
 * single action — Delete for the user's own content, Report for everyone
 * else's, or Retract Report when they already have an active report against it
 * (issues #304, #176) — so you can never report your own post or comment.
 */
@Composable
fun ActionSheetDialog(
    isOwn: Boolean,
    isReported: Boolean,
    itemLabel: String,
    onDismiss: () -> Unit,
    onReport: () -> Unit,
    onRetract: () -> Unit,
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
            } else if (isReported) {
                TextButton(onClick = { onRetract(); onDismiss() }) {
                    Text("Retract Report")
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

/**
 * Confirmation for retracting an existing report (issue #176). Shows the user's
 * original report reason pre-populated so they can see what they're retracting.
 */
@Composable
fun RetractReportDialog(
    reason: String,
    onDismiss: () -> Unit,
    onRetract: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Retract Report?") },
        text = {
            Column {
                Text("You reported this with the reason below. Retracting removes your report.")
                Spacer(modifier = Modifier.height(8.dp))
                TextField(
                    value = reason,
                    onValueChange = {},
                    readOnly = true,
                    singleLine = true
                )
            }
        },
        confirmButton = {
            Button(onClick = { onRetract(); onDismiss() }) {
                Text("Retract Report")
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

/**
 * The shared composer dialog for writing a comment — used both for a brand new
 * comment on the post and for replying to a thread (issues #266, #289, #290).
 * It always shows the character counter, and submitting dismisses the dialog
 * (and thus the keyboard) immediately while clearing the text, so tapping the
 * confirm button repeatedly can't post the same comment twice (issue #291).
 */
@Composable
fun CommentComposerDialog(title: String, onDismiss: () -> Unit, onSubmit: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            // A comment can span multiple lines, so this stays multiline (Enter
            // inserts a newline). The dialog's confirm/Cancel buttons remain
            // reachable above the keyboard, so no Done-to-dismiss is needed.
            Column {
                TextField(
                    value = text,
                    onValueChange = { text = it },
                    placeholder = { Text("Write a comment...") }
                )
                CharacterCounter(text = text, max = Constants.MAX_COMMENT_LENGTH)
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (text.isNotEmpty()) {
                        onSubmit(text)
                        onDismiss()
                    }
                },
                enabled = text.isNotEmpty() && isWithinLength(text, Constants.MAX_COMMENT_LENGTH)
            ) {
                Text("Post")
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
