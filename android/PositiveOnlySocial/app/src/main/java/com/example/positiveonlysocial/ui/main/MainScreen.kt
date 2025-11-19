package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.AddBox
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.NavController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen

@Composable
fun MainScreen(
    rootNavController: NavController, // For navigating out of the main flow (e.g. logout)
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    val bottomNavController = rememberNavController()
    
    Scaffold(
        bottomBar = {
            NavigationBar {
                val currentRoute = bottomNavController.currentBackStackEntryAsState().value?.destination?.route
                
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Home, contentDescription = "Home") },
                    label = { Text("Home") },
                    selected = currentRoute == Screen.Home.route,
                    onClick = { bottomNavController.navigate(Screen.Home.route) }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.List, contentDescription = "Feed") },
                    label = { Text("Feed") },
                    selected = currentRoute == Screen.Feed.route,
                    onClick = { bottomNavController.navigate(Screen.Feed.route) }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.AddBox, contentDescription = "Post") },
                    label = { Text("Post") },
                    selected = currentRoute == Screen.NewPost.route,
                    onClick = { bottomNavController.navigate(Screen.NewPost.route) }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Settings, contentDescription = "Settings") },
                    label = { Text("Settings") },
                    selected = currentRoute == Screen.Settings.route,
                    onClick = { bottomNavController.navigate(Screen.Settings.route) }
                )
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = bottomNavController,
            startDestination = Screen.Home.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Home.route) {
                HomeScreen(rootNavController, api, keychainHelper)
            }
            composable(Screen.Feed.route) {
                FeedScreen(rootNavController, api, keychainHelper)
            }
            composable(Screen.NewPost.route) {
                NewPostScreen(rootNavController, api, keychainHelper)
            }
            composable(Screen.Settings.route) {
                SettingsScreen(rootNavController, api, keychainHelper)
            }
        }
    }
}

// Helper to observe current back stack entry
@Composable
fun androidx.navigation.NavController.currentBackStackEntryAsState(): State<androidx.navigation.NavBackStackEntry?> {
    val currentNavBackStackEntry = remember { mutableStateOf(currentBackStackEntry) }
    DisposableEffect(this) {
        val listener = androidx.navigation.NavController.OnDestinationChangedListener { controller, _, _ ->
            currentNavBackStackEntry.value = controller.currentBackStackEntry
        }
        addOnDestinationChangedListener(listener)
        onDispose {
            removeOnDestinationChangedListener(listener)
        }
    }
    return currentNavBackStackEntry
}
