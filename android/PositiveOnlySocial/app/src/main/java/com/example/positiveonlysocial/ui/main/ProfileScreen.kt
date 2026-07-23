package com.example.positiveonlysocial.ui.main

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.FollowListMode
import com.example.positiveonlysocial.models.viewmodels.ProfileViewModel
import com.example.positiveonlysocial.models.viewmodels.ProfileViewModelFactory
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    username: String
) {
    PositiveOnlySocialTheme {
        // Top bar carries the username as the title (like iOS's navigationTitle)
        // and a back button, since this screen is always pushed onto the root
        // nav stack with no other way back (issue #260). The app bar lives here
        // rather than in ProfileBody because the bottom-nav Profile tab renders
        // the same body with no back arrow (issue #347).
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text(username) },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                )
            }
        ) { padding ->
            ProfileBody(
                navController = navController,
                api = api,
                keychainHelper = keychainHelper,
                username = username,
                modifier = Modifier.padding(padding)
            )
        }
    }
}

/**
 * A user's profile: the Posts / Followers / Following stats, the Follow and Block
 * actions (hidden on your own profile), and their post grid with in-place like /
 * report / retract-report / delete controls (issue #267).
 *
 * Shared by the root-stack [ProfileScreen] — anyone's profile, pushed with a back
 * arrow — and by the bottom-nav Profile tab, which shows the signed-in user's own
 * profile and must not show a back arrow (issue #347). The app bar is therefore
 * the caller's responsibility, not part of this body.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileBody(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    username: String,
    modifier: Modifier = Modifier
) {
    val viewModel: ProfileViewModel = viewModel(
        factory = ProfileViewModelFactory(api, keychainHelper)
    )

    val userPosts by viewModel.userPosts.collectAsState()
    val profileDetails by viewModel.profileDetails.collectAsState()
    val isFollowing by viewModel.isFollowing.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val isRefreshing by viewModel.isRefreshing.collectAsState()
    val isOwnProfile by viewModel.isOwnProfile.collectAsState()
    val isPhotoBusy by viewModel.isPhotoBusy.collectAsState()
    val reviewNotice by viewModel.reviewNotice.collectAsState()

    val postActions = viewModel.postActions
    val currentUsername by postActions.currentUsername.collectAsState()

    // Own profile-photo controls (issue #7). Picking a photo reuses the same
    // system picker as NewPostScreen; the bytes are read here (it needs a
    // Context) and handed to the view model, which uploads them via the presigned
    // post-image pipeline and calls setProfilePhoto.
    val context = LocalContext.current
    val photoScope = rememberCoroutineScope()
    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
        onResult = { uri ->
            if (uri != null) {
                photoScope.launch {
                    val bytes = try {
                        withContext(Dispatchers.IO) {
                            context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                        }
                    } catch (e: Exception) {
                        android.util.Log.e("ProfileScreen", "Failed to read picked profile photo $uri", e)
                        null
                    }
                    if (bytes != null) {
                        viewModel.setProfilePhoto(username, bytes)
                    }
                }
            }
        }
    )

    // Surfaces the outcome when one of your posts' async review (#282) resolves
    // to a rejection while this grid is visible. Only your own posts carry a
    // status, so this never fires on someone else's profile.
    reviewNotice?.let { notice ->
        AlertDialog(
            onDismissRequest = { viewModel.dismissReviewNotice() },
            title = { Text("Post Review") },
            text = { Text(notice) },
            confirmButton = {
                TextButton(
                    onClick = { viewModel.dismissReviewNotice() },
                    modifier = Modifier.testTag("OkButtonReviewNotice")
                ) { Text("OK") }
            }
        )
    }

    LaunchedEffect(username) {
        if (userPosts.isEmpty()) {
            viewModel.fetchUserPosts(username)
        }
        if (profileDetails == null) {
            viewModel.fetchProfile(username)
        }
    }

    Column(modifier = modifier.fillMaxSize()) {
        // Header
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Large header avatar (issue #7). The owner previews their own
            // not-yet-approved upload immediately; everyone else (and the owner
            // once approved) sees the live photo.
            val pendingAvatar = if (isOwnProfile) profileDetails?.pendingProfileImageUrl else null
            ProfileAvatar(
                imageUrl = pendingAvatar ?: profileDetails?.profileImageUrl,
                originalImageUrl = pendingAvatar ?: profileDetails?.profileImageOriginalUrl,
                contentDescription = "$username's profile photo",
                size = 96.dp
            )

            // Own-profile photo controls: add/change and remove, plus the
            // pending/rejected review status.
            if (isOwnProfile) {
                Spacer(modifier = Modifier.height(12.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedButton(
                        onClick = {
                            photoPickerLauncher.launch(
                                PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                            )
                        },
                        enabled = !isPhotoBusy,
                        modifier = Modifier.testTag("setProfilePhotoButton")
                    ) {
                        // A pending first upload (no live photo yet) still counts
                        // as "has a photo" so the label matches the Remove button.
                        val hasPhoto = profileDetails?.profileImageUrl != null ||
                            profileDetails?.pendingProfileImageUrl != null
                        Text(if (hasPhoto) "Change photo" else "Add photo")
                    }
                    if (profileDetails?.profileImageUrl != null || profileDetails?.pendingProfileImageUrl != null) {
                        OutlinedButton(
                            onClick = { viewModel.removeProfilePhoto(username) },
                            enabled = !isPhotoBusy,
                            modifier = Modifier.testTag("removeProfilePhotoButton")
                        ) {
                            Text("Remove")
                        }
                    }
                }
                if (isPhotoBusy) {
                    Spacer(modifier = Modifier.height(8.dp))
                    CircularProgressIndicator(modifier = Modifier.size(24.dp))
                } else {
                    val statusText = when (profileDetails?.profileImageStatus) {
                        "pending" -> "Your new photo is being reviewed."
                        "rejected" -> "Your last photo wasn't approved — try another."
                        else -> null
                    }
                    statusText?.let {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatItem(count = userPosts.size, label = "Posts", modifier = Modifier.testTag("tag_Posts"))
                // Only your own follow lists are viewable, so the counts tap
                // through on your own profile and are plain stats on anyone
                // else's (issue #8).
                StatItem(
                    count = profileDetails?.followerCount ?: 0, label = "Followers",
                    modifier = Modifier
                        .testTag("tag_Followers")
                        .then(
                            if (isOwnProfile) Modifier.clickable {
                                navController.navigate(Screen.FollowList.createRoute(FollowListMode.FOLLOWERS.route))
                            } else Modifier
                        ),
                )
                StatItem(
                    count = profileDetails?.followingCount ?: 0, label = "Following",
                    modifier = Modifier
                        .testTag("tag_Following")
                        .then(
                            if (isOwnProfile) Modifier.clickable {
                                navController.navigate(Screen.FollowList.createRoute(FollowListMode.FOLLOWING.route))
                            } else Modifier
                        ),
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (!isOwnProfile) {
                Button(
                    onClick = { viewModel.toggleFollow(username) },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isFollowing) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.primary
                    )
                ) {
                    Text(if (isFollowing) "Following" else "Follow")
                }

                Spacer(modifier = Modifier.height(8.dp))

                val isBlocked by viewModel.isBlocked.collectAsState()

                Button(
                    onClick = { viewModel.toggleBlock(username) },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isBlocked) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.surfaceVariant,
                        contentColor = if (isBlocked) MaterialTheme.colorScheme.onError else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                ) {
                    Text(if (isBlocked) "Unblock" else "Block")
                }
            }
        }

        Divider()

        if (isLoading && userPosts.isEmpty()) {
            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else {
            // Pull-to-refresh reloads the newest posts/details from the backend.
            // It wraps both the empty state and the grid so the user can always
            // pull to retry — even when the profile currently has no posts.
            PullToRefreshBox(
                isRefreshing = isRefreshing,
                onRefresh = { viewModel.refreshProfile(username) },
                modifier = Modifier.fillMaxSize()
            ) {
                if (userPosts.isEmpty()) {
                    // Scrollable so the pull-to-refresh gesture works with no posts.
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState()),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Spacer(modifier = Modifier.height(48.dp))
                        Text(
                            if (isOwnProfile) "You haven't posted anything yet."
                            else "$username hasn't posted anything yet."
                        )
                    }
                } else {
                    // Black backing shows through the 1dp gaps as thin borders between
                    // posts; the 1dp contentPadding extends that border around the outer edge.
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(3),
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.Black),
                        contentPadding = PaddingValues(1.dp),
                        horizontalArrangement = Arrangement.spacedBy(1.dp),
                        verticalArrangement = Arrangement.spacedBy(1.dp)
                    ) {
                        items(userPosts) { post ->
                            // The action bar sits below the tile rather than over
                            // it, so it can't swallow the tap that opens the post.
                            Column(modifier = Modifier.background(MaterialTheme.colorScheme.surface)) {
                                Box {
                                    PostImageWithFallback(
                                        post = post,
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .aspectRatio(1f)
                                            .clickable {
                                                navController.navigate(Screen.PostDetail.createRoute(post.postIdentifier))
                                            }
                                    )
                                    // Author-only classification state (#282): "In
                                    // review" while the async classifier runs, or
                                    // the appeal hint on a rejection. Only your own
                                    // posts ever carry a status, so this is simply
                                    // absent on someone else's profile.
                                    statusBadgeLabel(post.status)?.let { badge ->
                                        Text(
                                            text = badge,
                                            color = Color.White,
                                            style = MaterialTheme.typography.labelSmall,
                                            textAlign = TextAlign.Center,
                                            modifier = Modifier
                                                .align(Alignment.BottomCenter)
                                                .fillMaxWidth()
                                                .background(Color.Black.copy(alpha = 0.72f))
                                                .padding(vertical = 2.dp)
                                                .testTag("PostStatusBadge")
                                        )
                                    }
                                }
                                PostActionBar(
                                    post = post,
                                    isOwnPost = post.authorUsername == currentUsername,
                                    onToggleLike = { postActions.toggleLike(post) },
                                    onOpenMenu = { postActions.setPostForAction(post) },
                                    compact = true
                                )
                            }

                            if (post == userPosts.lastOrNull()) {
                                LaunchedEffect(Unit) {
                                    viewModel.fetchUserPosts(username)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // One set of confirmations for the whole grid.
    PostActionDialogs(postActions)
}

@Composable
fun StatItem(count: Int, label: String, modifier: Modifier) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = modifier) {
        Text(text = count.toString(), fontWeight = FontWeight.Bold)
        Text(text = label, style = MaterialTheme.typography.bodySmall)
    }
}

@Preview(showBackground = true)
@Composable
fun ProfileScreenPreview() {
    ProfileScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper,
        username = "mockuser"
    )
}

/** Overlay label for the author's own pending/rejected grid tiles (#282). */
private fun statusBadgeLabel(status: String?): String? = when (status) {
    "pending" -> "In review"
    "rejected" -> "Hidden — you can appeal"
    else -> null
}
