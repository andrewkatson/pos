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
    
    func login() {
        isLoggedIn = true
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
