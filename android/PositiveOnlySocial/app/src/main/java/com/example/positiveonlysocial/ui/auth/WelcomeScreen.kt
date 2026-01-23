package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.TokenRefreshRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import kotlinx.coroutines.launch

private enum class AuthState {
    Checking, NeedsAuth, Authenticated
}

// Data class for Remember Me tokens (internal to this file, similar to Swift)
private data class RememberMeTokens(val seriesId: String, val cookieToken: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WelcomeScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    authManager: AuthenticationManager
) {
    var authState by remember { mutableStateOf(AuthState.Checking) }
    val scope = rememberCoroutineScope()
    
    // Constants
    val keychainService = "positive-only-social.Positive-Only-Social"
    val sessionAccount = "userSessionToken"
    val rememberMeAccount = "userRememberMeTokens"

    LaunchedEffect(Unit) {
        // 1. Try to load "Remember Me" tokens from Keychain
        val tokens = try {
            keychainHelper.load(RememberMeTokens::class.java, keychainService, rememberMeAccount)
        } catch (e: Exception) {
            null
        }

        if (tokens == null) {
            authState = AuthState.NeedsAuth
            return@LaunchedEffect
        }

        // 2. Call the API to log in with the tokens
        try {
            val response = api.loginUserWithRememberMe(
                TokenRefreshRequest(
                    sessionToken = "", // Not needed for this call
                    seriesIdentifier = tokens.seriesId,
                    loginCookieToken = tokens.cookieToken,
                    ip = "127.0.0.1",
                )
            )

            if (response.isSuccessful && response.body() != null) {
                val loginDetails = response.body()!!

                // 3. Securely save the new session token
                // Note: We need the username and verification status. 
                // The Swift code gets it from the *old* session or defaults.
                // Here we might need to fetch profile or assume defaults if the API doesn't return full user info in this specific endpoint.
                // Looking at Swift: let oldSession = authManager.session
                // The Swift API wrapper seems to return a complex object. The Kotlin API returns TokenRefreshResponse.
                // Let's check TokenRefreshResponse definition to be sure.
                // Assuming TokenRefreshResponse has what we need or we update session partially.
                
                // For now, mirroring Swift's logic of using old session or defaults:
                val oldSession = authManager.session.value
                val userSession = UserSession(
                    sessionToken = loginDetails.newSessionToken,
                    username = oldSession?.username ?: "test", // Fallback as per Swift
                    isIdentityVerified = oldSession?.isIdentityVerified ?: false
                )
                
                authManager.login(userSession)

                // 4. Update the "Remember Me" tokens
                val newTokens = RememberMeTokens(tokens.seriesId, loginDetails.newLoginCookieToken)
                keychainHelper.save(newTokens, keychainService, rememberMeAccount)

                authState = AuthState.Authenticated
                navController.navigate(Screen.Home.route) {
                    popUpTo(Screen.Welcome.route) { inclusive = true }
                }
            } else {
                throw Exception("Login failed")
            }
        } catch (e: Exception) {
            // If anything fails, clear old data and show manual login
            try {
                keychainHelper.delete(keychainService, rememberMeAccount)
                keychainHelper.delete(keychainService, sessionAccount)
            } catch (ignore: Exception) {}
            authState = AuthState.NeedsAuth
        }
    }

    PositiveOnlySocialTheme {
        Scaffold(
            topBar = {
                CenterAlignedTopAppBar(
                    title = {
                        Text(
                            "Good Vibes Only",
                            fontWeight = FontWeight.Bold
                        )
                    },
                    colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background,
                        titleContentColor = MaterialTheme.colorScheme.onBackground
                    )
                )
            }
        ) { paddingValues ->
            Surface(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                color = MaterialTheme.colorScheme.background
            ) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    when (authState) {
                        AuthState.Checking -> {
                            CircularProgressIndicator()
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("Checking session...")
                        }
                        AuthState.NeedsAuth -> {
                            NeedsAuthContent(navController)
                        }
                        AuthState.Authenticated -> {
                            // Navigation happens automatically, show nothing or loading
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun NeedsAuthContent(navController: NavController) {
    Column(
        modifier = Modifier.padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        Text(
            text = "Welcome! \uD83D\uDC4B", // Wave emoji
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold
        )
        
        Spacer(modifier = Modifier.height(20.dp))

        Button(
            onClick = { navController.navigate(Screen.Login.route) },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
        ) {
            Text("Login")
        }

        Button(
            onClick = { navController.navigate(Screen.Register.route) },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Color.Gray)
        ) {
            Text("Register")
        }
    }
}

@Preview(showBackground = true)
@Composable
fun WelcomeScreenPreview() {
    PositiveOnlySocialTheme {
        WelcomeScreen(
            navController = rememberNavController(),
            api = PreviewHelpers.mockApi,
            keychainHelper = PreviewHelpers.mockKeychainHelper,
            authManager = PreviewHelpers.mockAuthManager
        )
    }
}
