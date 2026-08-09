package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.models.viewmodels.LikesTarget
import com.example.positiveonlysocial.models.viewmodels.PostListActions
import com.example.positiveonlysocial.util.ShareLinks

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
 * @param onOpenLikes when non-null, the like count on the signed-in user's *own*
 * post opens "who liked this" (issue #478). Never wired on anyone else's post —
 * the backend answers for nobody else's.
 * @param menu this post's [ActionMenu], rendered in a `Box` with the three-dots
 * button so the dropdown opens right next to it (issue #477). Callers pass
 * [PostActionMenu].
 */
@Composable
fun PostActionBar(
    post: Post,
    isOwnPost: Boolean,
    onToggleLike: () -> Unit,
    onOpenMenu: () -> Unit,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
    onOpenComments: (() -> Unit)? = null,
    onOpenLikes: (() -> Unit)? = null,
    menu: @Composable () -> Unit = {}
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

        // With no heart beside it the bare number says nothing about what it
        // counts, so your own posts spell it out the way PostDetailScreen does
        // (issue #476) — and tapping that label lists who liked it, since who
        // liked someone else's post is between them and their likers (#478).
        val likeCount = post.likeCount ?: 0
        val likeCountStyle = if (compact) MaterialTheme.typography.labelSmall
            else MaterialTheme.typography.bodyMedium
        if (isOwnPost && onOpenLikes != null) {
            Text(
                text = "$likeCount likes",
                style = likeCountStyle,
                // The text already says what it counts; the click label is what
                // tells TalkBack that tapping it opens anything.
                modifier = Modifier
                    .clickable(onClickLabel = "See who liked this") { onOpenLikes() }
                    .testTag("postLikesCount")
            )
        } else {
            Text(
                text = if (isOwnPost) "$likeCount likes" else "$likeCount",
                style = likeCountStyle
            )
        }

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

        // The Box is what the dropdown anchors to, so the menu opens next to the
        // button the user actually tapped rather than mid-screen (issue #477).
        Box {
            IconButton(onClick = onOpenMenu, modifier = Modifier.size(buttonSize)) {
                Icon(
                    Icons.Default.MoreHoriz,
                    contentDescription = "Options for post by ${post.authorUsername}",
                    modifier = Modifier.size(iconSize)
                )
            }
            menu()
        }
    }
}

/**
 * The action menu for one post in a list, anchored to that row's three-dots
 * button. Rendered once per row, so it takes [expanded] and [isOwn] as plain
 * values rather than collecting `postForAction` / `currentUsername` itself —
 * one collector per list, not one per visible row.
 *
 * [expanded] is true for the post [PostActionBar]'s button set as the menu
 * target.
 */
@Composable
fun PostActionMenu(actions: PostListActions, post: Post, expanded: Boolean, isOwn: Boolean) {
    val context = LocalContext.current

    ActionMenu(
        expanded = expanded,
        isOwn = isOwn,
        isReported = post.isReported,
        itemLabel = "Post",
        onDismiss = { actions.setPostForAction(null) },
        onShare = { ShareLinks.shareText(context, ShareLinks.postUrl(post.postIdentifier)) },
        onReport = { actions.setPostToReport(post) },
        onRetract = { actions.setPostToRetract(post) },
        onDelete = { actions.deletePost(post) },
        // Save / unsave lives in the 3-dot menu on mobile (issue #412); web has a
        // dedicated bookmark control.
        isSaved = post.isSaved == true,
        onToggleSave = { actions.toggleSave(post) }
    )
}

/**
 * The confirmations behind [PostActionBar]: the report composer, the retract
 * confirmation, and the error alert. Rendered once per list — a list shares one
 * [PostListActions], which holds which post (if any) each dialog is for.
 *
 * The action menu itself is not here: it's a [PostActionMenu] anchored to each
 * row's three-dots button (issue #477). The "who liked this" dialog (issue #478)
 * is here, though — it is a dialog, not an anchored menu.
 *
 * Reuses the same dialogs the post detail screen uses, so the two stay identical.
 */
@Composable
fun PostActionDialogs(actions: PostListActions, navController: NavController) {
    val postForLikes by actions.postForLikes.collectAsState()
    val postToReport by actions.postToReport.collectAsState()
    val postToRetract by actions.postToRetract.collectAsState()
    val alertMessage by actions.alertMessage.collectAsState()

    // "Who liked this" for one of your own posts (issue #478).
    postForLikes?.let { post ->
        LikesDialog(
            target = LikesTarget.Post(post.postIdentifier),
            navController = navController,
            api = actions.api,
            keychainHelper = actions.keychainHelper,
            onDismiss = { actions.setPostForLikes(null) }
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
