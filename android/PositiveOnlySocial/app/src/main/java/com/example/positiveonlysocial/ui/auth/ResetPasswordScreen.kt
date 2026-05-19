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
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
fun ResetPasswordScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    usernameOrEmail: String,
    resetToken: String
) {
    PositiveOnlySocialTheme {
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
                                    password = newPassword,
                                    resetToken = resetToken
                                )
                                val response = api.resetPassword(request = request)
                                if (!response.isSuccessful) {
                                    val backendError = response.errorBody()?.string()
                                        ?.let { runCatching { JSONObject(it).getString("error") }.getOrNull() }
                                    errorMessage = backendError ?: "Password reset failed. Please try again."
                                    showingErrorAlert = true
                                } else {
                                    navController.navigate(Screen.Login.route) {
                                        popUpTo(Screen.Welcome.route) { inclusive = false }
                                    }
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
                    Text("Reset Password")
                }
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
        usernameOrEmail = "test@example.com",
        resetToken = ""
    )
}
