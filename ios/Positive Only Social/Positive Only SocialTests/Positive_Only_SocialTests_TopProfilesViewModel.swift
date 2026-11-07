//
//  Positive_Only_SocialTests_TopProfilesViewModel.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// The Top profiles scoreboard (issue #588).
@MainActor
struct Positive_Only_SocialTests_TopProfilesViewModel {

    let stubAPI: StatefulStubbedAPI
    let keychainHelper: KeychainHelperProtocol

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    private func yield() async {
        try? await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")

        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }

    private func follow(_ username: String, as token: String) async throws {
        _ = try await stubAPI.followUser(sessionManagementToken: token, username: username, category: nil)
    }

    private func signIn(_ token: String, username: String, account: String) throws {
        let session = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(session, for: GVOAppConstants.keychainService, account: account)
    }

    @Test func testFetchTopProfiles_RanksByFollowersAndSkipsThoseWithNone() async throws {
        let sut = TopProfilesViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topProfilesRanks")

        // Given: popular has two followers, modest one, lonely none
        _ = try await registerUserAndGetToken(username: "popular")
        _ = try await registerUserAndGetToken(username: "modest")
        _ = try await registerUserAndGetToken(username: "lonely")
        let fanOne = try await registerUserAndGetToken(username: "fanone")
        try await follow("popular", as: fanOne)
        try await follow("modest", as: fanOne)
        let viewer = try await registerUserAndGetToken(username: "viewer")
        try await follow("popular", as: viewer)
        try signIn(viewer, username: "viewer", account: "topProfilesRanks")

        // When
        sut.fetchTopProfiles()
        await yield()

        // Then
        #expect(sut.topProfiles.map(\.username) == ["popular", "modest"])
        #expect(sut.topProfiles.map(\.followerCount) == [2, 1])
    }

    @Test func testFetchTopProfiles_LeavesOutPrivateAccounts() async throws {
        let sut = TopProfilesViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topProfilesPrivate")
        let secret = try await registerUserAndGetToken(username: "secret")
        _ = try await stubAPI.setAccountPrivacy(sessionManagementToken: secret, isPrivate: true)
        _ = try await registerUserAndGetToken(username: "open")
        let viewer = try await registerUserAndGetToken(username: "viewer")
        try await follow("open", as: viewer)
        try await follow("secret", as: viewer)
        try signIn(viewer, username: "viewer", account: "topProfilesPrivate")

        sut.fetchTopProfiles()
        await yield()

        #expect(sut.topProfiles.map(\.username) == ["open"])
    }

    @Test func testFetchTopProfiles_PagesUntilTheBoardRunsOut() async throws {
        stubAPI.topProfilesPageSize = 1
        let sut = TopProfilesViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topProfilesPages")
        _ = try await registerUserAndGetToken(username: "alpha")
        _ = try await registerUserAndGetToken(username: "beta")
        let viewer = try await registerUserAndGetToken(username: "viewer")
        try await follow("alpha", as: viewer)
        try await follow("beta", as: viewer)
        try signIn(viewer, username: "viewer", account: "topProfilesPages")

        sut.fetchTopProfiles()
        await yield()
        #expect(sut.topProfiles.map(\.username) == ["alpha"])
        #expect(!sut.reachedEnd)

        sut.fetchTopProfiles()
        await yield()
        #expect(sut.topProfiles.map(\.username) == ["alpha", "beta"])

        // An empty page means the whole board is loaded
        sut.fetchTopProfiles()
        await yield()
        #expect(sut.reachedEnd)
        #expect(stubAPI.getTopProfilesCallCount == 3)
    }

    @Test func testRefresh_ReloadsFromTheFirstPage() async throws {
        let sut = TopProfilesViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topProfilesRefresh")
        _ = try await registerUserAndGetToken(username: "alpha")
        let viewer = try await registerUserAndGetToken(username: "viewer")
        try signIn(viewer, username: "viewer", account: "topProfilesRefresh")

        sut.fetchTopProfiles()
        await yield()
        #expect(sut.topProfiles.isEmpty)

        try await follow("alpha", as: viewer)
        await sut.refresh()

        #expect(sut.topProfiles.map(\.username) == ["alpha"])
    }

    @Test func testFollowerCountLabel_Pluralizes() {
        #expect(TopProfile(username: "a", identityIsVerified: false, followerCount: 1).followerCountLabel == "1 follower")
        #expect(TopProfile(username: "a", identityIsVerified: false, followerCount: 0).followerCountLabel == "0 followers")
    }
}
