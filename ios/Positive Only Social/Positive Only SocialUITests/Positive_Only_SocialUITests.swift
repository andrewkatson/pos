//
//  Positive_Only_SocialUITests.swift
//  Positive Only SocialUITests
//
//  Created by Andrew Katson on 8/29/25.
//

import XCTest

final class Positive_Only_SocialUITests: XCTestCase {
    
    var app: XCUIApplication!
    var testUsername: String = ""
    var otherTestUsername: String = ""
    var newTestUsername: String = ""
    let strongPassword: String = "StrongPassword123!"
    let newStrongPassword: String = "NewStrongPassword456!"
    let elementTimeout: TimeInterval = 3

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false
        
        app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        // get the name and remove the opening
        var baseName = self.name.replacingOccurrences(of: "-[", with: "")

        // And then you'll need to remove the closing square bracket at the end of the test name
        baseName = baseName.replacingOccurrences(of: "]", with: "")
        
        app.launchEnvironment["test-name"] = baseName
        app.launch()

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
        testUsername = "\(baseName)_user"
        otherTestUsername = "\(baseName)_other_user"
        newTestUsername = "\(baseName)_new_user"
    }

    override func tearDownWithError() throws {
        // We want the test to teardown properly even if it fails midway through
        app.terminate()
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
                XCTAssertTrue(app.keyboards.buttons["Return"].waitForExistence(timeout: elementTimeout))
                app.keyboards.buttons["Return"].tap()
                break
            }
            attempt += 1
        }
    }
    
    private func typeText(element: XCUIElement, text: String) {
        let maxAttempts = 5
        var attempt = 0
        element.tap()
        while !element.hasFocus && app.keyboards.count == 0 && attempt < maxAttempts {
            element.tap()
            RunLoop.current.run(until: NSDate(timeIntervalSinceNow: 1.0) as Date)
            attempt += 1
        }
        XCTAssertTrue(element.hasFocus || app.keyboards.count > 0, "Element did not gain keyboard focus.")
        element.typeText(text)
    }
    
    private func assertOnWelcomeView(app: XCUIApplication) {
        // We wait until the "Welcome! 👋" text (which is in NeedsAuthView) appears.
        let welcomeText = app.staticTexts["Welcome! 👋"]
        
        // Use a robust existence check with a reasonable timeout.
        XCTAssertTrue(welcomeText.waitForExistence(timeout: elementTimeout), "The Welcome! 👋 text (NeedsAuthView) did not appear in time.")

        XCTAssertTrue(app.buttons["RegisterText"].waitForExistence(timeout: elementTimeout), "Register button is not empty")
        XCTAssertTrue(app.buttons["LoginText"].waitForExistence(timeout: elementTimeout), "Login button is not empty")
    }
    
    private func assertOnRegisterView(app: XCUIApplication) {
        XCTAssertTrue(app.textFields["UsernameTextField"].waitForExistence(timeout: elementTimeout), "Username field not present")
        XCTAssertTrue(app.textFields["EmailTextField"].waitForExistence(timeout: elementTimeout), "Email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].waitForExistence(timeout: elementTimeout), "Password field not present")
        XCTAssertTrue(app.secureTextFields["ConfirmPasswordSecureField"].waitForExistence(timeout: elementTimeout), "Confirm Password field not present")
        XCTAssertTrue(app.datePickers["DateOfBirthPicker"].waitForExistence(timeout: elementTimeout), "Date of birth picker not present")
        XCTAssertTrue(app.buttons["RegisterButton"].waitForExistence(timeout: elementTimeout), "Register button not present")
    }
    
    private func assertOnLoginView(app: XCUIApplication) {
        XCTAssertTrue(app.staticTexts["Login"].waitForExistence(timeout: elementTimeout), "Login text did not appear in time.")

        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].waitForExistence(timeout: elementTimeout), "Username or email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].waitForExistence(timeout: elementTimeout), "Password field not present")
        XCTAssertTrue(app.buttons["LoginButton"].waitForExistence(timeout: elementTimeout), "Login button not present")
        XCTAssertTrue(app.switches["RememberMeToggle"].waitForExistence(timeout: elementTimeout), "Remember me toggle not present")
        XCTAssertTrue(app.buttons["ForgotPasswordButton"].waitForExistence(timeout: elementTimeout), "Forgot password button not present")
    }
    
    private func assertOnHomeView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["Home"].waitForExistence(timeout: elementTimeout), "Home tab not present")
        XCTAssertTrue(app.buttons["Feed"].waitForExistence(timeout: elementTimeout), "Feed tab not present")
        XCTAssertTrue(app.buttons["Post"].waitForExistence(timeout: elementTimeout), "New post tab not present")
        XCTAssertTrue(app.buttons["Settings"].waitForExistence(timeout: elementTimeout), "Settings tab not present")
    }
    
    private func assertOnSettingsView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["LogoutButton"].waitForExistence(timeout: elementTimeout), "Logout button not present")
        XCTAssertTrue(app.buttons["DeleteAccountButton"].waitForExistence(timeout: elementTimeout), "Delete Account button not present")
    }
    
    private func assertOnProfileView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["FollowButton"].waitForExistence(timeout: elementTimeout), "Follow button not present")
        XCTAssertTrue(app.staticTexts["Following"].waitForExistence(timeout: elementTimeout), "Following stat item not present")
        XCTAssertTrue(app.staticTexts["Followers"].waitForExistence(timeout: elementTimeout), "Followers stat item not present")
        XCTAssertTrue(app.staticTexts["Posts"].waitForExistence(timeout: elementTimeout), "Posts stat item not present")
    }
    
    private func assertOnNewPostView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["SelectAPhotoPicker"].waitForExistence(timeout: elementTimeout), "Select a photo picker not present")
        XCTAssertTrue(app.textViews["CaptionTextEditor"].waitForExistence(timeout: elementTimeout), "Caption text editor not present")
        XCTAssertTrue(app.buttons["SharePostButton"].waitForExistence(timeout: elementTimeout), "Share post button is not empty")
    }
    
    private func assertOnFeedView(app: XCUIApplication) {
        XCTAssertTrue(app.segmentedControls["FeedTypePicker"].waitForExistence(timeout: elementTimeout), "Feed type picker not present")
    }
    
    private func assertOnPostDetailView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["PostCommentButton"].waitForExistence(timeout: elementTimeout), "Post comment button not present")
        XCTAssertTrue(app.buttons["PostImage"].waitForExistence(timeout: elementTimeout), "Post image not present in time")
        XCTAssertTrue(app.textFields["AddACommentTextFieldToPost"].waitForExistence(timeout: elementTimeout), "Add a comment text field not present")
    }
    
    private func ifOnHomeDeleteAccount(app: XCUIApplication) throws {
        if (app.buttons["Home"].exists) {
            try deleteAccountFromHome(app: app)
        }
    }
    
    private func registerUser(app: XCUIApplication, username: String, password: String) throws {
        // We wait until the "Welcome! 👋" text (which is in NeedsAuthView) appears.
        let welcomeText = app.staticTexts["Welcome! 👋"]
        
        // Use a robust existence check with a reasonable timeout.
        XCTAssertTrue(welcomeText.waitForExistence(timeout: elementTimeout), "The Welcome! 👋 text (NeedsAuthView) did not appear in time.")
        
        let registerButton = app.buttons["RegisterText"]
        XCTAssertTrue(registerButton.waitForExistence(timeout: elementTimeout))
        registerButton.tap()
        
        assertOnRegisterView(app: app)
        
        dismissKeyboardIfPresent(app)
        
        let usernameField = app.textFields["UsernameTextField"]
        XCTAssertTrue(usernameField.waitForExistence(timeout: elementTimeout))
        usernameField.tap()
        typeText(element: usernameField, text: username)
        
        let emailField = app.textFields["EmailTextField"]
        XCTAssertTrue(emailField.waitForExistence(timeout: elementTimeout))
        emailField.tap()
        typeText(element: emailField, text: "\(username)@test.com")
        
        let passwordField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordField.waitForExistence(timeout: elementTimeout))
        passwordField.tap()
        typeText(element: passwordField, text: password)
        
        let confirmPasswordField = app.secureTextFields["ConfirmPasswordSecureField"]
        XCTAssertTrue(confirmPasswordField.waitForExistence(timeout: elementTimeout))
        confirmPasswordField.tap()
        typeText(element: confirmPasswordField, text: password)
        
        let otherRegisterButton = app.buttons["RegisterButton"]
        XCTAssertTrue(otherRegisterButton.waitForExistence(timeout: elementTimeout))
        otherRegisterButton.tap()
        
        let privacyPolicyAlert = app.alerts["Privacy Policy"]
        XCTAssertTrue(privacyPolicyAlert.waitForExistence(timeout: elementTimeout))
        XCTAssertTrue(privacyPolicyAlert.buttons["Ok"].waitForExistence(timeout: elementTimeout))
        privacyPolicyAlert.buttons["Ok"].tap()
        
        assertOnHomeView(app: app)
        
        dismissSavePassword(app: app)
    }
    
    private func dismissSavePassword(app: XCUIApplication) {
        let notNowButton = app.buttons["Not Now"]
        if notNowButton.waitForExistence(timeout: elementTimeout) {
            notNowButton.tap()
        }
    }
    
    private func loginUser(app: XCUIApplication, username: String, password: String, rememberMe: Bool) throws {
        try registerUser(app: app, username: username, password: password)
        
        try logoutUserFromHome(app: app)
        
        let loginButton = app.buttons["LoginText"]
        XCTAssertTrue(loginButton.waitForExistence(timeout: elementTimeout))
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        dismissKeyboardIfPresent(app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: elementTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField, text: username)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordSecureField.waitForExistence(timeout: elementTimeout))
        passwordSecureField.tap()
        typeText(element: passwordSecureField, text: password)
        
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
        XCTAssertTrue(loginButton2.waitForExistence(timeout: elementTimeout))
        loginButton2.tap()
        
        assertOnHomeView(app: app)
        
        dismissSavePassword(app: app)
    }
    
    private func logoutUserFromHome(app: XCUIApplication) throws {
        let settingsTab = app.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: elementTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let logoutButton = app.buttons["LogoutButton"]
        XCTAssertTrue(logoutButton.waitForExistence(timeout: elementTimeout))
        logoutButton.tap()
        
        /// Don't know why but there is a hierarchy of confirm logout buttons
        let confirmLogoutButton = app.buttons["ConfirmLogoutButton"].firstMatch
        XCTAssertTrue(confirmLogoutButton.waitForExistence(timeout: elementTimeout))
        confirmLogoutButton.tap()
        
        assertOnWelcomeView(app: app)
    }
    
    private func deleteAccountFromHome(app: XCUIApplication) throws {
        let settingsTab = app.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: elementTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let deleteAccountButton = app.buttons["DeleteAccountButton"]
        XCTAssertTrue(deleteAccountButton.waitForExistence(timeout: elementTimeout))
        deleteAccountButton.tap()
        
        let confirmDeleteAccountButton = app.buttons["ConfirmDeleteAccountButton"].firstMatch
        XCTAssertTrue(confirmDeleteAccountButton.waitForExistence(timeout: elementTimeout))
        confirmDeleteAccountButton.tap()
        
        assertOnWelcomeView(app: app)
    }
    
    /// Assumes the user is logged in and we are on HomeView.
    private func makePost(app: XCUIApplication, postText: String) throws {
        assertOnHomeView(app: app)
        
        let newPostTab = app.buttons["Post"]
        XCTAssertTrue(newPostTab.waitForExistence(timeout: elementTimeout))
        newPostTab.tap()
        
        assertOnNewPostView(app: app)
        
        let captionTextEditor = app.textViews["CaptionTextEditor"]
        XCTAssertTrue(captionTextEditor.waitForExistence(timeout: elementTimeout))
        captionTextEditor.tap()
        typeText(element: captionTextEditor, text: postText)
        
        // Find the photo picker's main view (identifier may vary)
        let picker = app.buttons["SelectAPhotoPicker"]
        XCTAssertTrue(picker.waitForExistence(timeout: elementTimeout))
        picker.tap()

        let sharePostButton = app.buttons["SharePostButton"]
        XCTAssertTrue(sharePostButton.waitForExistence(timeout: elementTimeout))
        sharePostButton.tap()

        assertOnHomeView(app: app)
    }
    
    /// Makes a comment on the first post found in the For You Feed. Assumes the user is logged in and we are on HomeView and a post was made already.
    /// Ends on the PostDetailView.
    private func makeCommentOnPost(app: XCUIApplication, commentText: String) {
        assertOnHomeView(app: app)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: elementTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)
        
        XCTAssertTrue(firstPostElement.waitForExistence(timeout: elementTimeout))
        firstPostElement.tap()
        
        assertOnPostDetailView(app: app)
        
        let addACommentTextField = app.textFields["AddACommentTextFieldToPost"]
        XCTAssertTrue(addACommentTextField.waitForExistence(timeout: elementTimeout))
        addACommentTextField.tap()
        typeText(element: addACommentTextField, text: commentText)
        
        let postCommentButton = app.buttons["PostCommentButton"]
        XCTAssertTrue(postCommentButton.waitForExistence(timeout: elementTimeout))
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
        XCTAssertTrue(feedTab.waitForExistence(timeout: elementTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)
        
        XCTAssertTrue(firstPostElement.waitForExistence(timeout: elementTimeout))
        firstPostElement.tap()
        
        assertOnPostDetailView(app: app)
        
        // Wait for comments to load
        let replyButton = app.buttons["ReplyToCommentThreadButton"]
        XCTAssertTrue(replyButton.waitForExistence(timeout: elementTimeout))
        
        // Tap the Reply button to open the sheet
        replyButton.tap()
        
        // Wait for the reply sheet to appear
        let replySheet = app.navigationBars["Post Reply"]
        XCTAssertTrue(replySheet.waitForExistence(timeout: elementTimeout))
        
        // Find the TextEditor in the sheet
        // TextEditor appears as a textView in the accessibility hierarchy
        let replyTextEditor = app.textViews.firstMatch
        XCTAssertTrue(replyTextEditor.waitForExistence(timeout: elementTimeout))
        
        // Tap and type the reply
        replyTextEditor.tap()
        typeText(element: replyTextEditor, text: commentText)
        
        // Tap the Send button
        let sendButton = app.buttons["Send"]
        XCTAssertTrue(sendButton.waitForExistence(timeout: elementTimeout))
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
        
        try ifOnHomeDeleteAccount(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: true)
        
        app.launch()
        
        // If we end the app and relaunch after remember me we should automatically be on the HomeView
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testDeleteAccount() throws {
        
        try ifOnHomeDeleteAccount(app: app)
        
        // Remember me is true here so we can test that the deleting clears the token
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: true)

        let settingsTab = app.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: elementTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let deleteAccountButton = app.buttons["DeleteAccountButton"]
        XCTAssertTrue(deleteAccountButton.waitForExistence(timeout: elementTimeout))
        deleteAccountButton.tap()
        
        let confirmDeleteAccountButton = app.buttons["ConfirmDeleteAccountButton"].firstMatch
        XCTAssertTrue(confirmDeleteAccountButton.waitForExistence(timeout: elementTimeout))
        confirmDeleteAccountButton.tap()
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.buttons["LoginText"]
        XCTAssertTrue(loginButton.waitForExistence(timeout: elementTimeout))
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: elementTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField, text: testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordSecureField.waitForExistence(timeout: elementTimeout))
        passwordSecureField.tap()
        typeText(element: passwordSecureField, text: strongPassword)
        
        let loginButton2 = app.buttons["LoginButton"]
        XCTAssertTrue(loginButton2.waitForExistence(timeout: elementTimeout))
        loginButton2.tap()
        
        XCTAssertTrue(app.buttons["LoginFailedOkButton"].waitForExistence(timeout: elementTimeout), "Login should have failed")
        
        XCTAssertTrue(app.buttons["LoginFailedOkButton"].firstMatch.waitForExistence(timeout: elementTimeout))
        app.buttons["LoginFailedOkButton"].firstMatch.tap()
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        try registerUser(app: app, username: newTestUsername, password: strongPassword)
    }
    
    @MainActor
    func testResetPassword() throws {
        
        try ifOnHomeDeleteAccount(app: app)

        try registerUser(app: app, username: testUsername, password: strongPassword)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.buttons["LoginText"]
        XCTAssertTrue(loginButton.waitForExistence(timeout: elementTimeout))
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let forgotPasswordButton = app.buttons["ForgotPasswordButton"]
        XCTAssertTrue(forgotPasswordButton.waitForExistence(timeout: elementTimeout))
        forgotPasswordButton.tap()
        
        // Assert we are on request reset view
        XCTAssertTrue(app.buttons["RequestResetButton"].waitForExistence(timeout: elementTimeout), "Request reset button should exist")
        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].waitForExistence(timeout: elementTimeout), "Username or email text field should exist")
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: elementTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField, text: testUsername)
        
        let requestResetButton = app.buttons["RequestResetButton"]
        XCTAssertTrue(requestResetButton.waitForExistence(timeout: elementTimeout))
        requestResetButton.tap()
        
        // Assert we are on the verify reset view
        XCTAssertTrue(app.buttons["VerifyButton"].waitForExistence(timeout: elementTimeout), "Verify button should exist")
        XCTAssertTrue(app.textFields["6DigitPinTextField"].waitForExistence(timeout: elementTimeout), "6 Digit pin field should exist")
        
        let sixDigitPinTextField = app.textFields["6DigitPinTextField"]
        XCTAssertTrue(sixDigitPinTextField.waitForExistence(timeout: elementTimeout))
        sixDigitPinTextField.tap()
        // We hardcode the test value in StatefulStubbedAPI
        typeText(element: sixDigitPinTextField, text: "100000")
        
        let verifyButton = app.buttons["VerifyButton"]
        XCTAssertTrue(verifyButton.waitForExistence(timeout: elementTimeout))
        verifyButton.tap()
        
        // Assert we are on the reset password view
        XCTAssertTrue(app.buttons["ResetPasswordAndLoginButton"].waitForExistence(timeout: elementTimeout), "Reset password and login button should exist")
        XCTAssertTrue(app.textFields["UsernameTextField"].waitForExistence(timeout: elementTimeout), "Username text field should exist")
        XCTAssertTrue(app.textFields["EmailTextField"].waitForExistence(timeout: elementTimeout), "Email text field should exist")
        XCTAssertTrue(app.secureTextFields["NewPasswordSecureField"].waitForExistence(timeout: elementTimeout), "New password text field should exist")
        
        let emailTextField = app.textFields["EmailTextField"]
        XCTAssertTrue(emailTextField.waitForExistence(timeout: elementTimeout))
        emailTextField.tap()
        typeText(element: emailTextField, text: "\(testUsername)@test.com")
        
        let passwordTextField = app.secureTextFields["NewPasswordSecureField"]
        XCTAssertTrue(passwordTextField.waitForExistence(timeout: elementTimeout))
        passwordTextField.tap()
        typeText(element: passwordTextField, text: newStrongPassword)
        
        let resetPasswordAndLoginButton = app.buttons["ResetPasswordAndLoginButton"]
        XCTAssertTrue(resetPasswordAndLoginButton.waitForExistence(timeout: elementTimeout))
        resetPasswordAndLoginButton.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton2 = app.buttons["LoginText"]
        XCTAssertTrue(loginButton2.waitForExistence(timeout: elementTimeout))
        loginButton2.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField2 = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: elementTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField2, text: testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordSecureField.waitForExistence(timeout: elementTimeout))
        passwordSecureField.tap()
        typeText(element: passwordSecureField, text: newStrongPassword)
        
        let loginButton3 = app.buttons["LoginButton"]
        XCTAssertTrue(loginButton3.waitForExistence(timeout: elementTimeout))
        loginButton3.tap()
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testFollowAndUnfollowFromSearch() throws {
        
        try ifOnHomeDeleteAccount(app: app)
        
        try registerUser(app: app, username: otherTestUsername, password: strongPassword)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        let userSearchField = app.searchFields["Search for Users"]
        XCTAssertTrue(userSearchField.waitForExistence(timeout: elementTimeout))
        userSearchField.tap()
        typeText(element: userSearchField, text: otherTestUsername)
        
        let userLink = app.buttons[otherTestUsername]
        XCTAssertTrue(userLink.waitForExistence(timeout: elementTimeout))
        userLink.tap()
        
        assertOnProfileView(app: app)
        
        let followersLabel = app.staticTexts["FollowersCount"]
        let followButton = app.buttons["FollowButton"]
        
        // 1. Initial Check (Safe conversion from String to Int)
        // We use .label because that contains the actual text text displayed
        XCTAssertEqual(followersLabel.label, "0")
        
        // 2. Tap Follow
        XCTAssertTrue(followButton.waitForExistence(timeout: elementTimeout))
        followButton.tap()
        
        // 3. WAIT for the change (Async logic)
        // We create a predicate that checks if the label becomes "1"
        let existsPredicate = NSPredicate(format: "label == '1'")
        
        // Wait up to 5 seconds for the label to update
        expectation(for: existsPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
        
        // 4. Tap Unfollow
        XCTAssertTrue(followButton.waitForExistence(timeout: elementTimeout))
        followButton.tap()
        
        // 5. WAIT for it to go back to "0"
        let zeroPredicate = NSPredicate(format: "label == '0'")
        expectation(for: zeroPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
            homeButton.tap()
        }
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testFollowAndUnfollowFromPost() throws {
        
        try ifOnHomeDeleteAccount(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: elementTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // Make sure there is one post in For You and no posts in Following
        // 1. Find the Picker container
        let feedPicker = app.segmentedControls["FeedTypePicker"]
        XCTAssertTrue(feedPicker.waitForExistence(timeout: elementTimeout))

        // 2. Find the button INSIDE the picker
        let followingSegment = feedPicker.buttons["Following"]
        XCTAssertTrue(followingSegment.waitForExistence(timeout: elementTimeout))
        followingSegment.tap()
        
        let allPostsQuery = app.buttons.matching(identifier: "FollowingPostImage")
        XCTAssertEqual(allPostsQuery.count, 0)
        
        let forYouPickerTab = feedPicker.buttons["For You"]
        XCTAssertTrue(forYouPickerTab.waitForExistence(timeout: elementTimeout))
        forYouPickerTab.tap()
        
        let allPostsQuery2 = app.buttons.matching(identifier: "ForYouPostImage")
        XCTAssertEqual(allPostsQuery2.count, 1)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostAuthorsQuery = app.buttons.matching(identifier: "PostAuthor")

        // Now, get the specific element at index 0 (the first one)
        let firstPostAuthorElement = allPostAuthorsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostAuthorElement.waitForExistence(timeout: elementTimeout))
        firstPostAuthorElement.tap()

        assertOnProfileView(app: app)
        
        let followersLabel = app.staticTexts["FollowersCount"]
        let followButton = app.buttons["FollowButton"]
        
        // 1. Initial Check (Safe conversion from String to Int)
        // We use .label because that contains the actual text text displayed
        XCTAssertEqual(followersLabel.label, "0")
        
        // 2. Tap Follow
        XCTAssertTrue(followButton.waitForExistence(timeout: elementTimeout))
        followButton.tap()
        
        // 3. WAIT for the change (Async logic)
        // We create a predicate that checks if the label becomes "1"
        let existsPredicate = NSPredicate(format: "label == '1'")
        
        // Wait up to 5 seconds for the label to update
        expectation(for: existsPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
        
        // 4. Tap Unfollow
        XCTAssertTrue(followButton.waitForExistence(timeout: elementTimeout))
        followButton.tap()
        
        // 5. WAIT for it to go back to "0"
        let zeroPredicate = NSPredicate(format: "label == '0'")
        expectation(for: zeroPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: 5.0, handler: nil)
        
        /// We refollow so that we can check that the post now shows up in the "Following" Feed
        XCTAssertTrue(followButton.waitForExistence(timeout: elementTimeout))
        followButton.tap()
        
        // Go back to FeedView
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        // Make sure there is one post in For You and one post in Following
        // 1. Find the Picker container
        let feedPicker2 = app.segmentedControls["FeedTypePicker"]
        XCTAssertTrue(feedPicker2.waitForExistence(timeout: elementTimeout))

        // 2. Find the button INSIDE the picker
        let followingSegment2 = feedPicker2.buttons["Following"]
        XCTAssertTrue(followingSegment2.waitForExistence(timeout: elementTimeout))
        followingSegment2.tap()
        
        let allPostsQuery3 = app.buttons.matching(identifier: "FollowingPostImage")
        XCTAssertEqual(allPostsQuery3.count, 1)
        
        let forYouPickerTab2 = feedPicker2.buttons["For You"]
        XCTAssertTrue(forYouPickerTab2.waitForExistence(timeout: elementTimeout))
        forYouPickerTab2.tap()
        
        let allPostsQuery4 = app.buttons.matching(identifier: "ForYouPostImage")
        XCTAssertEqual(allPostsQuery4.count, 1)
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
            homeButton.tap()
        }
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testLikeAndUnlikePost() throws {
        
        try ifOnHomeDeleteAccount(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: elementTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: elementTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let postImage = app.buttons["PostImage"]
        XCTAssertTrue(postImage.waitForExistence(timeout: elementTimeout))
        postImage.doubleTap()
        
        let postLikesText = app.staticTexts["PostLikesText"]
        XCTAssertEqual(postLikesText.label, "1 likes")
        
        XCTAssertTrue(postImage.waitForExistence(timeout: elementTimeout))
        postImage.doubleTap()
        
        XCTAssertEqual(postLikesText.label, "0 likes")
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
            homeButton.tap()
        }
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testVerifyIdentity() throws {
        
        try ifOnHomeDeleteAccount(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        let settingsTab = app.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: elementTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let verifyIdentityButton = app.buttons["VerifyIdentityButton"]
        XCTAssertTrue(verifyIdentityButton.waitForExistence(timeout: elementTimeout), "Verify Identity button should be present for new user")
        verifyIdentityButton.tap()
        
        let submitVerificationButton = app.buttons["SubmitVerificationButton"]
        XCTAssertTrue(submitVerificationButton.waitForExistence(timeout: elementTimeout))
        
        // We just tap verify to send the default date (today)
        submitVerificationButton.tap()
        
        // Wait for success alert
        let successAlert = app.alerts["Identity Verified"]
        XCTAssertTrue(successAlert.waitForExistence(timeout: elementTimeout))
        XCTAssertTrue(successAlert.buttons["OK"].waitForExistence(timeout: elementTimeout))
        successAlert.buttons["OK"].tap()
        
        // Verify Identity submit button should be gone. This is a proxy for the dialog being gone.
        XCTAssertFalse(submitVerificationButton.exists, "Verify Identity submit button should disappear after verification")
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
            homeButton.tap()
        }
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testLikeAndUnlikeCommentOnPostAndThread() throws {
        
        try ifOnHomeDeleteAccount(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        makeCommentOnPost(app: app, commentText: "Comment On a Post")
        
        let firstBackButton = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(firstBackButton.waitForExistence(timeout: elementTimeout))
        firstBackButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        makeCommentOnThread(app: app, commentText: "Comment On a Thread")
        
        let backButton2 = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton2.waitForExistence(timeout: elementTimeout))
        backButton2.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton2 = app.buttons["Home"]
        XCTAssertTrue(homeButton2.waitForExistence(timeout: elementTimeout))
        homeButton2.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: elementTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: elementTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        // First we like and unlike the comment post comment
        let postCommentStackQuery = app.buttons.matching(identifier: "CommentStack")
        let postCommentStack = postCommentStackQuery.element(boundBy: 0)
        XCTAssertTrue(postCommentStack.waitForExistence(timeout: elementTimeout))
        postCommentStack.doubleTap()
        
        let postCommentLikesTextQuery = app.staticTexts.matching(identifier: "CommentLikesCount")
        let postCommentLikesText = postCommentLikesTextQuery.element(boundBy: 0)
        XCTAssertEqual(postCommentLikesText.label, "1 likes")
        
        XCTAssertTrue(postCommentStack.waitForExistence(timeout: elementTimeout))
        postCommentStack.doubleTap()
        
        XCTAssertEqual(postCommentLikesText.label, "0 likes")
        
        // Then we like and unlike the comment thread comment
        let postCommentStackQuery2 = app.buttons.matching(identifier: "CommentStack")
        let postCommentStack2 = postCommentStackQuery2.element(boundBy: 1)
        XCTAssertTrue(postCommentStack2.waitForExistence(timeout: elementTimeout))
        postCommentStack2.doubleTap()
        
        let postCommentLikesTextQuery2 = app.staticTexts.matching(identifier: "CommentLikesCount")
        let postCommentLikesText2 = postCommentLikesTextQuery2.element(boundBy: 1)
        XCTAssertEqual(postCommentLikesText2.label, "1 likes")
        
        XCTAssertTrue(postCommentStack2.waitForExistence(timeout: elementTimeout))
        postCommentStack2.doubleTap()
        
        XCTAssertEqual(postCommentLikesText2.label, "0 likes")
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        let homeButton3 = app.buttons["Home"]
        if homeButton3.exists {
            XCTAssertTrue(homeButton3.waitForExistence(timeout: elementTimeout))
            homeButton3.tap()
        }
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testReportPost() throws {
        
        try ifOnHomeDeleteAccount(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        makeCommentOnPost(app: app, commentText: "Comment On a Post")
        
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: elementTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: elementTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let postImage = app.buttons["PostImage"]
        // 2 second press
        XCTAssertTrue(postImage.waitForExistence(timeout: elementTimeout))
        postImage.press(forDuration: 2)
        
        let reasonTextField = app.textFields["ProvideAReasonTextField"]
        XCTAssertTrue(reasonTextField.waitForExistence(timeout: elementTimeout))
        reasonTextField.tap()
        typeText(element: reasonTextField, text: "Report post")
        
        let reportButton = app.buttons["SubmitReportButton"]
        XCTAssertTrue(reportButton.waitForExistence(timeout: elementTimeout))
        reportButton.tap()
        
        let reportedCommentIcon = app.images["ReportedPostIcon"]
        XCTAssertTrue(reportedCommentIcon.waitForExistence(timeout: elementTimeout), "Reported post icon is missing")
        
        let backButton2 = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton2.waitForExistence(timeout: elementTimeout))
        backButton2.tap()
        
        let homeButton2 = app.buttons["Home"]
        if homeButton2.exists {
            XCTAssertTrue(homeButton2.waitForExistence(timeout: elementTimeout))
            homeButton2.tap()
        }
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testReportComment() throws {
        
        try ifOnHomeDeleteAccount(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        try makePost(app: app, postText: "Some Post Caption")
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)
        
        makeCommentOnPost(app: app, commentText: "Comment On a Post")
        
        let backButton = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        makeCommentOnThread(app: app, commentText: "Comment On a Thread")
        
        let backButton2 = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton2.waitForExistence(timeout: elementTimeout))
        backButton2.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: elementTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: elementTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let commentStackQuery = app.buttons.matching(identifier: "CommentStack")
        let commentStack = commentStackQuery.element(boundBy: 0)
        // 2 second press
        XCTAssertTrue(commentStack.waitForExistence(timeout: elementTimeout))
        commentStack.press(forDuration: 2)
        
        let reasonTextField = app.textFields["ProvideAReasonTextField"]
        XCTAssertTrue(reasonTextField.waitForExistence(timeout: elementTimeout))
        reasonTextField.tap()
        typeText(element: reasonTextField, text: "Report comment thread")
        
        let reportButton = app.buttons["SubmitReportButton"]
        XCTAssertTrue(reportButton.waitForExistence(timeout: elementTimeout))
        reportButton.tap()
        
        let reportedCommentIcon = app.images["ReportedCommentIcon"]
        XCTAssertTrue(reportedCommentIcon.waitForExistence(timeout: elementTimeout), "Reported comment icon is missing")
        
        
        let commentStackQuery2 = app.buttons.matching(identifier: "CommentStack")
        let commentStack2 = commentStackQuery2.element(boundBy: 1)
        // 2 second press
        XCTAssertTrue(commentStack2.waitForExistence(timeout: elementTimeout))
        commentStack2.press(forDuration: 2)
        
        let reasonTextField2 = app.textFields["ProvideAReasonTextField"]
        XCTAssertTrue(reasonTextField2.waitForExistence(timeout: elementTimeout))
        reasonTextField2.tap()
        typeText(element: reasonTextField2, text: "Report comment reply")
        
        let reportButton2 = app.buttons["SubmitReportButton"]
        XCTAssertTrue(reportButton2.waitForExistence(timeout: elementTimeout))
        reportButton2.tap()
        
        let reportedCommentIcon2 = app.images.matching(identifier: "ReportedCommentIcon")
        XCTAssertEqual(reportedCommentIcon2.count, 2, "Expected 2 reported comment icons but only found \(reportedCommentIcon2.count)")
        
        let backButton3 = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton3.waitForExistence(timeout: elementTimeout))
        backButton3.tap()
        
        let homeButton2 = app.buttons["Home"]
        if homeButton2.exists {
            XCTAssertTrue(homeButton2.waitForExistence(timeout: elementTimeout))
            homeButton2.tap()
        }
        
        assertOnHomeView(app: app)
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            app.launch()

            do {
                try ifOnHomeDeleteAccount(app: app)
            } catch {
                XCTFail("ifOnHomeDeleteAccount threw error: \(error)")
            }
            
        }
        
        try registerUser(app: app, username: newTestUsername, password: strongPassword)
        assertOnHomeView(app: app)
    }

    @MainActor
    func testBlockAndUnblockUser() throws {
        
        try ifOnHomeDeleteAccount(app: app)
        
        // Setup: Create other user
        try registerUser(app: app, username: otherTestUsername, password: strongPassword)
        try logoutUserFromHome(app: app)
        
        // Login as main user
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        // Search for user
        let userSearchField = app.searchFields["Search for Users"]
        XCTAssertTrue(userSearchField.waitForExistence(timeout: elementTimeout))
        userSearchField.tap()
        typeText(element: userSearchField, text: otherTestUsername)
        
        let userLink = app.buttons[otherTestUsername]
        XCTAssertTrue(userLink.waitForExistence(timeout: elementTimeout))
        userLink.tap()
        
        assertOnProfileView(app: app)
        
        // Initially "Block" button should be visible
        let blockButton = app.buttons["Block"]
        XCTAssertTrue(blockButton.waitForExistence(timeout: elementTimeout))
        
        // Click Block
        blockButton.tap()
        
        // Verify changes to "Unblock"
        let unblockButton = app.buttons["Unblock"]
        XCTAssertTrue(unblockButton.waitForExistence(timeout: elementTimeout))
        
        // Click Unblock
        unblockButton.tap()
        
        // Verify changes back to "Block"
        XCTAssertTrue(blockButton.waitForExistence(timeout: elementTimeout))
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: elementTimeout))
        backButton.tap()
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: elementTimeout))
            homeButton.tap()
        }
        
        assertOnHomeView(app: app)
    }
}

