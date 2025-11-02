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
    private let sessionAccount = "userSessionToken"
    
    // A helper to access the keychain for setup/teardown
    private let keychain = KeychainHelper.shared
    
    // --- Test Setup ---
    
    init() {
        // This 'init' function runs before *each* @Test, acting like a 'setUp' method.
        // We delete any existing token to ensure each test starts in a clean,
        // predictable "logged out" state.
        do {
            try keychain.delete(service: keychainService, account: sessionAccount)
        } catch {
            // We can ignore errors here. If the item wasn't found,
            // that's fine—it's already in the state we want.
        }
    }

    // --- Test Cases ---

    @Test mutating func testInit_WhenKeychainIsEmpty_isLoggedInIsFalse() {
        // Given: The keychain is empty (guaranteed by our init() setup)
        
        // When: The AuthenticationManager is initialized
        sut = AuthenticationManager()
        
        // Then: The user should be logged out
        #expect(sut.isLoggedIn == false, "isLoggedIn should be false when no token exists")
    }

    @Test mutating func testInit_WhenKeychainHasToken_isLoggedInIsTrue() throws {
        // Given: A valid token is saved in the keychain
        let testToken = "abc-123-valid-token"
        try keychain.save(testToken, for: keychainService, account: sessionAccount)
        
        // When: The AuthenticationManager is initialized
        sut = AuthenticationManager()
        
        // Then: The user should be logged in
        #expect(sut.isLoggedIn == true, "isLoggedIn should be true when a token exists")
    }
    
    @Test mutating func testInit_WhenKeychainHasEmptyToken_isLoggedInIsFalse() throws {
        // Given: An *empty* token is saved in the keychain
        let emptyToken = ""
        try keychain.save(emptyToken, for: keychainService, account: sessionAccount)
        
        // When: The AuthenticationManager is initialized
        sut = AuthenticationManager()
        
        // Then: The user should be logged out (due to your `!token.isEmpty` check)
        #expect(sut.isLoggedIn == false, "isLoggedIn should be false for an empty token")
    }

    @Test mutating func testLogin_SetsIsLoggedInToTrue() async throws {
        // Given: The SUT is initialized in a logged-out state
        sut = AuthenticationManager()
        #expect(sut.isLoggedIn == false) // Verify initial state

        // When: login() is called
        sut.login(with: "abc-123-valid-token")
        
        // And: We wait for the background Task in login() to complete.
        // A tiny sleep is needed to let the new Task execute and update the state.
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 seconds
        
        // Then: The published property is updated to true
        #expect(sut.isLoggedIn == true, "isLoggedIn should be true after calling login()")
    }
    
    @Test mutating func testLogout_SetsIsLoggedInToFalse_AndClearsKeychain() async throws {
        // Given: A token is saved and the SUT is in a logged-in state
        try keychain.save("abc-123-token-to-delete", for: keychainService, account: sessionAccount)
        sut = AuthenticationManager()
        #expect(sut.isLoggedIn == true) // Verify initial logged-in state
        
        // When: logout() is called
        sut.logout()
        
        // And: We wait for the background Task in logout() to complete.
        // A tiny sleep is needed to let the new Task execute and update the state.
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 seconds
        
        // Then: The published property is updated to false
        #expect(sut.isLoggedIn == false, "isLoggedIn should be false after logout")
        
        // And: The token should be gone from the keychain
        let loadedToken: String? = try keychain.load(String.self, from: keychainService, account: sessionAccount)
        #expect(loadedToken == nil, "Keychain token should be nil after logout")
    }

}

