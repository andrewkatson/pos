package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.FollowRequestsViewModel
import com.example.positiveonlysocial.models.viewmodels.FollowRequestsViewModelFactory
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

/**
 * Lists everyone waiting to follow the signed-in private account, each with
 * Approve and Deny (issue #96). Reached from Settings and the owner's profile.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FollowRequestsScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    PositiveOnlySocialTheme {
        val viewModel: FollowRequestsViewModel = viewModel(
            factory = FollowRequestsViewModelFactory(api, keychainHelper)
        )

        val requests by viewModel.requests.collectAsState()
        val isLoading by viewModel.isLoading.collectAsState()
        val errorMessage by viewModel.errorMessage.collectAsState()
        val decidingUsernames by viewModel.decidingUsernames.collectAsState()
        val hasLoaded by viewModel.hasLoaded.collectAsState()
        val canLoadMore by viewModel.canLoadMore.collectAsState()
        val isLoadingMore by viewModel.isLoadingMore.collectAsState()

        LaunchedEffect(Unit) { viewModel.load() }

        if (errorMessage != null) {
            AlertDialog(
                onDismissRequest = { viewModel.clearError() },
                title = { Text("Error") },
                text = { Text(errorMessage ?: "Unknown error") },
                confirmButton = { Button(onClick = { viewModel.clearError() }) { Text("OK") } }
            )
        }

        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("Follow Requests") },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                )
            }
        ) { padding ->
            LazyColumn(modifier = Modifier.fillMaxSize().padding(padding)) {
                // Empty only once paging has ended: answering every loaded row
                // can leave older pages still to fetch.
                if (hasLoaded && requests.isEmpty() && !isLoading && !canLoadMore) {
                    item {
                        Text(
                            text = "No one is waiting to follow you.",
                            color = Color.Gray,
                            modifier = Modifier.padding(16.dp)
                        )
                    }
                }
                items(requests, key = { it.username }) { user ->
                    val deciding = user.username in decidingUsernames
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        ProfileAvatar(
                            imageUrl = user.authorProfileImageUrl,
                            originalImageUrl = user.authorProfileImageOriginalUrl,
                            // Decorative — the username is rendered next to it.
                            contentDescription = null,
                            size = 32.dp,
                            blurHash = user.authorProfileImageBlurHash
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(user.username, modifier = Modifier.weight(1f, fill = false))
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
                        Button(
                            onClick = { viewModel.approve(user.username) },
                            enabled = !deciding,
                            modifier = Modifier.testTag("approveFollowRequestButton")
                        ) {
                            Text("Approve")
                        }
                        Spacer(Modifier.width(8.dp))
                        OutlinedButton(
                            onClick = { viewModel.deny(user.username) },
                            enabled = !deciding,
                            modifier = Modifier.testTag("denyFollowRequestButton")
                        ) {
                            Text("Deny")
                        }
                    }
                    HorizontalDivider()
                }
                // The pager sits after the rows rather than inside the last one,
                // so it survives every loaded row being answered. Scrolling it
                // into view fetches the next page; the button retries a failed
                // fetch.
                if (hasLoaded && canLoadMore) {
                    item(key = "loadMore") {
                        LaunchedEffect(requests.size) { viewModel.loadMore() }
                        TextButton(
                            onClick = { viewModel.loadMore() },
                            enabled = !isLoadingMore,
                            modifier = Modifier.fillMaxWidth().padding(8.dp).testTag("loadMoreFollowRequestsButton")
                        ) {
                            Text("Load more")
                        }
                    }
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun FollowRequestsScreenPreview() {
    FollowRequestsScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper
    )
}
