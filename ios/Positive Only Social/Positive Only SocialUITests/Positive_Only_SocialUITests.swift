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
    let strongPassword: String = "StrongPassword123!"
    let newStrongPassword: String = "NewStrongPassword456!"

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
        testUsername = "\(self.name)_user"
        otherTestUsername = "\(self.name)_other_user"
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
        XCTAssertTrue(app.textViews["RegisterText"].exists, "Register button is not empty")
        XCTAssertTrue(app.textViews["LoginText"].exists, "Login button is not empty")
    }
    
    private func assertOnRegisterView(app: XCUIApplication) {
        XCTAssertTrue(app.textFields["UsernameTextField"].exists, "Username field not present")
        XCTAssertTrue(app.textFields["EmailTextField"].exists, "Email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].exists, "Password field not present")
        XCTAssertTrue(app.secureTextFields["ConfirmPasswordSecureField"].exists, "Confirm Password field not present")
        XCTAssertTrue(app.buttons["RegisterButton"].exists, "Register button not present")
    }
    
    private func assertOnLoginView(app: XCUIApplication) {
        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].exists, "Username or email field not present")
        XCTAssertTrue(app.secureTextFields["PasswordSecureField"].exists, "Password field not present")
        XCTAssertTrue(app.buttons["LoginButton"].exists, "Login button not present")
        XCTAssertTrue(app.switches["RememberMeToggle"].exists, "Remember me toggle not present")
        XCTAssertTrue(app.buttons["ForgotPasswordButton"].exists, "Forgot password button not present")
    }
    
    private func assertOnHomeView(app: XCUIApplication) {
        XCTAssertTrue(app.tabs["HomeTab"].exists, "Home tab not present")
        XCTAssertTrue(app.tabs["FeedTab"].exists, "Feed tab not present")
        XCTAssertTrue(app.tabs["NewPostTab"].exists, "New post tab not present")
        XCTAssertTrue(app.tabs["SettingsTab"].exists, "Settings tab not present")
    }
    
    private func assertOnSettingsView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["LogoutButton"].exists, "Logout button not present")
        XCTAssertTrue(app.buttons["DeleteAccountButton"].exists, "Delete Account button not present")
        XCTAssertTrue(app.buttons["CancelLogoutButton"].exists, "Cancel logout button not present")
        XCTAssertTrue(app.buttons["ConfirmLogoutButton"].exists, "Confirm logout button not present")
        XCTAssertTrue(app.buttons["CancelDeleteAccountButton"].exists, "Cancel delete account button not present")
        XCTAssertTrue(app.buttons["ConfirmDeleteAccountButton"].exists, "Confirm delete account button not present")
    }
    
    private func assertOnProfileView(app: XCUIApplication) {
        XCTAssertTrue(app.buttons["FollowButton"].exists, "Follow button not present")
        XCTAssertTrue(app.otherElements["Following"].exists, "Following stat item not present")
        XCTAssertTrue(app.otherElements["Followers"].exists, "Followers stat item not present")
        XCTAssertTrue(app.otherElements["Posts"].exists, "Posts stat item not present")
    }
    
    private func assertOnNewPostView(app: XCUIApplication) {
        XCTAssertTrue(app.otherElements["SelectAPhotoPicker"].exists, "Select a photo picker not present")
        XCTAssertTrue(app.otherElements["CaptionTextEditor"].exists, "Caption text editor not present")
        XCTAssertTrue(app.buttons["SharePostButton"].exists, "Share post button is not empty")
        XCTAssertTrue(app.buttons["OkButtonSuccess"].exists, "Ok button not present")
        XCTAssertTrue(app.buttons["OkButtonFailure"].exists, "Ok button not present")
    }
    
    private func registerUser(app: XCUIApplication, username: String, password: String) throws {
        let registerButton = app.textViews["RegisterText"]
        registerButton.tap()
        
        assertOnRegisterView(app: app)
        
        let usernameField = app.textFields["UsernameTextField"]
        usernameField.typeText(username)
        
        let emailField = app.textFields["EmailTextField"]
        emailField.typeText("\(username)@test.com")
        
        let passwordField = app.secureTextFields["PasswordSecureField"]
        passwordField.typeText(password)
        
        let confirmPasswordField = app.secureTextFields["ConfirmPasswordSecureField"]
        confirmPasswordField.typeText(password)
        
        let otherRegisterButton = app.buttons["RegisterButton"]
        otherRegisterButton.tap()
        
        assertOnHomeView(app: app)
    }
    
    private func loginUser(app: XCUIApplication, username: String, password: String, rememberMe: Bool) throws {
        try registerUser(app: app, username: username, password: password)
        
        try logoutUserFromHome(app: app)
        
        let loginButton = app.textViews["LoginText"]
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField.typeText(username)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        passwordSecureField.typeText(password)
        
        let rememberMeSwitch = app.switches["RememberMeToggle"]
        rememberMeSwitch.tap()
        
        let loginButton2 = app.buttons["LoginButton"]
        loginButton2.tap()
        
        assertOnHomeView(app: app)
    }
    
    private func logoutUserFromHome(app: XCUIApplication) throws {
        let settingsTab = app.tabs["SettingsTab"]
        settingsTab.tap()
        
        assertOnSettingsView(app: app)
        
        let logoutButton = app.buttons["LogoutButton"]
        logoutButton.tap()
        
        let confirmLogoutButton = app.buttons["ConfirmLogoutButton"]
        confirmLogoutButton.tap()
        
        assertOnWelcomeView(app: app)
    }
    
    /// Assumes the user is logged in and we are on HomeView.
    private func makePost(app: XCUIApplication, postText: String) throws {
        assertOnHomeView(app: app)
        
        let newPostTab = app.tabs["NewPostTab"]
        newPostTab.tap()
        
        assertOnNewPostView(app: app)
        
        let captionTextEditor = app.textViews["CaptionTextEditor"]
        captionTextEditor.typeText(postText)
        
        // Find the photo picker's main view (identifier may vary)
        let picker = app.otherElements["SelectAPhotoPicker"]
        picker.tap()
        
        // Deal with the prompts from the photos picker
        addUIInterruptionMonitor(withDescription: "System Alert") { (alert) -> Bool in
            if alert.buttons["Allow Full Access"].exists {
                alert.buttons["Allow Full Access"].tap()
                return true
            }
            if alert.buttons["Select Photos..."].exists {
                alert.buttons["Select Photos..."].tap()
                return true
            }
            return false
        }
        XCUIApplication().tap() // Dismiss the alert by tapping outside of it (or other interaction)

        // Find the desired photo within the picker using an accessibility label predicate
        // Photos in the simulator usually have labels starting with "Photo" followed by date/time info
        let targetPhoto = picker.images.element(matching: NSPredicate(format: "label CONTAINS[c] 'Photo'")).firstMatch

        XCTAssertTrue(targetPhoto.waitForExistence(timeout: 5), "The test photo should be visible")
        targetPhoto.tap()
        
        let sharePostButton = app.buttons["SharePostButton"]
        sharePostButton.tap()
        
        assertOnHomeView(app: app)
    }
    
    /// Makes a comment on the first post found in the For You Feed. Assumes the user is logged in and we are on HomeView.
    private func makeCommentOnPost(app: XCUIApplication, commentText: String) {
        assertOnHomeView(app: app)
        
    }
    
    // MARK: Tests
    @MainActor
    func testAutomaticLoginAfterRememberMe() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: true)
        
        try logoutUserFromHome(app: app)
        
        app.terminate()
        
        app.launch()
        
        // If we end the app and relaunch after remember me we should automatically be on the HomeView
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testDeleteAccount() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: true)

        let settingsTab = app.tabs["SettingsTab"]
        settingsTab.tap()
        
        let deleteAccountButton = app.buttons["DeleteAccountButton"]
        deleteAccountButton.tap()
        
        let confirmDeleteAccountButton = app.buttons["ConfirmDeleteAccountButton"]
        confirmDeleteAccountButton.tap()
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.textViews["LoginText"]
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField.typeText(testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        passwordSecureField.typeText(strongPassword)
        
        let loginButton2 = app.buttons["LoginButton"]
        loginButton2.tap()
        
        XCTAssertTrue(app.buttons["LoginFailedOkButton"].exists, "Login should have failed")
    }
    
    @MainActor
    func testResetPassword() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        try registerUser(app: app, username: testUsername, password: strongPassword)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton = app.textViews["LoginText"]
        loginButton.tap()
        
        assertOnLoginView(app: app)
        
        let forgotPasswordButton = app.buttons["ForgotPasswordButton"]
        forgotPasswordButton.tap()
        
        // Assert we are on request reset view
        XCTAssertTrue(app.buttons["RequestResetButton"].exists, "Request reset button should exist")
        XCTAssertTrue(app.textFields["UsernameOrEmailTextField"].exists, "Username or email text field should exist")
        
        let usernameOrEmailTextField = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField.typeText(testUsername)
        
        let requestResetButton = app.buttons["RequestResetButton"]
        requestResetButton.tap()
        
        // Assert we are on the verify reset view
        XCTAssertTrue(app.buttons["VerifyButton"].exists, "Verify button should exist")
        XCTAssertTrue(app.textFields["6DigitPinTextField"].exists, "6 Digit pin field should exist")
        
        let sixDigitPinTextField = app.textFields["6DigitPinTextField"]
        // We hardcode the test value in StatefulStubbedAPI
        sixDigitPinTextField.typeText("100000")
        
        let verifyButton = app.buttons["VerifyButton"]
        verifyButton.tap()
        
        // Assert we are on the reset password view
        XCTAssertTrue(app.buttons["ResetPasswordAndLoginButton"].exists, "Reset password and login button should exist")
        XCTAssertTrue(app.textFields["UsernameTextField"].exists, "Username text field should exist")
        XCTAssertTrue(app.textFields["EmailTextField"].exists, "Email text field should exist")
        XCTAssertTrue(app.secureTextFields["PasswordTextField"].exists, "Password text field should be empty")
        
        let emailTextField = app.textFields["EmailTextField"]
        emailTextField.typeText("\(testUsername)@test.com")
        
        let passwordTextField = app.secureTextFields["PasswordTextField"]
        passwordTextField.typeText(newStrongPassword)
        
        let resetPasswordAndLoginButton = app.buttons["ResetPasswordAndLoginButton"]
        resetPasswordAndLoginButton.tap()
        
        assertOnHomeView(app: app)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        let loginButton2 = app.textViews["LoginText"]
        loginButton2.tap()
        
        assertOnLoginView(app: app)
        
        let usernameOrEmailTextField2 = app.textFields["UsernameOrEmailTextField"]
        usernameOrEmailTextField2.typeText(testUsername)
        
        let passwordSecureField = app.secureTextFields["PasswordSecureField"]
        passwordSecureField.typeText(newStrongPassword)
        
        let loginButton3 = app.buttons["LoginButton"]
        loginButton3.tap()
        
        assertOnHomeView(app: app)
    }
    
    @MainActor
    func testFollowAndUnfollowFromSearch() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()
        
        try registerUser(app: app, username: otherTestUsername, password: strongPassword)
        
        try logoutUserFromHome(app: app)
        
        assertOnWelcomeView(app: app)
        
        try loginUser(app: app, username: testUsername, password: strongPassword, rememberMe: false)
        
        let userSearchField = app.searchFields["Search for Users"]
        userSearchField.tap()
        userSearchField.typeText(otherTestUsername)
        
        let userLink = app.links[otherTestUsername]
        userLink.tap()
        
        assertOnProfileView(app: app)
        
        let followers = app.textViews["FollowersCount"]
        XCTAssertEqual(followers.value as! Int, 0)
        
        let followButton = app.buttons["FollowButton"]
        followButton.tap()
        
        XCTAssertEqual(followers.value as! Int, 1)
        
        followButton.tap()
        
        XCTAssertEqual(followers.value as! Int, 0)
    }
    
    @MainActor
    func testFollowAndUnfollowFromPost() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }
    
    @MainActor
    func testLikeAndUnlikePost() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }
    
    @MainActor
    func testLikeAndUnlikeComment() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }
    
    @MainActor
    func testReportPost() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }
    
    @MainActor
    func testReportComment() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
