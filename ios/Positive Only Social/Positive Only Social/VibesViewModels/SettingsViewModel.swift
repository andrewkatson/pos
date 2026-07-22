//
//  SettingsViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import Foundation

@MainActor
final class SettingsViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    
    // Published properties for showing alerts in the view
    @Published var showingLogoutConfirm = false
    @Published var showingDeleteConfirm = false
    @Published var showingErrorAlert = false
    @Published var errorMessage = ""
    
    // Verification state
    @Published var showingVerificationAlert = false
    @Published var verificationMessage = ""
    @Published var showingVerificationInput = false

    // Two-factor authentication state (issue #348). `totpSetup` drives the
    // scan/confirm steps of the enrollment sheet; `recoveryCodes` (set once
    // confirm succeeds) drives the final save-your-codes step.
    @Published var totpSetup: TotpSetupFields?
    @Published var recoveryCodes: [String]?
    @Published var twoFactorStatusMessage = ""
    @Published var showingTwoFactorStatusAlert = false
    // Errors raised while the enrollment sheet is open are shown inline on that
    // sheet via this dedicated field, not the shared showingErrorAlert — two
    // `.alert`s bound to the same flag (one on the List, one on the sheet) have
    // undefined presentation in SwiftUI.
    @Published var twoFactorErrorMessage: String?
    // True while a confirm request is in flight. The enrollment sheet blocks
    // interactive dismissal during that window: the request can succeed on the
    // backend, and dismissing would drop the response (and with it the
    // one-time recovery codes) while 2FA is actually enabled.
    @Published var isConfirmingTotp = false
    
    // Unique identifiers for Keychain
    private let keychainService = GVOAppConstants.keychainService
    private let account: String
    
    convenience init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }
    
    /// Coordinates the full logout process.
    func logout(authManager: AuthenticationManager) {
        Task {
            do {
                // 1. Get the session token from Keychain
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    // If no token, we can't call the backend, but we can still log out locally.
                    authManager.logout()
                    return
                }
                
                // 2. Call the backend to invalidate the session
                _ = try await api.logoutUser(sessionManagementToken: userSession.sessionToken)
                
                NSLog("%@", "✅ Backend logout successful.")
                
            } catch {
                // Even if the backend call fails, we should still log out locally.
                NSLog("%@", "🔴 Backend logout failed: \(error.localizedDescription). Proceeding with local logout.")
            }
            
            // 3. Trigger the local logout via the AuthenticationManager
            authManager.logout()
        }
    }
    
    /// Coordinates the full account deletion process.
    func deleteAccount(authManager: AuthenticationManager) {
        Task {
            do {
                // 1. Get the session token from Keychain
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    // We need a token to delete the account. If it's missing, show an error.
                    errorMessage = "Session not found. Cannot delete account."
                    showingErrorAlert = true
                    return
                }
                
                // 2. Call the backend to delete the user's account
                _ = try await api.deleteUser(sessionManagementToken: userSession.sessionToken)
                
                NSLog("%@", "✅ Account deletion successful.")
                
                // 3. Log out locally by clearing all tokens and updating the auth state.
                authManager.logout()
                
            } catch {
                errorMessage = "Failed to delete account. Please try again."
                showingErrorAlert = true
                NSLog("%@", "🔴 Account deletion failed: \(error.localizedDescription)")
            }
        }
    }
    
    // MARK: - Two-Factor Authentication (issue #348)

    // Monotonic id for the current enrollment request. Every start/confirm bumps
    // it and captures the value; a response only applies if it still matches, so
    // a late response from a superseded, finished, or cancelled attempt is
    // dropped instead of overwriting newer state. (@MainActor makes the
    // read-modify-write safe without a lock.)
    private var totpRequestGeneration = 0

    /// Starts TOTP enrollment: fetches a fresh secret + otpauth:// URI for the
    /// scan step of the enrollment sheet.
    func startTotpSetup() {
        twoFactorErrorMessage = nil
        totpRequestGeneration += 1
        let generation = totpRequestGeneration
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    if generation == totpRequestGeneration { twoFactorErrorMessage = "Session not found." }
                    return
                }
                let data = try await api.setupTotp(sessionManagementToken: userSession.sessionToken)
                guard generation == totpRequestGeneration else { return }
                totpSetup = try JSONDecoder().decode(TotpSetupFields.self, from: data)
            } catch {
                if generation == totpRequestGeneration {
                    twoFactorErrorMessage = "Could not start two-factor setup: \(error.userFacingMessage)"
                }
            }
        }
    }

    /// Finishes TOTP enrollment by verifying one code from the authenticator.
    /// On success `recoveryCodes` is populated for the one-time display.
    func confirmTotp(code: String) {
        totpRequestGeneration += 1
        let generation = totpRequestGeneration
        isConfirmingTotp = true
        Task {
            defer {
                // Only the newest attempt owns the flag; an older one finishing
                // late must not unblock dismissal for the current attempt.
                if generation == totpRequestGeneration { isConfirmingTotp = false }
            }
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    if generation == totpRequestGeneration { twoFactorErrorMessage = "Session not found." }
                    return
                }
                let data = try await api.confirmTotp(sessionManagementToken: userSession.sessionToken, totpCode: code)
                guard generation == totpRequestGeneration else { return }
                let fields = try JSONDecoder().decode(ConfirmTotpFields.self, from: data)
                // Clear any error from a previous wrong attempt on success.
                twoFactorErrorMessage = nil
                recoveryCodes = fields.recoveryCodes
            } catch {
                if generation == totpRequestGeneration {
                    twoFactorErrorMessage = "Verification failed: \(error.userFacingMessage)"
                }
            }
        }
    }

    /// Dismisses the enrollment flow after the recovery codes have been shown.
    func finishTotpEnrollment() {
        // Invalidate any in-flight setup/confirm so a late response can't
        // repopulate state after the flow has ended.
        totpRequestGeneration += 1
        isConfirmingTotp = false
        totpSetup = nil
        recoveryCodes = nil
        twoFactorErrorMessage = nil
        twoFactorStatusMessage = "Two-factor authentication is now enabled."
        showingTwoFactorStatusAlert = true
    }

    /// Abandons a not-yet-confirmed enrollment (the pending secret is inert).
    func cancelTotpEnrollment() {
        totpRequestGeneration += 1
        isConfirmingTotp = false
        totpSetup = nil
        recoveryCodes = nil
        twoFactorErrorMessage = nil
    }

    /// Turns two-factor authentication off. Requires the account password plus
    /// a current authenticator code or an unused recovery code.
    func disableTotp(password: String, code: String, isRecoveryCode: Bool) {
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    errorMessage = "Session not found."
                    showingErrorAlert = true
                    return
                }
                // Recovery codes are sent lowercased to match the backend pattern.
                _ = try await api.disableTotp(
                    sessionManagementToken: userSession.sessionToken,
                    password: password,
                    totpCode: isRecoveryCode ? nil : code,
                    recoveryCode: isRecoveryCode ? code.lowercased() : nil
                )
                twoFactorStatusMessage = "Two-factor authentication has been disabled."
                showingTwoFactorStatusAlert = true
            } catch {
                errorMessage = "Could not disable two-factor authentication: \(error.userFacingMessage)"
                showingErrorAlert = true
            }
        }
    }

    /// Verifies the identity of the user
    func verifyIdentity(authManager: AuthenticationManager, dateOfBirth: Date) {
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    errorMessage = "Session not found."
                    showingErrorAlert = true
                    return
                }
                
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                let dateString = formatter.string(from: dateOfBirth)
                
                _ = try await api.verifyIdentity(sessionManagementToken: userSession.sessionToken, dateOfBirth: dateString)
                
                // Update local session to verified
                let newSession = UserSession(
                    sessionToken: userSession.sessionToken,
                    username: userSession.username,
                    userId: userSession.userId,
                    isIdentityVerified: true
                )
                
                // Save updated session to keychain and auth manager
                try keychainHelper.save(newSession, for: keychainService, account: account)
                authManager.login(with: newSession)
                
                verificationMessage = "Identity verified successfully!"
                showingVerificationAlert = true
                
            } catch {
                errorMessage = "Verification failed: \(error.userFacingMessage)"
                showingErrorAlert = true
            }
        }
    }
}
