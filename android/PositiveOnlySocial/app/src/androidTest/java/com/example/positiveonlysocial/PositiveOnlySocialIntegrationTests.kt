package com.example.positiveonlysocial

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.espresso.Espresso
import com.example.positiveonlysocial.di.DependencyProvider
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class PositiveOnlySocialIntegrationTests {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    // "Remember Me" logins now persist tokens to the keychain, and these tests
    // share one process, so a prior test's session could auto-log-in on the next
    // test's launch and skip the Welcome screen. Clear it so every test starts
    // from a clean, signed-out state.
    @Before
    fun clearPersistedAuth() {
        val keychain = DependencyProvider.keychainHelper
        keychain.delete("positive-only-social.Positive-Only-Social", "userRememberMeTokens")
        keychain.delete("positive-only-social.Positive-Only-Social", "userSessionToken")
    }

    private val testUsername = "test_user_${UUID.randomUUID().toString().take(5)}"
    private val otherTestUsername = "other_user_${UUID.randomUUID().toString().take(5)}"
    private val newTestUsername = "new_user_${UUID.randomUUID().toString().take(5)}"
    private val strongPassword = "StrongPassword123-"
    private val newStrongPassword = "NewStrongPassword456-"

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

    private fun assertOnCheckEmailView() {
        composeTestRule.onNodeWithText("Check Your Email").assertExists()
        composeTestRule.onNodeWithText("Resend Verification Email").assertExists()
        composeTestRule.onNodeWithText("Go to Login").assertExists()
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

        // Privacy Policy Dialog
        composeTestRule.onNodeWithText("Privacy Policy").assertExists()
        composeTestRule.onNodeWithText("Ok").performClick()

        // Registration parks the user on the "check your email" screen
        // (issue #237). The stub API pre-verifies accounts, so continue to
        // Login and sign in to reach Home.
        assertOnCheckEmailView()
        composeTestRule.onNodeWithText("Go to Login").performClick()
        assertOnLoginView()

        composeTestRule.onNodeWithText("Username or Email").performTextInput(username)
        composeTestRule.onNodeWithText("Password").performTextInput(password)
        composeTestRule.onNodeWithText("Login").performClick()

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

    private fun makePostViaApi(
        username: String,
        password: String,
        caption: String,
        // Null creates a text-only post (#307).
        imageUrl: String? = "https://example.com/image.jpg"
    ) =
        kotlinx.coroutines.runBlocking {
            val token = loginUserViaApi(username, password)
            val request = com.example.positiveonlysocial.data.model.CreatePostRequest(
                imageUrl = imageUrl,
                caption = caption
            )
            com.example.positiveonlysocial.di.DependencyProvider.api.makePost(token, request)
        }

    private fun makeCommentViaApi(username: String, password: String, postId: String, body: String) =
        kotlinx.coroutines.runBlocking {
            val token = loginUserViaApi(username, password)
            val request = com.example.positiveonlysocial.data.model.CommentRequest(body)
            com.example.positiveonlysocial.di.DependencyProvider.api.commentOnPost(token, postId, request)
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

        // Verify Reset — stub issues "stub_verification_token_<username>"
        composeTestRule.onNodeWithText("Verify Your Identity").assertExists()
        composeTestRule.onNodeWithText("Verification Token")
            .performTextInput("stub_verification_token_$testUsername")
        composeTestRule.onNodeWithText("Verify").performClick()

        // Reset Password
        composeTestRule.onNodeWithTag("ResetPasswordHeader").assertExists()
        composeTestRule.onNodeWithText("Username").performTextInput(testUsername)
        composeTestRule.onNodeWithText("Email").performTextInput("$testUsername@test.com")
        composeTestRule.onNodeWithText("New Password").performTextInput(newStrongPassword)
        composeTestRule.onNodeWithText("Confirm Password").performTextInput(newStrongPassword)
        composeTestRule.onNodeWithTag("ResetPasswordButton").performClick()

        // After reset the user is sent to Login (no session was created).
        assertOnLoginView()

        // Verify the new password works.
        composeTestRule.onNodeWithText("Username or Email").performTextInput(testUsername)
        composeTestRule.onNodeWithText("Password").performTextInput(newStrongPassword)
        composeTestRule.onNodeWithText("Login").performClick()
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

        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onNodeWithTag(otherTestUsername, useUnmergedTree = true).isDisplayed()
        }

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

        // Follow (disambiguate the clickable button from the "Following" stat label)
        composeTestRule.onNode(hasText("Follow") and hasClickAction()).performClick()
        composeTestRule.onNode(hasText("Following") and hasClickAction()).assertExists()

        // Verify Followers count is 1
        composeTestRule
            .onNodeWithTag("tag_Followers")
            .assert(hasAnyDescendant(hasText("1")))


        // Unfollow (target the button, not the "Following" stat label)
        composeTestRule.onNode(hasText("Following") and hasClickAction()).performClick()
        composeTestRule.onNode(hasText("Follow") and hasClickAction()).assertExists()
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

        // --- New method: tap the heart icon ---
        composeTestRule.onNodeWithContentDescription("Like post").performClick()
        composeTestRule.onNodeWithText("1 likes").assertExists()

        composeTestRule.onNodeWithContentDescription("Unlike post").performClick()
        composeTestRule.onNodeWithText("0 likes").assertExists()

        // --- Old method: double-tap the post image ---
        composeTestRule.onNodeWithContentDescription("Post Image").performTouchInput { doubleClick() }
        composeTestRule.onNodeWithText("1 likes").assertExists()

        composeTestRule.onNodeWithContentDescription("Post Image").performTouchInput { doubleClick() }
        composeTestRule.onNodeWithText("0 likes").assertExists()
    }

    @Test
    fun testOpenPostDetailFromHomeGrid() {
        // Setup: a user with one post.
        registerUserViaApi(testUsername, strongPassword)
        makePostViaApi(testUsername, strongPassword, "Home Grid Post")

        // Login as that user; the Home grid loads their posts.
        loginUser(testUsername, strongPassword, rememberMe = false)
        assertOnHomeView()

        // Tap the first post in the Home grid -> post detail.
        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onAllNodesWithContentDescription("Post Image").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()

        assertOnPostDetailView()
    }

    @Test
    fun testTextOnlyPostShowsCaptionTileInHomeGrid() {
        // A text-only post (#307) renders its caption as the grid tile instead
        // of an image, and still opens the detail view.
        registerUserViaApi(testUsername, strongPassword)
        makePostViaApi(testUsername, strongPassword, "Text Only Post", imageUrl = null)

        loginUser(testUsername, strongPassword, rememberMe = false)
        assertOnHomeView()

        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onAllNodesWithText("Text Only Post").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onAllNodesWithText("Text Only Post").onFirst().performClick()

        assertOnPostDetailView()
    }

    @Test
    fun testOpenPostDetailFromProfileGrid() {
        // Setup: an author with one post.
        registerUserViaApi(testUsername, strongPassword)
        makePostViaApi(testUsername, strongPassword, "Profile Grid Post")

        // Login as a different user and open the author's profile.
        loginUser(otherTestUsername, strongPassword, rememberMe = false, registerToo = true)

        composeTestRule.onNodeWithText("Search for Users").performTextInput(testUsername)
        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onNodeWithTag(testUsername, useUnmergedTree = true).isDisplayed()
        }
        composeTestRule.onNodeWithTag(testUsername, useUnmergedTree = true).performClick()
        assertOnProfileView()

        // Tap the first post in the Profile grid -> post detail.
        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onAllNodesWithContentDescription("Post Image").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()

        assertOnPostDetailView()
    }

    @Test
    fun testOpenPostDetailFromFollowingFeed() {
        // Setup: an author with one post.
        registerUserViaApi(testUsername, strongPassword)
        makePostViaApi(testUsername, strongPassword, "Following Feed Post")

        // Login as a different user and follow the author.
        loginUser(otherTestUsername, strongPassword, rememberMe = false, registerToo = true)

        composeTestRule.onNodeWithText("Search for Users").performTextInput(testUsername)
        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onNodeWithTag(testUsername, useUnmergedTree = true).isDisplayed()
        }
        composeTestRule.onNodeWithTag(testUsername, useUnmergedTree = true).performClick()
        assertOnProfileView()

        composeTestRule.onNode(hasText("Follow") and hasClickAction()).performClick()
        composeTestRule.onNode(hasText("Following") and hasClickAction()).assertExists()

        // Back to Home, then open the Following feed.
        Espresso.pressBack()
        composeTestRule.onNodeWithText("Feed").performClick()
        assertOnFeedView()
        composeTestRule.onNodeWithText("Following").performClick()

        // Tap the first post in the Following feed -> post detail.
        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onAllNodesWithContentDescription("Post Image").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()

        assertOnPostDetailView()
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
        
        // Make comment via the composer dialog
        composeTestRule.onNodeWithText("Add a comment...").performClick()
        composeTestRule.onNodeWithText("Write a comment...").performTextInput("Comment On a Post")
        // Target the dialog's clickable Post button: the post-detail top bar
        // title is also "Post", so text alone matches two nodes.
        composeTestRule.onNode(hasText("Post") and hasClickAction()).performClick()

        // Verify comment appears
        composeTestRule.onNodeWithText("Comment On a Post").assertExists()

        dismissKeyboardIfPresent()

        // Reply to thread via the same composer dialog. Scroll the Reply button
        // into view first so its tap isn't injected off-screen.
        composeTestRule.onNodeWithText("Reply").performScrollTo().performClick()
        composeTestRule.onNodeWithText("Write a comment...").performTextInput("Comment On a Thread")
        composeTestRule.onNode(hasText("Post") and hasClickAction()).performClick()

        // Now we logout
        Espresso.pressBack()
        Espresso.pressBack()
        logoutUserFromHome()

        loginUser(newTestUsername, strongPassword, false)

        // Go to Feed -> Post Detail
        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()
        
        // Verify both comments are visible before starting
        composeTestRule.onNodeWithText("Comment On a Post").assertExists()
        composeTestRule.onNodeWithText("Comment On a Thread").assertExists()

        // ======= Root comment =======

        // New method: tap the heart icon on the root comment. Scroll it into view
        // first so taps aren't injected at off-screen coordinates — with the body
        // on its own line, comments are taller and can sit below the fold on a
        // fresh navigation.
        composeTestRule.onNodeWithText("Comment On a Post").performScrollTo()
        composeTestRule.onAllNodesWithContentDescription("Like comment").onFirst().performClick()
        composeTestRule.onNodeWithText("1 likes").assertExists()

        // Tap "Unlike comment" — root comment is now the only liked one
        composeTestRule.onAllNodesWithContentDescription("Unlike comment").onFirst().performClick()
        composeTestRule.onAllNodesWithText("0 likes").assertCountEquals(3)

        // Old method: double-tap the root comment row
        composeTestRule.onNodeWithText("Comment On a Post").performScrollTo().performTouchInput { doubleClick() }
        composeTestRule.onNodeWithText("1 likes").assertExists()

        composeTestRule.onNodeWithText("Comment On a Post").performScrollTo().performTouchInput { doubleClick() }
        composeTestRule.onAllNodesWithText("0 likes").assertCountEquals(3)

        // ======= Thread reply =======

        // New method: tap the heart icon on the reply (last "Like comment" node).
        // Scroll the reply into view first, for the same off-screen reason.
        composeTestRule.onNodeWithText("Comment On a Thread").performScrollTo()
        composeTestRule.onAllNodesWithContentDescription("Like comment").onLast().performClick()
        composeTestRule.onAllNodesWithText("1 likes").onLast().assertExists()

        // Tap "Unlike comment" — reply is now the only liked one
        composeTestRule.onAllNodesWithContentDescription("Unlike comment").onFirst().performClick()
        composeTestRule.onAllNodesWithText("0 likes").assertCountEquals(3)

        // Old method: double-tap the reply row
        composeTestRule.onNodeWithText("Comment On a Thread").performScrollTo().performTouchInput { doubleClick() }
        composeTestRule.onAllNodesWithText("1 likes").onLast().assertExists()

        composeTestRule.onNodeWithText("Comment On a Thread").performScrollTo().performTouchInput { doubleClick() }
        composeTestRule.onAllNodesWithText("0 likes").assertCountEquals(3)
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
        
        // Long press opens the action menu; this is another user's post, so it
        // offers Report (not Delete).
        composeTestRule.onNodeWithContentDescription("Post Image").performTouchInput { longClick() }
        composeTestRule.onNodeWithText("Report Post").performClick()

        // Report Dialog
        composeTestRule.onNodeWithText("Reason for reporting...").performTextInput("Report post")
        composeTestRule.onNodeWithText("Submit").performClick()

        // Verify reported icon
        composeTestRule.onNodeWithContentDescription("Reported").assertExists()
    }

    @Test
    fun testReportComment() {
        // Setup: testUser owns both the post and the comment, so otherTestUser
        // (the viewer) can report the comment — you can't report your own.
        registerUserViaApi(testUsername, strongPassword)
        val postResponse = makePostViaApi(testUsername, strongPassword, "Some Post Caption")
        val postId = postResponse.body()?.postIdentifier ?: throw IllegalStateException("Failed to create post")
        makeCommentViaApi(testUsername, strongPassword, postId, "Comment to Report")

        loginUser(otherTestUsername, strongPassword, rememberMe = false, registerToo = true)

        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()

        // Long press the other user's comment; the menu offers Report. Scroll it
        // into view first so the long-press doesn't inject at off-screen
        // coordinates when the comment sits below the fold (taller comment rows).
        composeTestRule.onNodeWithText("Comment to Report").performScrollTo().performTouchInput { longClick() }
        composeTestRule.onNodeWithText("Report Comment").performClick()

        // Report Dialog
        composeTestRule.onNodeWithText("Reason for reporting...").performTextInput("Report comment")
        composeTestRule.onNodeWithText("Submit").performClick()

        // Verify reported icon
        composeTestRule.onNodeWithContentDescription("Reported").assertExists()
    }

    @Test
    fun testDeleteOwnPost() {
        // The viewer owns the post, so long-press offers Delete (not Report).
        registerUserViaApi(testUsername, strongPassword)
        makePostViaApi(testUsername, strongPassword, "Post to Delete")

        loginUser(testUsername, strongPassword, rememberMe = false)

        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()

        composeTestRule.onNodeWithContentDescription("Post Image").performTouchInput { longClick() }

        // It's the user's own post: Delete is offered, Report is not.
        composeTestRule.onNodeWithText("Report Post").assertDoesNotExist()
        composeTestRule.onNodeWithText("Delete Post").performClick()

        // Deleting pops the Post Detail screen back to the feed.
        composeTestRule.waitUntil(timeoutMillis = 5_000) {
            composeTestRule.onAllNodesWithText("Add a comment...").fetchSemanticsNodes().isEmpty()
        }
        assertOnFeedView()
    }

    @Test
    fun testDeleteOwnComment() {
        // The viewer owns the comment, so long-press offers Delete (not Report).
        registerUserViaApi(testUsername, strongPassword)
        val postResponse = makePostViaApi(testUsername, strongPassword, "Some Post Caption")
        val postId = postResponse.body()?.postIdentifier ?: throw IllegalStateException("Failed to create post")
        makeCommentViaApi(testUsername, strongPassword, postId, "Comment to Delete")

        loginUser(testUsername, strongPassword, rememberMe = false)

        composeTestRule.onNodeWithText("Feed").performClick()
        composeTestRule.onAllNodesWithContentDescription("Post Image").onFirst().performClick()

        // Scroll the comment fully into view first: with the body on its own
        // line each comment is taller, so on a fresh navigation (scrolled to the
        // top) the comment can sit below the fold — composed but off-screen, which
        // makes a touch inject at off-screen coordinates and fail.
        composeTestRule.onNodeWithText("Comment to Delete").performScrollTo().performTouchInput { longClick() }

        // It's the user's own comment: Delete is offered, Report is not.
        composeTestRule.onNodeWithText("Report Comment").assertDoesNotExist()
        composeTestRule.onNodeWithText("Delete Comment").performClick()

        // The comment is removed from the thread.
        composeTestRule.waitUntil(timeoutMillis = 5_000) {
            composeTestRule.onAllNodesWithText("Comment to Delete").fetchSemanticsNodes().isEmpty()
        }
        composeTestRule.onNodeWithText("Comment to Delete").assertDoesNotExist()
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

        // Wait until dialog disappears
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

        composeTestRule.waitUntil(timeoutMillis = 5000) {
            composeTestRule.onNodeWithTag(otherTestUsername, useUnmergedTree = true).isDisplayed()
        }

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
