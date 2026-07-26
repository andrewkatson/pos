//
//  Positive_Only_SocialTests_FollowListViewModel.swift
//  Positive Only Social
//
//  Tests for the Followers / Following screens: loading the signed-in user's
//  own follow lists. Only your own lists are ever fetched (issue #8).
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_FollowListViewModel {

    let stubAPI: StatefulStubbedAPI
    let keychainHelper: KeychainHelperProtocol

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    /// Registers a user and returns their token and User object.
    private func registerUser(username: String) async throws -> (token: String, user: User) {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        let token = try JSONDecoder().decode(RegFields.self, from: data).session_management_token
        return (token, User(username: username, identityIsVerified: false))
    }

    /// Logs a user in by saving their session to the keychain under `account`.
    private func setupLoggedInUser(user: User, token: String, account: String) async throws {
        let userSession = UserSession(sessionToken: token, username: user.username, userId: "1", isIdentityVerified: user.identityIsVerified)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)
    }

    // --- Following ---

    @Test func testFollowing_Empty() async throws {
        let (token, user) = try await registerUser(username: "loner")
        let account = "loner_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        let sut = FollowListViewModel(mode: .following, api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()

        #expect(sut.users.isEmpty)
        #expect(sut.errorMessage == nil)
    }

    @Test func testFollowing_ReturnsFollowsSortedByUsername() async throws {
        let (token, user) = try await registerUser(username: "mainUser")
        _ = try await registerUser(username: "zebraUser")
        _ = try await registerUser(username: "appleUser")
        let account = "mainUser_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.followUser(sessionManagementToken: token, username: "zebraUser")
        _ = try await stubAPI.followUser(sessionManagementToken: token, username: "appleUser")

        let sut = FollowListViewModel(mode: .following, api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()

        #expect(sut.users.map { $0.username } == ["appleUser", "zebraUser"])
    }

    // --- Followers ---

    @Test func testFollowers_ReturnsOnlyOwnFollowers() async throws {
        // viewer is followed by amy and zed; viewer follows nobody.
        let (viewerToken, viewer) = try await registerUser(username: "viewer")
        let (amyToken, _) = try await registerUser(username: "amy")
        let (zedToken, _) = try await registerUser(username: "zed")
        let account = "viewer_account"
        try await setupLoggedInUser(user: viewer, token: viewerToken, account: account)

        _ = try await stubAPI.followUser(sessionManagementToken: amyToken, username: "viewer")
        _ = try await stubAPI.followUser(sessionManagementToken: zedToken, username: "viewer")

        let followers = FollowListViewModel(mode: .followers, api: stubAPI, keychainHelper: keychainHelper, account: account)
        await followers.load()
        #expect(followers.users.map { $0.username } == ["amy", "zed"])

        // The viewer follows nobody — followers and following are distinct.
        let following = FollowListViewModel(mode: .following, api: stubAPI, keychainHelper: keychainHelper, account: account)
        await following.load()
        #expect(following.users.isEmpty)
    }

    @Test func testUnfollow_RemovesFromFollowingList() async throws {
        let (token, user) = try await registerUser(username: "follower")
        _ = try await registerUser(username: "followee")
        let account = "follower_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.followUser(sessionManagementToken: token, username: "followee")

        let sut = FollowListViewModel(mode: .following, api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()
        #expect(sut.users.count == 1, "Pre-condition: following one user")

        _ = try await stubAPI.unfollowUser(sessionManagementToken: token, username: "followee")
        await sut.load()
        #expect(sut.users.isEmpty)
    }
}
