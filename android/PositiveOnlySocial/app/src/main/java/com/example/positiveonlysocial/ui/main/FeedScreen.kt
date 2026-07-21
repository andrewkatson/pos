package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.FeedViewModel
import com.example.positiveonlysocial.models.viewmodels.FeedViewModelFactory
import com.example.positiveonlysocial.models.viewmodels.FollowingFeedViewModel
import com.example.positiveonlysocial.models.viewmodels.FollowingFeedViewModelFactory
import com.example.positiveonlysocial.models.viewmodels.PostListActions
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.navigation.openProfileFor
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import com.example.positiveonlysocial.util.RelativeTime
import com.example.positiveonlysocial.util.parseBackendDate

@Composable
fun FeedScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    PositiveOnlySocialTheme {
        var selectedTab by remember { mutableIntStateOf(0) }
        val tabs = listOf("For You", "Following")

        Column(modifier = Modifier.fillMaxSize()) {
            TabRow(selectedTabIndex = selectedTab) {
                tabs.forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        text = { Text(title) }
                    )
                }
            }

            when (selectedTab) {
                0 -> ForYouFeed(navController, api, keychainHelper)
                1 -> FollowingFeed(navController, api, keychainHelper)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ForYouFeed(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    val viewModel: FeedViewModel = viewModel(
        factory = FeedViewModelFactory(api, keychainHelper)
    )
    val posts by viewModel.feedPosts.collectAsState()
    val isLoadingNextPage by viewModel.isLoadingNextPage.collectAsState()
    val isRefreshing by viewModel.isRefreshing.collectAsState()

    val postActions = viewModel.postActions
    val currentUsername by postActions.currentUsername.collectAsState()

    LaunchedEffect(Unit) {
        if (posts.isEmpty()) {
            viewModel.fetchFeed()
        }
    }

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = { viewModel.refreshFeed() },
        modifier = Modifier.fillMaxSize()
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            items(posts) { post ->
                PostItem(
                    post = post,
                    navController = navController,
                    actions = postActions,
                    currentUsername = currentUsername
                )

                if (post == posts.lastOrNull()) {
                    LaunchedEffect(Unit) {
                        viewModel.fetchFeed()
                    }
                }
            }

            if (isLoadingNextPage) {
                item {
                    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = androidx.compose.ui.Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            }
        }

        // One set of confirmations for every post in the feed.
        PostActionDialogs(postActions)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FollowingFeed(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    val viewModel: FollowingFeedViewModel = viewModel(
        factory = FollowingFeedViewModelFactory(api, keychainHelper)
    )
    val posts by viewModel.followingPosts.collectAsState()
    val isLoadingNextPage by viewModel.isLoadingNextPage.collectAsState()
    val isRefreshing by viewModel.isRefreshing.collectAsState()

    val postActions = viewModel.postActions
    val currentUsername by postActions.currentUsername.collectAsState()

    LaunchedEffect(Unit) {
        if (posts.isEmpty()) {
            viewModel.fetchFollowingFeed()
        }
    }

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = { viewModel.refreshFollowingFeed() },
        modifier = Modifier.fillMaxSize()
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            items(posts) { post ->
                PostItem(
                    post = post,
                    navController = navController,
                    actions = postActions,
                    currentUsername = currentUsername
                )

                if (post == posts.lastOrNull()) {
                    LaunchedEffect(Unit) {
                        viewModel.fetchFollowingFeed()
                    }
                }
            }

            if (isLoadingNextPage) {
                item {
                    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = androidx.compose.ui.Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            }
        }

        // One set of confirmations for every post in the feed.
        PostActionDialogs(postActions)
    }
}

@Composable
fun PostItem(
    post: com.example.positiveonlysocial.data.model.Post,
    navController: NavController,
    actions: PostListActions,
    currentUsername: String?
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            text = post.authorUsername,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.clickable {
                // Your own name goes to the Profile tab, not a pushed copy of it.
                navController.openProfileFor(post.authorUsername, currentUsername)
            }
        )

        // Square, cropped to fill so images keep a standard size, with a thin
        // black border to match the grid views.
        PostImageWithFallback(
            post = post,
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(1f)
                .border(1.dp, Color.Black)
                .clickable {
                    navController.navigate(Screen.PostDetail.createRoute(post.postIdentifier))
                }
        )

        // Like / comment count / report / retract / delete without leaving the
        // feed (issues #267, #249). A sibling of the image, so it can't swallow
        // the tap that opens the post.
        PostActionBar(
            post = post,
            isOwnPost = post.authorUsername == currentUsername,
            onToggleLike = { actions.toggleLike(post) },
            onOpenMenu = { actions.setPostForAction(post) },
            onOpenComments = {
                navController.navigate(Screen.PostDetail.createRoute(post.postIdentifier))
            }
        )

        // How long ago the post was made, at the same coarse granularity as the
        // post detail screen and comment times (issues #249, #174). Older backend
        // responses omit creation_time, in which case no label is shown at all.
        post.creationTime?.let { parseBackendDate(it) }?.let { created ->
            Text(
                text = RelativeTime.format(created),
                fontSize = 12.sp,
                color = Color.Gray
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
fun FeedScreenPreview() {
    FeedScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper
    )
}
