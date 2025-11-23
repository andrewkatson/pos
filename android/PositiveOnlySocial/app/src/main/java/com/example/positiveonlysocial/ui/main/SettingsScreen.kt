package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.security.KeychainHelper
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.SettingsViewModel
import com.example.positiveonlysocial.models.viewmodels.SettingsViewModelFactory
import com.example.positiveonlysocial.ui.navigation.Screen
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    authenticationManager: AuthenticationManager
) {
    val viewModel: SettingsViewModel = viewModel(
        factory = SettingsViewModelFactory(api, authenticationManager, keychainHelper)
    )
    
    // We need AuthenticationManager to perform the actual logout/delete state update
    // Ideally this should be injected or passed.
    // Assuming we can get it from CompositionLocal or passed down.
    // For now, creating a new instance is WRONG because it won't share state.
    // It must be passed.
    // Updating MainScreen to pass it or using a singleton/DI.
    // Since I didn't pass it to MainScreen, I should probably fix that.
    // But wait, MainScreen doesn't take AuthManager.
    // Let's assume for now we can't easily get the shared instance without DI.
    // However, `AuthenticationManager` is designed to be a singleton.
    // If I use the one from `DependencyProvider` (if I added it there), it would work.
    // I didn't add it to DependencyProvider yet.
    // I will assume for this file that I can get it, or I'll add it to DependencyProvider in a separate step.
    // Let's use a placeholder for now and I'll fix DependencyProvider.
    
    // Temporary fix: We need to access the AuthManager used in Login/Register.
    // Since I don't have Hilt, I should have put it in DependencyProvider.
    // I will assume DependencyProvider.authManager exists.
    
    var showingLogoutConfirm by remember { mutableStateOf(false) }
    var showingDeleteConfirm by remember { mutableStateOf(false) }
    
    // Observing ViewModel state
    val errorMessage by viewModel.errorMessage.collectAsState()
    val showingErrorAlert by viewModel.showingErrorAlert.collectAsState()

    if (showingLogoutConfirm) {
        AlertDialog(
            onDismissRequest = { showingLogoutConfirm = false },
            title = { Text("Are you sure you want to log out?") },
            confirmButton = {
                Button(
                    onClick = {
                        showingLogoutConfirm = false
                        // Perform logout
                        // We need the auth manager here.
                        // viewModel.logout(authManager)
                        // Since I can't access authManager easily here without changing signature,
                        // I'll assume I can pass it or get it.
                        // Let's assume I'll update DependencyProvider to include it.
                        // val authManager = DependencyProvider.authManager
                        viewModel.logout()

                        // For now, just navigating to Login as a visual effect, 
                        // but logic needs AuthManager.
                        navController.navigate(Screen.Login.route) {
                            popUpTo(Screen.Home.route) { inclusive = true }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color.Red)
                ) {
                    Text("Logout")
                }
            },
            dismissButton = {
                Button(onClick = { showingLogoutConfirm = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    if (showingDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showingDeleteConfirm = false },
            title = { Text("Delete Your Account?") },
            text = { Text("This action is permanent and cannot be undone.") },
            confirmButton = {
                Button(
                    onClick = {
                        showingDeleteConfirm = false
                        viewModel.deleteAccount()
                        navController.navigate(Screen.Login.route) {
                            popUpTo(Screen.Home.route) { inclusive = true }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color.Red)
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                Button(onClick = { showingDeleteConfirm = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    if (showingErrorAlert) {
        AlertDialog(
            onDismissRequest = { viewModel.clearError() },
            title = { Text("Error") },
            text = { Text(errorMessage ?: "Unknown error") },
            confirmButton = {
                Button(onClick = { viewModel.clearError() }) {
                    Text("OK")
                }
            }
        )
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            text = "Settings",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(16.dp)
        )
        
        ListListItem(text = "Logout", textColor = Color.Red) {
            showingLogoutConfirm = true
        }
        
        HorizontalDivider()
        
        Text(
            text = "Account Actions",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(16.dp)
        )
        
        ListListItem(text = "Delete Account", textColor = Color.Red) {
            showingDeleteConfirm = true
        }
    }
}

@Composable
fun ListListItem(text: String, textColor: Color = Color.Unspecified, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = text,
            color = textColor,
            modifier = Modifier.padding(16.dp)
        )
    }
}
