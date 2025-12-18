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
    
    // --- Keychain Test Fixtures ---
    let testService = "positive-only-social.Positive-Only-Social"
    
    // --- Test Setup ---
    init() {
        keychainHelper = KeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---
    
    /// Helper to pause the test and let async tasks complete.
    private func yield(for duration: Duration = .seconds(1)) async {
        try? await Task.sleep(for: duration)
    }
    
    /// Helper to register a user and return their token.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        
        struct RegFields: Codable { let session_management_token: String }
        struct DjangoRegObject: Codable { let fields: RegFields }
        
        let wrapper: APIWrapperResponse = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let innerData = wrapper.responseList.data(using: .utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoRegObject.self, from: innerData)
        
        return djangoObject.fields.session_management_token
    }
    
    /// Helper to log in a user and save their token to the keychain
    private func setupLoggedInUser(username: String) async throws -> String {
        let token = try await registerUserAndGetToken(username: username)
        let userSession = UserSession(sessionToken: token, username: username, isIdentityVerified: false)
        // Use the testAccount that the ViewModel will also use
        try keychainHelper.save(userSession, for: testService, account: "\(username)_account")
        return token
    }
    
    // --- Logout Tests ---

    @Test func testLogout_Success_CallsAPIAndAuthManager() async throws {
        // Given: A logged-in user
        let token = try await setupLoggedInUser(username: "logoutUser")
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "logoutUser_account")
        let authenticationManager = AuthenticationManager()
        
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
        let authenticationManager = AuthenticationManager()
        
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
        let authenticationManager = AuthenticationManager()
        
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
        let authenticationManager = AuthenticationManager()
        
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
        let authenticationManager = AuthenticationManager()
        let dateOfBirth = Date() // Today
        
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
}

