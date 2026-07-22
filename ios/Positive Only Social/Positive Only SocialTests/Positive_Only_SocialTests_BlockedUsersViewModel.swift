//
//  Positive_Only_SocialTests_BlockedUsersViewModel.swift
//  Positive Only Social
//
//  Tests for the Blocked Users screen: loading the block list and
//  unblocking users from it.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_BlockedUsersViewModel {

    // --- SUT & Stub ---
    let stubAPI: StatefulStubbedAPI
    let keychainHelper: KeychainHelperProtocol

    // --- Test Setup ---
    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---

    /// Helper to register a user and return both their token and User object.
    private func registerUser(username: String) async throws -> (token: String, user: User) {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")

        struct RegFields: Decodable { let session_management_token: String }
        let token = try JSONDecoder().decode(RegFields.self, from: data).session_management_token
        let user = User(username: username, identityIsVerified: false)
        return (token, user)
    }

    /// Helper to log in a user and save their token to the keychain
    private func setupLoggedInUser(user: User, token: String, account: String) async throws {
        let userSession = UserSession(sessionToken: token, username: user.username, userId: "1", isIdentityVerified: user.identityIsVerified)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)
    }

    // --- Tests ---

    @Test func testLoad_NoBlocks_IsEmpty() async throws {
        // Given: A logged-in user with no blocks
        let (token, user) = try await registerUser(username: "lonelyUser")
        let account = "lonelyUser_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        let sut = BlockedUsersViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        // When: The list is loaded
        await sut.load()

        // Then: It is empty with no error
        #expect(sut.blockedUsers.isEmpty)
        #expect(sut.errorMessage == nil)
    }

    @Test func testLoad_ReturnsBlockedUsersSortedByUsername() async throws {
        // Given: A logged-in user who has blocked two users
        let (token, user) = try await registerUser(username: "mainUser")
        let (_, _) = try await registerUser(username: "zebraUser")
        let (_, _) = try await registerUser(username: "appleUser")
        let account = "mainUser_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.toggleBlock(sessionManagementToken: token, username: "zebraUser")
        _ = try await stubAPI.toggleBlock(sessionManagementToken: token, username: "appleUser")

        let sut = BlockedUsersViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        // When: The list is loaded
        await sut.load()

        // Then: Both blocked users are listed, sorted by username
        #expect(sut.blockedUsers.map { $0.username } == ["appleUser", "zebraUser"])
    }

    @Test func testUnblock_RemovesUserFromListAndBackend() async throws {
        // Given: A logged-in user who has blocked someone
        let (token, user) = try await registerUser(username: "blocker")
        let (targetToken, _) = try await registerUser(username: "blockee")
        let account = "blocker_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.toggleBlock(sessionManagementToken: token, username: "blockee")

        let sut = BlockedUsersViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()
        #expect(sut.blockedUsers.count == 1, "Pre-condition: one blocked user")

        // When: The user is unblocked
        await sut.unblock(username: "blockee")

        // Then: The list is empty locally and in the backend
        #expect(sut.blockedUsers.isEmpty)
        #expect(sut.errorMessage == nil)

        let data = try await stubAPI.getBlockedUsers(sessionManagementToken: token)
        let remaining = try JSONDecoder().decode([User].self, from: data)
        #expect(remaining.isEmpty, "Backend should no longer list the user as blocked")
        // The unblocked user can interact again (their session still works).
        _ = try await stubAPI.followUser(sessionManagementToken: targetToken, username: "blocker")
    }

    @Test func testUnblock_UnknownUser_SetsErrorAndKeepsList() async throws {
        // Given: A logged-in user who has blocked someone
        let (token, user) = try await registerUser(username: "errBlocker")
        _ = try await registerUser(username: "errBlockee")
        let account = "errBlocker_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.toggleBlock(sessionManagementToken: token, username: "errBlockee")

        let sut = BlockedUsersViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()

        // When: Unblocking a user that does not exist
        await sut.unblock(username: "ghostUser")

        // Then: An error is surfaced and the list is unchanged
        #expect(sut.errorMessage != nil)
        #expect(sut.blockedUsers.count == 1)
    }
}
