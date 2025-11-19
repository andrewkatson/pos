package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.User
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.ProfileViewModel
import com.example.positiveonlysocial.models.viewmodels.ProfileViewModelFactory
import com.example.positiveonlysocial.ui.navigation.Screen

@Composable
fun ProfileScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    username: String
) {
    // Create a dummy user object since ViewModel expects one, but we only have username from route
    // Ideally ViewModel should accept username or we fetch user first.
    // Based on Swift code, ProfileView takes a User object.
    // But navigation route only passes username.
    // Let's assume we construct a minimal User object or modify ViewModel to accept username.
    // For now, constructing minimal User.
    val user = User(username = username, identityIsVerified = false)
    
    val viewModel: ProfileViewModel = viewModel(
        factory = ProfileViewModelFactory(user, api, keychainHelper)
    )
    
    val userPosts by viewModel.userPosts.collectAsState()
    val profileDetails by viewModel.profileDetails.collectAsState()
    val isFollowing by viewModel.isFollowing.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    LaunchedEffect(Unit) {
        if (userPosts.isEmpty()) {
            viewModel.fetchUserPosts()
        }
        if (profileDetails == null) {
            viewModel.fetchProfileDetails()
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
                StatItem(count = userPosts.size, label = "Posts")
                StatItem(count = profileDetails?.followerCount ?: 0, label = "Followers")
                StatItem(count = profileDetails?.followingCount ?: 0, label = "Following")
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Button(
                onClick = { viewModel.toggleFollow() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isFollowing) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.primary
                )
            ) {
                Text(if (isFollowing) "Following" else "Follow")
            }
        }
        
        Divider()
        
        if (isLoading && userPosts.isEmpty()) {
            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (userPosts.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("$username hasn't posted anything yet.")
            }
        } else {
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
                    
                    if (post == userPosts.lastOrNull()) {
                        LaunchedEffect(Unit) {
                            viewModel.fetchUserPosts()
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun StatItem(count: Int, label: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = count.toString(), fontWeight = FontWeight.Bold)
        Text(text = label, style = MaterialTheme.typography.bodySmall)
    }
}
