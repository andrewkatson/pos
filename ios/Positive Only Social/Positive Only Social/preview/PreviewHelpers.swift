//
//  PreviewHelpers.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import Foundation
import SwiftUI

// MARK: - Mock Keychain Helper

class MockKeychainHelper: KeychainHelperProtocol {
    private var storage: [String: Data] = [:]
    
    func save<T: Codable>(_ value: T, for service: String, account: String) throws {
        let key = "\(service):\(account)"
        let data = try JSONEncoder().encode(value)
        storage[key] = data
    }
    
    func load<T: Codable>(_ type: T.Type, from service: String, account: String) throws -> T? {
        let key = "\(service):\(account)"
        guard let data = storage[key] else { return nil }
        return try JSONDecoder().decode(T.self, from: data)
    }
    
    func delete(service: String, account: String) throws {
        let key = "\(service):\(account)"
        storage.removeValue(forKey: key)
    }
}

// MARK: - Preview Helpers

struct PreviewHelpers {
    static let api: APIProtocol = StatefulStubbedAPI()
    static let keychainHelper: KeychainHelperProtocol = MockKeychainHelper()
    
    @MainActor static var authManager: AuthenticationManager {
        let manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychainHelper)
        // Pre-populate with a logged-in user if needed for specific previews
        return manager
    }
    
    // Helper to create a logged-in auth manager
    @MainActor static func loggedInAuthManager() -> AuthenticationManager {
        let manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychainHelper)
        manager.login(with: UserSession(sessionToken: "mock_token", username: "preview_user", isIdentityVerified: true))
        return manager
    }
}
