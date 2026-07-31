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

    // Contact Information (issues #194/#197). The signed-in account's own
    // username + email, loaded on mount for the Settings header. Nil until the
    // fetch resolves; the view shows a placeholder in the meantime and simply
    // keeps it if the (non-fatal) request fails.
    @Published var currentUsername: String?
    @Published var currentEmail: String?

    // Change-password state (issue #197). Errors raised while the sheet is open
    // surface inline via `passwordChangeErrorMessage` (not the shared
    // showingErrorAlert — two `.alert`s on one flag are undefined in SwiftUI),
    // and `passwordChangeSucceeded` signals the view to dismiss the sheet, after
    // which the confirmation alert is raised. `isChangingPassword` blocks a
    // double-submit while a request is in flight.
    @Published var passwordChangeErrorMessage: String?
    @Published var passwordChangeSucceeded = false
    @Published var passwordChangeStatusMessage = ""
    @Published var showingPasswordChangeStatusAlert = false
    @Published var isChangingPassword = false

    // Positive interest tags state (issues #446/#35). `interestOptions` is the
    // preset vocabulary; `selectedInterestSlugs`/`freeformInterests` are the
    // working selection (prefilled from the server, editable, removable);
    // `rejectedInterests` surfaces freeform terms the classifier dropped on the
    // last save. `interestsSaved` signals the sheet to dismiss on a clean save.
    @Published var interestOptions: [InterestOption] = []
    @Published var selectedInterestSlugs: [String] = []
    @Published var freeformInterests: [String] = []
    @Published var rejectedInterests: [RejectedInterest] = []
    @Published var isLoadingInterests = false
    @Published var isSavingInterests = false
    @Published var interestsErrorMessage: String?
    @Published var interestsSaved = false
    @Published var interestsStatusMessage = ""
    @Published var showingInterestsStatusAlert = false

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
    
    // MARK: - Contact Information & Change Password (issues #194 / #197)

    /// Loads the signed-in account's own username + email for the Contact
    /// Information section (load-on-mount, matching the rest of the app). A
    /// failure here is non-fatal: the section just keeps its placeholder.
    func loadCurrentUser() {
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    return
                }
                let data = try await api.getCurrentUser(sessionManagementToken: userSession.sessionToken)
                let fields = try JSONDecoder().decode(CurrentUserFields.self, from: data)
                currentUsername = fields.username
                currentEmail = fields.email
            } catch {
                // Non-fatal: leave the placeholder in place.
                NSLog("%@", "🔴 Could not load current user: \(error.localizedDescription)")
            }
        }
    }

    /// Changes the account password. The current password is required as well as
    /// the session, mirroring the backend, so a stolen session alone cannot
    /// change it; on success the backend evicts every other session and all
    /// remember-me cookies (a password change should evict other devices), while
    /// the caller's current session is preserved so they stay signed in here.
    func changePassword(currentPassword: String, newPassword: String) {
        passwordChangeErrorMessage = nil
        isChangingPassword = true
        Task {
            defer { isChangingPassword = false }
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    passwordChangeErrorMessage = "Session not found."
                    return
                }
                _ = try await api.changePassword(sessionManagementToken: userSession.sessionToken,
                                                 currentPassword: currentPassword,
                                                 newPassword: newPassword)
                // Clear any error from a previous failed attempt on success and
                // signal the sheet to close; the confirmation alert is raised
                // once it dismisses (see finishPasswordChange).
                passwordChangeErrorMessage = nil
                passwordChangeSucceeded = true
            } catch {
                passwordChangeErrorMessage = error.userFacingMessage
            }
        }
    }

    /// Called after the change-password sheet has closed on success: raises the
    /// confirmation alert and resets the success flag.
    func finishPasswordChange() {
        passwordChangeSucceeded = false
        passwordChangeErrorMessage = nil
        passwordChangeStatusMessage = "Your password has been changed."
        showingPasswordChangeStatusAlert = true
    }

    /// Called when the change-password sheet closes without succeeding (Cancel
    /// or swipe-down): clears any inline error so it doesn't linger.
    func cancelPasswordChange() {
        passwordChangeSucceeded = false
        passwordChangeErrorMessage = nil
        isChangingPassword = false
    }

    // MARK: - Positive interest tags (issues #446/#35)

    /// Loads the preset vocabulary and the user's current selection to prefill
    /// the Interests sheet. A failure surfaces inline; the sheet stays usable.
    func loadInterests() {
        isLoadingInterests = true
        interestsErrorMessage = nil
        rejectedInterests = []
        Task {
            defer { isLoadingInterests = false }
            do {
                let optionsData = try await api.getInterestOptions()
                interestOptions = try JSONDecoder().decode(InterestOptionsResponse.self, from: optionsData).options
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    interestsErrorMessage = "Session not found."
                    return
                }
                let data = try await api.getInterests(sessionManagementToken: userSession.sessionToken)
                let current = try JSONDecoder().decode(InterestsResponse.self, from: data)
                selectedInterestSlugs = current.categories
                freeformInterests = current.freeform
            } catch {
                interestsErrorMessage = error.userFacingMessage
            }
        }
    }

    /// Toggle a preset bucket on/off (deselecting removes it on save).
    func toggleInterest(_ slug: String) {
        if let index = selectedInterestSlugs.firstIndex(of: slug) {
            selectedInterestSlugs.remove(at: index)
        } else {
            selectedInterestSlugs.append(slug)
        }
    }

    /// Add one or more freeform terms (a comma-separated entry is split), deduped
    /// and capped, mirroring the backend limit.
    func addFreeformInterests(_ terms: [String]) {
        var seen = Set(freeformInterests.map { $0.lowercased() })
        for term in terms {
            let key = term.lowercased()
            if !seen.contains(key) && freeformInterests.count < GVOAppConstants.maxFreeformInterests {
                seen.insert(key)
                freeformInterests.append(term)
            }
        }
    }

    func removeFreeformInterest(_ term: String) {
        freeformInterests.removeAll { $0 == term }
    }

    /// Save the full remaining selection (full-replace semantics). On a clean
    /// save the sheet dismisses; if the server rejected any freeform term the
    /// sheet stays open showing which were dropped.
    func saveInterests() {
        isSavingInterests = true
        interestsErrorMessage = nil
        rejectedInterests = []
        Task {
            defer { isSavingInterests = false }
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    interestsErrorMessage = "Session not found."
                    return
                }
                let data = try await api.setInterests(sessionManagementToken: userSession.sessionToken,
                                                      categories: selectedInterestSlugs,
                                                      freeform: freeformInterests)
                let result = try JSONDecoder().decode(SetInterestsResponse.self, from: data)
                // Re-seed both from the response, exactly as loadInterests does:
                // some terms may have been dropped, and the stored buckets are
                // the union of picks and what the accepted terms mapped to.
                // Otherwise a sheet left open after a partial rejection shows
                // different chips than the same sheet reopened.
                freeformInterests = result.freeform.accepted
                selectedInterestSlugs = result.categories
                rejectedInterests = result.freeform.rejected
                if result.freeform.rejected.isEmpty {
                    interestsSaved = true
                }
            } catch {
                interestsErrorMessage = error.userFacingMessage
            }
        }
    }

    /// Called after the Interests sheet dismisses on a clean save: raises the
    /// confirmation alert and resets the flag.
    func finishInterestsSave() {
        interestsSaved = false
        interestsStatusMessage = "Your interests have been updated."
        showingInterestsStatusAlert = true
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

    /// Finishes TOTP enrollment by verifying the account password and one code
    /// from the authenticator. On success `recoveryCodes` is populated for the
    /// one-time display. The password is what stops a stolen session from
    /// binding an attacker's authenticator and locking the real owner out.
    func confirmTotp(password: String, code: String) {
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
                let data = try await api.confirmTotp(sessionManagementToken: userSession.sessionToken,
                                                     password: password, totpCode: code)
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
