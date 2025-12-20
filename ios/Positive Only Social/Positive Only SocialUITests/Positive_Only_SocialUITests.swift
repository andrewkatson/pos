//
//  Positive_Only_SocialUITests.swift
//  Positive Only SocialUITests
//
//  Created by Andrew Katson on 8/29/25.
//

import XCTest

final class Positive_Only_SocialUITests: XCTestCase {
    
    var testUsername: String = ""
    var otherTestUsername: String = ""
    var newTestUsername: String = ""
    let strongPassword: String = "StrongPassword123!"
    let newStrongPassword: String = "NewStrongPassword456!"

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false
        
        // get the name and remove the opening
        var baseName = self.name.replacingOccurrences(of: "-[", with: "")

        // And then you'll need to remove the closing square bracket at the end of the test name
        baseName = baseName.replacingOccurrences(of: "]", with: "")

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
        testUsername = "\(baseName)_user"
        otherTestUsername = "\(baseName)_other_user"
        newTestUsername = "\(baseName)_new_user"
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }
    
    // MARK: Helpers
    private func yield(duration: Duration = .seconds(1)) async {
        try? await Task.sleep(for: duration)
    }
    
    private func dismissKeyboardIfPresent(_ app: XCUIApplication) {
        let maxAttempts = 5
        var attempt = 0
        while (true && attempt < maxAttempts) {
            RunLoop.current.run(until: NSDate(timeIntervalSinceNow: 1.0) as Date)
            if app.keyboards.buttons["Return"].exists {
                app.keyboards.buttons["Return"].tap()
                break
            }
            attempt += 1
        }
    }
    
    private func assertOnWelcomeView(app: XCUIApplication) {
        // We wait until the "Welcome! 👋" text (which is in NeedsAuthView) appears.
        let welcomeText = app.staticTexts["Welcome! 👋"]
        
        // Use a robust existence check with a reasonable timeout.
        XCTAssertTrue(welcomeText.waitForExistence(timeout: 10), "The Welcome! 👋 text (NeedsAuthView) did not appear in time.")

        XCTAssertTrue(app.buttons["RegisterText"].exists, "Register button is not empty")
        XCTAssertTrue(app.buttons["LoginText"].exists, "Login button is not empty")
    }
    
    private func assertOnRegisterView(app: XCUIApplication) {
        XCTAssertTrue(app.textFields["UsernameTextField"].exists, "Username field not present")
        XCTAssertTrue(app.textFields["EmailTextField"].exists, "Email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].exists, "Password field not present")
        XCTAssertTrue(app.secureTextFields["ConfirmPasswordSecureField"].exists, "Confirm Password field not present")
        XCTAssertTrue(app.datePickers["DateOfBirthPicker"].exists, "Date of birth picker not present")
        XCTAssertTrue(app.buttons["RegisterButton"].exists, "Register button not present")
    }
    
    private func assertOnLoginView(app: XCUIApplication) {
        XCTAssertTrue(app.staticTexts["Login"].waitForExistence(timeout: 10), "Login text did not appear in time.")

        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].exists, "Username or email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].exists, "Password field not present")
        XCTAssertTrue(app.buttons["LoginButton"].exists, "Login button not present")
        XCTAssertTrue(app.switches["RememberMeToggle"].exists, "Remember me toggle not present")
        XCTAssertTrue(app.buttons["ForgotPasswordButton"].exists, "Forgot password button not present")
    }
    
    private func assertOnHomeView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["Home"].exists, "Home tab not present")
        XCTAssertTrue(app.buttons["Feed"].exists, "Feed tab not present")
        XCTAssertTrue(app.buttons["Post"].exists, "New post tab not present")
        XCTAssertTrue(app.buttons["Settings"].exists, "Settings tab not present")
    }
    
    private func assertOnSettingsView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["LogoutButton"].exists, "Logout button not present")
        XCTAssertTrue(app.buttons["DeleteAccountButton"].exists, "Delete Account button not present")
    }
    
    private func assertOnProfileView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["FollowButton"].exists, "Follow button not present")
        XCTAssertTrue(app.staticTexts["Following"].exists, "Following stat item not present")
        XCTAssertTrue(app.staticTexts["Followers"].exists, "Followers stat item not present")
        XCTAssertTrue(app.staticTexts["Posts"].exists, "Posts stat item not present")
    }
    
    private func assertOnNewPostView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["SelectAPhotoPicker"].exists, "Select a photo picker not present")
        XCTAssertTrue(app.textViews["CaptionTextEditor"].exists, "Caption text editor not present")
        XCTAssertTrue(app.buttons["SharePostButton"].exists, "Share post button is not empty")
    }
    
    private func assertOnFeedView(app: XCUIApplication) {
        XCTAssertTrue(app.segmentedControls["FeedTypePicker"].exists, "Feed type picker not present")
    }
    
    private func assertOnPostDetailView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["PostCommentButton"].exists, "Post comment button not present")
        XCTAssertTrue(app.buttons["PostImage"].waitForExistence(timeout: 10), "Post image not present in time")
        XCTAssertTrue(app.textFields["AddACommentTextFieldToPost"].exists, "Add a comment text field not present")
    }
    
    private func ifOnHomeLogout(app: XCUIApplication) throws {
        if (app.buttons["Home"].exists) {
            try logoutUserFromHome(app: app)
        }
    }
    
    private func registerUser(app: XCUIApplication, username: String, password: String) throws {
        // We wait until the "Welcome! 👋" text (which is in NeedsAuthView) appears.
        let welcomeText = app.staticTexts["Welcome! 👋"]
        
        // Use a robust existence check with a reasonable timeout.
        XCTAssertTrue(welcomeText.waitForExistence(timeout: 10), "The Welcome! 👋 text (NeedsAuthView) did not appear in time.")
        
        let registerButton = app.buttons["RegisterText"]
        registerButton.tap()
        
        assertOnRegisterView(app: app)
        
        let usernameField = app.textFields["UsernameTextField"]
        usernameField.tap()
        usernameField.typeText(username)
        
        let emailField = app.textFields["EmailTextField"]
        emailField.tap()
        emailField.typeText("\(username)@test.com")
        
        let passwordField = app.secureTextFields["PasswordSecureField"]
        passwordField.tap()
        passwordField.typeText(password)
        
        let confirmPasswordField = app.secureTextFields["ConfirmPasswordSecureField"]
        confirmPasswordField.tap()
        confirmPasswordField.typeText(password)
        
        let otherRegisterButton = app.buttons["RegisterButton"]
        otherRegisterButton.tap()
        
        let privacyPolicyAlert = app.alerts["Privacy Policy"]
        XCTAssertTrue(privacyPolicyAlert.waitForExistence(timeout: 5))
        privacyPolicyAlert.buttons["Ok"].tap()
        
        assertOnHomeView(app: app)
    }
    
    private func loginUser(app: XCUIApplication, username: String, password: String, rememberMe: Bool) throws {
        try registerUser(app: app, username: username, password: password)
        
        try logoutUserFromHome(app: app)
        
        let loginButton = app.buttons["LoginText"]
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField.tap()
        usernameOrEmailTextField.typeText(username)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        passwordSecureField.tap()
        passwordSecureField.typeText(password)
        
        if (rememberMe) {
            dismissKeyboardIfPresent(app)
            
            let rememberMeSwitch = app.switches["RememberMeToggle"]
            if let value = rememberMeSwitch.value as? String, value == "0" {
                // We don't always get the tap to work so we have to do this
                let knob = rememberMeSwitch.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5))
                knob.tap()
            }
            
            XCTAssertEqual(rememberMeSwitch.value as? String, "1", "Remember me toggle should now be on")
        }
        
        let loginButton2 = app.buttons["LoginButton"]
        loginButton2.tap()
        
        assertOnHomeView(app: app)
    }
    
    private func logoutUserFromHome(app: XCUIApplication) throws {
        let settingsTab = app.buttons["Settings"]
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let logoutButton = app.buttons["LogoutButton"]
        logoutButton.tap()
        
        /// Don't know why but there is a hierarchy of confirm logout buttons
        let confirmLogoutButton = app.buttons["ConfirmLogoutButton"].firstMatch
        confirmLogoutButton.tap()
        
        assertOnWelcomeView(app: app)
    }
    
    /// Assumes the user is logged in and we are on HomeView.
    private func makePost(app: XCUIApplication, postText: String) throws {
        assertOnHomeView(app: app)
        
        let newPostTab = app.buttons["Post"]
        newPostTab.tap()
        
        assertOnNewPostView(app: app)
        
        let captionTextEditor = app.textViews["CaptionTextEditor"]
        captionTextEditor.tap()
        captionTextEditor.typeText(postText)
        
        // Find the photo picker's main view (identifier may vary)
        let picker = app.buttons["SelectAPhotoPicker"]
        picker.tap()

        let sharePostButton = app.buttons["SharePostButton"]
        sharePostButton.tap()
        
        assertOnHomeView(app: app)
    }
    
    /// Makes a comment on the first post found in the For You Feed. Assumes the user is logged in and we are on HomeView and a post was made already.
    /// Ends on the PostDetailView.
    private func makeCommentOnPost(app: XCUIApplication, commentText: String) {
        assertOnHomeView(app: app)
        
        let feedTab = app.buttons["Feed"]
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)
        
        firstPostElement.tap()
        
        assertOnPostDetailView(app: app)
        
        let addACommentTextField = app.textFields["AddACommentTextFieldToPost"]
        addACommentTextField.tap()
        addACommentTextField.typeText(commentText)
        
        let postCommentButton = app.buttons["PostCommentButton"]
        postCommentButton.tap()
        
        dismissKeyboardIfPresent(app)
        
        // Should be one comment total
        let commentElements = app.staticTexts.matching(identifier: "CommentText")
        XCTAssert(commentElements.count == 1, "Expected to find 1 comment, but found \(commentElements.count)")
        
        assertOnPostDetailView(app: app)
    }
    
    /// Makes a comment on the first comment thread found on the first post found in the For You Feed. Assumes the user is logged in and we are on
    /// HomeView and a post was made already. Ends on the PostDetailView.
    private func makeCommentOnThread(app: XCUIApplication, commentText: String) {
        assertOnHomeView(app: app)
        
        let feedTab = app.buttons["Feed"]
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)
        
        firstPostElement.tap()
        
        assertOnPostDetailView(app: app)
        
        // Wait for comments to load
        let replyButton = app.buttons["ReplyToCommentThreadButton"]
        XCTAssertTrue(replyButton.waitForExistence(timeout: 5))
        
        // Tap the Reply button to open the sheet
        replyButton.tap()
        
        // Wait for the reply sheet to appear
        let replySheet = app.navigationBars["Post Reply"]
        XCTAssertTrue(replySheet.waitForExistence(timeout: 2))
        
        // Find the TextEditor in the sheet
        // TextEditor appears as a textView in the accessibility hierarchy
        let replyTextEditor = app.textViews.firstMatch
        XCTAssertTrue(replyTextEditor.exists)
        
        // Tap and type the reply
        replyTextEditor.tap()
        replyTextEditor.typeText(commentText)
        
        // Tap the Send button
        let sendButton = app.buttons["Send"]
        XCTAssertTrue(sendButton.exists)
        XCTAssertTrue(sendButton.isEnabled)
        sendButton.tap()
        
        // Should be two comments total
        let commentElements = app.staticTexts.matching(identifier: "CommentText")
        XCTAssert(commentElements.count == 2, "Expected to find 2 comments, but found \(commentElements.count)")
        
        assertOnPostDetailView(app: app)
    }
    
    // MARK: Tests
    @MainActor
    func testAutomaticLoginAfterRememberMe() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: true)
        
        app.terminate()
        
        app.launch()
        
        // If we end the app and relaunch after remember me we should automatically be on the HomeView
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testDeleteAccount() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        // Remember me is true here so we can test that the deleting clears the token
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: true)

        let settingsTab = app.buttons["Settings"]
        settingsTab.tap()
        
        let deleteAccountButton = app.buttons["DeleteAccountButton"]
        deleteAccountButton.tap()
        
        let confirmDeleteAccountButton = app.buttons["ConfirmDeleteAccountButton"].firstMatch
        confirmDeleteAccountButton.tap()
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.buttons["LoginText"]
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField.tap()
        usernameOrEmailTextField.typeText(testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        passwordSecureField.tap()
        passwordSecureField.typeText(strongPassword)
        
        let loginButton2 = app.buttons["LoginButton"]
        loginButton2.tap()
        
        XCTAssertTrue(app.buttons["LoginFailedOkButton"].exists, "Login should have failed")
    }
    
    @MainActor
    func testResetPassword() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)

        try registerUser(app: app, username: testUsername, password: strongPassword)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.buttons["LoginText"]
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let forgotPasswordButton = app.buttons["ForgotPasswordButton"]
        forgotPasswordButton.tap()
        
        // Assert we are on request reset view
        XCTAssertTrue(app.buttons["RequestResetButton"].exists, "Request reset button should exist")
        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].exists, "Username or email text field should exist")
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField.tap()
        usernameOrEmailTextField.typeText(testUsername)
        
        let requestResetButton = app.buttons["RequestResetButton"]
        requestResetButton.tap()
        
        // Assert we are on the verify reset view
        XCTAssertTrue(app.buttons["VerifyButton"].exists, "Verify button should exist")
        XCTAssertTrue(app.textFields["6DigitPinTextField"].exists, "6 Digit pin field should exist")
        
        let sixDigitPinTextField = app.textFields["6DigitPinTextField"]
        sixDigitPinTextField.tap()
        // We hardcode the test value in StatefulStubbedAPI
        sixDigitPinTextField.typeText("100000")
        
        let verifyButton = app.buttons["VerifyButton"]
        verifyButton.tap()
        
        // Assert we are on the reset password view
        XCTAssertTrue(app.buttons["ResetPasswordAndLoginButton"].exists, "Reset password and login button should exist")
        XCTAssertTrue(app.textFields["UsernameTextField"].exists, "Username text field should exist")
        XCTAssertTrue(app.textFields["EmailTextField"].exists, "Email text field should exist")
        XCTAssertTrue(app.secureTextFields["NewPasswordSecureField"].exists, "New password text field should exist")
        
        let emailTextField = app.textFields["EmailTextField"]
        emailTextField.tap()
        emailTextField.typeText("\(testUsername)@test.com")
        
        let passwordTextField = app.secureTextFields["NewPasswordSecureField"]
        passwordTextField.tap()
        passwordTextField.typeText(newStrongPassword)
        
        let resetPasswordAndLoginButton = app.buttons["ResetPasswordAndLoginButton"]
        resetPasswordAndLoginButton.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton2 = app.buttons["LoginText"]
        loginButton2.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField2 = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField.tap()
        usernameOrEmailTextField2.typeText(testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        passwordSecureField.tap()
        passwordSecureField.typeText(newStrongPassword)
        
        let loginButton3 = app.buttons["LoginButton"]
        loginButton3.tap()
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testFollowAndUnfollowFromSearch() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        try registerUser(app: app, username: otherTestUsername, password: strongPassword)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        let userSearchField = app.searchFields["Search for Users"]
        userSearchField.tap()
        userSearchField.typeText(otherTestUsername)
        
        let userLink = app.buttons[otherTestUsername]
        userLink.tap()
        
        assertOnProfileView(app: app)
        
        let followersLabel = app.staticTexts["FollowersCount"]
        let followButton = app.buttons["FollowButton"]
        
        // 1. Initial Check (Safe conversion from String to Int)
        // We use .label because that contains the actual text text displayed
        XCTAssertEqual(followersLabel.label, "0")
        
        // 2. Tap Follow
        followButton.tap()
        
        // 3. WAIT for the change (Async logic)
        // We create a predicate that checks if the label becomes "1"
        let existsPredicate = NSPredicate(format: "label == '1'")
        
        // Wait up to 5 seconds for the label to update
        expectation(for: existsPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
        
        // 4. Tap Unfollow
        followButton.tap()
        
        // 5. WAIT for it to go back to "0"
        let zeroPredicate = NSPredicate(format: "label == '0'")
        expectation(for: zeroPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
    }
    
    @MainActor
    func testFollowAndUnfollowFromPost() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // Make sure there is one post in For You and no posts in Following
        // 1. Find the Picker container
        let feedPicker = app.segmentedControls["FeedTypePicker"]
        XCTAssertTrue(feedPicker.exists)

        // 2. Find the button INSIDE the picker
        let followingSegment = feedPicker.buttons["Following"]
        followingSegment.tap()
        
        let allPostsQuery = app.buttons.matching(identifier: "FollowingPostImage")
        XCTAssertEqual(allPostsQuery.count, 0)
        
        let forYouPickerTab = feedPicker.buttons["For You"]
        forYouPickerTab.tap()
        
        let allPostsQuery2 = app.buttons.matching(identifier: "ForYouPostImage")
        XCTAssertEqual(allPostsQuery2.count, 1)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostAuthorsQuery = app.buttons.matching(identifier: "PostAuthor")

        // Now, get the specific element at index 0 (the first one)
        let firstPostAuthorElement = allPostAuthorsQuery.element(boundBy: 0)

        firstPostAuthorElement.tap()

        assertOnProfileView(app: app)
        
        let followersLabel = app.staticTexts["FollowersCount"]
        let followButton = app.buttons["FollowButton"]
        
        // 1. Initial Check (Safe conversion from String to Int)
        // We use .label because that contains the actual text text displayed
        XCTAssertEqual(followersLabel.label, "0")
        
        // 2. Tap Follow
        followButton.tap()
        
        // 3. WAIT for the change (Async logic)
        // We create a predicate that checks if the label becomes "1"
        let existsPredicate = NSPredicate(format: "label == '1'")
        
        // Wait up to 5 seconds for the label to update
        expectation(for: existsPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
        
        // 4. Tap Unfollow
        followButton.tap()
        
        // 5. WAIT for it to go back to "0"
        let zeroPredicate = NSPredicate(format: "label == '0'")
        expectation(for: zeroPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
        
        /// We refollow so that we can check that the post now shows up in the "Following" Feed
        followButton.tap()
        
        // Go back to FeedView
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        // Make sure there is one post in For You and one post in Following
        // 1. Find the Picker container
        let feedPicker2 = app.segmentedControls["FeedTypePicker"]
        XCTAssertTrue(feedPicker2.exists)

        // 2. Find the button INSIDE the picker
        let followingSegment2 = feedPicker2.buttons["Following"]
        followingSegment2.tap()
        
        let allPostsQuery3 = app.buttons.matching(identifier: "FollowingPostImage")
        XCTAssertEqual(allPostsQuery3.count, 1)
        
        let forYouPickerTab2 = feedPicker2.buttons["For You"]
        forYouPickerTab2.tap()
        
        let allPostsQuery4 = app.buttons.matching(identifier: "ForYouPostImage")
        XCTAssertEqual(allPostsQuery4.count, 1)
    }
    
    @MainActor
    func testLikeAndUnlikePost() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let postImage = app.buttons["PostImage"]
        postImage.doubleTap()
        
        let postLikesText = app.staticTexts["PostLikesText"]
        XCTAssertEqual(postLikesText.label, "1 likes")
        
        postImage.doubleTap()
        
        XCTAssertEqual(postLikesText.label, "0 likes")
    }
    
    @MainActor
    func testVerifyIdentity() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        let settingsTab = app.buttons["Settings"]
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let verifyIdentityButton = app.buttons["VerifyIdentityButton"]
        XCTAssertTrue(verifyIdentityButton.exists, "Verify Identity button should be present for new user")
        verifyIdentityButton.tap()
        
        let submitVerificationButton = app.buttons["SubmitVerificationButton"]
        XCTAssertTrue(submitVerificationButton.waitForExistence(timeout: 2))
        
        // We just tap verify to send the default date (today)
        submitVerificationButton.tap()
        
        // Wait for success alert
        let successAlert = app.alerts["Identity Verified"]
        XCTAssertTrue(successAlert.waitForExistence(timeout: 5))
        successAlert.buttons["OK"].tap()
        
        // Verify Identity submit button should be gone. This is a proxy for the dialog being gone.
        XCTAssertFalse(submitVerificationButton.exists, "Verify Identity submit button should disappear after verification")
    }
    
    @MainActor
    func testLikeAndUnlikeCommentOnPostAndThread() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        makeCommentOnPost(app: app, commentText: "Comment On a Post")
        
        let firstBackButton = app.navigationBars.buttons.element(boundBy: 0)
        firstBackButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        makeCommentOnThread(app: app, commentText: "Comment On a Thread")
        
        let backButton2 = app.navigationBars.buttons.element(boundBy: 0)
        backButton2.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton2 = app.buttons["Home"]
        homeButton2.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        // First we like and unlike the comment post comment
        let postCommentStackQuery = app.buttons.matching(identifier: "CommentStack")
        let postCommentStack = postCommentStackQuery.element(boundBy: 0)
        postCommentStack.doubleTap()
        
        let postCommentLikesTextQuery = app.staticTexts.matching(identifier: "CommentLikesCount")
        let postCommentLikesText = postCommentLikesTextQuery.element(boundBy: 0)
        XCTAssertEqual(postCommentLikesText.label, "1 likes")
        
        postCommentStack.doubleTap()
        
        XCTAssertEqual(postCommentLikesText.label, "0 likes")
        
        // Then we like and unlike the comment thread comment
        let postCommentStackQuery2 = app.buttons.matching(identifier: "CommentStack")
        let postCommentStack2 = postCommentStackQuery2.element(boundBy: 1)
        postCommentStack2.doubleTap()
        
        let postCommentLikesTextQuery2 = app.staticTexts.matching(identifier: "CommentLikesCount")
        let postCommentLikesText2 = postCommentLikesTextQuery2.element(boundBy: 1)
        XCTAssertEqual(postCommentLikesText2.label, "1 likes")
        
        postCommentStack2.doubleTap()
        
        XCTAssertEqual(postCommentLikesText2.label, "0 likes")
    }
    
    @MainActor
    func testReportPost() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        makeCommentOnPost(app: app, commentText: "Comment On a Post")
        
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let postImage = app.buttons["PostImage"]
        // 2 second press
        postImage.press(forDuration: 2)
        
        let reasonTextField = app.textFields["ProvideAReasonTextField"]
        reasonTextField.tap()
        reasonTextField.typeText("Report post")
        
        let reportButton = app.buttons["SubmitReportButton"]
        reportButton.tap()
        
        let reportedCommentIcon = app.images["ReportedPostIcon"]
        XCTAssertTrue(reportedCommentIcon.exists, "Reported post icon is missing")
    }
    
    @MainActor
    func testReportComment() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        makeCommentOnPost(app: app, commentText: "Comment On a Post")
        
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        makeCommentOnThread(app: app, commentText: "Comment On a Thread")
        
        let backButton2 = app.navigationBars.buttons.element(boundBy: 0)
        backButton2.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let commentStackQuery = app.buttons.matching(identifier: "CommentStack")
        let commentStack = commentStackQuery.element(boundBy: 0)
        // 2 second press
        commentStack.press(forDuration: 2)
        
        let reasonTextField = app.textFields["ProvideAReasonTextField"]
        reasonTextField.tap()
        reasonTextField.typeText("Report comment thread")
        
        let reportButton = app.buttons["SubmitReportButton"]
        reportButton.tap()
        
        let reportedCommentIcon = app.images["ReportedCommentIcon"]
        XCTAssertTrue(reportedCommentIcon.exists, "Reported comment icon is missing")
        
        
        let commentStackQuery2 = app.buttons.matching(identifier: "CommentStack")
        let commentStack2 = commentStackQuery2.element(boundBy: 1)
        // 2 second press
        commentStack2.press(forDuration: 2)
        
        let reasonTextField2 = app.textFields["ProvideAReasonTextField"]
        reasonTextField2.tap()
        reasonTextField2.typeText("Report comment reply")
        
        let reportButton2 = app.buttons["SubmitReportButton"]
        reportButton2.tap()
        
        let reportedCommentIcon2 = app.images.matching(identifier: "ReportedCommentIcon")
        XCTAssertEqual(reportedCommentIcon2.count, 2, "Expected 2 reported comment icons but only found \(reportedCommentIcon2.count)")
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            let app = XCUIApplication()
            app.launch()

            do {
                try ifOnHomeLogout(app: app)
            } catch {
                XCTFail("ifOnHomeLogout threw error: \(error)")
            }
        }
    }

    @MainActor
    func testBlockAndUnblockUser() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        
        app.launch()
        
        try ifOnHomeLogout(app: app)
        
        // Setup: Create other user
        try registerUser(app: app, username: otherTestUsername, password: strongPassword)
        try logoutUserFromHome(app: app)
        
        // Login as main user
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        // Search for user
        let userSearchField = app.searchFields["Search for Users"]
        userSearchField.tap()
        userSearchField.typeText(otherTestUsername)
        
        let userLink = app.buttons[otherTestUsername]
        XCTAssertTrue(userLink.waitForExistence(timeout: 5))
        userLink.tap()
        
        assertOnProfileView(app: app)
        
        // Initially "Block" button should be visible
        let blockButton = app.buttons["Block"]
        XCTAssertTrue(blockButton.exists)
        
        // Click Block
        blockButton.tap()
        
        // Verify changes to "Unblock"
        let unblockButton = app.buttons["Unblock"]
        XCTAssertTrue(unblockButton.waitForExistence(timeout: 2))
        
        // Click Unblock
        unblockButton.tap()
        
        // Verify changes back to "Block"
        XCTAssertTrue(blockButton.waitForExistence(timeout: 2))
    }
}

