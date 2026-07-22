package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.models.viewmodels.PostListActions

/**
 * The like / reported-flag / options row shown with a post in a list, so posts
 * can be liked, reported, un-reported and deleted without opening each one
 * (issue #267). It offers exactly what [PostDetailScreen] offers for a post.
 *
 * Pair it with [PostActionDialogs], which renders the confirmations once for the
 * whole list rather than once per post.
 *
 * It is laid out as a sibling of the post's image — never an overlay — so it can
 * never swallow the tap that opens the post's detail screen.
 *
 * @param compact shrinks the controls for the three-column profile grid, where a
 * cell is only about a third of the screen wide.
 * @param onOpenComments when non-null, a comment-count control is shown that
 * opens the post (issue #249). The square profile-grid tiles pass null — there's
 * no room for it there.
 */
@Composable
fun PostActionBar(
    post: Post,
    isOwnPost: Boolean,
    onToggleLike: () -> Unit,
    onOpenMenu: () -> Unit,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
    onOpenComments: (() -> Unit)? = null
) {
    val buttonSize = if (compact) 32.dp else 48.dp
    val iconSize = if (compact) 16.dp else 24.dp

    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = if (compact) Arrangement.Center else Arrangement.Start
    ) {
        // The backend rejects liking your own post, so the control is hidden on
        // it — matching the post detail screen.
        if (!isOwnPost) {
            IconButton(onClick = onToggleLike, modifier = Modifier.size(buttonSize)) {
                Icon(
                    if (post.isLiked) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                    // Scoped to the author so these never collide with the post
                    // detail screen's own "Like post" control in UI tests.
                    contentDescription = if (post.isLiked) {
                        "Unlike post by ${post.authorUsername}"
                    } else {
                        "Like post by ${post.authorUsername}"
                    },
                    tint = Color.Red,
                    modifier = Modifier.size(iconSize)
                )
            }
        }

        Text(
            text = "${post.likeCount ?: 0}",
            style = if (compact) MaterialTheme.typography.labelSmall
            else MaterialTheme.typography.bodyMedium
        )

        // How many comments the post has; tapping it opens the post so they can
        // be read (issue #249).
        if (onOpenComments != null) {
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(onClick = onOpenComments, modifier = Modifier.size(buttonSize)) {
                Icon(
                    Icons.Default.ChatBubbleOutline,
                    contentDescription = "Comments on the post by ${post.authorUsername}",
                    modifier = Modifier.size(iconSize)
                )
            }
            Text(
                text = "${post.commentCount ?: 0}",
                style = MaterialTheme.typography.bodyMedium
            )
        }

        if (!compact) {
            Spacer(modifier = Modifier.weight(1f))
        } else {
            Spacer(modifier = Modifier.width(4.dp))
        }

        if (post.isReported) {
            Icon(
                Icons.Default.Flag,
                contentDescription = "You reported the post by ${post.authorUsername}",
                tint = Color.Red,
                modifier = Modifier.size(iconSize)
            )
        }

        IconButton(onClick = onOpenMenu, modifier = Modifier.size(buttonSize)) {
            Icon(
                Icons.Default.MoreHoriz,
                contentDescription = "Options for post by ${post.authorUsername}",
                modifier = Modifier.size(iconSize)
            )
        }
    }
}

/**
 * The confirmations behind [PostActionBar]: the action menu (Delete on your own
 * post, Retract Report when you already reported it, Report otherwise), the
 * report composer, the retract confirmation, and the error alert. Rendered once
 * per list — a list shares one [PostListActions], which holds which post (if any)
 * each dialog is for.
 *
 * Reuses the same dialogs the post detail screen uses, so the two stay identical.
 */
@Composable
fun PostActionDialogs(actions: PostListActions) {
    val currentUsername by actions.currentUsername.collectAsState()
    val postForAction by actions.postForAction.collectAsState()
    val postToReport by actions.postToReport.collectAsState()
    val postToRetract by actions.postToRetract.collectAsState()
    val alertMessage by actions.alertMessage.collectAsState()

    postForAction?.let { post ->
        ActionSheetDialog(
            isOwn = post.authorUsername == currentUsername,
            isReported = post.isReported,
            itemLabel = "Post",
            onDismiss = { actions.setPostForAction(null) },
            onReport = { actions.setPostToReport(post) },
            onRetract = { actions.setPostToRetract(post) },
            onDelete = { actions.deletePost(post) }
        )
    }

    postToRetract?.let { post ->
        RetractReportDialog(
            reason = post.reportReason ?: "",
            onDismiss = { actions.setPostToRetract(null) },
            onRetract = { actions.retractReport(post) }
        )
    }

    postToReport?.let { post ->
        ReportDialog(
            onDismiss = { actions.setPostToReport(null) },
            onSubmit = { reason -> actions.reportPost(post, reason) }
        )
    }

    alertMessage?.let { message ->
        AlertDialog(
            onDismissRequest = { actions.dismissAlert() },
            title = { Text("Error") },
            text = { Text(message) },
            confirmButton = {
                Button(onClick = { actions.dismissAlert() }) {
                    Text("OK")
                }
            }
        )
    }
}
