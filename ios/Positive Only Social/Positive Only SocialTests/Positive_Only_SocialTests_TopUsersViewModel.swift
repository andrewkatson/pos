//
//  Positive_Only_SocialTests_TopUsersViewModel.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// The most-followed people board (issue #562).
@MainActor
struct Positive_Only_SocialTests_TopUsersViewModel {

    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!

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

    private func signIn(_ token: String, username: String, account: String) throws {
        let session = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(session, for: GVOAppConstants.keychainService, account: account)
    }

    @Test func testFetchTopUsers_RanksByFollowersAndSkipsUnfollowed() async throws {
        stubAPI.pageSize = 10
        let sut = TopUsersViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topUsersRank")
        _ = try await registerUserAndGetToken(username: "quiet")
        _ = try await registerUserAndGetToken(username: "star")
        _ = try await registerUserAndGetToken(username: "rising")
        let fan1 = try await registerUserAndGetToken(username: "fan1")
        _ = try await stubAPI.followUser(sessionManagementToken: fan1, username: "star")
        _ = try await stubAPI.followUser(sessionManagementToken: fan1, username: "rising")
        let fan2 = try await registerUserAndGetToken(username: "fan2")
        _ = try await stubAPI.followUser(sessionManagementToken: fan2, username: "star")
        try signIn(fan2, username: "fan2", account: "topUsersRank")

        sut.fetchTopUsers()
        await yield()

        #expect(sut.topUsers.map(\.user.username) == ["star", "rising"])
        #expect(sut.topUsers.map(\.followerCount) == [2, 1])
        #expect(sut.isLoadingNextPage == false)
    }

    @Test func testFetchTopUsers_PaginatesAndStops() async throws {
        stubAPI.pageSize = 1
        let sut = TopUsersViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topUsersPages")
        _ = try await registerUserAndGetToken(username: "alpha")
        _ = try await registerUserAndGetToken(username: "bravo")
        let fan = try await registerUserAndGetToken(username: "fan")
        _ = try await stubAPI.followUser(sessionManagementToken: fan, username: "alpha")
        _ = try await stubAPI.followUser(sessionManagementToken: fan, username: "bravo")
        try signIn(fan, username: "fan", account: "topUsersPages")

        sut.fetchTopUsers()
        await yield()
        sut.fetchTopUsers()
        await yield()
        #expect(sut.topUsers.map(\.user.username) == ["alpha", "bravo"])

        // An empty page stops further fetches
        sut.fetchTopUsers()
        await yield()
        sut.fetchTopUsers()
        await yield()
        #expect(stubAPI.getTopUsersCallCount == 3)
    }

    @Test func testTopUserDecodesFlatRow() throws {
        let json = #"[{"username":"star","identity_is_verified":true,"follower_count":12}]"#
        let rows = try JSONDecoder().decode([TopUser].self, from: Data(json.utf8))
        #expect(rows.first?.user.username == "star")
        #expect(rows.first?.user.identityIsVerified == true)
        #expect(rows.first?.followerCount == 12)
    }
}
