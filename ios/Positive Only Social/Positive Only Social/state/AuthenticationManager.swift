//
//  AuthenticationManager.swift
//  Vibes
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

    /// Whether the signed-in user still has to accept the privacy policy before
    /// using the app (issue #620).
    ///
    /// For now this is unconditional: nothing records which version of the
    /// policy a user accepted, so every launch that restores a session, and
    /// every fresh login, asks again. It lives in memory only, so relaunching
    /// the app counts as "opening the app" and re-prompts. Once the backend
    /// records an acceptance timestamp, this is the flag to drive from it.
    @Published private(set) var needsPrivacyPolicyAcceptance: Bool = false
    
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

        // An unverified email blocks every authenticated endpoint, so a
        // session that hits email_not_verified is useless — drop it too.
        notificationCenter.publisher(for: .emailNotVerified)
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
                // Opening the app with a saved session asks again (#620).
                self.needsPrivacyPolicyAcceptance = true
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
    
    /// Call this after your API login call succeeds.
    ///
    /// - Parameter keepPrivacyPolicyAcceptance: Pass true only when updating the
    ///   session of a user who is already signed in and using the app (identity
    ///   verification rewrites it in place), so they aren't asked to accept the
    ///   privacy policy again mid-session (#620). Every other login — a sign-in,
    ///   or remember-me auto-login — asks.
    func login(with sessionData: UserSession, keepPrivacyPolicyAcceptance: Bool = false) {
        
        // --- Acquire lock for thread-safety ---
        lock.lock()
        // --- Ensure lock is released on exit, even if an error is thrown ---
        defer { lock.unlock() }
        
        do {
            // Save the *entire* session object to the Keychain
            try keychainHelper.save(sessionData, for: keychainService, account: sessionAccount)

            // Signing in has to accept the privacy policy (#620), unless this
            // only updates the session of someone already using the app.
            if !keepPrivacyPolicyAcceptance || !self.isLoggedIn {
                self.needsPrivacyPolicyAcceptance = true
            }

            // Publish the new session and state
            self.session = sessionData
            self.isLoggedIn = true
            
        } catch {
            NSLog("%@", "Failed to save session: \(error)")
            // Handle error (e.g., show an alert)
        }
    }
    
    /// Records that the signed-in user accepted the privacy policy (#620).
    func acceptPrivacyPolicy() {
        needsPrivacyPolicyAcceptance = false
    }

    func logout() {
        logoutCallCount += 1

        // Drop the prompt synchronously rather than in the Task below: logging
        // out is also how the user declines the policy, and the alert must not
        // re-present itself in the moment before the session is cleared.
        needsPrivacyPolicyAcceptance = false

        Task {
            // Delete the *entire* session object
            try? keychainHelper.delete(service: keychainService, account: sessionAccount)
            
            // Clear the published properties
            self.session = nil
            self.isLoggedIn = false
        }
    }
}
