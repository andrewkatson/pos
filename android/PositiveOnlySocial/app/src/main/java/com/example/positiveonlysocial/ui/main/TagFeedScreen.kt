package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.TagFeedViewModel
import com.example.positiveonlysocial.models.viewmodels.TagFeedViewModelFactory
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

/**
 * The tag feed (issue #379): the posts carrying a given #hashtag, newest first,
 * paginated. Opened by tapping a #hashtag in a caption; reuses the same PostItem
 * row (and its in-place like/report/delete actions) the feeds use.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TagFeedScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    tag: String
) {
    PositiveOnlySocialTheme {
        val viewModel: TagFeedViewModel = viewModel(
            factory = TagFeedViewModelFactory(api, keychainHelper, tag)
        )
        val posts by viewModel.posts.collectAsState()
        val isLoadingNextPage by viewModel.isLoadingNextPage.collectAsState()
        val isRefreshing by viewModel.isRefreshing.collectAsState()

        val postActions = viewModel.postActions
        val currentUsername by postActions.currentUsername.collectAsState()

        LaunchedEffect(Unit) {
            if (posts.isEmpty()) {
                viewModel.fetchNextPage()
            }
        }

        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("#$tag") },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                )
            }
        ) { padding ->
            PullToRefreshBox(
                isRefreshing = isRefreshing,
                onRefresh = { viewModel.refresh() },
                modifier = Modifier.fillMaxSize().padding(padding)
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(24.dp)
                ) {
                    if (posts.isEmpty() && !isLoadingNextPage) {
                        item {
                            Text(
                                text = "No posts with #$tag yet.",
                                color = Color.Gray,
                                modifier = Modifier.padding(16.dp)
                            )
                        }
                    }

                    items(posts) { post ->
                        PostItem(
                            post = post,
                            navController = navController,
                            actions = postActions,
                            currentUsername = currentUsername
                        )

                        if (post == posts.lastOrNull()) {
                            LaunchedEffect(Unit) {
                                viewModel.fetchNextPage()
                            }
                        }
                    }

                    if (isLoadingNextPage) {
                        item {
                            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                                CircularProgressIndicator()
                            }
                        }
                    }
                }

                PostActionDialogs(postActions, navController)
            }
        }
    }
}

@androidx.compose.ui.tooling.preview.Preview(showBackground = true)
@Composable
fun TagFeedScreenPreview() {
    TagFeedScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper,
        tag = "sunset"
    )
}
