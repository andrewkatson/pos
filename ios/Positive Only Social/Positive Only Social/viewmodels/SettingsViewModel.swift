//
//  SettingsViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import Foundation

@MainActor
final class SettingsViewModel: ObservableObject {
    private let api: APIProtocol
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
    
    // Unique identifiers for Keychain
    private let keychainService = "positive-only-social.Positive-Only-Social" // CHANGE to your app's bundle ID
    private let account: String
    
    convenience init(api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(api: APIProtocol, keychainHelper: KeychainHelperProtocol, account: String) {
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
                
                print("✅ Backend logout successful.")
                
            } catch {
                // Even if the backend call fails, we should still log out locally.
                print("🔴 Backend logout failed: \(error.localizedDescription). Proceeding with local logout.")
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
                
                print("✅ Account deletion successful.")
                
                // 3. Log out locally by clearing all tokens and updating the auth state.
                authManager.logout()
                
            } catch {
                errorMessage = "Failed to delete account. Please try again."
                showingErrorAlert = true
                print("🔴 Account deletion failed: \(error.localizedDescription)")
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
                    isIdentityVerified: true
                )
                
                // Save updated session to keychain and auth manager
                try keychainHelper.save(newSession, for: keychainService, account: account)
                authManager.login(with: newSession)
                
                verificationMessage = "Identity verified successfully!"
                showingVerificationAlert = true
                
            } catch {
                errorMessage = "Verification failed: \(error.localizedDescription)"
                showingErrorAlert = true
            }
        }
    }
}
