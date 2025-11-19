package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen
import kotlinx.coroutines.launch

@Composable
fun VerifyResetScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    usernameOrEmail: String
) {
    var pin by remember { mutableStateOf("") }
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
            text = "Enter the 6-digit PIN sent to $usernameOrEmail.",
            style = MaterialTheme.typography.bodyMedium
        )

        TextField(
            value = pin,
            onValueChange = { newValue ->
                if (newValue.length <= 6 && newValue.all { it.isDigit() }) {
                    pin = newValue
                }
            },
            label = { Text("6-Digit PIN") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
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
                        val resetId = pin.toIntOrNull()
                        if (resetId == null || pin.length != 6) {
                            errorMessage = "PIN must be a 6-digit number."
                            showingErrorAlert = true
                            isLoading = false
                            return@launch
                        }

                        try {
                            api.verifyPasswordReset(usernameOrEmail = usernameOrEmail, resetID = resetId)
                            // On success, navigate to ResetPasswordScreen
                            navController.navigate(Screen.ResetPassword.createRoute(usernameOrEmail))
                        } catch (e: Exception) {
                            errorMessage = "Invalid PIN or an unknown error occurred."
                            showingErrorAlert = true
                        } finally {
                            isLoading = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = pin.length == 6
            ) {
                Text("Verify")
            }
        }
    }
}
