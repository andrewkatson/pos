package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.ResetRequest
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen
import kotlinx.coroutines.launch

@Composable
fun RequestResetScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    var usernameOrEmail by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var showingErrorAlert by remember { mutableStateOf(false) }

    val scope = rememberCoroutineScope()

    if (showingErrorAlert) {
        AlertDialog(
            onDismissRequest = { showingErrorAlert = false },
            title = { Text("Error") },
            text = { Text(errorMessage ?: "An unknown error occurred.") },
            confirmButton = {
                Button(onClick = { showingErrorAlert = false }) {
                    Text("OK")
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        Text(
            text = "Find Your Account",
            style = MaterialTheme.typography.headlineSmall
        )

        TextField(
            value = usernameOrEmail,
            onValueChange = { usernameOrEmail = it },
            label = { Text("Username or Email") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email)
        )

        if (isLoading) {
            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else {
            Button(
                onClick = {
                    scope.launch {
                        isLoading = true
                        try {
                            val request = ResetRequest(usernameOrEmail = usernameOrEmail)
                            api.requestReset(request = request)
                            // On success, navigate to VerifyResetScreen
                            navController.navigate(Screen.VerifyReset.createRoute(usernameOrEmail))
                        } catch (e: Exception) {
                            errorMessage = e.localizedMessage ?: "An unknown error occurred."
                            showingErrorAlert = true
                        } finally {
                            isLoading = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = usernameOrEmail.isNotEmpty()
            ) {
                Text("Request Reset")
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun RequestResetScreenPreview() {
    RequestResetScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper
    )
}
