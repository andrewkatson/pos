package com.example.positiveonlysocial.ui.auth

import android.util.Log
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.RememberMeTokens
import com.example.positiveonlysocial.data.model.TokenRefreshRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import kotlinx.coroutines.launch

private const val TAG = "WelcomeScreen"

private enum class AuthState {
    Checking, NeedsAuth, Authenticated
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WelcomeScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    authManager: AuthenticationManager
) {
    var authState by remember { mutableStateOf(AuthState.Checking) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    val keychainService = "positive-only-social.Positive-Only-Social"
    val sessionAccount = "userSessionToken"
    val rememberMeAccount = "userRememberMeTokens"

    LaunchedEffect(Unit) {
        try {
            // Try to load "Remember Me" tokens from Keychain
            val tokens = try {
                keychainHelper.load(RememberMeTokens::class.java, keychainService, rememberMeAccount)
            } catch (e: Exception) {
                Log.w(TAG, "No remember me tokens found: ${e.message}")
                null
            }

            if (tokens == null) {
                authState = AuthState.NeedsAuth
                return@LaunchedEffect
            }

            // Call the API to log in with the tokens
            try {
                // Load the persisted session first: the backend requires the
                // original session_management_token (which must belong to the
                // cookie's user) for the remember-me refresh, so we pass it in
                // rather than an empty string.
                val existingSession = authManager.session.value
                    ?: keychainHelper.load(UserSession::class.java, keychainService, sessionAccount)
                if (existingSession == null) {
                    throw Exception("Automatic sign-in failed. Please log in again.")
                }
                if (existingSession.userId.isEmpty()) {
                    throw Exception("Automatic sign-in failed. Please log in again.")
                }

                val response = api.loginUserWithRememberMe(
                    TokenRefreshRequest(
                        sessionToken = existingSession.sessionToken,
                        seriesIdentifier = tokens.seriesId,
                        loginCookieToken = tokens.cookieToken,
                        ip = "127.0.0.1",
                    )
                )

                if (response.isSuccessful && response.body() != null) {
                    val loginDetails = response.body()!!
                    val userSession = UserSession(
                        sessionToken = loginDetails.newSessionToken,
                        username = existingSession.username,
                        userId = existingSession.userId,
                        isIdentityVerified = existingSession.isIdentityVerified
                    )

                    authManager.login(userSession)

                    // Update the "Remember Me" tokens
                    val newTokens = RememberMeTokens(tokens.seriesId, loginDetails.newLoginCookieToken)
                    keychainHelper.save(newTokens, keychainService, rememberMeAccount)

                    authState = AuthState.Authenticated
                    navController.navigate(Screen.Home.route) {
                        popUpTo(Screen.Welcome.route) { inclusive = true }
                    }
                } else {
                    throw Exception("Login failed with status: ${response.code()}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Auto-login failed", e)
                errorMessage = e.message
                // Clear old data and show manual login
                try {
                    keychainHelper.delete(keychainService, rememberMeAccount)
                    keychainHelper.delete(keychainService, sessionAccount)
                } catch (ignore: Exception) {
                    Log.w(TAG, "Failed to clear keychain: ${ignore.message}")
                }
                authState = AuthState.NeedsAuth
            }
        } catch (e: Exception) {
            Log.e(TAG, "LaunchedEffect error", e)
            errorMessage = e.message
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
                            if (errorMessage != null) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    "Debug: $errorMessage",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color.Gray
                                )
                            }
                        }
                        AuthState.NeedsAuth -> {
                            NeedsAuthContent(navController, errorMessage)
                        }
                        AuthState.Authenticated -> {
                            CircularProgressIndicator()
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("Logging in...")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun NeedsAuthContent(navController: NavController, debugMessage: String? = null) {
    Column(
        modifier = Modifier.padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        Text(
            text = "Welcome! 👋",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold
        )

        if (debugMessage != null) {
            Text(
                "Debug: $debugMessage",
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray
            )
        }

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