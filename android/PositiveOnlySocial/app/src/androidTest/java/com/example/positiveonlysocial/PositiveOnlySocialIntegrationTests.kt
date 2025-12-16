package com.example.positiveonlysocial

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.espresso.Espresso
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class PositiveOnlySocialIntegrationTests {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    private val testUsername = "test_user_${UUID.randomUUID().toString().take(5)}"
    private val otherTestUsername = "other_user_${UUID.randomUUID().toString().take(5)}"
    private val newTestUsername = "new_user_${UUID.randomUUID().toString().take(5)}"
    private val strongPassword = "StrongPassword123!"
    private val newStrongPassword = "NewStrongPassword456!"

    // MARK: Helpers

    private fun dismissKeyboardIfPresent() {
        Espresso.closeSoftKeyboard()
    }

    private fun assertOnWelcomeView() {
        composeTestRule.onNodeWithText("Register").assertExists()
        composeTestRule.onNodeWithText("Login").assertExists()
    }

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
        // Assuming Bottom Navigation items
        composeTestRule.onNodeWithText("Home").assertExists()
        composeTestRule.onNodeWithText("Feed").assertExists()
        composeTestRule.onNodeWithText("Post")
            .assertExists() // "New Post" might be just "Post" or icon
        composeTestRule.onNodeWithText("Settings").assertExists()
    }

    private fun assertOnSettingsView() {
        composeTestRule.onNodeWithText("Logout").assertExists()
        composeTestRule.onNodeWithText("Delete Account").assertExists()
    }

    private fun assertOnProfileView() {
        composeTestRule.waitUntil(timeoutMillis = 10000) {
            composeTestRule
                .onAllNodesWithTag("tag_Posts")
                .fetchSemanticsNodes().isNotEmpty()
        }

        composeTestRule
            .onNodeWithTag("tag_Followers", true).assertIsDisplayed()
        composeTestRule
            .onNodeWithTag("tag_Following", true).assertIsDisplayed()
        composeTestRule
            .onNodeWithTag("tag_Posts", true).assertIsDisplayed()
    }

    private fun assertOnNewPostView() {
        composeTestRule.onNodeWithText("Select a photo").assertExists()
        composeTestRule.onNodeWithText("Caption").assertExists()
        composeTestRule.onNodeWithText("Share Post").assertExists()
    }

    private fun assertOnFeedView() {
        composeTestRule.onNodeWithText("For You").assertExists()
        composeTestRule.onNodeWithText("Following").assertExists()
    }

    private fun assertOnPostDetailView() {
        composeTestRule.onNodeWithText("Add a comment...").assertExists()
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

        assertOnHomeView()
    }

    private fun loginUser(username: String, password: String, rememberMe: Boolean, registerToo: Boolean = false) {
        if (registerToo) {
            registerUser(username, password)
            logoutUserFromHome()
        }

        composeTestRule.onNodeWithText("Login").performClick()
        assertOnLoginView()

        composeTestRule.onNodeWithText("Username or Email").performTextInput(username)
        composeTestRule.onNodeWithText("Password").performTextInput(password)

        if (rememberMe) {
            composeTestRule.onNodeWithText("Remember Me").performClick() // Toggle switch
        }

        composeTestRule.onNodeWithText("Login").performClick()
        assertOnHomeView()
    }

    private fun logoutUserFromHome() {
        composeTestRule.onNodeWithText("Settings").performClick()
        assertOnSettingsView()
        
        composeTestRule.onNodeWithText("Logout").performClick()
        composeTestRule.onNodeWithText("Confirm").performClick() // Assuming confirm dialog
        
        assertOnLoginView()
    }

    private fun registerUserViaApi(username: String, password: String) = kotlinx.coroutines.runBlocking {
        val request = com.example.positiveonlysocial.data.model.RegisterRequest(
            username = username,
            email = "$username@test.com",
            password = password,
            rememberMe = "false",
            ip = "127.0.0.1",
            dateOfBirth = "1970-01-01"
        )
        com.example.positiveonlysocial.di.DependencyProvider.api.register(request)
    }


    private fun loginUserViaApi(username: String, password: String): String =
        kotlinx.coroutines.runBlocking {
            val request = com.example.positiveonlysocial.data.model.LoginRequest(
                usernameOrEmail = username,
                password = password,
                rememberMe = "false",
                ip = "127.0.0.1"
            )
            val response =
                com.example.positiveonlysocial.di.DependencyProvider.api.loginUser(request)
            response.body()?.sessionToken ?: throw IllegalStateException("Failed to login via API")
        }

    private fun makePostViaApi(username: String, password: String, caption: String) =
        kotlinx.coroutines.runBlocking {
            val token = loginUserViaApi(username, password)
            val request = com.example.positiveonlysocial.data.model.CreatePostRequest(
                imageUrl = "https://example.com/image.jpg",
                caption = caption
            )
            com.example.positiveonlysocial.di.DependencyProvider.api.makePost(token, request)
        }

    // MARK: Tests

    @Test
    fun testDeleteAccount() {
        // Register and Login
        loginUser(testUsername, strongPassword, rememberMe = true, registerToo = true)

        // Navigate to Settings
        composeTestRule.onNodeWithText("Settings").performClick()

        // Click Delete Account
        composeTestRule.onNodeWithText("Delete Account").performClick()

        // Confirm Delete
        composeTestRule.onNodeWithText("Delete").performClick()

        // Should be on Login/Welcome
        assertOnLoginView()

        // Try to login again
        composeTestRule.onNodeWithText("Username or Email").performTextInput(testUsername)
        composeTestRule.onNodeWithText("Password").performTextInput(strongPassword)
        composeTestRule.onNodeWithText("Login").performClick()

        // Should fail
        composeTestRule.onNodeWithText("Login Failed").assertExists()
        composeTestRule.onNodeWithText("OK").performClick()
    }

    @Test
    fun testResetPassword() {
        // Register
        registerUser(testUsername, strongPassword)
        logoutUserFromHome()

        // Go to Login -> Forgot Password
        composeTestRule.onNodeWithText("Login").performClick()
        composeTestRule.onNodeWithText("Forgot Password?").performClick()

        // Request Reset
        composeTestRule.onNodeWithText("Find Your Account").assertExists()
        composeTestRule.onNodeWithText("Username or Email").performTextInput(testUsername)
        composeTestRule.onNodeWithText("Request Reset").performClick()

        // Verify Reset
        composeTestRule.onNodeWithText("Verify Your Identity").assertExists()
        composeTestRule.onNodeWithText("Enter 6-Digit PIN")
            .performTextInput("123456") // Static PIN
        composeTestRule.onNodeWithText("Verify").performClick()

        // Reset Password
        composeTestRule.onNodeWithText("Reset Password").assertExists()
        composeTestRule.onNodeWithText("Username").performTextInput(testUsername)
        composeTestRule.onNodeWithText("Email").performTextInput("$testUsername@test.com")
        composeTestRule.onNodeWithText("New Password").performTextInput(newStrongPassword)
        composeTestRule.onNodeWithText("Confirm Password").performTextInput(newStrongPassword)
        composeTestRule.onNodeWithText("Reset Password and Login").performClick()

        assertOnHomeView()
    }

    @Test
    fun testFollowAndUnfollowFromSearch() {
        // Setup: Create other user via API
        registerUserViaApi(otherTestUsername, strongPassword)

        // Login as main user
        loginUser(testUsername, strongPassword, rememberMe = false, registerToo = true)

        // Search for user but only a substring so we can just click on the full name and verify the
        // substring search works
        composeTestRule.onNodeWithText("Search for Users").performTextInput("other_user")

        composeTestRule
            .onNodeWithTag(
                otherTestUsername, useUnmergedTree = true
            )
            .performClick()

        // Should be on Profile View
        assertOnProfileView()

        // Verify Followers count is 0
        composeTestRule
            .onNodeWithTag("tag_Followers", true)
            .assert(hasAnyDescendant(hasText("0")))

        // Follow
        composeTestRule.onNodeWithText("Follow").performClick()
        composeTestRule.onNodeWithText("Following").assertExists()

        // Verify Followers count is 1
        composeTestRule
            .onNodeWithTag("tag_Followers")
            .assert(hasAnyDescendant(hasText("1")))


        // Unfollow
        composeTestRule.onNodeWithText("Following").performClick()
        composeTestRule.onNodeWithText("Follow").assertExists()
    }
    @Test
    fun testLikeAndUnlikePost() {
        // Setup
        registerUserViaApi(testUsername, strongPassword)
        val postResponse = makePostViaApi(testUsername, strongPassword, "Some Post Caption")
        val postId = postResponse.body()?.postIdentifier ?: throw IllegalStateException("Failed to create post")
        
        // Login as other user
        loginUser(otherTestUsername, strongPassword, rememberMe = false, registerToo = true)
        
        // Go to Feed
        composeTestRule.onNodeWithText("Feed").performClick()
        assertOnFeedView()
        
        // Find post and click to go to detail
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()
        
        assertOnPostDetailView()
        
        // Double tap to like
        composeTestRule.onNodeWithContentDescription("Post Image").performTouchInput { doubleClick() }
        
        // Verify like count
        composeTestRule.onNodeWithText("1 likes").assertExists()
        
        // Double tap to unlike
        composeTestRule.onNodeWithContentDescription("Post Image").performTouchInput { doubleClick() }
        
        // Verify like count
        composeTestRule.onNodeWithText("0 likes").assertExists()
    }

    @Test
    fun testLikeAndUnlikeCommentOnPostAndThread() {
        // Setup
        registerUserViaApi(testUsername, strongPassword)
        registerUserViaApi(newTestUsername, strongPassword)
        val postResponse = makePostViaApi(testUsername, strongPassword, "Some Post Caption")
        val postId = postResponse.body()?.postIdentifier ?: throw IllegalStateException("Failed to create post")
        
        loginUser(otherTestUsername, strongPassword, rememberMe = false, registerToo = true)
        
        // Go to Feed -> Post Detail
        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()
        
        // Make comment
        composeTestRule.onNodeWithText("Add a comment...").performTextInput("Comment On a Post")
        composeTestRule.onNodeWithText("Post").performClick()
        
        // Verify comment appears
        composeTestRule.onNodeWithText("Comment On a Post").assertExists()

        dismissKeyboardIfPresent()

        // Reply to thread
        composeTestRule.onNodeWithText("Reply").performClick()
        composeTestRule.onNodeWithText("Your reply...").performTextInput("Comment On a Thread")
        composeTestRule.onNodeWithText("Send").performClick()

        // Now we logout
        Espresso.pressBack()
        Espresso.pressBack()
        logoutUserFromHome()

        loginUser(newTestUsername, strongPassword, false)

        // Go to Feed -> Post Detail
        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()
        
        // Like comment (double tap on comment row)
        composeTestRule.onNodeWithText("Comment On a Post").performTouchInput { doubleClick() }

        // Verify like count
        composeTestRule.onNodeWithText("1 likes").assertExists()
        
        // Unlike comment
        composeTestRule.onNodeWithText("Comment On a Post").performTouchInput { doubleClick() }
        
        // Verify like count
        composeTestRule
            .onAllNodesWithText("0 likes")
            .assertCountEquals(3)
        
        // Verify reply appears
        composeTestRule.onNodeWithText("Comment On a Thread").assertExists()
        
        // Like reply
        composeTestRule.onNodeWithText("Comment On a Thread").performTouchInput { doubleClick() }
        composeTestRule.onAllNodesWithText("1 likes").onLast().assertExists()

        composeTestRule.onNodeWithText("Comment On a Thread").performTouchInput { doubleClick() }
        composeTestRule
            .onAllNodesWithText("0 likes")
            .assertCountEquals(3)
    }

    @Test
    fun testReportPost() {
        // Setup
        registerUserViaApi(testUsername, strongPassword)
        val postResponse = makePostViaApi(testUsername, strongPassword, "Some Post Caption")
        val postId = postResponse.body()?.postIdentifier ?: throw IllegalStateException("Failed to create post")
        
        loginUser(otherTestUsername, strongPassword, rememberMe = false, registerToo = true)
        
        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()
        
        // Long press to report
        composeTestRule.onNodeWithContentDescription("Post Image").performTouchInput { longClick() }
        
        // Report Dialog
        composeTestRule.onNodeWithText("Report").assertExists()
        composeTestRule.onNodeWithText("Reason for reporting...").performTextInput("Report post")
        composeTestRule.onNodeWithText("Submit").performClick()
        
        // Verify reported icon
        composeTestRule.onNodeWithContentDescription("Reported").assertExists()
    }

    @Test
    fun testReportComment() {
        // Setup
        registerUserViaApi(testUsername, strongPassword)
        val postResponse = makePostViaApi(testUsername, strongPassword, "Some Post Caption")
        val postId = postResponse.body()?.postIdentifier ?: throw IllegalStateException("Failed to create post")
        
        loginUser(otherTestUsername, strongPassword, rememberMe = false, registerToo = true)
        
        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()
        
        // Make comment
        composeTestRule.onNodeWithText("Add a comment...").performTextInput("Comment to Report")
        composeTestRule.onNodeWithText("Post").performClick()
        
        // Long press comment
        composeTestRule.onNodeWithText("Comment to Report").performTouchInput { longClick() }
        
        // Report Dialog
        composeTestRule.onNodeWithText("Report").assertExists()
        composeTestRule.onNodeWithText("Reason for reporting...").performTextInput("Report comment")
        composeTestRule.onNodeWithText("Submit").performClick()

        // Verify reported icon
        composeTestRule.onNodeWithContentDescription("Reported").assertExists()
    }
    @Test
    fun testVerifyIdentity() {
        // Register and Login
        loginUser(testUsername, strongPassword, rememberMe = true, registerToo = true)

        // Navigate to Settings
        composeTestRule.onNodeWithText("Settings").performClick()

        // Click Verify Identity
        composeTestRule.onNodeWithText("Verify Identity").performClick()

        // Assert Dialog appears
        composeTestRule.onNodeWithTag("verifyIdentityDialog").assertExists()

        // Enter Date
        composeTestRule.onNodeWithText("YYYY-MM-DD").performTextInput("1970-01-01")

        composeTestRule.onNodeWithText("Verify").performClick()

        // Verify Success
        // Wait for success message/alert
        composeTestRule.waitUntil(timeoutMillis = 5000) {
             composeTestRule.onAllNodesWithText("Identity verified successfully!").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onNodeWithTag("verifyIdentityDialog").isNotDisplayed()
        }

        // Verify "Verify Identity" button is GONE
        composeTestRule.onNodeWithTag("verifyIdentityDialog").assertDoesNotExist()
    }

    @Test
    fun testBlockAndUnblockUser() {
        // Setup: Create other user via API
        registerUserViaApi(otherTestUsername, strongPassword)
        
        // Login as main user
        loginUser(testUsername, strongPassword, rememberMe = false, registerToo = true)

        // Search for user
        composeTestRule.onNodeWithText("Search for Users").performTextInput("other_user")
        composeTestRule
            .onNodeWithTag(otherTestUsername, useUnmergedTree = true)
            .performClick()

        assertOnProfileView()
        
        // Initially "Block" button should be visible
        composeTestRule.onNodeWithText("Block").assertExists()
        
        // Click Block
        composeTestRule.onNodeWithText("Block").performClick()
        
        // Verify changes to "Unblock"
        composeTestRule.onNodeWithText("Unblock").assertExists()
        
        // Click Unblock
        composeTestRule.onNodeWithText("Unblock").performClick()
        
        // Verify changes back to "Block"
        composeTestRule.onNodeWithText("Block").assertExists()
    }
}
