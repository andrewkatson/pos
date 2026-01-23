package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.HomeViewModel
import com.example.positiveonlysocial.models.viewmodels.HomeViewModelFactory
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

@OptIn(ExperimentalMaterial3Api::class)
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
        
        val userPosts by viewModel.userPosts.collectAsState()
        val searchedUsers by viewModel.searchedUsers.collectAsState()
        val searchText by viewModel.searchText.collectAsState()
        
        // Trigger initial fetch
        LaunchedEffect(Unit) {
            if (userPosts.isEmpty()) {
                viewModel.fetchMyPosts()
            }
        }

        Column(modifier = Modifier.fillMaxSize()) {
            // Search Bar
            TextField(
                value = searchText,
                onValueChange = { viewModel.updateSearchText(it) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                placeholder = { Text("Search for Users") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true
            )

            if (searchText.isNotEmpty()) {
                // Search Results
                LazyVerticalGrid(
                    columns = GridCells.Fixed(1),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(searchedUsers) { user ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    navController.navigate(Screen.Profile.createRoute(user.username))
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
                                Icon(
                                    imageVector = Icons.Default.Person,
                                    contentDescription = null,
                                    modifier = Modifier.size(40.dp)
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
            } else {
                // User Posts Grid
                LazyVerticalGrid(
                    columns = GridCells.Fixed(3),
                    contentPadding = PaddingValues(2.dp),
                    horizontalArrangement = Arrangement.spacedBy(2.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
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
                        
                        // Infinite scroll trigger
                        if (post == userPosts.lastOrNull()) {
                            LaunchedEffect(Unit) {
                                viewModel.fetchMyPosts()
                            }
                        }
                    }
                }
            }
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
