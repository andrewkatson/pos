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
    private let keychainService = "positive-only-social.Positive-Only-Social"
    private let userSessionAccount = "userSessionToken"
    
    // A helper to access the keychain for setup/teardown
    private let keychain : KeychainHelperProtocol!
    
    // --- Test setup ---
    init() {
        keychain = KeychainHelper()
        
        try? keychain.delete(service: keychainService, account: userSessionAccount)
    }
    
    // --- Test Cases ---

    @Test mutating func testInit_WhenKeychainIsEmpty_isLoggedInIsFalse() async throws {
        // Given: The keychain is empty (guaranteed by our init() setup)
        
        // When: The AuthenticationManager is initialized
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain)
        
        // Then: The user should be logged out
        #expect(sut.isLoggedIn == false, "isLoggedIn should be false when no token exists")
        
        // Clean things up
        sut.logout()
        
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
    }

    @Test mutating func testInit_WhenKeychainHasToken_isLoggedInIsTrue() async throws {
        // Given: A valid token is saved in the keychain
        let testToken = "abc-123-valid-token"
        let testUsername = "username"
        let userSession = UserSession(sessionToken: testToken, username: testUsername, isIdentityVerified: false)
        try keychain.save(userSession, for: keychainService, account: userSessionAccount)
        
        // When: The AuthenticationManager is initialized
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain)
        
        // Then: The user should be logged in
        #expect(sut.isLoggedIn == true, "isLoggedIn should be true when a token exists")
        // Clean things up
        sut.logout()
        
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
    }

    @Test mutating func testLogin_SetsIsLoggedInToTrue() async throws {
        // Given: The SUT is initialized in a logged-out state
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain)
        #expect(sut.isLoggedIn == false) // Verify initial state

        // When: login() is called
        let token = "abc-123-valid-token"
        let testUsername = "username"
        let userSession = UserSession(sessionToken: token, username: testUsername, isIdentityVerified: false)
        sut.login(with: userSession)
        
        // And: We wait for the background Task in login() to complete.
        // A tiny sleep is needed to let the new Task execute and update the state.
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 seconds
        
        // Then: The published property is updated to true
        #expect(sut.isLoggedIn == true, "isLoggedIn should be true after calling login()")
        
        // Clean things up
        sut.logout()
        
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
    }
    
    @Test mutating func testLogout_SetsIsLoggedInToFalse_AndClearsKeychain() async throws {
        // Given: A token is saved and the SUT is in a logged-in state
        let token = "abc-123-valid-token"
        let testUsername = "username"
        let userSession = UserSession(sessionToken: token, username: testUsername, isIdentityVerified: false)
        try keychain.save(userSession, for: keychainService, account: userSessionAccount)
        sut = AuthenticationManager(shouldAutoLogin: true, keychainHelper: keychain)
        
        // Wait to login
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
        
        #expect(sut.isLoggedIn == true) // Verify initial logged-in state
        
        // When: logout() is called
        sut.logout()
        
        // And: We wait for the background Task in logout() to complete.
        // A tiny sleep is needed to let the new Task execute and update the state.
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
        
        // Then: The published property is updated to false
        #expect(sut.isLoggedIn == false, "isLoggedIn should be false after logout")
        
        // And: The token should be gone from the keychain
        let loadedToken: String? = try keychain.load(UserSession.self, from: keychainService, account: userSessionAccount)?.sessionToken
        #expect(loadedToken == nil, "Keychain token should be nil after logout")
        
        // Clean things up
        sut.logout()
        
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
    }

}

