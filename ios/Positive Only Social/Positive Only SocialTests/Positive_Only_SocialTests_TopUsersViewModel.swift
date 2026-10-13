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

    @Test func testFetchTopUsers_RepeatOnlyPage_DoesNotStall() async throws {
        stubAPI.pageSize = 2
        let sut = TopUsersViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topUsersRepeatOnly")
        for name in ["alpha", "bravo", "charlie", "delta", "echo"] {
            _ = try await registerUserAndGetToken(username: name)
        }
        var fans: [String] = []
        for index in 1...4 {
            fans.append(try await registerUserAndGetToken(username: "fan\(index)"))
        }
        func follow(_ fanIndices: [Int], _ username: String) async throws {
            for index in fanIndices {
                _ = try await stubAPI.followUser(sessionManagementToken: fans[index], username: username)
            }
        }
        // alpha 3, bravo 2, then charlie / delta / echo on 1 each (by name)
        try await follow([0, 1, 2], "alpha")
        try await follow([0, 1], "bravo")
        try await follow([0], "charlie")
        try await follow([0], "delta")
        try await follow([0], "echo")
        try signIn(fans[3], username: "fan4", account: "topUsersRepeatOnly")

        // Page 0: alpha, bravo
        sut.fetchTopUsers()
        await yield()
        #expect(sut.topUsers.map(\.user.username) == ["alpha", "bravo"])

        // charlie and delta climb to 4, so page 1 is alpha, bravo again
        try await follow([1, 2, 3], "charlie")
        try await follow([1, 2, 3], "delta")

        // One fetch walks past the repeat-only page to echo on page 2
        sut.fetchTopUsers()
        await yield()
        #expect(sut.topUsers.map(\.user.username) == ["alpha", "bravo", "echo"])
        #expect(stubAPI.getTopUsersCallCount == 3)
        #expect(sut.isLoadingNextPage == false)
    }

    @Test func testTopUsers_LeaveOutPrivateAccounts() async throws {
        stubAPI.pageSize = 10
        let secretToken = try await registerUserAndGetToken(username: "secret")
        _ = try await stubAPI.setAccountPrivacy(sessionManagementToken: secretToken, isPrivate: true)
        _ = try await registerUserAndGetToken(username: "open")
        let fanToken = try await registerUserAndGetToken(username: "fan")
        _ = try await stubAPI.followUser(sessionManagementToken: fanToken, username: "open")
        _ = try await stubAPI.followUser(sessionManagementToken: fanToken, username: "secret")
        _ = try await stubAPI.approveFollowRequest(sessionManagementToken: secretToken, username: "fan")

        let data = try await stubAPI.getTopUsers(sessionManagementToken: fanToken, batch: 0)
        #expect(try JSONDecoder().decode([TopUser].self, from: data).map(\.user.username) == ["open"])
    }

    @Test func testFollowerWhoVerifiesAsMinor_DropsFromBoardAndProfileAlike() async throws {
        stubAPI.pageSize = 10
        _ = try await registerUserAndGetToken(username: "star")
        let fan1 = try await registerUserAndGetToken(username: "fan1")
        _ = try await stubAPI.followUser(sessionManagementToken: fan1, username: "star")
        let fan2 = try await registerUserAndGetToken(username: "fan2")
        _ = try await stubAPI.followUser(sessionManagementToken: fan2, username: "star")
        let sixteen = Calendar.current.date(byAdding: .year, value: -16, to: Date())!
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        _ = try await stubAPI.verifyIdentity(sessionManagementToken: fan2, dateOfBirth: formatter.string(from: sixteen))

        let viewer = try await registerUserAndGetToken(username: "viewer")
        let board = try JSONDecoder().decode(
            [TopUser].self, from: try await stubAPI.getTopUsers(sessionManagementToken: viewer, batch: 0))
        #expect(board.map(\.user.username) == ["star"])
        #expect(board.first?.followerCount == 1)

        struct Profile: Decodable { let follower_count: Int }
        let profile = try JSONDecoder().decode(
            Profile.self, from: try await stubAPI.getProfileDetails(sessionManagementToken: viewer, username: "star"))
        #expect(profile.follower_count == board.first?.followerCount)
    }

    @Test func testTopUserDecodesFlatRow() throws {
        let json = #"[{"username":"star","identity_is_verified":true,"follower_count":12}]"#
        let rows = try JSONDecoder().decode([TopUser].self, from: Data(json.utf8))
        #expect(rows.first?.user.username == "star")
        #expect(rows.first?.user.identityIsVerified == true)
        #expect(rows.first?.followerCount == 12)
    }
}
