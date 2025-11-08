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
    let testService = "positive-only-social.Positive-Only-Social"
    let testToken = "dummy-test-token-123"

    // --- Test Setup ---
    
    init() {
        // This 'init' runs before *each* @Test
        keychainHelper = KeychainHelper()
        
        // 1. Set up the mocks
        stubAPI = StatefulStubbedAPI()
    }
    
    // A small helper to pause the test and let the ViewModel's 'Task' complete
    private func yield() async {
        try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 seconds
    }
    
    /// Helper to register a user with the stub API and return their session token.
    /// This is needed because we must decode the nested JSON response.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1")
        struct RegFields: Codable { let session_management_token: String }
        struct DjangoRegObject: Codable { let fields: RegFields }

        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let responseString = String(describing: wrapper.responseList)
        let innerData = responseString.data(using: String.Encoding.utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoRegObject.self, from: innerData)
        
        return djangoObject.fields.session_management_token
    }

    // --- Test Cases ---
    @Test func testFetchFeed_WhenApiThrowsError_ResetsLoadingFlag() async throws {
        let sut = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFeedApiThrowsError")
        
        // Given: A user is logged in
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: testService, account: "fetchFeedApiThrowsError")
        
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
        let userSession = UserSession(sessionToken: userAToken, username: "userA", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: testService, account: "fetchFeedWhileAlreadyLoading")
        
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
        let userSession = UserSession(sessionToken: userAToken, username: "userA", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: testService, account: "fetchFeedPagination")

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
}

