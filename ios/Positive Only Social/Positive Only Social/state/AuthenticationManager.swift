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
    private let keychainService = GVOAppConstants.keychainService
    private var sessionAccount: String {
        let base = "userSessionToken"
        guard isUITesting(), let testName = ProcessInfo.processInfo.environment["test-name"] else {
            return base
        }
        return base + "-" + testName
    }
    
    private let keychainHelper: KeychainHelperProtocol

    // The notification center used to observe app-wide events such as
    // account bans. Injectable so tests can isolate it from the shared
    // `.default` center and avoid cross-test contamination.
    private let notificationCenter: NotificationCenter

    // A private lock to ensure thread-safe access to the keychain.
    private let lock = NSLock()
    
    private var cancellables = Set<AnyCancellable>()
    
    private(set) var logoutCallCount = 0
    
    // Keep a default init
    convenience init() {
        // By default, do not try to auto-login
        // since UI and app runs will know they are not unit tests
        // and pass true to shouldAutoLogin
        self.init(shouldAutoLogin: false, keychainHelper: KeychainHelper())
    }
    
    init(shouldAutoLogin: Bool, keychainHelper: KeychainHelperProtocol, notificationCenter: NotificationCenter = .default) {
        self.keychainHelper = keychainHelper
        self.notificationCenter = notificationCenter

        // Check for a session token when the app starts
        if shouldAutoLogin {
            checkInitialState()
        } else {
            self.session = nil
            self.isLoggedIn = false
        }
        
        // A banned account has its sessions revoked server-side; when the API
        // layer sees the account_banned rejection, drop the local session so
        // the user lands back on the welcome screen.
        notificationCenter.publisher(for: .accountBanned)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in self?.logout() }
            .store(in: &cancellables)
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
            NSLog("%@", "Failed to save session: \(error)")
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
