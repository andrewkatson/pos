package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items as lazyItems
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.HomeViewModel
import com.example.positiveonlysocial.models.viewmodels.HomeViewModelFactory
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.dismissKeyboardOnTap
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

/**
 * The first bottom-nav destination: the signed-in user's own profile, reachable
 * in one tap from anywhere (issue #347). It renders the same [ProfileBody] the
 * root-stack [ProfileScreen] does — stats, post grid and the in-place post
 * actions — minus the back arrow, since this destination is not pushed onto
 * anything. Follow/Block are already hidden for your own profile.
 *
 * The user-search bar stays on top exactly as before: typing at least three
 * characters searches, and while a search is active the results replace the
 * profile body.
 */
@Composable
fun HomeScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    PositiveOnlySocialTheme {
        val viewModel: HomeViewModel = viewModel(
            factory = HomeViewModelFactory(api, keychainHelper)
        )

        val searchedUsers by viewModel.searchedUsers.collectAsState()
        val searchText by viewModel.searchText.collectAsState()
        val isSearching by viewModel.isSearching.collectAsState()
        val currentUsername by viewModel.currentUsername.collectAsState()

        val hasMoreResults by viewModel.hasMoreResults.collectAsState()
        val allSearchResults by viewModel.allSearchResults.collectAsState()
        val isLoadingAllResults by viewModel.isLoadingAllResults.collectAsState()

        val errorMessage by viewModel.errorMessage.collectAsState()

        var showAllResultsDialog by remember { mutableStateOf(false) }
        val focusManager = LocalFocusManager.current

        Column(modifier = Modifier.fillMaxSize().dismissKeyboardOnTap()) {
            // Search Bar
            TextField(
                value = searchText,
                onValueChange = { viewModel.updateSearchText(it) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                placeholder = { Text("Search for Users") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { focusManager.clearFocus() })
            )

            if (searchText.trim().isNotEmpty()) {
                // Search Results
                LazyVerticalGrid(
                    columns = GridCells.Fixed(1),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    when {
                        searchText.trim().length < 3 -> {
                            item {
                                Text(
                                    text = "Enter at least 3 characters",
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(24.dp)
                                        .testTag("SearchStatus")
                                )
                            }
                        }

                        isSearching -> {
                            item {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(24.dp),
                                    contentAlignment = androidx.compose.ui.Alignment.Center
                                ) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.testTag("SearchLoading")
                                    )
                                }
                            }
                        }

                        searchedUsers.isEmpty() -> {
                            item {
                                Text(
                                    text = "No users found",
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(24.dp)
                                        .testTag("SearchStatus")
                                )
                            }
                        }
}
                    if (searchText.trim().length >= 3 && !isSearching) {
                    items(searchedUsers) { user ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    if (user.username == currentUsername) {
                                        // You're already on your own profile —
                                        // clearing the search reveals it rather
                                        // than pushing a duplicate of it.
                                        viewModel.updateSearchText("")
                                    } else {
                                        navController.navigate(Screen.Profile.createRoute(user.username))
                                    }
                                },
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(16.dp)
                                    .testTag(user.username),
                                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
                            ) {
                                ProfileAvatar(
                                    imageUrl = user.authorProfileImageUrl,
                                    originalImageUrl = user.authorProfileImageOriginalUrl,
                                    // Decorative — the username is rendered next to it.
                                    contentDescription = null,
                                    size = 40.dp,
                                    blurHash = user.authorProfileImageBlurHash
                                )
                                Spacer(modifier = Modifier.width(16.dp))
                                Text(
                                    text = user.username,
                                    style = MaterialTheme.typography.bodyLarge
                                )
                                if (user.identityIsVerified) {
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Icon(
                                        imageVector = Icons.Default.CheckCircle,
                                        contentDescription = "Verified",
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }
                        }
                    }
                    if (hasMoreResults) {
                        item {
                            Button(
                                onClick = {
                                    showAllResultsDialog = true
                                    viewModel.loadAllSearchResults()
                                },
                                enabled = !isLoadingAllResults,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(
                                    if (isLoadingAllResults) {
                                        "Loading..."
                                    } else {
                                        "View all results"
                                    }
                                )
                            }
                        }
                    }
                    }
                }
            } else {
                // The signed-in user's own profile.
                val username = currentUsername
                if (username != null) {
                    ProfileBody(
                        navController = navController,
                        api = api,
                        keychainHelper = keychainHelper,
                        username = username,
                        // Takes the space left under the search bar.
                        modifier = Modifier.weight(1f)
                    )
                } else {
                    // No readable session behind this screen. That should be
                    // unreachable — you can't get here without signing in — but
                    // when secure storage failed it *was* reachable, and the
                    // `?.let` that used to be here rendered nothing at all, so
                    // the whole profile silently vanished (issue #503). Say what
                    // happened instead of showing an empty tab.
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        contentAlignment = androidx.compose.ui.Alignment.Center
                    ) {
                        Text(
                            text = Constants.SESSION_MISSING_MESSAGE,
                            textAlign = TextAlign.Center,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier
                                .padding(24.dp)
                                .testTag("NoSessionNotice")
                        )
                    }
                }
            }
        }
        if (errorMessage != null) {
    AlertDialog(
        onDismissRequest = {
            showAllResultsDialog = false
            viewModel.clearError()
        },
        title = { Text("Search error") },
        text = {
            Text(errorMessage ?: "Something went wrong. Please try again.")
        },
        confirmButton = {
            Button(
                onClick = {
                    showAllResultsDialog = false
                    viewModel.clearError() }) {
                Text("OK")
            }
        }
    )
}
        if (showAllResultsDialog && errorMessage == null) {
            AlertDialog(
                onDismissRequest = {
                    showAllResultsDialog = false
                },
                title = {
                    Text("Search results")
                },
                text = {
                    if (isLoadingAllResults) {
                        Box(
                            modifier = Modifier.fillMaxWidth(),
                            contentAlignment = androidx.compose.ui.Alignment.Center
                        ) {
                            CircularProgressIndicator()
                        }
                    } else {
                        LazyColumn {
                            lazyItems(allSearchResults) { user ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable {
                                            showAllResultsDialog = false

                                            if (user.username == currentUsername) {
                                                viewModel.updateSearchText("")
                                            } else {
                                                navController.navigate(
                                                    Screen.Profile.createRoute(user.username)
                                                )
                                            }
                                        }
                                        .padding(12.dp),
                                    verticalAlignment =
                                        androidx.compose.ui.Alignment.CenterVertically
                                ) {
                                    ProfileAvatar(
                                        imageUrl = user.authorProfileImageUrl,
                                        originalImageUrl = user.authorProfileImageOriginalUrl,
                                        contentDescription = null,
                                        size = 40.dp,
                                        blurHash = user.authorProfileImageBlurHash
                                    )

                                    Spacer(modifier = Modifier.width(16.dp))

                                    Text(
                                        text = user.username,
                                        style = MaterialTheme.typography.bodyLarge
                                    )

                                    if (user.identityIsVerified) {
                                        Spacer(modifier = Modifier.width(8.dp))

                                        Icon(
                                            imageVector = Icons.Default.CheckCircle,
                                            contentDescription = "Verified",
                                            tint = MaterialTheme.colorScheme.primary,
                                            modifier = Modifier.size(16.dp)
                                        )
                                    }
                                }
                            }
                        }
                    }
                },
                confirmButton = {},
                dismissButton = {
                    TextButton(
                        onClick = {
                            showAllResultsDialog = false
                        }
                    ) {
                        Text("Close")
                    }
                }
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
fun HomeScreenPreview() {
    HomeScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper
    )
}
