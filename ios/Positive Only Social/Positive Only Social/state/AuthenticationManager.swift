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
    
    // Unique identifiers for Keychain
    private let keychainService = "positive-only-social.Positive-Only-Social"
    private let sessionAccount = "userSessionToken"
    
    init() {
        // Check for a session token when the app starts
        checkInitialState()
    }
    
    private func checkInitialState() {
        do {
            // If we can successfully load a token, the user is logged in.
            if let token = try KeychainHelper.shared.load(String.self, from: keychainService, account: sessionAccount) {
                isLoggedIn = !token.isEmpty
            } else {
                isLoggedIn = false
            }
        } catch {
            isLoggedIn = false
        }
    }
 
    func login(with token: String) {
        Task {
            do {
                // 1. Save the token securely
                try KeychainHelper.shared.save(token, for: keychainService, account: sessionAccount)
                
                // 2. Update the state to refresh the UI
                isLoggedIn = true
                
            } catch {
                // If saving fails, don't log the user in
                print("Failed to save token to keychain: \(error)")
                isLoggedIn = false
            }
        }
    }
    
    func logout() {
        Task {
            // Clear the token from the Keychain
            try? KeychainHelper.shared.delete(service: keychainService, account: sessionAccount)
            
            // Update the published property to trigger a UI change
            isLoggedIn = false
        }
    }
}
