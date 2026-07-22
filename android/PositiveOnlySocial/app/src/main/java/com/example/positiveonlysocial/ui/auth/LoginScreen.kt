package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.LoginRequest
import com.example.positiveonlysocial.data.model.LoginTwoFactorRequest
import com.example.positiveonlysocial.data.model.RememberMeTokens
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.ui.dismissKeyboardOnTap
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    authManager: AuthenticationManager
) {
    PositiveOnlySocialTheme {
        var usernameOrEmail by remember { mutableStateOf("") }
        var password by remember { mutableStateOf("") }
        var rememberMe by remember { mutableStateOf(false) }
        var isLoading by remember { mutableStateOf(false) }
        var errorMessage by remember { mutableStateOf<String?>(null) }
        var showingErrorAlert by remember { mutableStateOf(false) }

        // Two-factor step (issue #348). Set when login answered with a
        // challenge instead of a session; the login form is replaced by the
        // code-entry step until the challenge is exchanged (or the user goes
        // back).
        var twoFactorChallengeToken by remember { mutableStateOf<String?>(null) }
        var twoFactorCode by remember { mutableStateOf("") }
        var useRecoveryCode by remember { mutableStateOf(false) }

        val scope = rememberCoroutineScope()
        val focusManager = LocalFocusManager.current

        // Keychain identifiers, matching WelcomeScreen's auto-login reader and
        // AuthenticationManager's session store.
        val keychainService = "positive-only-social.Positive-Only-Social"
        val rememberMeAccount = "userRememberMeTokens"

        // Authenticator codes are 6 digits; recovery codes are 10 hex
        // characters (backend/user_system/constants.py Patterns).
        val trimmedCode = twoFactorCode.trim()
        val isTwoFactorCodeValid = if (useRecoveryCode) {
            trimmedCode.length == 10 && trimmedCode.lowercase().all { it in "0123456789abcdef" }
        } else {
            trimmedCode.length == 6 && trimmedCode.all { it.isDigit() }
        }

        /** Shared tail of both login steps: persist the session and enter the app. */
        suspend fun completeLogin(
            sessionToken: String?,
            username: String?,
            userId: String?,
            seriesIdentifier: String?,
            loginCookieToken: String?
        ) {
            if (sessionToken == null || userId == null) {
                errorMessage = "Login failed: the server response was missing a session token or user ID."
                showingErrorAlert = true
                return
            }
            val session = UserSession(
                sessionToken = sessionToken,
                username = username ?: usernameOrEmail,
                userId = userId,
                isIdentityVerified = false
            )
            authManager.login(session)

            // Persist (or clear) the remember-me tokens so WelcomeScreen can
            // silently re-authenticate on the next launch. Mirrors iOS
            // LoginView. Best-effort: a storage failure must not block this
            // session's login.
            try {
                if (rememberMe && seriesIdentifier != null && loginCookieToken != null) {
                    keychainHelper.save(
                        RememberMeTokens(seriesIdentifier, loginCookieToken),
                        keychainService,
                        rememberMeAccount
                    )
                } else {
                    keychainHelper.delete(keychainService, rememberMeAccount)
                }
            } catch (e: Exception) {
                android.util.Log.w(
                    "LoginScreen",
                    "Failed to persist/clear remember-me tokens; continuing without auto-login.",
                    e,
                )
            }

            navController.navigate(Screen.Home.route) {
                popUpTo(Screen.Login.route) { inclusive = true }
            }
        }

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
                .dismissKeyboardOnTap()
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

            if (twoFactorChallengeToken != null) {
                // MARK: - Two-factor code entry step
                Text(
                    if (useRecoveryCode) "Enter one of your recovery codes. Each code works only once."
                    else "Enter the 6-digit code from your authenticator app."
                )

                TextField(
                    value = twoFactorCode,
                    onValueChange = { twoFactorCode = it },
                    label = { Text(if (useRecoveryCode) "Recovery Code" else "Authenticator Code") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("TwoFactorCodeField"),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = if (useRecoveryCode) KeyboardType.Ascii else KeyboardType.NumberPassword,
                        imeAction = ImeAction.Done
                    ),
                    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
                )

                if (isLoading) {
                    CircularProgressIndicator()
                } else {
                    Button(
                        onClick = {
                            // Snapshot the token before suspending: it can be
                            // cleared (Back to login, or an expired-challenge
                            // reset) while this request is in flight, and !!
                            // inside the coroutine would then crash.
                            val challengeToken = twoFactorChallengeToken ?: return@Button
                            scope.launch {
                                isLoading = true
                                try {
                                    val code = twoFactorCode.trim()
                                    val response = api.loginUser2FA(
                                        LoginTwoFactorRequest(
                                            challengeToken = challengeToken,
                                            totpCode = if (useRecoveryCode) null else code,
                                            // Recovery codes are sent lowercased to
                                            // match the backend pattern.
                                            recoveryCode = if (useRecoveryCode) code.lowercase() else null
                                        )
                                    )
                                    if (response.isSuccessful) {
                                        val body = response.body()
                                        completeLogin(
                                            sessionToken = body?.sessionToken,
                                            username = body?.username,
                                            userId = body?.userId,
                                            seriesIdentifier = body?.seriesIdentifier,
                                            loginCookieToken = body?.loginCookieToken
                                        )
                                    } else {
                                        val errorMsg = ApiErrors.messageFor(response, fallback = "Verification failed. Please try again.")
                                        if (errorMsg == Constants.INVALID_TWO_FACTOR_CHALLENGE) {
                                            // The challenge timed out (or was
                                            // invalidated): start over from the
                                            // default authenticator-code entry.
                                            twoFactorChallengeToken = null
                                            twoFactorCode = ""
                                            useRecoveryCode = false
                                            errorMessage = "Your login expired. Please sign in again."
                                        } else {
                                            errorMessage = errorMsg
                                        }
                                        showingErrorAlert = true
                                    }
                                } catch (e: Exception) {
                                    errorMessage = "Verification failed. Please check your network connection."
                                    showingErrorAlert = true
                                } finally {
                                    isLoading = false
                                }
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("VerifyTwoFactorButton"),
                        enabled = isTwoFactorCodeValid
                    ) {
                        Text("Verify", fontWeight = FontWeight.Bold)
                    }
                }

                // Both are disabled mid-request so the code kind can't change
                // under an in-flight verification, and so a completing request
                // can't log the user in after they've navigated back.
                TextButton(
                    onClick = {
                        useRecoveryCode = !useRecoveryCode
                        twoFactorCode = ""
                    },
                    enabled = !isLoading
                ) {
                    Text(if (useRecoveryCode) "Use an authenticator code instead" else "Use a recovery code instead")
                }

                TextButton(
                    onClick = {
                        twoFactorChallengeToken = null
                        twoFactorCode = ""
                        useRecoveryCode = false
                    },
                    enabled = !isLoading
                ) {
                    Text("Back to login")
                }
            } else {
                TextField(
                    value = usernameOrEmail,
                    onValueChange = { usernameOrEmail = it },
                    label = { Text("Username or Email") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
                )

                TextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Remember Me")
                    Spacer(modifier = Modifier.weight(1f))
                    Switch(
                        checked = rememberMe,
                        onCheckedChange = { rememberMe = it },
                        // Tag the actual toggle so tests flip it directly. Clicking the
                        // "Remember Me" label does nothing — it's a sibling, not the switch.
                        modifier = Modifier.testTag("RememberMeToggle")
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
                                    val loginRequest = LoginRequest(
                                        usernameOrEmail = usernameOrEmail,
                                        password = password,
                                        rememberMe = rememberMe.toString(),
                                        ip = "127.0.0.1"
                                    )

                                    val response = api.loginUser(
                                        request = loginRequest
                                    )

                                    if (response.isSuccessful) {
                                        val body = response.body()
                                        if (body?.twoFactorRequired == true && body.challengeToken != null) {
                                            // Password accepted, but the account
                                            // needs its second factor. Start in
                                            // the default authenticator-code mode.
                                            twoFactorChallengeToken = body.challengeToken
                                            twoFactorCode = ""
                                            useRecoveryCode = false
                                        } else {
                                            completeLogin(
                                                sessionToken = body?.sessionToken,
                                                username = body?.username,
                                                userId = body?.userId,
                                                seriesIdentifier = body?.seriesIdentifier,
                                                loginCookieToken = body?.loginCookieToken
                                            )
                                        }
                                    } else {
                                        val errorMsg = ApiErrors.messageFor(response, fallback = "Login failed. Please check your credentials.")
                                        errorMessage = when (errorMsg) {
                                            Constants.ACCOUNT_BANNED -> Constants.ACCOUNT_SUSPENDED_MESSAGE
                                            Constants.EMAIL_NOT_VERIFIED -> Constants.EMAIL_NOT_VERIFIED_MESSAGE
                                            else -> errorMsg
                                        }
                                        showingErrorAlert = true
                                    }
                                } catch (e: Exception) {
                                    errorMessage = "Login failed. Please check your network connection."
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
            }

            Spacer(modifier = Modifier.weight(1f))
        }
    }
}

@Preview(showBackground = true)
@Composable
fun LoginScreenPreview() {
    LoginScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper,
        authManager = PreviewHelpers.mockAuthManager
    )
}
