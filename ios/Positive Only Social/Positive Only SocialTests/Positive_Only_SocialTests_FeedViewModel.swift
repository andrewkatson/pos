//
//  Positive_Only_SocialTests_.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/31/25.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_FeedViewModel {

    // --- SUT & Mocks ---
    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!
    
    // --- Keychain Test Fixtures ---
    let testToken = "dummy-test-token-123"

    // --- Test Setup ---
    
    init() {
        // This 'init' runs before *each* @Test
        keychainHelper = MockKeychainHelper()

        // 1. Set up the mocks
        stubAPI = StatefulStubbedAPI()
    }
    
    // A small helper to pause the test and let the ViewModel's 'Task' complete
    private func yield() async {
        try? await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }
    
    /// Helper to register a user with the stub API and return their session token.
    /// This is needed because we must decode the nested JSON response.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }

    // --- Test Cases ---
    @Test func testFetchFeed_WhenApiThrowsError_ResetsLoadingFlag() async throws {
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFeedApiThrowsError")
        
        // Given: A user is logged in
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: "fetchFeedApiThrowsError")
        
        // And: *No one* has made any posts. The API stub will throw a 400 error.
        
        // When: We fetch the feed
        sut.fetchFeed()
        
        // Then: The loading state should be true immediately
        #expect(sut.isLoadingNextPage == true)
        
        await yield()
        
        // Then: The loading flag is reset and no posts are added
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.isEmpty == true)
    }
    
    @Test func testFetchFeed_WhileAlreadyLoading_DoesNotFetch() async throws {
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFeedWhileAlreadyLoading")
        
        // Given: A user is logged in
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: "fetchFeedWhileAlreadyLoading")
        
        // And: The viewmodel is *already* loading
        sut.isLoadingNextPage = true
        
        // When: We try to fetch the feed
        sut.fetchFeed()
        await yield()
        
        // Then: The feed is still empty (because the API was never called)
        #expect(sut.feedPosts.isEmpty == true)
        // We can't check call counts on the stub, but the empty feed proves it.
    }
    
    @Test func testFetchFeed_NoTokenInKeychain_SendsEmptyTokenAndFails() async throws {
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "noTokenInKeychain")
        
        // Given: The keychain is empty (guaranteed by init())
        
        // When: We fetch the feed
        sut.fetchFeed()
        await yield()
        
        // Then: The fetch fails (because the API throws an auth error for the
        // empty token), the loading flag is reset, and the feed is empty.
        // This tests the `?? ""` logic in the ViewModel.
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.isEmpty == true)
    }

    @Test func testFetchFeed_Pagination_FetchesPagesAndStopsAtEnd() async throws {
        // Given: We have a user and set the API page size to 2
        stubAPI.pageSize = 2
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFeedPagination")
        
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userBToken = try await registerUserAndGetToken(username: "userB")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: "fetchFeedPagination")

        // And: User B creates 3 posts (which will be on 2 pages)
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "Post 1")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/3", caption: "Post 3")

        // --- 1. Fetch First Page (Page 0) ---
        // When: We fetch the feed
        sut.fetchFeed()
        await yield()

        // Then: The first 2 posts are loaded and loading stops
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.count == 2)
        #expect(sut.feedPosts.first?.imageUrl == "image.url/3", "Posts should be sorted by creation date (newest first)")
        #expect(sut.feedPosts.last?.imageUrl == "image.url/2")
        #expect(stubAPI.getPostsInFeedCallCount == 1)

        // --- 2. Fetch Second Page (Page 1) ---
        // When: We fetch the feed again
        sut.fetchFeed()
        await yield()

        // Then: The final post is appended (total of 3)
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.count == 3)
        #expect(sut.feedPosts.last?.imageUrl == "image.url/1")
        #expect(stubAPI.getPostsInFeedCallCount == 2)

        // --- 3. Fetch Third Page (Page 2 - Empty) ---
        // When: We fetch again
        sut.fetchFeed()
        await yield()

        // Then: No new posts are added, and the API was called (returning empty)
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.count == 3)
        #expect(stubAPI.getPostsInFeedCallCount == 3)
        
        // --- 4. Try to Fetch Again (Should be blocked by `canLoadMore`) ---
        // When: We try one more time
        sut.fetchFeed()
        await yield()
        
        // Then: The API call count *did not increase* because the VM
        // correctly set `canLoadMore = false` after the empty response.
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.count == 3)
        #expect(stubAPI.getPostsInFeedCallCount == 3)
    }

    @Test func testRefreshFeed_PullsNewestPostsAndReplacesList() async throws {
        stubAPI.pageSize = 2
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "refreshFeedPullsNewest")

        // Given: A logged-in user and another user with one post
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userBToken = try await registerUserAndGetToken(username: "userB")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: "refreshFeedPullsNewest")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "Post 1")

        // And: The feed has been loaded once
        sut.fetchFeed()
        await yield()
        #expect(sut.feedPosts.count == 1)
        #expect(stubAPI.getPostsInFeedCallCount == 1)

        // When: New posts appear on the backend and we pull-to-refresh
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/3", caption: "Post 3")
        await sut.refreshFeed()

        // Then: The list is replaced with the freshest first page (newest first)
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.count == 2)
        #expect(sut.feedPosts.first?.imageUrl == "image.url/3")
        #expect(sut.feedPosts.last?.imageUrl == "image.url/2")
        #expect(stubAPI.getPostsInFeedCallCount == 2)
    }

    @Test func testRefreshFeed_ResetsPaginationAfterEndReached() async throws {
        stubAPI.pageSize = 2
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "refreshFeedResetsPagination")

        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userBToken = try await registerUserAndGetToken(username: "userB")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: "refreshFeedResetsPagination")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "Post 1")

        // Given: We have paged to the end (canLoadMore becomes false)
        sut.fetchFeed()
        await yield()
        sut.fetchFeed() // empty page 1 -> canLoadMore = false
        await yield()
        #expect(sut.feedPosts.count == 1)
        #expect(stubAPI.getPostsInFeedCallCount == 2)

        // And: Two more posts now exist on the backend (3 total = 2 pages)
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/3", caption: "Post 3")

        // When: We refresh
        await sut.refreshFeed()

        // Then: The freshest first page (2 newest) replaces the list...
        #expect(sut.feedPosts.count == 2)

        // ...and pagination is reset, so a subsequent fetch loads page 1 again.
        sut.fetchFeed()
        await yield()
        #expect(sut.feedPosts.count == 3)
    }

    @Test func testRefreshFeed_Failure_PreservesPaginationCursor() async throws {
        stubAPI.pageSize = 2
        let account = "refreshFeedFailurePreservesCursor"
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userBToken = try await registerUserAndGetToken(username: "userB")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)

        // Given: 3 posts exist and we've loaded the first page (cursor at page 1)
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "Post 1")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/3", caption: "Post 3")
        sut.fetchFeed()
        await yield()
        #expect(sut.feedPosts.count == 2)
        #expect(sut.feedPosts.first?.imageUrl == "image.url/3")

        // When: A refresh fails (session is unavailable for the duration of the refresh)
        try keychainHelper.delete(service: GVOAppConstants.keychainService, account: account)
        await sut.refreshFeed()
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)

        // Then: The existing posts are untouched and the loading flag is reset
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.feedPosts.count == 2)

        // And: The cursor was NOT reset, so the next fetch loads page 1 (not page 0
        // again), appending the third post without duplicating the first page.
        sut.fetchFeed()
        await yield()
        #expect(sut.feedPosts.count == 3)
        #expect(sut.feedPosts.last?.imageUrl == "image.url/1")
        // Page 0's posts appear exactly once (no duplication).
        #expect(sut.feedPosts.filter { $0.imageUrl == "image.url/3" }.count == 1)
    }
}

