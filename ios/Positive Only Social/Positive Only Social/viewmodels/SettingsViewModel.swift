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
    
    // Published properties for showing alerts in the view
    @Published var showingLogoutConfirm = false
    @Published var showingDeleteConfirm = false
    @Published var showingErrorAlert = false
    @Published var errorMessage = ""
    
    // Unique identifiers for Keychain
    private let keychainService = "positive-only-social.Positive-Only-Social" // CHANGE to your app's bundle ID
    private let sessionAccount = "userSessionToken"
    
    init(api: APIProtocol) {
        self.api = api
    }
    
    /// Coordinates the full logout process.
    func logout(authManager: AuthenticationManager) {
        Task {
            do {
                // 1. Get the session token from Keychain
                guard let token = try KeychainHelper.shared.load(String.self, from: keychainService, account: sessionAccount) else {
                    // If no token, we can't call the backend, but we can still log out locally.
                    authManager.logout()
                    return
                }
                
                // 2. Call the backend to invalidate the session
                _ = try await api.logoutUser(sessionManagementToken: token)
                
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
                guard let token = try KeychainHelper.shared.load(String.self, from: keychainService, account: sessionAccount) else {
                    // We need a token to delete the account. If it's missing, show an error.
                    errorMessage = "Session token not found. Cannot delete account."
                    showingErrorAlert = true
                    return
                }
                
                // 2. Call the backend to delete the user's account
                _ = try await api.deleteUser(sessionManagementToken: token)
                
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
}
