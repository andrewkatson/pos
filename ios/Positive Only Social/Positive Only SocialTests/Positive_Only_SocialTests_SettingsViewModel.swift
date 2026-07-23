//
//  Positive_Only_SocialTests_SettingsViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/31/25.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_SettingsViewModel {

    // --- SUT & Stubs ---
    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!

    // An isolated notification center so a parallel test posting `.accountBanned`
    // to the shared `.default` center cannot trigger an extra logout() on the
    // AuthenticationManager instances created here.
    private let notificationCenter = NotificationCenter()

    /// Builds an AuthenticationManager isolated from the shared notification center.
    private func makeAuthManager() -> AuthenticationManager {
        AuthenticationManager(shouldAutoLogin: false,
                              keychainHelper: keychainHelper,
                              notificationCenter: notificationCenter)
    }
    
    // --- Keychain Test Fixtures ---
    
    // --- Test Setup ---
    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---
    
    /// Helper to pause the test and let async tasks complete.
    private func yield(for duration: Duration = .seconds(TestConstants.shortTimeout)) async {
        try? await Task.sleep(for: duration)
    }
    
    /// Helper to register a user and return their token.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }
    
    /// Helper to log in a user and save their token to the keychain
    private func setupLoggedInUser(username: String) async throws -> String {
        let token = try await registerUserAndGetToken(username: username)
        let userSession = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        // Use the testAccount that the ViewModel will also use
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: "\(username)_account")
        return token
    }
    
    // --- Logout Tests ---

    @Test func testLogout_Success_CallsAPIAndAuthManager() async throws {
        // Given: A logged-in user
        let token = try await setupLoggedInUser(username: "logoutUser")
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "logoutUser_account")
        let authenticationManager = makeAuthManager()
        
        // When: Logout is called
        sut.logout(authManager: authenticationManager)
        await yield()

        // Then: The auth manager's logout is called
        #expect(authenticationManager.logoutCallCount == 1)
        
        // And: The API was called to invalidate the session
        // We test this by trying to find the session in the stubAPI
        let session = stubAPI.findSession(byToken: token)
        #expect(session == nil, "Session should be deleted from the backend")
    }
    
    @Test func testLogout_NoSessionInKeychain_OnlyCallsAuthManager() async throws {
        // Given: No user is logged in (keychain is empty)
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "logoutNoSession_account")
        let authenticationManager = makeAuthManager()
        
        // When: Logout is called
        sut.logout(authManager: authenticationManager)
        await yield()

        // Then: The auth manager's logout is still called (to clear local state)
        #expect(authenticationManager.logoutCallCount == 1)
        
        // And: The API was never called (because no token was found)
        // This is an indirect check; we know no user was logged in, so if api.logout
        // were called, it would have thrown an error, which this test doesn't expect.
        // The main check is that mockAuthManager.logoutCallCount is 1.
    }
    
    // --- Delete Account Tests ---
    
    @Test func testDeleteAccount_Success_CallsAPIAndAuthManager() async throws {
        // Given: A logged-in user
        let token = try await setupLoggedInUser(username: "deleteUser")
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "deleteUser_account")
        let authenticationManager = makeAuthManager()
        
        // When: Delete account is called
        sut.deleteAccount(authManager: authenticationManager)
        await yield()

        // Then: The auth manager's logout is called
        #expect(authenticationManager.logoutCallCount == 1)
        #expect(sut.showingErrorAlert == false)
        
        // And: The user and their session were deleted from the API
        let session = stubAPI.findSession(byToken: token)
        let user = stubAPI.findUser(byUsername: "deleteUser")
        #expect(session == nil, "Session should be deleted from the backend")
        #expect(user == nil, "User should be deleted from the backend")
    }
    
    @Test func testDeleteAccount_NoSessionInKeychain_ShowsError() async throws {
        // Given: No user is logged in (keychain is empty)
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "deleteAccountNoSession_account")
        let authenticationManager = makeAuthManager()
        
        // When: Delete account is called
        sut.deleteAccount(authManager: authenticationManager)
        await yield()
        
        // Then: The auth manager is NOT called
        #expect(authenticationManager.logoutCallCount == 0)
        
        // And: An error is shown
        #expect(sut.showingErrorAlert == true)
        #expect(sut.errorMessage == "Session not found. Cannot delete account.")
    }
    
    // --- Verify Identity Tests ---
    
    @Test func testVerifyIdentity_Success_CallsAPIAndAuthManager() async throws {
        // Given: A logged-in user
        let token = try await setupLoggedInUser(username: "verifyUser")
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "verifyUser_account")
        let authenticationManager = makeAuthManager()
        let dateOfBirth = Date.now
        
        // When: Verify Identity is called
        sut.verifyIdentity(authManager: authenticationManager, dateOfBirth: dateOfBirth)
        await yield()
        
        // Then: The auth manager is updated (indicating local session update)
        // Since stubAPI.verifyIdentity updates the user in the stub, we mainly check if the view model state updated
        // and if the auth manager got a new session with isIdentityVerified = true.
        // However, AuthenticationManager is a class we can't easily peek into unless we mock it or check its published property.
        // But we can check the View Model's state.
        
        #expect(sut.showingVerificationAlert == true)
        #expect(sut.verificationMessage == "Identity verified successfully!")

        // And: Check the backend state
        let user = stubAPI.findUser(byUsername: "verifyUser")
        #expect(user?.identityIsVerified == true, "User should be verified in the backend")
    }

    // --- Two-Factor Authentication Tests (issue #348) ---

    /// Helper to run setup + confirm through the view model, returning the SUT.
    private func enrollInTwoFactor(username: String) async throws -> SettingsViewModel {
        _ = try await setupLoggedInUser(username: username)
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "\(username)_account")

        sut.startTotpSetup()
        await yield()
        sut.confirmTotp(password: "123", code: StatefulStubbedAPI.stubTotpCode)
        await yield()
        return sut
    }

    @Test func testStartTotpSetup_PopulatesSecretAndUri() async throws {
        _ = try await setupLoggedInUser(username: "totpSetupUser")
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "totpSetupUser_account")

        sut.startTotpSetup()
        await yield()

        #expect(sut.totpSetup != nil)
        #expect(sut.totpSetup?.otpauthUri.hasPrefix("otpauth://totp/") == true)
        #expect(sut.showingErrorAlert == false)
    }

    @Test func testConfirmTotp_EnablesAndReturnsRecoveryCodes() async throws {
        let sut = try await enrollInTwoFactor(username: "totpConfirmUser")

        #expect(sut.recoveryCodes?.count == 10)
        #expect(stubAPI.findUser(byUsername: "totpConfirmUser")?.totpEnabled == true)

        // Finishing clears the sheet state and raises the status alert.
        sut.finishTotpEnrollment()
        #expect(sut.totpSetup == nil)
        #expect(sut.recoveryCodes == nil)
        #expect(sut.showingTwoFactorStatusAlert == true)
    }

    @Test func testConfirmTotp_WrongCode_ShowsErrorAndStaysDisabled() async throws {
        _ = try await setupLoggedInUser(username: "totpWrongCodeUser")
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "totpWrongCodeUser_account")

        sut.startTotpSetup()
        await yield()
        sut.confirmTotp(password: "123", code: "000000")
        await yield()

        // Enrollment-sheet errors surface inline via twoFactorErrorMessage, not
        // the List's showingErrorAlert (two alerts on one flag are undefined).
        #expect(sut.twoFactorErrorMessage != nil)
        #expect(sut.recoveryCodes == nil)
        #expect(stubAPI.findUser(byUsername: "totpWrongCodeUser")?.totpEnabled == false)
    }

    @Test func testConfirmTotp_WrongPassword_DoesNotEnrol() async throws {
        // A stolen session must not be enough to bind an authenticator: that
        // would hand the thief the recovery codes and lock the owner out, since
        // disabling then needs a code only the thief has.
        _ = try await setupLoggedInUser(username: "totpWrongPasswordUser")
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "totpWrongPasswordUser_account")

        sut.startTotpSetup()
        await yield()
        sut.confirmTotp(password: "wrong", code: StatefulStubbedAPI.stubTotpCode)
        await yield()

        #expect(sut.twoFactorErrorMessage != nil)
        #expect(sut.recoveryCodes == nil)
        #expect(stubAPI.findUser(byUsername: "totpWrongPasswordUser")?.totpEnabled == false)

        // The correct password still completes the same enrolment.
        sut.confirmTotp(password: "123", code: StatefulStubbedAPI.stubTotpCode)
        await yield()
        #expect(sut.recoveryCodes?.count == 10)
        #expect(stubAPI.findUser(byUsername: "totpWrongPasswordUser")?.totpEnabled == true)
    }

    @Test func testDisableTotp_Success_TurnsTwoFactorOff() async throws {
        let sut = try await enrollInTwoFactor(username: "totpDisableUser")
        sut.finishTotpEnrollment()
        sut.showingTwoFactorStatusAlert = false

        // Password matches the one registerUserAndGetToken uses.
        sut.disableTotp(password: "123", code: StatefulStubbedAPI.stubTotpCode, isRecoveryCode: false)
        await yield()

        #expect(sut.showingTwoFactorStatusAlert == true)
        #expect(sut.twoFactorStatusMessage == "Two-factor authentication has been disabled.")
        #expect(stubAPI.findUser(byUsername: "totpDisableUser")?.totpEnabled == false)
    }

    @Test func testDisableTotp_WrongPassword_ShowsError() async throws {
        let sut = try await enrollInTwoFactor(username: "totpDisableWrongPwUser")

        sut.disableTotp(password: "wrong", code: StatefulStubbedAPI.stubTotpCode, isRecoveryCode: false)
        await yield()

        #expect(sut.showingErrorAlert == true)
        #expect(stubAPI.findUser(byUsername: "totpDisableWrongPwUser")?.totpEnabled == true)
    }

    @Test func testDisableTotp_RecoveryCode_IsAcceptedAndConsumed() async throws {
        let sut = try await enrollInTwoFactor(username: "totpDisableRecoveryUser")
        let recoveryCode = try #require(sut.recoveryCodes?.first)

        sut.disableTotp(password: "123", code: recoveryCode, isRecoveryCode: true)
        await yield()

        #expect(sut.showingTwoFactorStatusAlert == true)
        #expect(stubAPI.findUser(byUsername: "totpDisableRecoveryUser")?.totpEnabled == false)
    }

    // --- Two-Factor Login Flow (stub API level) ---

    @Test func testLogin_WithTwoFactorEnabled_ReturnsChallengeThenSession() async throws {
        _ = try await enrollInTwoFactor(username: "totpLoginUser")

        // Login answers with a challenge, not a session.
        let loginData = try await stubAPI.loginUser(usernameOrEmail: "totpLoginUser", password: "123", rememberMe: "false", ip: "127.0.0.1")
        let challenge = try JSONDecoder().decode(TwoFactorRequiredFields.self, from: loginData)
        #expect(challenge.twoFactorRequired == true)

        // The code exchanges the challenge for a normal session.
        let sessionData = try await stubAPI.loginUser2FA(challengeToken: challenge.challengeToken, totpCode: StatefulStubbedAPI.stubTotpCode, recoveryCode: nil, ip: "127.0.0.1")
        let session = try JSONDecoder().decode(LoginResponseFields.self, from: sessionData)
        #expect(stubAPI.findSession(byToken: session.sessionManagementToken) != nil)

        // The challenge is single-use.
        await #expect(throws: APIError.self) {
            _ = try await self.stubAPI.loginUser2FA(challengeToken: challenge.challengeToken, totpCode: StatefulStubbedAPI.stubTotpCode, recoveryCode: nil, ip: "127.0.0.1")
        }
    }

    @Test func testLogin2FA_RecoveryCodeIsSingleUse() async throws {
        let sut = try await enrollInTwoFactor(username: "totpRecoveryLoginUser")
        let recoveryCode = try #require(sut.recoveryCodes?.first)

        let firstLogin = try await stubAPI.loginUser(usernameOrEmail: "totpRecoveryLoginUser", password: "123", rememberMe: "false", ip: "127.0.0.1")
        let firstChallenge = try JSONDecoder().decode(TwoFactorRequiredFields.self, from: firstLogin)
        _ = try await stubAPI.loginUser2FA(challengeToken: firstChallenge.challengeToken, totpCode: nil, recoveryCode: recoveryCode, ip: "127.0.0.1")

        // A spent code is refused on the next login.
        let secondLogin = try await stubAPI.loginUser(usernameOrEmail: "totpRecoveryLoginUser", password: "123", rememberMe: "false", ip: "127.0.0.1")
        let secondChallenge = try JSONDecoder().decode(TwoFactorRequiredFields.self, from: secondLogin)
        await #expect(throws: APIError.self) {
            _ = try await self.stubAPI.loginUser2FA(challengeToken: secondChallenge.challengeToken, totpCode: nil, recoveryCode: recoveryCode, ip: "127.0.0.1")
        }
    }
}

