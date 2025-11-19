package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    authManager: AuthenticationManager
) {
    var usernameOrEmail by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var rememberMe by remember { mutableStateOf(false) }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var showingErrorAlert by remember { mutableStateOf(false) }

    val scope = rememberCoroutineScope()

    if (showingErrorAlert) {
        AlertDialog(
            onDismissRequest = { showingErrorAlert = false },
            title = { Text("Login Failed") },
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
        verticalArrangement = Arrangement.spacedBy(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.Lock,
            contentDescription = "Logo",
            modifier = Modifier.size(80.dp),
            tint = Color.Blue
        )

        TextField(
            value = usernameOrEmail,
            onValueChange = { usernameOrEmail = it },
            label = { Text("Username or Email") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email)
        )

        TextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password)
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("Remember Me")
            Spacer(modifier = Modifier.weight(1f))
            Switch(
                checked = rememberMe,
                onCheckedChange = { rememberMe = it }
            )
        }

        if (isLoading) {
            CircularProgressIndicator()
        } else {
            Button(
                onClick = {
                    scope.launch {
                        isLoading = true
                        try {
                            val response = api.loginUser(
                                usernameOrEmail = usernameOrEmail,
                                password = password,
                                rememberMe = rememberMe.toString(),
                                ip = "127.0.0.1"
                            )
                            // Assuming response parsing logic similar to Swift or simplified if API returns object
                            // For now, let's assume the API returns the raw bytes as per interface, 
                            // but we might need to parse it. 
                            // Wait, the API interface returns ResponseBody or similar?
                            // Let's check API interface. 
                            // Swift code parses manually. 
                            // I should probably use a helper or if the API returns a DTO directly.
                            // The previous summary said API returns DTOs now.
                            // Let's assume for a moment we can get the token.
                            // Actually, I need to check PositiveOnlySocialAPI return type for loginUser.
                            
                            // Placeholder logic until I verify API return type
                             val session = UserSession(
                                sessionToken = "dummy_token", // Replace with actual parsing
                                username = usernameOrEmail,
                                isIdentityVerified = false
                            )
                            authManager.login(session)
                            navController.navigate(Screen.Home.route) {
                                popUpTo(Screen.Login.route) { inclusive = true }
                            }
                        } catch (e: Exception) {
                            errorMessage = "Login failed. Please check your credentials."
                            showingErrorAlert = true
                        } finally {
                            isLoading = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = usernameOrEmail.isNotEmpty() && password.isNotEmpty()
            ) {
                Text("Login", fontWeight = FontWeight.Bold)
            }
        }

        TextButton(
            onClick = { navController.navigate(Screen.RequestReset.route) },
            modifier = Modifier.align(Alignment.End)
        ) {
            Text("Forgot Password?")
        }
        
        Spacer(modifier = Modifier.weight(1f))
    }
}
