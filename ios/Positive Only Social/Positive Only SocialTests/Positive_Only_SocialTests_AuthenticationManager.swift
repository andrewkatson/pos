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

    /// A stub backend with no simulated latency, and a signed-up account on it.
    private func makeStubWithAccount(_ username: String) async throws -> (StatefulStubbedAPI, String) {
        let api = StatefulStubbedAPI()
        api.simulatedLatency = 0
        let data = try await api.register(username: username, email: "\(username)@test.com", password: "123",
                                          rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        return (api, try JSONDecoder().decode(RegFields.self, from: data).session_management_token)
    }

    /// A manager signed in with `token`, isolated from the shared keychain.
    private func makeSignedInManager(token: String) -> AuthenticationManager {
        let manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: MockKeychainHelper(),
                                            notificationCenter: notificationCenter)
        manager.login(with: UserSession(sessionToken: token, username: "username", userId: "1", isIdentityVerified: false))
        return manager
    }

    @Test mutating func testRestoredSession_StartsPrivacyPolicyCheck() async throws {
        // Given: A session saved from a previous launch
        let userSession = UserSession(sessionToken: "restored-token", username: "username", userId: "1", isIdentityVerified: false)
        try keychain.save(userSession, for: keychainService, account: userSessionAccount)

        // When: The app opens and restores it
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)

        // Then: Opening the app checks the privacy policy acceptance again,
        // without showing the alert before the backend has answered
        #expect(sut.isLoggedIn == true)
        #expect(sut.isCheckingPrivacyPolicyAcceptance == true, "Opening the app signed in must check the privacy policy again")
        #expect(sut.needsPrivacyPolicyAcceptance == false)

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testSignedOutLaunch_DoesNotNeedPrivacyPolicyAcceptance() async throws {
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain, notificationCenter: notificationCenter)

        #expect(sut.isLoggedIn == false)
        #expect(sut.isCheckingPrivacyPolicyAcceptance == false, "Nobody is signed in, so there is nothing to check")
        #expect(sut.needsPrivacyPolicyAcceptance == false, "Nobody is signed in, so there is nobody to ask")
    }

    @Test func testFreshLogin_StartsPrivacyPolicyCheck() async throws {
        let manager = makeSignedInManager(token: "token")

        #expect(manager.isCheckingPrivacyPolicyAcceptance == true, "A fresh sign-in must check the privacy policy")
        #expect(manager.needsPrivacyPolicyAcceptance == false)
    }

    @Test func testCheck_NothingOnRecord_Asks() async throws {
        // An existing member who never accepted anything has a null version.
        let (api, token) = try await makeStubWithAccount("nothingOnRecord")
        let manager = makeSignedInManager(token: token)

        await manager.checkPrivacyPolicyAcceptance(api: api)

        #expect(manager.isCheckingPrivacyPolicyAcceptance == false)
        #expect(manager.needsPrivacyPolicyAcceptance == true)
    }

    @Test func testCheck_CurrentVersionOnRecord_DoesNotAsk() async throws {
        let (api, token) = try await makeStubWithAccount("currentOnRecord")
        _ = try await api.acceptPolicies(sessionManagementToken: token, policyVersion: GVOAppConstants.policyVersion)
        let manager = makeSignedInManager(token: token)

        await manager.checkPrivacyPolicyAcceptance(api: api)

        #expect(manager.isCheckingPrivacyPolicyAcceptance == false)
        #expect(manager.needsPrivacyPolicyAcceptance == false, "Already accepted this version, so don't ask again")
    }

    @Test func testCheck_NewerVersionOnRecord_DoesNotAsk() async throws {
        let (api, token) = try await makeStubWithAccount("newerOnRecord")
        _ = try await api.acceptPolicies(sessionManagementToken: token, policyVersion: "9999-12-31")
        let manager = makeSignedInManager(token: token)

        await manager.checkPrivacyPolicyAcceptance(api: api)

        #expect(manager.needsPrivacyPolicyAcceptance == false)
    }

    @Test func testCheck_OlderVersionOnRecord_Asks() async throws {
        let (api, token) = try await makeStubWithAccount("olderOnRecord")
        _ = try await api.acceptPolicies(sessionManagementToken: token, policyVersion: "2000-01-01")
        let manager = makeSignedInManager(token: token)

        await manager.checkPrivacyPolicyAcceptance(api: api)

        #expect(manager.needsPrivacyPolicyAcceptance == true)
    }

    @Test func testCheck_RequestFails_Asks() async throws {
        // A session the backend doesn't know: GET /me/ fails, so ask.
        let api = StatefulStubbedAPI()
        api.simulatedLatency = 0
        let manager = makeSignedInManager(token: "unknown-token")

        await manager.checkPrivacyPolicyAcceptance(api: api)

        #expect(manager.isCheckingPrivacyPolicyAcceptance == false)
        #expect(manager.needsPrivacyPolicyAcceptance == true)
    }

    @Test func testCheck_SupersededByLogout_DoesNotAsk() async throws {
        let (api, token) = try await makeStubWithAccount("supersededCheck")
        api.simulatedLatency = 0.2
        let manager = makeSignedInManager(token: token)

        // The check is waiting on the backend when the user logs out.
        let check = Task { await manager.checkPrivacyPolicyAcceptance(api: api) }
        try await Task.sleep(for: .milliseconds(50))
        manager.logout()
        await check.value

        #expect(manager.needsPrivacyPolicyAcceptance == false, "A check from the previous session must not raise the alert")
        #expect(manager.isCheckingPrivacyPolicyAcceptance == false)
    }

    @Test func testCheck_WithNothingPending_DoesNotCallBackend() async throws {
        let (api, token) = try await makeStubWithAccount("nothingPending")
        let manager = makeSignedInManager(token: token)
        manager.acceptPrivacyPolicy()

        await manager.checkPrivacyPolicyAcceptance(api: api)

        #expect(manager.needsPrivacyPolicyAcceptance == false)
    }

    @Test func testAcceptPrivacyPolicy_ClearsPromptAndRecordsBundledVersion() async throws {
        let (api, token) = try await makeStubWithAccount("acceptRecords")
        let manager = makeSignedInManager(token: token)
        await manager.checkPrivacyPolicyAcceptance(api: api)
        #expect(manager.needsPrivacyPolicyAcceptance == true)

        // When: The user taps Accept
        let recording = manager.acceptPrivacyPolicy(recordingWith: api)

        // Then: The alert closes at once, and the backend records the version
        #expect(manager.needsPrivacyPolicyAcceptance == false)
        #expect(manager.isLoggedIn == true, "Accepting keeps the user signed in")
        await recording.value
        #expect(api.findUser(byUsername: "acceptRecords")?.policiesAcceptedVersion == GVOAppConstants.policyVersion)

        // And: The next sign-in finds it on record and doesn't ask
        let next = makeSignedInManager(token: token)
        await next.checkPrivacyPolicyAcceptance(api: api)
        #expect(next.needsPrivacyPolicyAcceptance == false)
    }

    @Test func testAcceptPrivacyPolicy_RecordingFails_StillLetsUserIn() async throws {
        let api = StatefulStubbedAPI()
        api.simulatedLatency = 0
        let manager = makeSignedInManager(token: "unknown-token")
        await manager.checkPrivacyPolicyAcceptance(api: api)

        await manager.acceptPrivacyPolicy(recordingWith: api).value

        #expect(manager.needsPrivacyPolicyAcceptance == false)
        #expect(manager.isLoggedIn == true)
    }

    @Test func testIsPolicyVersionCurrent() {
        #expect(AuthenticationManager.isPolicyVersionCurrent(nil, bundledVersion: "2026-11-22") == false)
        #expect(AuthenticationManager.isPolicyVersionCurrent("2026-11-21", bundledVersion: "2026-11-22") == false)
        #expect(AuthenticationManager.isPolicyVersionCurrent("2026-11-22", bundledVersion: "2026-11-22") == true)
        #expect(AuthenticationManager.isPolicyVersionCurrent("2027-01-01", bundledVersion: "2026-11-22") == true)
    }

    @Test mutating func testSessionRefresh_KeepsPrivacyPolicyAcceptance() async throws {
        // Given: A signed-in user who already accepted
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))
        sut.acceptPrivacyPolicy()

        // When: Their session is updated in place (identity verification)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: true),
                  keepPrivacyPolicyAcceptance: true)

        // Then: They aren't asked, or checked, again mid-session
        #expect(sut.needsPrivacyPolicyAcceptance == false)
        #expect(sut.isCheckingPrivacyPolicyAcceptance == false)

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testLoginWhileStillLoggedIn_ChecksAgain() async throws {
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))
        sut.acceptPrivacyPolicy()

        // A login that isn't an in-place update checks, whatever isLoggedIn says
        sut.login(with: UserSession(sessionToken: "token-2", username: "username", userId: "1", isIdentityVerified: false))

        #expect(sut.isCheckingPrivacyPolicyAcceptance == true)

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    @Test mutating func testLogout_ClearsPromptImmediately_AndNextLoginChecksAgain() async throws {
        let api = StatefulStubbedAPI()
        api.simulatedLatency = 0
        sut = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychain, notificationCenter: notificationCenter)
        sut.login(with: UserSession(sessionToken: "token", username: "username", userId: "1", isIdentityVerified: false))
        await sut.checkPrivacyPolicyAcceptance(api: api)
        #expect(sut.needsPrivacyPolicyAcceptance == true)

        // When: The user declines by logging out
        sut.logout()

        // Then: The prompt is gone straight away, before the session is cleared,
        // so the alert can't re-present itself
        #expect(sut.needsPrivacyPolicyAcceptance == false)
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
        #expect(sut.isLoggedIn == false)

        // And: Signing in again checks again
        sut.login(with: UserSession(sessionToken: "token-2", username: "username", userId: "1", isIdentityVerified: false))
        #expect(sut.isCheckingPrivacyPolicyAcceptance == true)

        sut.logout()
        try await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }
}
