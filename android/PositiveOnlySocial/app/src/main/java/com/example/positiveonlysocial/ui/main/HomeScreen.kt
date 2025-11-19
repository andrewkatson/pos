package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.HomeViewModel
import com.example.positiveonlysocial.models.viewmodels.HomeViewModelFactory
import com.example.positiveonlysocial.ui.navigation.Screen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
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
            // TODO: Implement UserSearchResultsView equivalent
            Text("Search Results Placeholder")
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
                                navController.navigate(Screen.PostDetail.createRoute(post.id))
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
