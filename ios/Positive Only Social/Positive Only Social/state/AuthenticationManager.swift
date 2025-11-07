//
//  AuthenticationManager.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import Foundation
import Combine

@MainActor
final class AuthenticationManager: ObservableObject {
    @Published var isLoggedIn: Bool = false
    
    // This is the new source of truth for the session data
    @Published var session: UserSession?
    
    // Unique identifiers for Keychain
    private let keychainService = "positive-only-social.Positive-Only-Social"
    private let sessionAccount = "userSessionToken"
    
    private let keychainHelper: KeychainHelperProtocol
    
    // A private lock to ensure thread-safe access to the keychain.
    private let lock = NSLock()
    
    private(set) var logoutCallCount = 0
    
    // Keep a default init
    convenience init() {
        // By default, do not try to auto-login
        // since UI and app runs will know they are not unit tests
        // and pass true to shouldAutoLogin
        self.init(shouldAutoLogin: false, keychainHelper: KeychainHelper())
    }
    
    init(shouldAutoLogin: Bool, keychainHelper: KeychainHelperProtocol) {
        self.keychainHelper = keychainHelper
        
        // Check for a session token when the app starts
        if shouldAutoLogin {
            checkInitialState()
        } else {
            self.session = nil
            self.isLoggedIn = false
        }
    }
    
    private func checkInitialState() {
        do {
            // Try to load the *entire* session object
            if let loadedSession = try keychainHelper.load(UserSession.self, from: keychainService, account: sessionAccount) {
                // We're logged in, and we have the user data
                self.session = loadedSession
                self.isLoggedIn = true
            } else {
                // No session object found
                self.session = nil
                self.isLoggedIn = false
            }
        } catch {
            self.session = nil
            self.isLoggedIn = false
        }
    }
    
    /// Call this after your API login call succeeds
    func login(with sessionData: UserSession) {
        
        // --- Acquire lock for thread-safety ---
        lock.lock()
        // --- Ensure lock is released on exit, even if an error is thrown ---
        defer { lock.unlock() }
        
        do {
            // Save the *entire* session object to the Keychain
            try keychainHelper.save(sessionData, for: keychainService, account: sessionAccount)
            
            // Publish the new session and state
            self.session = sessionData
            self.isLoggedIn = true
            
        } catch {
            print("Failed to save session: \(error)")
            // Handle error (e.g., show an alert)
        }
    }
    
    func logout() {
        logoutCallCount += 1
        
        Task {
            // Delete the *entire* session object
            try? keychainHelper.delete(service: keychainService, account: sessionAccount)
            
            // Clear the published properties
            self.session = nil
            self.isLoggedIn = false
        }
    }
}
