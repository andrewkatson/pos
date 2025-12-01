package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.FeedViewModel
import com.example.positiveonlysocial.models.viewmodels.FeedViewModelFactory
import com.example.positiveonlysocial.models.viewmodels.FollowingFeedViewModel
import com.example.positiveonlysocial.models.viewmodels.FollowingFeedViewModelFactory
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.navigation.Screen

@Composable
fun FeedScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
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

    LaunchedEffect(Unit) {
        if (posts.isEmpty()) {
            viewModel.fetchFeed()
        }
    }

    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        items(posts) { post ->
            PostItem(post = post, navController = navController)
            
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
}

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

    LaunchedEffect(Unit) {
        if (posts.isEmpty()) {
            viewModel.fetchFollowingFeed()
        }
    }

    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        items(posts) { post ->
            PostItem(post = post, navController = navController)

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
}

@Composable
fun PostItem(
    post: com.example.positiveonlysocial.data.model.Post,
    navController: NavController
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            text = post.authorUsername,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.clickable {
                navController.navigate(Screen.Profile.createRoute(post.authorUsername))
            }
        )

        AsyncImage(
            model = post.imageUrl,
            contentDescription = "Post Image",
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(1f)
                .clickable {
                    navController.navigate(Screen.PostDetail.createRoute(post.postIdentifier))
                },
            contentScale = ContentScale.Crop
        )
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
