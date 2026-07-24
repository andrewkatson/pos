package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.ResendVerificationEmailRequest
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import kotlinx.coroutines.launch

/**
 * Shown right after registration: the account exists but cannot log in until
 * the verification link in the welcome email is clicked (issue #237).
 */
@Composable
fun CheckEmailScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    email: String,
    // The new member's join number (issue #198). Non-null right after
    // registration; null when the screen is reached any other way.
    membershipNumber: Int? = null
) {
    PositiveOnlySocialTheme {
        var isResending by remember { mutableStateOf(false) }
        var resendMessage by remember { mutableStateOf<String?>(null) }
        // Greet a brand new member with their join number (issue #198).
        var showingWelcome by remember { mutableStateOf(membershipNumber != null) }

        val scope = rememberCoroutineScope()

        if (showingWelcome && membershipNumber != null) {
            AlertDialog(
                onDismissRequest = { showingWelcome = false },
                title = { Text("Welcome! 🎉") },
                text = { Text("You're member #$membershipNumber!") },
                confirmButton = {
                    Button(onClick = { showingWelcome = false }) {
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
            Text(
                text = "Check Your Email",
                fontSize = 30.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(top = 40.dp)
            )

            Text(
                text = "We sent a verification link to $email. Click it to activate your account — " +
                    "you won't be able to log in until your email is verified.",
                textAlign = TextAlign.Center
            )

            resendMessage?.let {
                Text(
                    text = it,
                    fontSize = 12.sp,
                    textAlign = TextAlign.Center
                )
            }

            if (isResending) {
                CircularProgressIndicator()
            } else {
                Button(
                    onClick = {
                        isResending = true
                        resendMessage = null
                        scope.launch {
                            try {
                                val response = api.resendVerificationEmail(
                                    ResendVerificationEmailRequest(usernameOrEmail = email)
                                )
                                resendMessage = if (response.isSuccessful) {
                                    "A new verification email is on its way. Check your inbox."
                                } else {
                                    ApiErrors.messageFor(response, fallback = "Could not resend the email. Please try again.")
                                }
                            } catch (e: Exception) {
                                resendMessage = ApiErrors.messageFor(e, fallback = "Could not resend the email. Please try again.")
                            } finally {
                                isResending = false
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Resend Verification Email", fontWeight = FontWeight.Bold)
                }
            }

            Button(
                onClick = {
                    navController.navigate(Screen.Login.route) {
                        // Registration is complete; keep only Welcome beneath so
                        // "back" can't return to the registration form.
                        popUpTo(Screen.Welcome.route)
                    }
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Go to Login", fontWeight = FontWeight.Bold)
            }

            Spacer(modifier = Modifier.weight(1f))
        }
    }
}

@Preview(showBackground = true)
@Composable
fun CheckEmailScreenPreview() {
    CheckEmailScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        email = "you@example.com"
    )
}
