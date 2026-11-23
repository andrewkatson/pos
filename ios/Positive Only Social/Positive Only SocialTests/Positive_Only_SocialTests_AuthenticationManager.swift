//
//  Positive_Only_SocialTests_.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/31/25.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_AuthenticationManager {

    var sut: AuthenticationManager!
        
    // --- Test Fixtures ---
    
    // Use the same constants as the SUT to interact with the same keychain items
    private let keychainService = GVOAppConstants.keychainService
    private let userSessionAccount = "userSessionToken"
    
    // A helper to access the keychain for setup/teardown
    private let keychain : KeychainHelperProtocol!

    // An isolated notification center so the `.accountBanned` post in
    // testAccountBannedNotification_LogsOut cannot reach managers created by
    // other tests running in parallel (which would call an extra logout()).
    private let notificationCenter = NotificationCenter()

    // --- Test setup ---
    init() {
        keychain = KeychainHelper()

        try? keychain.delete(service: keychainService, account: userSessionAccount)
    }
    
    // --- Test Cases ---

    @Test mutating func testInit_WhenKeychainIsEmpty_isLoggedInIsFalse() async throws {
        // Given: The keychain is empty (guaranteed by our init() setup)
        
        // When: The AuthenticationManager is initialized
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)
        
        // Then: The user should be logged out
        #expect(sut.isLoggedIn == false, "isLoggedIn should be false when no token exists")
        
        // Clean things up
        sut.logout()
        
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testInit_WhenKeychainHasToken_isLoggedInIsTrue() async throws {
        // Given: A valid token is saved in the keychain
        let testToken = "abc-123-valid-token"
        let testUsername = "username"
        let userSession = UserSession(sessionToken: testToken, username: testUsername, userId: "1", isIdentityVerified: false)
        try keychain.save(userSession, for: keychainService, account: userSessionAccount)
        
        // When: The AuthenticationManager is initialized
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)
        
        // Then: The user should be logged in
        #expect(sut.isLoggedIn == true, "isLoggedIn should be true when a token exists")
        // Clean things up
        sut.logout()
        
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testLogin_SetsIsLoggedInToTrue() async throws {
        // Given: The SUT is initialized in a logged-out state
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)
        #expect(sut.isLoggedIn == false) // Verify initial state

        // When: login() is called
        let token = "abc-123-valid-token"
        let testUsername = "username"
        let userSession = UserSession(sessionToken: token, username: testUsername, userId: "1", isIdentityVerified: false)
        sut.login(with: userSession)
        
        // And: We wait for the background Task in login() to complete.
        // A tiny sleep is needed to let the new Task execute and update the state.
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
        
        // Then: The published property is updated to true
        #expect(sut.isLoggedIn == true, "isLoggedIn should be true after calling login()")
        
        // Clean things up
        sut.logout()
        
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }
    
    @Test mutating func testLogout_SetsIsLoggedInToFalse_AndClearsKeychain() async throws {
        // Given: A token is saved and the SUT is in a logged-in state
        let token = "abc-123-valid-token"
        let testUsername = "username"
        let userSession = UserSession(sessionToken: token, username: testUsername, userId: "1", isIdentityVerified: false)
        try keychain.save(userSession, for: keychainService, account: userSessionAccount)
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)
        
        // Wait to login
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
        
        #expect(sut.isLoggedIn == true) // Verify initial logged-in state
        
        // When: logout() is called
        sut.logout()
        
        // And: We wait for the background Task in logout() to complete.
        // A tiny sleep is needed to let the new Task execute and update the state.
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
        
        // Then: The published property is updated to false
        #expect(sut.isLoggedIn == false, "isLoggedIn should be false after logout")
        
        // And: The token should be gone from the keychain
        let loadedToken: String? = try keychain.load(UserSession.self, from: keychainService, account: userSessionAccount)?.sessionToken
        #expect(loadedToken == nil, "Keychain token should be nil after logout")
        
        // Clean things up
        sut.logout()
        
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }


    @Test mutating func testAccountBannedNotification_LogsOut() async throws {
        // Given: A logged-in manager
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "banneduser", userId: "user-id", isIdentityVerified: false))
        #expect(sut.isLoggedIn == true)

        // When: The API layer reports the account is banned
        notificationCenter.post(name: .accountBanned, object: nil)
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))

        // Then: The session is dropped
        #expect(sut.isLoggedIn == false, "An account_banned rejection must log the user out")
        #expect(sut.session == nil)
        #expect(sut.logoutCallCount == 1)
    }

    @Test mutating func testEmailNotVerifiedNotification_LogsOut() async throws {
        // Given: A logged-in manager
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "unverifieduser", userId: "user-id", isIdentityVerified: false))
        #expect(sut.isLoggedIn == true)

        // When: The API layer reports the account's email is unverified
        notificationCenter.post(name: .emailNotVerified, object: nil)
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))

        // Then: The session is dropped — it can't do anything until verification
        #expect(sut.isLoggedIn == false, "An email_not_verified rejection must log the user out")
        #expect(sut.session == nil)
        #expect(sut.logoutCallCount == 1)
    }

    // MARK: - Privacy policy re-accept (issue #620)

    @Test mutating func testRestoredSession_NeedsPrivacyPolicyAcceptance() async throws {
        // Given: A session saved from a previous launch
        let userSession = UserSession(sessionToken: "restored-token", username: "username", userId: "1", isIdentityVerified: false)
        try keychain.save(userSession, for: keychainService, account: userSessionAccount)

        // When: The app opens and restores it
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)

        // Then: The user is asked to accept the privacy policy again
        #expect(sut.isLoggedIn == true)
        #expect(sut.needsPrivacyPolicyAcceptance == true, "Opening the app signed in must ask for the privacy policy again")

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testSignedOutLaunch_DoesNotNeedPrivacyPolicyAcceptance() async throws {
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)

        #expect(sut.isLoggedIn == false)
        #expect(sut.needsPrivacyPolicyAcceptance == false, "Nobody is signed in, so there is nobody to ask")
    }

    @Test mutating func testFreshLogin_NeedsPrivacyPolicyAcceptance() async throws {
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)

        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))

        #expect(sut.needsPrivacyPolicyAcceptance == true, "A fresh sign-in must ask for the privacy policy")

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testAcceptPrivacyPolicy_ClearsPrompt() async throws {
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))

        sut.acceptPrivacyPolicy()

        #expect(sut.needsPrivacyPolicyAcceptance == false)
        #expect(sut.isLoggedIn == true, "Accepting keeps the user signed in")

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testSessionRefresh_KeepsPrivacyPolicyAcceptance() async throws {
        // Given: A signed-in user who already accepted
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))
        sut.acceptPrivacyPolicy()

        // When: Their session is updated in place (identity verification)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: true),
                  keepPrivacyPolicyAcceptance: true)

        // Then: They aren't asked again mid-session
        #expect(sut.needsPrivacyPolicyAcceptance == false)

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testLoginWhileStillLoggedIn_AsksAgain() async throws {
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))
        sut.acceptPrivacyPolicy()

        // A login that isn't an in-place update asks, whatever isLoggedIn says
        sut.login(with: UserSession(sessionToken: "token-2", username: "username", userId: "1", isIdentityVerified: false))

        #expect(sut.needsPrivacyPolicyAcceptance == true)

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testLogout_ClearsPromptImmediately_AndNextLoginAsksAgain() async throws {
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))
        #expect(sut.needsPrivacyPolicyAcceptance == true)

        // When: The user declines by logging out
        sut.logout()

        // Then: The prompt is gone straight away, before the session is cleared,
        // so the alert can't re-present itself
        #expect(sut.needsPrivacyPolicyAcceptance == false)
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
        #expect(sut.isLoggedIn == false)

        // And: Signing in again asks again
        sut.login(with: UserSession(sessionToken: "token-2", username: "username", userId: "1", isIdentityVerified: false))
        #expect(sut.needsPrivacyPolicyAcceptance == true)

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }
}
