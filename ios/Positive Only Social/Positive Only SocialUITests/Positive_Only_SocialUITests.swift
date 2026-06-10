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
    let strongPassword: String = "StrongPassword123@"
    let newStrongPassword: String = "NewStrongPassword456@"

    override func setUpWithError() throws {
        try super.setUpWithError()
        // Force to portrait so that we don't squish things and fail the tests
        XCUIDevice.shared.orientation = .portrait
        
        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false
        
        app = XCUIApplication()
        app.launchArguments.append("--ui_testing")
        // get the name and remove the opening bracket and closing bracket,
        // then replace spaces (between class name and method name) with underscores
        // so the resulting username contains only word characters.
        var baseName = self.name.replacingOccurrences(of: "-[", with: "")
        baseName = baseName.replacingOccurrences(of: "]", with: "")
        baseName = baseName.replacingOccurrences(of: " ", with: "_")
        
        app.launchEnvironment["test-name"] = baseName
        app.launch()

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
        testUsername = "\(baseName)_user"
        otherTestUsername = "\(baseName)_other_user"
        newTestUsername = "\(baseName)_new_user"

        // Automatically dismiss any "Save Password" / "Update Password" system
        // dialogs (presented by SpringBoard, not the app) that would otherwise
        // block interactions. The monitor fires the next time the test tries to
        // interact with a UI element while the system dialog is in front.
        // "Choose My Own Password" / "Don't Use" cover the Strong Password variant
        // when iOS surfaces it as a system-level interrupt rather than an in-app sheet.
        addUIInterruptionMonitor(withDescription: "Password dialog") { alert -> Bool in
            for title in ["Not Now", "Never for This Website", "Cancel",
                          "Choose My Own Password", "Choose My Own…", "Don't Use"] {
                if alert.buttons[title].exists {
                    alert.buttons[title].tap()
                    return true
                }
            }
            return false
        }
    }

    override func tearDownWithError() throws {
        // We want the test to teardown properly even if it fails midway through
        app.terminate()
        
        try super.tearDownWithError()
    }
    
    // MARK: Helpers
    private func yield(duration: Duration = .seconds(TestConstants.shortTimeout)) async {
        try? await Task.sleep(for: duration)
    }
    
    private func dismissKeyboardIfPresent(_ app: XCUIApplication) {
        let maxAttempts = 5
        var attempt = 0
        while (true && attempt < maxAttempts) {
            RunLoop.current.run(until: NSDate(timeIntervalSinceNow: 1.0) as Date)
            if app.keyboards.buttons["Return"].exists {
                XCTAssertTrue(app.keyboards.buttons["Return"].waitForExistence(timeout: TestConstants.shortTimeout))
                app.keyboards.buttons["Return"].tap()
                break
            }
            attempt += 1
        }
    }

    /// Dismisses the iOS "Use Strong Password" AutoFill panel/sheet if it is showing.
    /// In newer iOS the suggestion appears as a floating panel above the keyboard with
    /// an "xmark" close button (SF Symbol); older iOS uses an action sheet with text
    /// buttons. We try both styles.
    ///
    /// - Parameter shouldWait: Pass `true` for password fields where the panel takes a
    ///   couple of seconds to appear (adds ~2 s to the first probe); pass `false` for
    ///   regular text fields where the panel never shows (stays at 0.5 s so tests stay fast).
    private func dismissStrongPasswordIfPresent(shouldWait: Bool) {
        let firstProbeTimeout: TimeInterval = shouldWait ? 2.0 : 0.5
        // Newer iOS (17+): floating AutoFill panel has an X / xmark close button.
        for (index, title) in ["xmark", "Close", "close"].enumerated() {
            let timeout = index == 0 ? firstProbeTimeout : 0.5
            if app.buttons[title].waitForExistence(timeout: timeout) {
                app.buttons[title].tap()
                return
            }
        }
        // Older iOS / action-sheet style: text buttons on a sheet.
        for title in ["Choose My Own Password", "Choose My Own…", "Don't Use"] {
            if app.buttons[title].waitForExistence(timeout: 0.5) {
                app.buttons[title].tap()
                return
            }
        }
    }

    private func typeText(element: XCUIElement, text: String) {
        let maxAttempts = 5
        var attempt = 0

        element.tap()

        // The "Use Strong Password" AutoFill panel appears immediately on the
        // first tap and prevents the field from ever gaining focus.  Dismiss it
        // right here — before the focus-check loop — so the loop can succeed.
        // Only password (secure) fields trigger the panel, so we only wait for
        // it on those fields; plain text fields use a fast 0.5 s probe.
        dismissStrongPasswordIfPresent(shouldWait: element.elementType == .secureTextField)

        while (!element.hasFocus || app.keyboards.count == 0) && attempt < maxAttempts {
            element.tap()
            RunLoop.current.run(until: NSDate(timeIntervalSinceNow: 1.0) as Date)
            attempt += 1
        }

        XCTAssertTrue(element.hasFocus || app.keyboards.count > 0, "Element did not gain keyboard focus.")

        // Clear any pre-existing content so that a retry never appends to
        // stale text.  Triple-tap selects all text in a field on iOS; the
        // following typeText call then replaces the selection.
        let existing = (element.value as? String) ?? ""
        if !existing.isEmpty {
            element.tap(withNumberOfTaps: 3, numberOfTouches: 1)
            RunLoop.current.run(until: NSDate(timeIntervalSinceNow: 0.3) as Date)
        }

        element.typeText(text)
    }
    
    private func assertOnWelcomeView(app: XCUIApplication) {
        // We wait until the "Welcome! 👋" text (which is in NeedsAuthView) appears.
        let welcomeText = app.staticTexts["Welcome! 👋"]
        
        // Use a robust existence check with a reasonable timeout.
        XCTAssertTrue(welcomeText.waitForExistence(timeout: TestConstants.shortTimeout), "The Welcome! 👋 text (NeedsAuthView) did not appear in time.")

        XCTAssertTrue(app.buttons["RegisterText"].waitForExistence(timeout: TestConstants.shortTimeout), "Register button is not empty")
        XCTAssertTrue(app.buttons["LoginText"].waitForExistence(timeout: TestConstants.shortTimeout), "Login button is not empty")
    }
    
    private func assertOnRegisterView(app: XCUIApplication) {
        XCTAssertTrue(app.textFields["UsernameTextField"].waitForExistence(timeout: TestConstants.shortTimeout), "Username field not present")
        XCTAssertTrue(app.textFields["EmailTextField"].waitForExistence(timeout: TestConstants.shortTimeout), "Email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].waitForExistence(timeout: TestConstants.shortTimeout), "Password field not present")
        XCTAssertTrue(app.secureTextFields["ConfirmPasswordSecureField"].waitForExistence(timeout: TestConstants.shortTimeout), "Confirm Password field not present")
        XCTAssertTrue(app.datePickers["DateOfBirthPicker"].waitForExistence(timeout: TestConstants.shortTimeout), "Date of birth picker not present")
        XCTAssertTrue(app.buttons["RegisterButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Register button not present")
    }
    
    private func assertOnLoginView(app: XCUIApplication) {
        XCTAssertTrue(app.staticTexts["Login"].waitForExistence(timeout: TestConstants.shortTimeout), "Login text did not appear in time.")

        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].waitForExistence(timeout: TestConstants.shortTimeout), "Username or email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].waitForExistence(timeout: TestConstants.shortTimeout), "Password field not present")
        XCTAssertTrue(app.buttons["LoginButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Login button not present")
        XCTAssertTrue(app.switches["RememberMeToggle"].waitForExistence(timeout: TestConstants.shortTimeout), "Remember me toggle not present")
        XCTAssertTrue(app.buttons["ForgotPasswordButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Forgot password button not present")
    }
    
    private func assertOnHomeView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["Home"].waitForExistence(timeout: TestConstants.shortTimeout), "Home tab not present")
        XCTAssertTrue(app.buttons["Feed"].waitForExistence(timeout: TestConstants.shortTimeout), "Feed tab not present")
        XCTAssertTrue(app.buttons["Post"].waitForExistence(timeout: TestConstants.shortTimeout), "New post tab not present")
        XCTAssertTrue(app.buttons["Settings"].waitForExistence(timeout: TestConstants.shortTimeout), "Settings tab not present")
    }
    
    private func assertOnSettingsView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["LogoutButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Logout button not present")
        XCTAssertTrue(app.buttons["DeleteAccountButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Delete Account button not present")
    }
    
    private func assertOnProfileView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["FollowButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Follow button not present")
        XCTAssertTrue(app.staticTexts["Following"].waitForExistence(timeout: TestConstants.shortTimeout), "Following stat item not present")
        XCTAssertTrue(app.staticTexts["Followers"].waitForExistence(timeout: TestConstants.shortTimeout), "Followers stat item not present")
        XCTAssertTrue(app.staticTexts["Posts"].waitForExistence(timeout: TestConstants.shortTimeout), "Posts stat item not present")
    }
    
    private func assertOnNewPostView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["SelectAPhotoPicker"].waitForExistence(timeout: TestConstants.shortTimeout), "Select a photo picker not present")
        XCTAssertTrue(app.textViews["CaptionTextEditor"].waitForExistence(timeout: TestConstants.shortTimeout), "Caption text editor not present")
        XCTAssertTrue(app.buttons["SharePostButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Share post button is not empty")
    }
    
    private func assertOnFeedView(app: XCUIApplication) {
        XCTAssertTrue(app.segmentedControls["FeedTypePicker"].waitForExistence(timeout: TestConstants.shortTimeout), "Feed type picker not present")
    }
    
    private func assertOnPostDetailView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["PostCommentButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Post comment button not present")
        XCTAssertTrue(app.buttons["PostImage"].waitForExistence(timeout: TestConstants.shortTimeout), "Post image not present in time")
        XCTAssertTrue(app.textFields["AddACommentTextFieldToPost"].waitForExistence(timeout: TestConstants.shortTimeout), "Add a comment text field not present")
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
        XCTAssertTrue(welcomeText.waitForExistence(timeout: TestConstants.shortTimeout), "The Welcome! 👋 text (NeedsAuthView) did not appear in time.")
        
        let registerButton = app.buttons["RegisterText"]
        XCTAssertTrue(registerButton.waitForExistence(timeout: TestConstants.shortTimeout))
        registerButton.tap()
        
        assertOnRegisterView(app: app)
        
        dismissKeyboardIfPresent(app)
        
        let usernameField = app.textFields["UsernameTextField"]
        XCTAssertTrue(usernameField.waitForExistence(timeout: TestConstants.shortTimeout))
        usernameField.tap()
        typeText(element: usernameField, text: username)
        
        let emailField = app.textFields["EmailTextField"]
        XCTAssertTrue(emailField.waitForExistence(timeout: TestConstants.shortTimeout))
        emailField.tap()
        typeText(element: emailField, text: "\(username)@test.com")
        
        let passwordField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordField.waitForExistence(timeout: TestConstants.shortTimeout))
        passwordField.tap()
        typeText(element: passwordField, text: password)
        
        let confirmPasswordField = app.secureTextFields["ConfirmPasswordSecureField"]
        XCTAssertTrue(confirmPasswordField.waitForExistence(timeout: TestConstants.shortTimeout))
        confirmPasswordField.tap()
        typeText(element: confirmPasswordField, text: password)

        // The keyboard can obscure the "Register" button at the bottom of the
        // screen, so dismiss it before trying to tap the button.
        dismissKeyboardIfPresent(app)

        let otherRegisterButton = app.buttons["RegisterButton"]
        XCTAssertTrue(otherRegisterButton.waitForExistence(timeout: TestConstants.shortTimeout))
        otherRegisterButton.tap()
        
        let privacyPolicyAlert = app.alerts["Privacy Policy"]
        XCTAssertTrue(privacyPolicyAlert.waitForExistence(timeout: TestConstants.shortTimeout))
        XCTAssertTrue(privacyPolicyAlert.buttons["Ok"].waitForExistence(timeout: TestConstants.shortTimeout))
        privacyPolicyAlert.buttons["Ok"].tap()
        
        assertOnHomeView(app: app)
        
        dismissSavePassword(app: app)
    }
    
    private func dismissSavePassword(app: XCUIApplication) {
        let notNowButton = app.buttons["Not Now"]
        if notNowButton.waitForExistence(timeout: TestConstants.shortTimeout) {
            notNowButton.tap()
        }
    }
    
    private func loginUser(app: XCUIApplication, username: String, password: String, rememberMe: Bool) throws {
        try registerUser(app: app, username: username, password: password)
        
        try logoutUserFromHome(app: app)
        
        let loginButton = app.buttons["LoginText"]
        XCTAssertTrue(loginButton.waitForExistence(timeout: TestConstants.shortTimeout))
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        dismissKeyboardIfPresent(app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField, text: username)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordSecureField.waitForExistence(timeout: TestConstants.shortTimeout))
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
        XCTAssertTrue(loginButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        loginButton2.tap()
        
        assertOnHomeView(app: app)
        
        dismissSavePassword(app: app)
    }
    
    private func logoutUserFromHome(app: XCUIApplication) throws {
        let settingsTab = app.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: TestConstants.shortTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let logoutButton = app.buttons["LogoutButton"]
        XCTAssertTrue(logoutButton.waitForExistence(timeout: TestConstants.shortTimeout))
        logoutButton.tap()
        
        /// Don't know why but there is a hierarchy of confirm logout buttons
        let confirmLogoutButton = app.buttons["ConfirmLogoutButton"].firstMatch
        XCTAssertTrue(confirmLogoutButton.waitForExistence(timeout: TestConstants.shortTimeout))
        confirmLogoutButton.tap()
        
        assertOnWelcomeView(app: app)
    }
    
    private func deleteAccountFromHome(app: XCUIApplication) throws {
        let settingsTab = app.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: TestConstants.shortTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let deleteAccountButton = app.buttons["DeleteAccountButton"]
        XCTAssertTrue(deleteAccountButton.waitForExistence(timeout: TestConstants.shortTimeout))
        deleteAccountButton.tap()
        
        let confirmDeleteAccountButton = app.buttons["ConfirmDeleteAccountButton"].firstMatch
        XCTAssertTrue(confirmDeleteAccountButton.waitForExistence(timeout: TestConstants.shortTimeout))
        confirmDeleteAccountButton.tap()
        
        assertOnWelcomeView(app: app)
    }
    
    /// Assumes the user is logged in and we are on HomeView.
    private func makePost(app: XCUIApplication, postText: String) throws {
        assertOnHomeView(app: app)
        
        let newPostTab = app.buttons["Post"]
        XCTAssertTrue(newPostTab.waitForExistence(timeout: TestConstants.shortTimeout))
        newPostTab.tap()
        
        assertOnNewPostView(app: app)
        
        let captionTextEditor = app.textViews["CaptionTextEditor"]
        XCTAssertTrue(captionTextEditor.waitForExistence(timeout: TestConstants.shortTimeout))
        captionTextEditor.tap()
        typeText(element: captionTextEditor, text: postText)
        
        // Find the photo picker's main view (identifier may vary)
        let picker = app.buttons["SelectAPhotoPicker"]
        XCTAssertTrue(picker.waitForExistence(timeout: TestConstants.shortTimeout))
        picker.tap()

        let sharePostButton = app.buttons["SharePostButton"]
        XCTAssertTrue(sharePostButton.waitForExistence(timeout: TestConstants.shortTimeout))
        sharePostButton.tap()

        assertOnHomeView(app: app)
    }
    
    /// Makes a comment on the first post found in the For You Feed. Assumes the user is logged in and we are on HomeView and a post was made already.
    /// Ends on the PostDetailView.
    private func makeCommentOnPost(app: XCUIApplication, commentText: String) {
        assertOnHomeView(app: app)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)
        
        XCTAssertTrue(firstPostElement.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPostElement.tap()
        
        assertOnPostDetailView(app: app)
        
        let addACommentTextField = app.textFields["AddACommentTextFieldToPost"]
        XCTAssertTrue(addACommentTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        addACommentTextField.tap()
        typeText(element: addACommentTextField, text: commentText)
        
        let postCommentButton = app.buttons["PostCommentButton"]
        XCTAssertTrue(postCommentButton.waitForExistence(timeout: TestConstants.shortTimeout))
        postCommentButton.tap()
        
        dismissKeyboardIfPresent(app)
        
        // Should be one comment total
        let commentElements = app.staticTexts.matching(identifier: "CommentText")
        expectation(for: NSPredicate(format: "count == 1"), evaluatedWith: commentElements, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
        XCTAssert(commentElements.count == 1, "Expected to find 1 comment, but found \(commentElements.count)")
        
        assertOnPostDetailView(app: app)
    }
    
    /// Makes a comment on the first comment thread found on the first post found in the For You Feed. Assumes the user is logged in and we are on
    /// HomeView and a post was made already. Ends on the PostDetailView.
    private func makeCommentOnThread(app: XCUIApplication, commentText: String) {
        assertOnHomeView(app: app)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)
        
        XCTAssertTrue(firstPostElement.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPostElement.tap()
        
        assertOnPostDetailView(app: app)
        
        // Wait for comments to load
        let replyButton = app.buttons["ReplyToCommentThreadButton"]
        XCTAssertTrue(replyButton.waitForExistence(timeout: TestConstants.shortTimeout))
        
        // Tap the Reply button to open the sheet
        replyButton.tap()
        
        // Wait for the reply sheet to appear
        let replySheet = app.navigationBars["Post Reply"]
        XCTAssertTrue(replySheet.waitForExistence(timeout: TestConstants.shortTimeout))
        
        // Find the TextEditor in the sheet
        // TextEditor appears as a textView in the accessibility hierarchy
        let replyTextEditor = app.textViews.firstMatch
        XCTAssertTrue(replyTextEditor.waitForExistence(timeout: TestConstants.shortTimeout))
        
        // Tap and type the reply
        replyTextEditor.tap()
        typeText(element: replyTextEditor, text: commentText)
        
        // Tap the Send button
        let sendButton = app.buttons["Send"]
        XCTAssertTrue(sendButton.waitForExistence(timeout: TestConstants.shortTimeout))
        XCTAssertTrue(sendButton.isEnabled)
        sendButton.tap()
        
        // Should be two comments total
        let commentElements = app.staticTexts.matching(identifier: "CommentText")
        expectation(for: NSPredicate(format: "count == 2"), evaluatedWith: commentElements, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
        XCTAssert(commentElements.count == 2, "Expected to find 2 comments, but found \(commentElements.count)")
        
        assertOnPostDetailView(app: app)
    }
    
    /// Waits for an element's accessibility label to equal the expected value. Like/unlike updates
    /// are applied optimistically on the SwiftUI run loop, and XCUITest reads the accessibility label
    /// from a separate process, so a plain `XCTAssertEqual` can race the re-render. Waiting on a
    /// predicate makes the check robust, matching how the rest of this file handles async values.
    private func waitForLabel(_ element: XCUIElement, toEqual expected: String) {
        let predicate = NSPredicate(format: "label == %@", expected)
        expectation(for: predicate, evaluatedWith: element, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
    }

    // MARK: Tests

    /// Issue #205: tapping anywhere outside a text field should dismiss the
    /// keyboard so the buttons it was covering (Register, Login, …) become
    /// reachable again. Exercised on the Register screen; the dismissal itself
    /// is purely a UI behavior, though the test first clears any signed-in
    /// state via `ifOnHomeDeleteAccount` to reach the Welcome → Register flow.
    @MainActor
    func testTappingOutsideFieldDismissesKeyboard() throws {
        try ifOnHomeDeleteAccount(app: app)

        // Navigate to the Register screen.
        let welcomeText = app.staticTexts["Welcome! 👋"]
        XCTAssertTrue(welcomeText.waitForExistence(timeout: TestConstants.shortTimeout),
                      "Welcome view did not appear")
        let registerButton = app.buttons["RegisterText"]
        XCTAssertTrue(registerButton.waitForExistence(timeout: TestConstants.shortTimeout))
        registerButton.tap()
        assertOnRegisterView(app: app)

        // Focus a field so the keyboard appears.
        let usernameField = app.textFields["UsernameTextField"]
        XCTAssertTrue(usernameField.waitForExistence(timeout: TestConstants.shortTimeout))
        usernameField.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: TestConstants.shortTimeout),
                      "Keyboard should appear when a text field is focused")

        // Tap a non-interactive area outside any field (the screen title, which
        // sits inside the tappable container). The keyboard should dismiss.
        let title = app.staticTexts["Create Account"]
        XCTAssertTrue(title.waitForExistence(timeout: TestConstants.shortTimeout))
        title.tap()

        let keyboardGone = NSPredicate(format: "count == 0")
        expectation(for: keyboardGone, evaluatedWith: app.keyboards, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
    }

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
        XCTAssertTrue(settingsTab.waitForExistence(timeout: TestConstants.shortTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let deleteAccountButton = app.buttons["DeleteAccountButton"]
        XCTAssertTrue(deleteAccountButton.waitForExistence(timeout: TestConstants.shortTimeout))
        deleteAccountButton.tap()
        
        let confirmDeleteAccountButton = app.buttons["ConfirmDeleteAccountButton"].firstMatch
        XCTAssertTrue(confirmDeleteAccountButton.waitForExistence(timeout: TestConstants.shortTimeout))
        confirmDeleteAccountButton.tap()
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.buttons["LoginText"]
        XCTAssertTrue(loginButton.waitForExistence(timeout: TestConstants.shortTimeout))
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField, text: testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordSecureField.waitForExistence(timeout: TestConstants.shortTimeout))
        passwordSecureField.tap()
        typeText(element: passwordSecureField, text: strongPassword)
        
        let loginButton2 = app.buttons["LoginButton"]
        XCTAssertTrue(loginButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        loginButton2.tap()
        
        XCTAssertTrue(app.buttons["LoginFailedOkButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Login should have failed")
        
        XCTAssertTrue(app.buttons["LoginFailedOkButton"].firstMatch.waitForExistence(timeout: TestConstants.shortTimeout))
        app.buttons["LoginFailedOkButton"].firstMatch.tap()
        
        dismissSavePassword(app: app)
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()
        
        dismissSavePassword(app: app)
        
        try registerUser(app: app, username: newTestUsername, password: strongPassword)
    }
    
    @MainActor
    func testResetPassword() throws {
        
        try ifOnHomeDeleteAccount(app: app)

        try registerUser(app: app, username: testUsername, password: strongPassword)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.buttons["LoginText"]
        XCTAssertTrue(loginButton.waitForExistence(timeout: TestConstants.shortTimeout))
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let forgotPasswordButton = app.buttons["ForgotPasswordButton"]
        XCTAssertTrue(forgotPasswordButton.waitForExistence(timeout: TestConstants.shortTimeout))
        forgotPasswordButton.tap()
        
        // Assert we are on request reset view
        XCTAssertTrue(app.buttons["RequestResetButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Request reset button should exist")
        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].waitForExistence(timeout: TestConstants.shortTimeout), "Username or email text field should exist")
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField, text: testUsername)
        
        let requestResetButton = app.buttons["RequestResetButton"]
        XCTAssertTrue(requestResetButton.waitForExistence(timeout: TestConstants.shortTimeout))
        requestResetButton.tap()
        
        // Assert we are on the verify reset view
        XCTAssertTrue(app.buttons["VerifyButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Verify button should exist")
        XCTAssertTrue(app.textFields["VerificationTokenTextField"].waitForExistence(timeout: TestConstants.shortTimeout), "Verification token field should exist")

        let verificationTokenTextField = app.textFields["VerificationTokenTextField"]
        XCTAssertTrue(verificationTokenTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        verificationTokenTextField.tap()
        // The stub value is set in StatefulStubbedAPI.requestPasswordReset
        typeText(element: verificationTokenTextField, text: "stub_verification_token_\(testUsername)")
        
        let verifyButton = app.buttons["VerifyButton"]
        XCTAssertTrue(verifyButton.waitForExistence(timeout: TestConstants.shortTimeout))
        verifyButton.tap()
        
        // Assert we are on the reset password view
        XCTAssertTrue(app.buttons["ResetPasswordAndLoginButton"].waitForExistence(timeout: TestConstants.shortTimeout), "Reset password and login button should exist")
        XCTAssertTrue(app.textFields["UsernameTextField"].waitForExistence(timeout: TestConstants.shortTimeout), "Username text field should exist")
        XCTAssertTrue(app.textFields["EmailTextField"].waitForExistence(timeout: TestConstants.shortTimeout), "Email text field should exist")
        XCTAssertTrue(app.secureTextFields["NewPasswordSecureField"].waitForExistence(timeout: TestConstants.shortTimeout), "New password text field should exist")
        XCTAssertTrue(app.secureTextFields["ConfirmNewPasswordSecureField"].waitForExistence(timeout: TestConstants.shortTimeout), "Confirm new password text field should exist")

        let emailTextField = app.textFields["EmailTextField"]
        XCTAssertTrue(emailTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        emailTextField.tap()
        typeText(element: emailTextField, text: "\(testUsername)@test.com")

        let passwordTextField = app.secureTextFields["NewPasswordSecureField"]
        XCTAssertTrue(passwordTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        passwordTextField.tap()
        typeText(element: passwordTextField, text: newStrongPassword)

        let confirmNewPasswordTextField = app.secureTextFields["ConfirmNewPasswordSecureField"]
        XCTAssertTrue(confirmNewPasswordTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        confirmNewPasswordTextField.tap()
        typeText(element: confirmNewPasswordTextField, text: newStrongPassword)

        // The keyboard can obscure the "Reset Password and Login" button at the
        // bottom of the screen, so dismiss it before trying to tap the button.
        dismissKeyboardIfPresent(app)

        let resetPasswordAndLoginButton = app.buttons["ResetPasswordAndLoginButton"]
        XCTAssertTrue(resetPasswordAndLoginButton.waitForExistence(timeout: TestConstants.shortTimeout))
        resetPasswordAndLoginButton.tap()
        
        dismissSavePassword(app: app)
        
        assertOnHomeView(app: app)
        
        dismissSavePassword(app: app)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton2 = app.buttons["LoginText"]
        XCTAssertTrue(loginButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        loginButton2.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField2 = app.textFields["UsernameOrEmailTextField"]
        XCTAssertTrue(usernameOrEmailTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        usernameOrEmailTextField.tap()
        typeText(element: usernameOrEmailTextField2, text: testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        XCTAssertTrue(passwordSecureField.waitForExistence(timeout: TestConstants.shortTimeout))
        passwordSecureField.tap()
        typeText(element: passwordSecureField, text: newStrongPassword)
        
        let loginButton3 = app.buttons["LoginButton"]
        XCTAssertTrue(loginButton3.waitForExistence(timeout: TestConstants.shortTimeout))
        loginButton3.tap()
        
        dismissSavePassword(app: app)
        
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
        XCTAssertTrue(userSearchField.waitForExistence(timeout: TestConstants.shortTimeout))
        userSearchField.tap()
        typeText(element: userSearchField, text: otherTestUsername)
        
        let userLink = app.buttons[otherTestUsername]
        XCTAssertTrue(userLink.waitForExistence(timeout: TestConstants.shortTimeout))
        userLink.tap()
        
        assertOnProfileView(app: app)
        
        let followersLabel = app.staticTexts["FollowersCount"]
        let followButton = app.buttons["FollowButton"]
        
        // 1. Initial Check (Safe conversion from String to Int)
        // We use .label because that contains the actual text text displayed
        XCTAssertEqual(followersLabel.label, "0")
        
        // 2. Tap Follow
        XCTAssertTrue(followButton.waitForExistence(timeout: TestConstants.shortTimeout))
        followButton.tap()
        
        // 3. WAIT for the change (Async logic)
        // We create a predicate that checks if the label becomes "1"
        let existsPredicate = NSPredicate(format: "label == '1'")
        
        // Wait up to 5 seconds for the label to update
        expectation(for: existsPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
        
        // 4. Tap Unfollow
        XCTAssertTrue(followButton.waitForExistence(timeout: TestConstants.shortTimeout))
        followButton.tap()
        
        // 5. WAIT for it to go back to "0"
        let zeroPredicate = NSPredicate(format: "label == '0'")
        expectation(for: zeroPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
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
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // Make sure there is one post in For You and no posts in Following
        // 1. Find the Picker container
        let feedPicker = app.segmentedControls["FeedTypePicker"]
        XCTAssertTrue(feedPicker.waitForExistence(timeout: TestConstants.shortTimeout))

        // 2. Find the button INSIDE the picker
        let followingSegment = feedPicker.buttons["Following"]
        XCTAssertTrue(followingSegment.waitForExistence(timeout: TestConstants.shortTimeout))
        followingSegment.tap()
        
        let allPostsQuery = app.buttons.matching(identifier: "FollowingPostImage")
        expectation(for: NSPredicate(format: "count == 0"), evaluatedWith: allPostsQuery, handler: nil)
        waitForExpectations(timeout: TestConstants.shortTimeout, handler: nil)
        XCTAssertEqual(allPostsQuery.count, 0)
        
        let forYouPickerTab = feedPicker.buttons["For You"]
        XCTAssertTrue(forYouPickerTab.waitForExistence(timeout: TestConstants.shortTimeout))
        forYouPickerTab.tap()
        
        let allPostsQuery2 = app.buttons.matching(identifier: "ForYouPostImage")
        expectation(for: NSPredicate(format: "count == 1"), evaluatedWith: allPostsQuery2, handler: nil)
        waitForExpectations(timeout: TestConstants.shortTimeout, handler: nil)
        XCTAssertEqual(allPostsQuery2.count, 1)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostAuthorsQuery = app.buttons.matching(identifier: "PostAuthor")

        // Now, get the specific element at index 0 (the first one)
        let firstPostAuthorElement = allPostAuthorsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostAuthorElement.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPostAuthorElement.tap()

        assertOnProfileView(app: app)
        
        let followersLabel = app.staticTexts["FollowersCount"]
        let followButton = app.buttons["FollowButton"]
        
        // 1. Initial Check (Safe conversion from String to Int)
        // We use .label because that contains the actual text text displayed
        XCTAssertEqual(followersLabel.label, "0")
        
        // 2. Tap Follow
        XCTAssertTrue(followButton.waitForExistence(timeout: TestConstants.shortTimeout))
        followButton.tap()
        
        // 3. WAIT for the change (Async logic)
        // We create a predicate that checks if the label becomes "1"
        let existsPredicate = NSPredicate(format: "label == '1'")
        
        // Wait up to 5 seconds for the label to update
        expectation(for: existsPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
        
        // 4. Tap Unfollow
        XCTAssertTrue(followButton.waitForExistence(timeout: TestConstants.shortTimeout))
        followButton.tap()
        
        // 5. WAIT for it to go back to "0"
        let zeroPredicate = NSPredicate(format: "label == '0'")
        expectation(for: zeroPredicate, evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)
        
        /// We refollow so that we can check that the post now shows up in the "Following" Feed
        XCTAssertTrue(followButton.waitForExistence(timeout: TestConstants.shortTimeout))
        followButton.tap()
        
        // Go back to FeedView
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        // Make sure there is one post in For You and one post in Following
        // 1. Find the Picker container
        let feedPicker2 = app.segmentedControls["FeedTypePicker"]
        XCTAssertTrue(feedPicker2.waitForExistence(timeout: TestConstants.shortTimeout))

        // 2. Find the button INSIDE the picker
        let followingSegment2 = feedPicker2.buttons["Following"]
        XCTAssertTrue(followingSegment2.waitForExistence(timeout: TestConstants.shortTimeout))
        followingSegment2.tap()
        
        let allPostsQuery3 = app.buttons.matching(identifier: "FollowingPostImage")
        expectation(for: NSPredicate(format: "count == 1"), evaluatedWith: allPostsQuery3, handler: nil)
        waitForExpectations(timeout: TestConstants.shortTimeout, handler: nil)
        XCTAssertEqual(allPostsQuery3.count, 1)
        
        let forYouPickerTab2 = feedPicker2.buttons["For You"]
        XCTAssertTrue(forYouPickerTab2.waitForExistence(timeout: TestConstants.shortTimeout))
        forYouPickerTab2.tap()
        
        let allPostsQuery4 = app.buttons.matching(identifier: "ForYouPostImage")
        expectation(for: NSPredicate(format: "count == 1"), evaluatedWith: allPostsQuery4, handler: nil)
        waitForExpectations(timeout: TestConstants.shortTimeout, handler: nil)
        XCTAssertEqual(allPostsQuery4.count, 1)
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
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
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)

        let postImage = app.buttons["PostImage"]
        XCTAssertTrue(postImage.waitForExistence(timeout: TestConstants.shortTimeout))

        let postLikesText = app.staticTexts["PostLikesText"]

        // --- New method: tap the heart button ---
        let likePostButton = app.buttons["Like post"]
        XCTAssertTrue(likePostButton.waitForExistence(timeout: TestConstants.shortTimeout))
        likePostButton.tap()
        waitForLabel(postLikesText, toEqual: "1 likes")

        let unlikePostButton = app.buttons["Unlike post"]
        XCTAssertTrue(unlikePostButton.waitForExistence(timeout: TestConstants.shortTimeout))
        unlikePostButton.tap()
        waitForLabel(postLikesText, toEqual: "0 likes")

        // --- Old method: double-tap the post image ---
        XCTAssertTrue(postImage.waitForExistence(timeout: TestConstants.shortTimeout))
        postImage.doubleTap()
        waitForLabel(postLikesText, toEqual: "1 likes")

        XCTAssertTrue(postImage.waitForExistence(timeout: TestConstants.shortTimeout))
        postImage.doubleTap()
        waitForLabel(postLikesText, toEqual: "0 likes")

        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()

        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
            homeButton.tap()
        }

        assertOnHomeView(app: app)
    }
    
    /// A newly created post shows up in the Home grid in real time (without a
    /// manual refresh), and tapping it opens the post detail view.
    @MainActor
    func testOpenPostDetailFromHomeGrid() throws {

        try ifOnHomeDeleteAccount(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)

        try makePost(app: app, postText: "Home Grid Post")

        // Dismiss the success alert, which returns to the Home tab. The grid is
        // refreshed as part of creating the post, so it appears live.
        // SwiftUI exposes the alert button as a nested Button with the same
        // identifier, so scope to the alert and take firstMatch to avoid an
        // ambiguous "multiple matching elements" failure.
        let okButton = app.alerts.buttons["OkButtonSuccess"].firstMatch
        if okButton.waitForExistence(timeout: TestConstants.shortTimeout) {
            okButton.tap()
        }

        assertOnHomeView(app: app)

        let myPosts = app.buttons.matching(identifier: "MyPostImage")
        expectation(for: NSPredicate(format: "count >= 1"), evaluatedWith: myPosts, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)

        let firstPost = myPosts.element(boundBy: 0)
        XCTAssertTrue(firstPost.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPost.tap()

        assertOnPostDetailView(app: app)
    }

    /// Tapping a post in another user's Profile grid opens the post detail view.
    @MainActor
    func testOpenPostDetailFromProfileGrid() throws {

        try ifOnHomeDeleteAccount(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        try makePost(app: app, postText: "Profile Grid Post")
        try logoutUserFromHome(app: app)

        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)

        // Search for the author and open their profile.
        let userSearchField = app.searchFields["Search for Users"]
        XCTAssertTrue(userSearchField.waitForExistence(timeout: TestConstants.shortTimeout))
        userSearchField.tap()
        typeText(element: userSearchField, text: testUsername)

        let userLink = app.buttons[testUsername]
        XCTAssertTrue(userLink.waitForExistence(timeout: TestConstants.shortTimeout))
        userLink.tap()

        assertOnProfileView(app: app)

        let profilePosts = app.buttons.matching(identifier: "ProfilePostImage")
        expectation(for: NSPredicate(format: "count >= 1"), evaluatedWith: profilePosts, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)

        let firstPost = profilePosts.element(boundBy: 0)
        XCTAssertTrue(firstPost.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPost.tap()

        assertOnPostDetailView(app: app)
    }

    /// Tapping a post in the Following feed opens the post detail view.
    @MainActor
    func testOpenPostDetailFromFollowingFeed() throws {

        try ifOnHomeDeleteAccount(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        try makePost(app: app, postText: "Following Feed Post")
        try logoutUserFromHome(app: app)

        try loginUser(app: app, username: otherTestUsername, password: strongPassword, rememberMe: false)

        // Follow the author so their post shows up in the Following feed.
        let userSearchField = app.searchFields["Search for Users"]
        XCTAssertTrue(userSearchField.waitForExistence(timeout: TestConstants.shortTimeout))
        userSearchField.tap()
        typeText(element: userSearchField, text: testUsername)

        let userLink = app.buttons[testUsername]
        XCTAssertTrue(userLink.waitForExistence(timeout: TestConstants.shortTimeout))
        userLink.tap()

        assertOnProfileView(app: app)

        let followButton = app.buttons["FollowButton"]
        XCTAssertTrue(followButton.waitForExistence(timeout: TestConstants.shortTimeout))
        followButton.tap()

        let followersLabel = app.staticTexts["FollowersCount"]
        expectation(for: NSPredicate(format: "label == '1'"), evaluatedWith: followersLabel, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)

        // Go back to the feed and switch to the Following tab.
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()

        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()

        assertOnFeedView(app: app)

        let feedPicker = app.segmentedControls["FeedTypePicker"]
        XCTAssertTrue(feedPicker.waitForExistence(timeout: TestConstants.shortTimeout))
        let followingSegment = feedPicker.buttons["Following"]
        XCTAssertTrue(followingSegment.waitForExistence(timeout: TestConstants.shortTimeout))
        followingSegment.tap()

        let followingPosts = app.buttons.matching(identifier: "FollowingPostImage")
        expectation(for: NSPredicate(format: "count == 1"), evaluatedWith: followingPosts, handler: nil)
        waitForExpectations(timeout: TestConstants.timeout, handler: nil)

        let firstPost = followingPosts.element(boundBy: 0)
        XCTAssertTrue(firstPost.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPost.tap()

        assertOnPostDetailView(app: app)
    }

    @MainActor
    func testVerifyIdentity() throws {

        try ifOnHomeDeleteAccount(app: app)

        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)

        let settingsTab = app.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: TestConstants.shortTimeout))
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let verifyIdentityButton = app.buttons["VerifyIdentityButton"]
        XCTAssertTrue(verifyIdentityButton.waitForExistence(timeout: TestConstants.shortTimeout), "Verify Identity button should be present for new user")
        verifyIdentityButton.tap()
        
        let submitVerificationButton = app.buttons["SubmitVerificationButton"]
        XCTAssertTrue(submitVerificationButton.waitForExistence(timeout: TestConstants.shortTimeout))
        
        // We just tap verify to send the default date (today)
        submitVerificationButton.tap()
        
        // Wait for success alert
        let successAlert = app.alerts["Identity Verified"]
        XCTAssertTrue(successAlert.waitForExistence(timeout: TestConstants.shortTimeout))
        XCTAssertTrue(successAlert.buttons["OK"].waitForExistence(timeout: TestConstants.shortTimeout))
        successAlert.buttons["OK"].tap()
        
        // Verify Identity submit button should be gone. This is a proxy for the dialog being gone.
        XCTAssertFalse(submitVerificationButton.exists, "Verify Identity submit button should disappear after verification")
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
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
        XCTAssertTrue(firstBackButton.waitForExistence(timeout: TestConstants.shortTimeout))
        firstBackButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        makeCommentOnThread(app: app, commentText: "Comment On a Thread")
        
        let backButton2 = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton2.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton2 = app.buttons["Home"]
        XCTAssertTrue(homeButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        homeButton2.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        // --- Root comment ---
        let postCommentStackQuery = app.buttons.matching(identifier: "CommentStack")
        let postCommentStack = postCommentStackQuery.element(boundBy: 0)
        XCTAssertTrue(postCommentStack.waitForExistence(timeout: TestConstants.shortTimeout))

        let postCommentLikesTextQuery = app.staticTexts.matching(identifier: "CommentLikesCount")
        let postCommentLikesText = postCommentLikesTextQuery.element(boundBy: 0)

        // New method: tap the heart button
        let firstLikeCommentButton = app.buttons.matching(NSPredicate(format: "label == 'Like comment'")).element(boundBy: 0)
        XCTAssertTrue(firstLikeCommentButton.waitForExistence(timeout: TestConstants.shortTimeout))
        firstLikeCommentButton.tap()
        waitForLabel(postCommentLikesText, toEqual: "1 likes")

        let firstUnlikeCommentButton = app.buttons.matching(NSPredicate(format: "label == 'Unlike comment'")).element(boundBy: 0)
        XCTAssertTrue(firstUnlikeCommentButton.waitForExistence(timeout: TestConstants.shortTimeout))
        firstUnlikeCommentButton.tap()
        waitForLabel(postCommentLikesText, toEqual: "0 likes")

        // Old method: double-tap the comment row
        XCTAssertTrue(postCommentStack.waitForExistence(timeout: TestConstants.shortTimeout))
        postCommentStack.doubleTap()
        waitForLabel(postCommentLikesText, toEqual: "1 likes")

        XCTAssertTrue(postCommentStack.waitForExistence(timeout: TestConstants.shortTimeout))
        postCommentStack.doubleTap()
        waitForLabel(postCommentLikesText, toEqual: "0 likes")

        // --- Thread reply ---
        let postCommentStackQuery2 = app.buttons.matching(identifier: "CommentStack")
        let postCommentStack2 = postCommentStackQuery2.element(boundBy: 1)
        XCTAssertTrue(postCommentStack2.waitForExistence(timeout: TestConstants.shortTimeout))

        let postCommentLikesTextQuery2 = app.staticTexts.matching(identifier: "CommentLikesCount")
        let postCommentLikesText2 = postCommentLikesTextQuery2.element(boundBy: 1)

        // New method: tap the heart button on the reply
        // boundBy: 1 because root comment's heart is still at index 0 (not liked)
        let secondLikeCommentButton = app.buttons.matching(NSPredicate(format: "label == 'Like comment'")).element(boundBy: 1)
        XCTAssertTrue(secondLikeCommentButton.waitForExistence(timeout: TestConstants.shortTimeout))
        secondLikeCommentButton.tap()
        waitForLabel(postCommentLikesText2, toEqual: "1 likes")

        // After liking the reply, it becomes the only "Unlike comment" button
        let secondUnlikeCommentButton = app.buttons.matching(NSPredicate(format: "label == 'Unlike comment'")).element(boundBy: 0)
        XCTAssertTrue(secondUnlikeCommentButton.waitForExistence(timeout: TestConstants.shortTimeout))
        secondUnlikeCommentButton.tap()
        waitForLabel(postCommentLikesText2, toEqual: "0 likes")

        // Old method: double-tap the reply row
        XCTAssertTrue(postCommentStack2.waitForExistence(timeout: TestConstants.shortTimeout))
        postCommentStack2.doubleTap()
        waitForLabel(postCommentLikesText2, toEqual: "1 likes")

        XCTAssertTrue(postCommentStack2.waitForExistence(timeout: TestConstants.shortTimeout))
        postCommentStack2.doubleTap()
        waitForLabel(postCommentLikesText2, toEqual: "0 likes")
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()
        
        let homeButton3 = app.buttons["Home"]
        if homeButton3.exists {
            XCTAssertTrue(homeButton3.waitForExistence(timeout: TestConstants.shortTimeout))
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
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let postImage = app.buttons["PostImage"]
        // 2 second press
        XCTAssertTrue(postImage.waitForExistence(timeout: TestConstants.shortTimeout))
        postImage.press(forDuration: 2)
        
        let reasonTextField = app.textFields["ProvideAReasonTextField"]
        XCTAssertTrue(reasonTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        reasonTextField.tap()
        typeText(element: reasonTextField, text: "Report post")
        
        let reportButton = app.buttons["SubmitReportButton"]
        XCTAssertTrue(reportButton.waitForExistence(timeout: TestConstants.shortTimeout))
        reportButton.tap()
        
        let reportedCommentIcon = app.images["ReportedPostIcon"]
        XCTAssertTrue(reportedCommentIcon.waitForExistence(timeout: TestConstants.shortTimeout), "Reported post icon is missing")
        
        let backButton2 = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton2.tap()
        
        let homeButton2 = app.buttons["Home"]
        if homeButton2.exists {
            XCTAssertTrue(homeButton2.waitForExistence(timeout: TestConstants.shortTimeout))
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
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()
        
        assertOnFeedView(app: app)
        
        let homeButton = app.buttons["Home"]
        XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
        homeButton.tap()
        
        assertOnHomeView(app: app)
        
        makeCommentOnThread(app: app, commentText: "Comment On a Thread")
        
        let backButton2 = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton2.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        try loginUser(app: app, username: newTestUsername, password: strongPassword, rememberMe: false)
        
        let feedTab = app.buttons["Feed"]
        XCTAssertTrue(feedTab.waitForExistence(timeout: TestConstants.shortTimeout))
        feedTab.tap()
        
        assertOnFeedView(app: app)
        
        // First, get the query for all elements matching our identifier.
        // (NavigationLinks are 'buttons' in the accessibility tree)
        let allPostsQuery = app.buttons.matching(identifier: "ForYouPostImage")

        // Now, get the specific element at index 0 (the first one)
        let firstPostElement = allPostsQuery.element(boundBy: 0)

        XCTAssertTrue(firstPostElement.waitForExistence(timeout: TestConstants.shortTimeout))
        firstPostElement.tap()

        assertOnPostDetailView(app: app)
        
        let commentStackQuery = app.buttons.matching(identifier: "CommentStack")
        let commentStack = commentStackQuery.element(boundBy: 0)
        // 2 second press
        XCTAssertTrue(commentStack.waitForExistence(timeout: TestConstants.shortTimeout))
        commentStack.press(forDuration: 2)
        
        let reasonTextField = app.textFields["ProvideAReasonTextField"]
        XCTAssertTrue(reasonTextField.waitForExistence(timeout: TestConstants.shortTimeout))
        reasonTextField.tap()
        typeText(element: reasonTextField, text: "Report comment thread")
        
        let reportButton = app.buttons["SubmitReportButton"]
        XCTAssertTrue(reportButton.waitForExistence(timeout: TestConstants.shortTimeout))
        reportButton.tap()
        
        let reportedCommentIcon = app.images["ReportedCommentIcon"]
        XCTAssertTrue(reportedCommentIcon.waitForExistence(timeout: TestConstants.shortTimeout), "Reported comment icon is missing")
        
        
        let commentStackQuery2 = app.buttons.matching(identifier: "CommentStack")
        let commentStack2 = commentStackQuery2.element(boundBy: 1)
        // 2 second press
        XCTAssertTrue(commentStack2.waitForExistence(timeout: TestConstants.shortTimeout))
        commentStack2.press(forDuration: 2)
        
        let reasonTextField2 = app.textFields["ProvideAReasonTextField"]
        XCTAssertTrue(reasonTextField2.waitForExistence(timeout: TestConstants.shortTimeout))
        reasonTextField2.tap()
        typeText(element: reasonTextField2, text: "Report comment reply")
        
        let reportButton2 = app.buttons["SubmitReportButton"]
        XCTAssertTrue(reportButton2.waitForExistence(timeout: TestConstants.shortTimeout))
        reportButton2.tap()
        
        let reportedCommentIcon2 = app.images.matching(identifier: "ReportedCommentIcon")
        expectation(for: NSPredicate(format: "count == 2"), evaluatedWith: reportedCommentIcon2, handler: nil)
        waitForExpectations(timeout: TestConstants.shortTimeout, handler: nil)
        XCTAssertEqual(reportedCommentIcon2.count, 2, "Expected 2 reported comment icons but only found \(reportedCommentIcon2.count)")
        
        let backButton3 = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton3.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton3.tap()
        
        let homeButton2 = app.buttons["Home"]
        if homeButton2.exists {
            XCTAssertTrue(homeButton2.waitForExistence(timeout: TestConstants.shortTimeout))
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
        XCTAssertTrue(userSearchField.waitForExistence(timeout: TestConstants.shortTimeout))
        userSearchField.tap()
        typeText(element: userSearchField, text: otherTestUsername)
        
        let userLink = app.buttons[otherTestUsername]
        XCTAssertTrue(userLink.waitForExistence(timeout: TestConstants.shortTimeout))
        userLink.tap()
        
        assertOnProfileView(app: app)
        
        // Initially "Block" button should be visible
        let blockButton = app.buttons["Block"]
        XCTAssertTrue(blockButton.waitForExistence(timeout: TestConstants.shortTimeout))
        
        // Click Block
        blockButton.tap()
        
        // Verify changes to "Unblock"
        let unblockButton = app.buttons["Unblock"]
        XCTAssertTrue(unblockButton.waitForExistence(timeout: TestConstants.shortTimeout))
        
        // Click Unblock
        unblockButton.tap()
        
        // Verify changes back to "Block"
        XCTAssertTrue(blockButton.waitForExistence(timeout: TestConstants.shortTimeout))
        
        let backButton = app.navigationBars.firstMatch.buttons.element(boundBy: 0)
        XCTAssertTrue(backButton.waitForExistence(timeout: TestConstants.shortTimeout))
        backButton.tap()
        
        let homeButton = app.buttons["Home"]
        if homeButton.exists {
            XCTAssertTrue(homeButton.waitForExistence(timeout: TestConstants.shortTimeout))
            homeButton.tap()
        }
        
        assertOnHomeView(app: app)
    }
}

