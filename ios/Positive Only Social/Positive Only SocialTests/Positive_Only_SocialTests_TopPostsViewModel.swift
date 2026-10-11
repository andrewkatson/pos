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

    @Test func testSelectPeriod_ClearsOldBoardWhileReloading() async throws {
        stubAPI.pageSize = 10
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topSelectClears")
        let authorToken = try await registerUserAndGetToken(username: "author")
        _ = try await makePost(token: authorToken, caption: "post")
        let viewerToken = try await registerUserAndGetToken(username: "viewer")
        try signIn(viewerToken, username: "viewer", account: "topSelectClears")

        sut.fetchTopPosts()
        await yield()
        #expect(sut.topPosts.count == 1)

        // When: The user switches period
        sut.selectPeriod(.year)

        // Then: The old rows are dropped right away, so the new page's rows are
        // fresh and the last one's onAppear can drive pagination again
        #expect(sut.topPosts.isEmpty)
        await yield()
        #expect(sut.topPosts.count == 1)
    }

    @Test func testSelectPeriod_WhileLoading_StillReloadsNewPeriod() async throws {
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topSelectWhileLoading")
        let token = try await registerUserAndGetToken(username: "viewer")
        try signIn(token, username: "viewer", account: "topSelectWhileLoading")

        // Given: The weekly board is still loading (the stub sleeps per call)
        sut.fetchTopPosts()
        #expect(sut.isLoadingNextPage == true)

        // When: The user switches period mid-load
        sut.selectPeriod(.year)
        await yield()

        // Then: The yearly board was still requested, rather than the switch
        // being swallowed by the in-flight load's loading guard
        #expect(stubAPI.getTopPostsCallCount == 2)
        #expect(stubAPI.lastTopPostsPeriod == "year")
        #expect(sut.isLoadingNextPage == false)
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

    @Test func testTopPosts_StayWithinViewersAgeBand() async throws {
        stubAPI.pageSize = 10
        // A verified 16-year-old and an adult each post publicly.
        let teenToken = try await registerUserAndGetToken(username: "teen")
        let sixteen = Calendar.current.date(byAdding: .year, value: -16, to: Date())!
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        _ = try await stubAPI.verifyIdentity(sessionManagementToken: teenToken, dateOfBirth: formatter.string(from: sixteen))
        let teenPost = try await makePost(token: teenToken, caption: "teen")
        let adultToken = try await registerUserAndGetToken(username: "adult")
        let adultPost = try await makePost(token: adultToken, caption: "adult")

        struct Row: Decodable { let post_identifier: String }
        func ids(_ token: String) async throws -> [String] {
            let data = try await stubAPI.getTopPosts(sessionManagementToken: token, batch: 0, period: "week")
            return try JSONDecoder().decode([Row].self, from: data).map(\.post_identifier)
        }
        #expect(try await ids(adultToken) == [adultPost])
        #expect(try await ids(teenToken) == [teenPost])
    }

    @Test func testFetchTopPosts_RepeatedPostAcrossPages_ListedOnce() async throws {
        stubAPI.pageSize = 2
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topDedupe")
        let authorToken = try await registerUserAndGetToken(username: "author")
        let oldest = try await makePost(token: authorToken, caption: "oldest")
        _ = try await makePost(token: authorToken, caption: "middle")
        _ = try await makePost(token: authorToken, caption: "newest")
        let viewerToken = try await registerUserAndGetToken(username: "viewer")
        try signIn(viewerToken, username: "viewer", account: "topDedupe")

        // Page 0: newest, middle (no likes yet, so newest first)
        sut.fetchTopPosts()
        await yield()
        #expect(sut.topPosts.count == 2)

        // The oldest post climbs to #1, pushing middle onto page 1 again
        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: oldest)
        sut.fetchTopPosts()
        await yield()

        // middle is not listed twice
        #expect(sut.topPosts.count == 2)
        #expect(Set(sut.topPosts.map(\.id)).count == sut.topPosts.count)
    }

    @Test func testFetchTopPosts_RepeatOnlyPage_DoesNotStall() async throws {
        stubAPI.pageSize = 2
        let sut = TopPostsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "topRepeatOnly")
        let authorToken = try await registerUserAndGetToken(username: "author")
        let p1 = try await makePost(token: authorToken, caption: "p1")
        let p2 = try await makePost(token: authorToken, caption: "p2")
        let p3 = try await makePost(token: authorToken, caption: "p3")
        let p4 = try await makePost(token: authorToken, caption: "p4")
        let p5 = try await makePost(token: authorToken, caption: "p5")
        let viewerToken = try await registerUserAndGetToken(username: "viewer")
        try signIn(viewerToken, username: "viewer", account: "topRepeatOnly")

        // Page 0: p5, p4 (no likes yet, so newest first)
        sut.fetchTopPosts()
        await yield()
        #expect(sut.topPosts.map(\.id) == [p5, p4])

        // p2 and p1 climb above them, so page 1 is now p5, p4 again
        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: p2)
        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: p1)

        // One fetch walks past the repeat-only page to p3 on page 2
        sut.fetchTopPosts()
        await yield()
        #expect(sut.topPosts.map(\.id) == [p5, p4, p3])
        #expect(sut.isLoadingNextPage == false)
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
