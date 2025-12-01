package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.PasswordResetSubmitRequest
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen
import kotlinx.coroutines.launch

@Composable
fun ResetPasswordScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    usernameOrEmail: String
) {
    var username by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var showingErrorAlert by remember { mutableStateOf(false) }

    val scope = rememberCoroutineScope()

    val isPasswordMatching = confirmPassword.isEmpty() || newPassword == confirmPassword
    val isFormValid = username.isNotEmpty() && email.isNotEmpty() && newPassword.isNotEmpty() && newPassword == confirmPassword

    // Pre-fill username or email based on input
    LaunchedEffect(usernameOrEmail) {
        if (usernameOrEmail.contains("@")) {
            email = usernameOrEmail
        } else {
            username = usernameOrEmail
        }
    }

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
            text = "Reset Password",
            style = MaterialTheme.typography.headlineSmall
        )

        Text(
            text = "Confirm Credentials",
            style = MaterialTheme.typography.titleMedium
        )

        TextField(
            value = username,
            onValueChange = { username = it },
            label = { Text("Username") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        TextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Email") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email)
        )

        Text(
            text = "Set New Password",
            style = MaterialTheme.typography.titleMedium
        )

        TextField(
            value = newPassword,
            onValueChange = { newPassword = it },
            label = { Text("New Password") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password)
        )

        TextField(
            value = confirmPassword,
            onValueChange = { confirmPassword = it },
            label = { Text("Confirm Password") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password)
        )

        if (!isPasswordMatching) {
            Text(
                text = "Passwords do not match.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.fillMaxWidth()
            )
        }

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
                            val request = PasswordResetSubmitRequest(
                                username = username,
                                email = email,
                                password = newPassword
                            )
                            api.resetPassword(
                                request = request
                            )
                            // On success, navigate to Home (or Login, but Swift goes to Home so let's assume auto-login or just Home)
                            // Swift code: didResetSuccessfully = true -> HomeView
                            // We should probably navigate to Login to be safe or Home if we can auto-login.
                            // The Swift code implies it logs in or just goes to Home. 
                            // Let's go to Home for now to match Swift behavior, but note we might not have a session.
                            // Actually, without a session token, Home might fail. 
                            // But let's follow the Swift flow.
                            navController.navigate(Screen.Home.route) {
                                popUpTo(Screen.Login.route) { inclusive = true }
                            }
                        } catch (e: Exception) {
                            errorMessage = e.localizedMessage ?: "An unknown error occurred."
                            showingErrorAlert = true
                        } finally {
                            isLoading = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = isFormValid
            ) {
                Text("Reset Password and Login")
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun ResetPasswordScreenPreview() {
    ResetPasswordScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper,
        usernameOrEmail = "test@example.com"
    )
}
