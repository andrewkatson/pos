//
//  Positive_Only_SocialTests.swift
//  Positive Only SocialTests
//
//  Created by Andrew Katson on 8/29/25.
//

import Testing
import Security
import Foundation

@testable import Positive_Only_Social

struct Positive_Only_SocialTests_KeyChainHelper {

    var sut: KeychainHelper!
    
    // --- Test Fixtures ---
    
    // Define a unique service and account name for testing to avoid collisions
    let testService = "com.positiveonlysocial.tests.keychain"
    let testAccount = "unitTestAccount"

    // Define a sample Codable struct for saving and loading
    struct TestData: Codable, Equatable {
        let id: UUID
        let message: String
    }
    
    let testValue = TestData(id: UUID(), message: "Hello, Keychain!")
    
    // --- Test Setup (replaces traditional setUp) ---
        
    init() {
        // 1. Initialize the System Under Test (sut)
        sut = KeychainHelper()
        
        // 2. Clean up the keychain before EACH test
        // This ensures tests are isolated and don't fail because of
        // data left over from a previous test run.
        do {
            try sut.delete(service: testService, account: testAccount)
        } catch {
            // We can ignore errors here, as the item might not exist,
            // which is the state we want anyway.
            print("Cleanup: No pre-existing keychain item to delete, which is normal.")
        }
    }

    // --- Test Cases ---

    @Test func testSaveAndLoad_Success() throws {
        // Given: A value to save
        let valueToSave = TestData(id: UUID(), message: "Test Save/Load")
        
        // When: We save the value
        try sut.save(valueToSave, for: testService, account: "saveAndLoadSuccess")
        
        // And: We load the value back
        let loadedValue: TestData? = try sut.load(TestData.self, from: testService, account: "saveAndLoadSuccess")
        
        // Then: The loaded value should not be nil and should match the saved value
        #expect(loadedValue != nil, "Loaded value should not be nil")
        #expect(valueToSave == loadedValue, "Loaded value should equal the saved value")
    }

    @Test func testLoad_NonExistent_ReturnsNil() throws {
        // Given: An empty keychain (guaranteed by setUp)
        
        // When: We try to load a value that was never saved
        let loadedValue: TestData? = try sut.load(TestData.self, from: testService, account: "loadNonExistent")
        
        // Then: The result should be nil
        #expect(loadedValue == nil, "Loading a non-existent item should return nil")
    }
    
    @Test func testUpdate_Success() throws {
        // Given: An initial value is saved
        let initialValue = TestData(id: UUID(), message: "Initial Value")
        try sut.save(initialValue, for: testService, account: "update")
        
        // When: A new value is saved to the *same* service and account
        let updatedValue = TestData(id: UUID(), message: "Updated Value")
        try sut.save(updatedValue, for: testService, account: "update")
        
        // Then: Loading the value should return the new, updated value
        let loadedValue: TestData? = try sut.load(TestData.self, from: testService, account: "update")
        #expect(updatedValue == loadedValue, "Loading after a save should return the updated value")
        #expect(initialValue != loadedValue, "Loading should not return the old value")
    }
    
    @Test func testDelete_Success() throws {
        // Given: A value is saved in the keychain
        try sut.save(testValue, for: testService, account: "delete")
        
        // And: We confirm it's there
        let loadedValue: TestData? = try sut.load(TestData.self, from: testService, account: "delete")
        #expect(loadedValue != nil, "Value should exist before deleting")
        
        // When: We delete the value
        try sut.delete(service: testService, account: "delete")
        
        // Then: Loading it again should return nil
        let reloadedValue: TestData? = try sut.load(TestData.self, from: testService, account:"delete")
        #expect(reloadedValue == nil, "Value should be nil after deletion")
    }
    
    @Test func testDelete_NonExistent_DoesNotThrow() throws {
        // Given: An empty keychain (guaranteed by setUp)
        
        // When: We try to delete an item that doesn't exist
        // Then: The function should complete without throwing an error
        // (This tests the `status != errSecItemNotFound` check in your delete function)
        do {
            try sut.delete(service: testService, account: "deleteNonExistent")
        } catch {
            Issue.record("Deleting a non-existent item should not throw an error: \(error)")
        }
    }
    
    @Test func testLoad_TypeMismatch_ThrowsDecodingError() throws {
        // Given: We save a value of one type (our TestData struct)
        try sut.save(testValue, for: testService, account: "typeMismatch")
        
        // When: We try to load that same data as an incompatible type (e.g., String)
        // Then: The load function should throw a DecodingError
        do {
            _ = try sut.load(String.self, from: testService, account: "typeMismatch")
            Issue.record("Expected a DecodingError, but no error was thrown")
        } catch let error as DecodingError {
            // success
            _ = error
        } catch {
            Issue.record("Expected a DecodingError, but got: \(error)")
        }
    }
    
    @Test func testSave_InvalidCodable_ThrowsEncodingError() {
        // Given: A value that cannot be encoded by JSONEncoder (e.g., Double.infinity)
        let invalidValue = Double.infinity
        
        // When: We attempt to save it
        // Then: The save function should throw an EncodingError
        do {
            try sut.save(invalidValue, for: testService, account: "saveInvalidCodable")
            Issue.record("Expected an EncodingError, but no error was thrown")
        } catch let error as EncodingError {
            // success
            _ = error
        } catch {
            Issue.record("Expected an EncodingError, but got: \(error)")
        }
    }
}

