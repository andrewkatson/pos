package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.LikesTarget
import com.example.positiveonlysocial.models.viewmodels.LikesViewModel
import com.example.positiveonlysocial.models.viewmodels.LikesViewModelFactory
import com.example.positiveonlysocial.ui.navigation.openProfileFor

/**
 * "Who liked this" (issue #478): the scrollable, batched list of accounts behind
 * one of your own posts' or comments' like counts, opened by tapping that count.
 *
 * Only your own content is listed — the backend answers for nobody else's — so
 * callers make the count tappable only on their own posts and comments.
 *
 * Likers arrive a batch at a time rather than all at once, so a post with
 * thousands of likes costs one screenful of rows to open. The list scrolls
 * inside the dialog and "Load more" appends the next batch, mirroring the feed's
 * pagination. Each row taps through to that user's profile.
 *
 * Mirrors the web LikesModal and the iOS LikesView.
 */
@Composable
fun LikesDialog(
    target: LikesTarget,
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    onDismiss: () -> Unit
) {
    // Keyed by the target so opening the dialog for a different post/comment
    // builds a fresh view model rather than reusing the previous list.
    val viewModel: LikesViewModel = viewModel(
        key = target.toString(),
        factory = LikesViewModelFactory(target, api, keychainHelper)
    )

    val users by viewModel.users.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val canLoadMore by viewModel.canLoadMore.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()

    LaunchedEffect(target) { viewModel.load() }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(target.title) },
        text = {
            // Bounded and scrolled inside the dialog so a post with hundreds of
            // likes doesn't grow it past the screen.
            LazyColumn(modifier = Modifier.heightIn(max = 320.dp)) {
                if (errorMessage != null) {
                    item {
                        Text(
                            text = errorMessage ?: "",
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                }
                if (users.isEmpty() && !isLoading && errorMessage == null) {
                    item {
                        Text(
                            text = "No one has liked this yet.",
                            color = Color.Gray,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                }
                items(users, key = { it.username }) { user ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                onDismiss()
                                navController.openProfileFor(user.username, viewModel.currentUsername)
                            }
                            .padding(vertical = 8.dp)
                            .testTag("likesRow"),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Decorative — the row already opens the profile and the
                        // username is right next to it.
                        ProfileAvatar(
                            imageUrl = user.authorProfileImageUrl,
                            originalImageUrl = user.authorProfileImageOriginalUrl,
                            contentDescription = null,
                            size = 28.dp
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(user.username)
                        if (user.identityIsVerified) {
                            Spacer(Modifier.width(4.dp))
                            Icon(
                                Icons.Filled.CheckCircle,
                                contentDescription = "Verified",
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                        Spacer(Modifier.weight(1f))
                    }
                    HorizontalDivider()
                }
                if (isLoading) {
                    item { CircularProgressIndicator(modifier = Modifier.padding(vertical = 8.dp)) }
                }
                if (canLoadMore && !isLoading) {
                    item {
                        TextButton(
                            onClick = { viewModel.loadMore() },
                            modifier = Modifier.testTag("likesLoadMore")
                        ) {
                            Text("Load more")
                        }
                    }
                }
            }
        },
        confirmButton = { Button(onClick = onDismiss) { Text("Close") } }
    )
}
