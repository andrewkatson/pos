package com.example.positiveonlysocial

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.positiveonlysocial.di.DependencyProvider
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/**
 * Android counterpart to the iOS `testAutomaticLoginAfterRememberMe` UI test
 * (Positive Only SocialUITests). After logging in with "Remember Me" on, killing
 * and relaunching the app should land the user straight on Home without
 * re-entering credentials — the WelcomeScreen reads the persisted Remember Me
 * tokens and silently refreshes the session.
 *
 * Uses [createEmptyComposeRule] (instead of `createAndroidComposeRule`) so the
 * test owns the [ActivityScenario] lifecycle and can launch a genuinely fresh
 * Activity for the "relaunch". Recreating the existing Activity would restore the
 * saved Navigation back stack straight to Home and never exercise the auto-login.
 */
@RunWith(AndroidJUnit4::class)
class RememberMeLoginTest {

    @get:Rule
    val composeTestRule = createEmptyComposeRule()

    private val testUsername = "remember_user_${UUID.randomUUID().toString().take(5)}"
    private val strongPassword = "StrongPassword123@"

    // Matches the identifiers used by WelcomeScreen / AuthenticationManager.
    private val keychainService = "positive-only-social.Positive-Only-Social"
    private val rememberMeAccount = "userRememberMeTokens"
    private val sessionAccount = "userSessionToken"

    private var scenario: ActivityScenario<MainActivity>? = null

    @Before
    fun clearPersistedAuth() = clearKeychain()

    @After
    fun tearDown() {
        scenario?.close()
        // Don't leak a logged-in session into other tests running in this process.
        clearKeychain()
    }

    private fun clearKeychain() {
        val keychain = DependencyProvider.keychainHelper
        keychain.delete(keychainService, rememberMeAccount)
        keychain.delete(keychainService, sessionAccount)
    }

    @Test
    fun testAutomaticLoginAfterRememberMe() {
        // First launch: register, log out, then log back in with Remember Me on.
        scenario = ActivityScenario.launch(MainActivity::class.java)

        registerUser(testUsername, strongPassword)
        logoutUserFromHome()
        loginWithRememberMe(testUsername, strongPassword)
        assertOnHomeView()

        // Simulate killing and relaunching the app: a brand-new Activity with no
        // saved navigation state starts at the Welcome screen, whose auto-login
        // reads the persisted Remember Me tokens and signs us straight in.
        scenario?.close()
        scenario = ActivityScenario.launch(MainActivity::class.java)

        // If the tokens were not persisted at login we'd be stuck on the Welcome
        // screen, so waiting for the Home tabs proves the auto-login happened.
        composeTestRule.waitUntil(timeoutMillis = 10_000) {
            composeTestRule.onAllNodesWithText("Settings").fetchSemanticsNodes().isNotEmpty()
        }
        assertOnHomeView()
    }

    // MARK: Helpers (mirrored from PositiveOnlySocialIntegrationTests)

    private fun assertOnRegisterView() {
        composeTestRule.onNodeWithText("Create Account").assertExists()
        composeTestRule.onNodeWithText("Username").assertExists()
        composeTestRule.onNodeWithText("Email").assertExists()
        composeTestRule.onNodeWithText("Password").assertExists()
        composeTestRule.onNodeWithText("Confirm Password").assertExists()
        composeTestRule.onNodeWithText("Register").assertExists()
    }

    private fun assertOnLoginView() {
        composeTestRule.onNodeWithText("Username or Email").assertExists()
        composeTestRule.onNodeWithText("Password").assertExists()
        composeTestRule.onNodeWithText("Login").assertExists()
        composeTestRule.onNodeWithText("Remember Me").assertExists()
        composeTestRule.onNodeWithText("Forgot Password?").assertExists()
    }

    private fun assertOnHomeView() {
        composeTestRule.onNodeWithText("Home").assertExists()
        composeTestRule.onNodeWithText("Feed").assertExists()
        composeTestRule.onNodeWithText("Post").assertExists()
        composeTestRule.onNodeWithText("Settings").assertExists()
    }

    private fun assertOnSettingsView() {
        composeTestRule.onNodeWithText("Logout").assertExists()
        composeTestRule.onNodeWithText("Delete Account").assertExists()
    }

    private fun registerUser(username: String, password: String) {
        composeTestRule.onNodeWithText("Register").performClick()
        assertOnRegisterView()

        composeTestRule.onNodeWithText("Username").performTextInput(username)
        composeTestRule.onNodeWithText("Email").performTextInput("$username@test.com")
        composeTestRule.onNodeWithText("Date of Birth (YYYY-MM-DD)").performTextInput("1970-01-01")
        composeTestRule.onNodeWithText("Password").performTextInput(password)
        composeTestRule.onNodeWithText("Confirm Password").performTextInput(password)

        composeTestRule.onNodeWithText("Register").performClick()

        // Privacy Policy dialog.
        composeTestRule.onNodeWithText("Privacy Policy").assertExists()
        composeTestRule.onNodeWithText("Ok").performClick()

        assertOnHomeView()
    }

    private fun logoutUserFromHome() {
        composeTestRule.onNodeWithText("Settings").performClick()
        assertOnSettingsView()

        composeTestRule.onNodeWithText("Logout").performClick()
        composeTestRule.onNodeWithText("Confirm").performClick()

        assertOnLoginView()
    }

    private fun loginWithRememberMe(username: String, password: String) {
        // logoutUserFromHome leaves us on the Login screen.
        assertOnLoginView()

        composeTestRule.onNodeWithText("Username or Email").performTextInput(username)
        composeTestRule.onNodeWithText("Password").performTextInput(password)
        composeTestRule.onNodeWithText("Remember Me").performClick()

        composeTestRule.onNodeWithText("Login").performClick()
        assertOnHomeView()
    }
}
