//
//  KeychainHelper.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import Foundation
import Security

/// A class to provide simple, generic, and secure access to the iOS Keychain.
final class KeychainHelper {
    
    // MARK: - Singleton
    static let shared = KeychainHelper()
    private init() {}

    // MARK: - Public Methods

    /// Saves a Codable value to the Keychain for a specific account and service.
    /// - Parameters:
    ///   - value: The Codable value to save.
    ///   - service: A unique identifier for the service (e.g., your app's bundle ID).
    ///   - account: A unique identifier for the account (e.g., "sessionToken", "userCredentials").
    func save<T: Codable>(_ value: T, for service: String, account: String) throws {
        do {
            // Encode the value to a Data object.
            let data = try JSONEncoder().encode(value)
            // Save the data to the Keychain.
            try saveData(data, for: service, account: account)
        } catch {
            // Re-throw any encoding or saving errors.
            throw error
        }
    }

    /// Loads a Codable value from the Keychain.
    /// - Parameters:
    ///   - type: The `Type` of the Codable object to decode the data into.
    ///   - service: The service identifier used when saving.
    ///   - account: The account identifier used when saving.
    /// - Returns: The decoded value, or `nil` if it doesn't exist.
    func load<T: Codable>(_ type: T.Type, from service: String, account: String) throws -> T? {
        do {
            // Try to load the data from the Keychain.
            guard let data = try loadData(from: service, account: account) else {
                return nil // No data found for this service/account.
            }
            // Decode the data into the specified type.
            let value = try JSONDecoder().decode(T.self, from: data)
            return value
        } catch {
            // Re-throw any loading or decoding errors.
            throw error
        }
    }

    /// Deletes a value from the Keychain.
    func delete(service: String, account: String) throws {
        // Create a query to identify the item to delete.
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]

        // Execute the deletion.
        let status = SecItemDelete(query as CFDictionary)
        
        // Throw an error if the deletion failed for any reason other than "not found".
        if status != errSecSuccess && status != errSecItemNotFound {
            throw KeychainError.operationError(status)
        }
    }

    // MARK: - Private Core Functions

    private func saveData(_ data: Data, for service: String, account: String) throws {
        // Create a query to find an existing item.
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        
        // Set the attributes for the new or updated item.
        let attributes: [String: Any] = [
            kSecValueData as String: data
        ]

        // Check if the item already exists to decide whether to update or add.
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)

        // If the item doesn't exist (errSecItemNotFound), we need to add it.
        if status == errSecItemNotFound {
            var newQuery = query
            newQuery[kSecValueData as String] = data
            // kSecAttrAccessibleWhenUnlockedThisDeviceOnly is a good security default.
            newQuery[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            
            let addStatus = SecItemAdd(newQuery as CFDictionary, nil)
            if addStatus != errSecSuccess {
                throw KeychainError.operationError(addStatus)
            }
        } else if status != errSecSuccess {
            // If the update failed for any other reason, throw an error.
            throw KeychainError.operationError(status)
        }
    }

    private func loadData(from service: String, account: String) throws -> Data? {
        // Create a query to find the item.
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: kCFBooleanTrue!,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)

        // If the item was found, it will be in the `item` variable.
        if status == errSecSuccess {
            return item as? Data
        }
        // If it wasn't found, that's okay, just return nil.
        else if status == errSecItemNotFound {
            return nil
        }
        // If any other error occurred, throw it.
        else {
            throw KeychainError.operationError(status)
        }
    }
    
    // MARK: - Error Enum
    enum KeychainError: Error, LocalizedError {
        case operationError(OSStatus)
        var errorDescription: String? {
            "Keychain operation failed with status: \(self)"
        }
    }
}
