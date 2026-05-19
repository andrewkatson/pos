package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.VerificationRequest
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
fun VerifyResetScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    usernameOrEmail: String,
    onVerified: (String) -> Unit
) {
    PositiveOnlySocialTheme {
        var verificationToken by remember { mutableStateOf("") }
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
                text = "Verify Your Identity",
                style = MaterialTheme.typography.headlineSmall
            )

            Text(
                text = "Enter the verification token sent to $usernameOrEmail.",
                style = MaterialTheme.typography.bodyMedium
            )

            TextField(
                value = verificationToken,
                onValueChange = { verificationToken = it },
                label = { Text("Verification Token") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
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
                                val response = api.verifyReset(
                                    VerificationRequest(
                                        usernameOrEmail = usernameOrEmail,
                                        verificationToken = verificationToken
                                    )
                                )
                                if (!response.isSuccessful) {
                                    val backendError = response.errorBody()?.string()
                                        ?.let { runCatching { JSONObject(it).getString("error") }.getOrNull() }
                                    errorMessage = backendError ?: "Invalid token or an unknown error occurred."
                                    showingErrorAlert = true
                                    isLoading = false
                                    return@launch
                                }
                                val resetToken = response.body()?.resetToken
                                if (resetToken == null) {
                                    errorMessage = "Verification failed: no reset token received."
                                    showingErrorAlert = true
                                    isLoading = false
                                    return@launch
                                }
                                onVerified(resetToken)
                                navController.navigate(Screen.ResetPassword.createRoute(usernameOrEmail))
                            } catch (e: Exception) {
                                errorMessage = "Invalid token or an unknown error occurred."
                                showingErrorAlert = true
                            } finally {
                                isLoading = false
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = verificationToken.isNotEmpty()
                ) {
                    Text("Verify")
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun VerifyResetScreenPreview() {
    VerifyResetScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper,
        usernameOrEmail = "test@example.com",
        onVerified = {}
    )
}
