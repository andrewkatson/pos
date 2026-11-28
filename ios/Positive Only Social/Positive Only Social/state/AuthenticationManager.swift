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
    /// using the app (issue #620). Drives the re-accept alert.
    ///
    /// Every launch that restores a session, and every fresh login, starts a
    /// check (`isCheckingPrivacyPolicyAcceptance`): `checkPrivacyPolicyAcceptance`
    /// asks the backend which version the user last accepted, and this only
    /// turns true when that is missing or older than the version this build
    /// bundles — or when the check fails, since asking is the safe answer.
    /// Accepting records the bundled version on the backend.
    @Published private(set) var needsPrivacyPolicyAcceptance: Bool = false

    /// True from a login (or a restored session) until the backend has said
    /// whether the user still has to accept the privacy policy (issue #620).
    @Published private(set) var isCheckingPrivacyPolicyAcceptance: Bool = false

    /// Bumped by every login and logout, so a check still in flight for an
    /// earlier session can't settle the next one.
    private var privacyPolicyCheckGeneration = 0
    
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
                // Opening the app with a saved session checks again (#620).
                startPrivacyPolicyCheck()
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

            // Signing in checks the privacy policy acceptance afresh (#620),
            // unless this only updates the session of someone already using
            // the app.
            if !keepPrivacyPolicyAcceptance || !self.isLoggedIn {
                startPrivacyPolicyCheck()
            }

            // Publish the new session and state
            self.session = sessionData
            self.isLoggedIn = true
            
        } catch {
            NSLog("%@", "Failed to save session: \(error)")
            // Handle error (e.g., show an alert)
        }
    }
    
    /// Whether a version on record covers the one this build shows. Versions
    /// are `YYYY-MM-DD` dates, so they compare as strings; someone who accepted
    /// a newer copy on a more up-to-date client isn't asked about this one.
    static func isPolicyVersionCurrent(_ acceptedVersion: String?,
                                       bundledVersion: String = GVOAppConstants.policyVersion) -> Bool {
        guard let acceptedVersion else { return false }
        return acceptedVersion >= bundledVersion
    }

    private func startPrivacyPolicyCheck() {
        privacyPolicyCheckGeneration += 1
        needsPrivacyPolicyAcceptance = false
        isCheckingPrivacyPolicyAcceptance = true
    }

    /// Asks the backend which privacy policy version the signed-in user last
    /// accepted (GET /me/) and settles the pending check (#620): the alert only
    /// comes up when that is missing or older than `GVOAppConstants.policyVersion`,
    /// or when the request fails. Does nothing when no check is pending.
    func checkPrivacyPolicyAcceptance(api: Networking) async {
        guard isCheckingPrivacyPolicyAcceptance, let token = session?.sessionToken else { return }
        let generation = privacyPolicyCheckGeneration
        var acceptedVersion: String?
        do {
            let data = try await api.getCurrentUser(sessionManagementToken: token)
            acceptedVersion = try JSONDecoder().decode(CurrentUserFields.self, from: data).policiesAcceptedVersion
        } catch {
            acceptedVersion = nil
        }
        guard generation == privacyPolicyCheckGeneration, isCheckingPrivacyPolicyAcceptance else { return }
        isCheckingPrivacyPolicyAcceptance = false
        needsPrivacyPolicyAcceptance = !Self.isPolicyVersionCurrent(acceptedVersion)
    }

    /// Records, for this session, that the signed-in user accepted the privacy
    /// policy (#620). Also used right after the Google consent dialog, whose
    /// sign-up the backend already records.
    func acceptPrivacyPolicy() {
        isCheckingPrivacyPolicyAcceptance = false
        needsPrivacyPolicyAcceptance = false
    }

    /// The user tapped Accept on the re-accept alert: let them in at once (the
    /// alert closes synchronously) and record the bundled version on the
    /// backend. Recording is best-effort, like logout — if it fails they are
    /// simply asked again next time. Returns the recording task for tests.
    @discardableResult
    func acceptPrivacyPolicy(recordingWith api: Networking) -> Task<Void, Never> {
        let token = session?.sessionToken
        acceptPrivacyPolicy()
        return Task {
            guard let token else { return }
            _ = try? await api.acceptPolicies(sessionManagementToken: token,
                                              policyVersion: GVOAppConstants.policyVersion)
        }
    }

    func logout() {
        logoutCallCount += 1

        // Drop the prompt synchronously rather than in the Task below: logging
        // out is also how the user declines the policy, and the alert must not
        // re-present itself in the moment before the session is cleared.
        privacyPolicyCheckGeneration += 1
        isCheckingPrivacyPolicyAcceptance = false
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
