package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.ProfileViewModel
import com.example.positiveonlysocial.models.viewmodels.ProfileViewModelFactory
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    username: String
) {
    PositiveOnlySocialTheme {
        val viewModel: ProfileViewModel = viewModel(
            factory = ProfileViewModelFactory(api, keychainHelper)
        )
        
        val userPosts by viewModel.userPosts.collectAsState()
        val profileDetails by viewModel.profileDetails.collectAsState()
        val isFollowing by viewModel.isFollowing.collectAsState()
        val isLoading by viewModel.isLoading.collectAsState()
        val isRefreshing by viewModel.isRefreshing.collectAsState()
        val isOwnProfile by viewModel.isOwnProfile.collectAsState()

        LaunchedEffect(Unit) {
            if (userPosts.isEmpty()) {
                viewModel.fetchUserPosts(username)
            }
            if (profileDetails == null) {
                viewModel.fetchProfile(username)
            }
        }

        Column(modifier = Modifier.fillMaxSize()) {
            // Header
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = username,
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    StatItem(count = userPosts.size, label = "Posts", modifier = Modifier.testTag("tag_Posts"))
                    StatItem(
                        count = profileDetails?.followerCount ?: 0, label = "Followers",
                        modifier = Modifier.testTag("tag_Followers"),
                    )
                    StatItem(count = profileDetails?.followingCount ?: 0, label = "Following", modifier = Modifier.testTag("tag_Following"))
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
                            Text("$username hasn't posted anything yet.")
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
                                AsyncImage(
                                    model = post.imageUrl,
                                    contentDescription = "Post Image",
                                    modifier = Modifier
                                        .aspectRatio(1f)
                                        .clickable {
                                            navController.navigate(Screen.PostDetail.createRoute(post.postIdentifier))
                                        },
                                    contentScale = ContentScale.Crop
                                )

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
    }
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
