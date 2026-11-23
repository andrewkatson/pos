package com.example.positiveonlysocial

import android.content.Context
import android.util.Base64
import androidx.compose.material3.Text
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.auth.GoogleSignInProviding
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.ui.auth.LoginScreen
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.preview.MockKeychainHelper
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * A first Google sign-in from the login screen must not create an account until
 * the user agrees to the privacy policy and terms (PR #622). Renders the real
 * LoginScreen against the in-memory stub, which applies the same consent gate as
 * login_user_google, with Google's account picker replaced by a fake.
 */
@RunWith(AndroidJUnit4::class)
class GoogleSignUpConsentTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    private val homeMarker = "HOME_SCREEN_REACHED"

    /** Hands back an unsigned token carrying the claims the stub reads. */
    private class FakeGoogleSignIn : GoogleSignInProviding {
        override val isConfigured = true
        override suspend fun signIn(context: Context): String {
            val flags = Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING
            val header = Base64.encodeToString("""{"alg":"none"}""".toByteArray(), flags)
            val claims = """{"sub":"consent-sub","email":"consentperson@example.com","email_verified":true}"""
            return "$header.${Base64.encodeToString(claims.toByteArray(), flags)}.sig"
        }
    }

    @Before
    fun showLoginScreen() {
        val api = StatefulStubbedAPI()
        val keychain = MockKeychainHelper()
        val authManager = AuthenticationManager(keychain)
        composeTestRule.setContent {
            val navController = rememberNavController()
            NavHost(navController = navController, startDestination = Screen.Login.route) {
                composable(Screen.Login.route) {
                    LoginScreen(
                        navController = navController,
                        api = api,
                        keychainHelper = keychain,
                        authManager = authManager,
                        googleSignIn = FakeGoogleSignIn(),
                    )
                }
                composable(Screen.Home.route) { Text(homeMarker) }
            }
        }
    }

    private fun tapGoogleAndWaitForConsent() {
        composeTestRule.onNodeWithTag("GoogleSignInButton").performClick()
        composeTestRule.waitUntil(timeoutMillis = 5_000) {
            composeTestRule.onAllNodesWithText(Constants.GOOGLE_SIGN_UP_CONSENT_TITLE)
                .fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test
    fun aNewGoogleAccountIsAskedForConsentAndCancelCreatesNothing() {
        tapGoogleAndWaitForConsent()

        // Asking is not a failure: no error dialog alongside it.
        composeTestRule.onNodeWithText("Login Failed").assertDoesNotExist()
        composeTestRule.onNodeWithText(Constants.PRIVACY_POLICY_TEXT).assertExists()

        composeTestRule.onNodeWithTag("GoogleConsentCancelButton").performClick()

        composeTestRule.onNodeWithText(Constants.GOOGLE_SIGN_UP_CONSENT_TITLE).assertDoesNotExist()
        composeTestRule.onNodeWithText(homeMarker).assertDoesNotExist()
        composeTestRule.onNodeWithText("Forgot Password?").assertIsDisplayed()

        // Nothing was created, so trying again asks again.
        tapGoogleAndWaitForConsent()
    }

    @Test
    fun readingTheTermsKeepsTheConsentDialogAndAgreeingSignsIn() {
        tapGoogleAndWaitForConsent()

        // Below the full privacy policy in a scrolling column, so it can be
        // off screen on a short phone.
        composeTestRule.onNodeWithTag("GoogleConsentTermsButton").performScrollTo().performClick()
        composeTestRule.onNodeWithText("Terms of Service").assertExists()
        composeTestRule.onNodeWithText("Ok").performClick()

        // Still there once the terms close: the held token wasn't discarded.
        composeTestRule.onNodeWithTag("GoogleConsentAgreeButton").assertExists().performClick()

        composeTestRule.waitUntil(timeoutMillis = 5_000) {
            composeTestRule.onAllNodesWithText(homeMarker).fetchSemanticsNodes().isNotEmpty()
        }
    }
}
