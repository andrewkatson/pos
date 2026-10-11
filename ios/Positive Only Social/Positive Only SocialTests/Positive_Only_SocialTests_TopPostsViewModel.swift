//
//  Positive_Only_SocialTests_TopPostsViewModel.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// The Top posts scoreboard (issue #558).
@MainActor
struct Positive_Only_SocialTests_TopPostsViewModel {

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

    private func makePost(token: String, caption: String, audience: String? = nil) async throws -> String {
        let data = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "image.url/\(caption)", caption: caption, audience: audience)
        struct PostFields: Decodable { let post_identifier: String }
        return try JSONDecoder().decode(PostFields.self, from: data).post_identifier
    }

    private func signIn(_ token: String, username: String, account: String) throws {
        let session = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(session, for: GVOAppConstants.keychainService, account: account)
    }

    @Test func testFetchTopPosts_RanksPublicPostsByLikes() async throws {
        stubAPI.pageSize = 10
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topRanksByLikes")

        // Given: An author with a quiet post, a loved post and a family-only post
        let authorToken = try await registerUserAndGetToken(username: "author")
        let quiet = try await makePost(token: authorToken, caption: "quiet")
        let loved = try await makePost(token: authorToken, caption: "loved")
        _ = try await makePost(token: authorToken, caption: "family", audience: PostAudience.family.rawValue)

        // And: A viewer who liked the loved post
        let viewerToken = try await registerUserAndGetToken(username: "viewer")
        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: loved)
        try signIn(viewerToken, username: "viewer", account: "topRanksByLikes")

        // When
        sut.fetchTopPosts()
        await yield()

        // Then: Most-liked first, and the restricted post never competes
        #expect(sut.topPosts.map(\.id) == [loved, quiet])
        #expect(stubAPI.lastTopPostsPeriod == TopPostPeriod.week.rawValue)
    }

    @Test func testSelectPeriod_ReloadsWithNewPeriod() async throws {
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topSelectPeriod")
        let token = try await registerUserAndGetToken(username: "viewer")
        try signIn(token, username: "viewer", account: "topSelectPeriod")

        sut.fetchTopPosts()
        await yield()
        #expect(stubAPI.getTopPostsCallCount == 1)

        // When: The user switches to the yearly board
        sut.selectPeriod(.year)
        await yield()

        // Then: It reloads with the new window
        #expect(sut.selectedPeriod == .year)
        #expect(stubAPI.getTopPostsCallCount == 2)
        #expect(stubAPI.lastTopPostsPeriod == "year")

        // And: Re-selecting the same period doesn't refetch
        sut.selectPeriod(.year)
        await yield()
        #expect(stubAPI.getTopPostsCallCount == 2)
    }

    @Test func testFetchTopPosts_Pagination_FetchesPagesAndStops() async throws {
        stubAPI.pageSize = 2
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topPagination")
        let authorToken = try await registerUserAndGetToken(username: "author")
        for index in 1...3 {
            _ = try await makePost(token: authorToken, caption: "post\(index)")
        }
        let viewerToken = try await registerUserAndGetToken(username: "viewer")
        try signIn(viewerToken, username: "viewer", account: "topPagination")

        sut.fetchTopPosts()
        await yield()
        #expect(sut.topPosts.count == 2)

        sut.fetchTopPosts()
        await yield()
        #expect(sut.topPosts.count == 3)

        // An empty page stops further fetches
        sut.fetchTopPosts()
        await yield()
        sut.fetchTopPosts()
        await yield()
        #expect(sut.topPosts.count == 3)
        #expect(stubAPI.getTopPostsCallCount == 3)
    }

    @Test func testFetchTopPosts_NoSession_LeavesFeedEmpty() async throws {
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topNoSession")

        sut.fetchTopPosts()
        await yield()

        #expect(sut.isLoadingNextPage == false)
        #expect(sut.topPosts.isEmpty)
        #expect(stubAPI.getTopPostsCallCount == 0)
    }
}
