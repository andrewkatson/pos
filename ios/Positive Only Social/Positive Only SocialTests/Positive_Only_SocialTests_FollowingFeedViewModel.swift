//
//  Positive_Only_SocialTests_FollowingFeedViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/31/25.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_FollowingFeedViewModel {

    // --- SUT & Stub ---
    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!
    
    // --- Keychain Test Fixtures ---
    let testService = "positive-only-social.Positive-Only-Social"
    
    // --- Test Setup ---
    
    init() {
        keychainHelper = KeychainHelper()
        
        // This 'init' runs before *each* @Test
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---
    
    private func yield() async {
        try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
    }
    
    /// Helper to register a user with the stub API and return their session token.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        
        struct RegFields: Codable { let session_management_token: String }
        struct DjangoRegObject: Codable { let fields: RegFields }

        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let innerData = wrapper.responseList.data(using: .utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoRegObject.self, from: innerData)
        
        return djangoObject.fields.session_management_token
    }

    // --- Test Cases ---
    @Test func testFetchFollowingFeed_UserNotFollowingAnyone_IsEmpty() async throws {
        let sut = FollowingFeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFollowingFeedUserNotFollowingAnyone")

        // Given: A user is logged in
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: testService, account: "fetchFollowingFeedUserNotFollowingAnyone")
        
        // And: Another user posts, but our user *does not* follow them
        let userBToken = try await registerUserAndGetToken(username: "userB")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "Post 1")
        
        // When: We fetch the following feed
        sut.fetchFollowingFeed()
        
        await yield()
        
        // Then: The loading flag is reset and no posts are added
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.followingPosts.isEmpty == true)
        #expect(stubAPI.getPostsForFollowedUsersCallCount == 1)
    }
    
    @Test func testFetchFollowingFeed_WhileAlreadyLoading_DoesNotFetch() async throws {
        let sut = FollowingFeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFollowingFeedWhileAlreadyLoading")
        
        // Given: A user is logged in
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: testService, account: "fetchFollowingFeedWhileAlreadyLoading")
        
        // And: The viewmodel is *already* loading
        sut.isLoadingNextPage = true
        
        // When: We try to fetch the feed
        sut.fetchFollowingFeed()
        await yield()
        
        // Then: The API was never called and the posts list is still empty
        #expect(stubAPI.getPostsForFollowedUsersCallCount == 0)
        #expect(sut.followingPosts.isEmpty == true)
    }
    
    @Test func testFetchFollowingFeed_NoTokenInKeychain_Fails() async throws {
        let sut = FollowingFeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFollowingFeedKeychainEmpty")
        
        // Given: The keychain is empty (guaranteed by init())
        
        // When: We fetch the feed
        sut.fetchFollowingFeed()
        await yield()
        
        // Then: The fetch fails (API throws auth error), flag is reset, feed is empty.
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.followingPosts.isEmpty == true)
    }
    
    @Test func testFetchFollowingFeed_Pagination_FetchesPagesAndStops() async throws {
        let sut = FollowingFeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchFollowingFeedPagination")
        
        // Given: We have a user and set the API page size to 2
        stubAPI.pageSize = 2
        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userBToken = try await registerUserAndGetToken(username: "userB")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: testService, account: "fetchFollowingFeedPagination")

        // And: User A follows User B
        _ = try await stubAPI.followUser(sessionManagementToken: userAToken, username: "userB")
        
        // And: User B creates 3 posts (which will be on 2 pages)
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "Post 1")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/3", caption: "Post 3")

        // --- 1. Fetch First Page (Page 0) ---
        sut.fetchFollowingFeed()
        await yield()

        // Then: The first 2 posts are loaded (newest first)
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.followingPosts.count == 2)
        #expect(sut.followingPosts.first?.imageUrl == "image.url/3")
        #expect(stubAPI.getPostsForFollowedUsersCallCount == 1)

        // --- 2. Fetch Second Page (Page 1) ---
        sut.fetchFollowingFeed()
        await yield()

        // Then: The final post is appended (total of 3)
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.followingPosts.count == 3)
        #expect(sut.followingPosts.last?.imageUrl == "image.url/1")
        #expect(stubAPI.getPostsForFollowedUsersCallCount == 2)

        // --- 3. Fetch Third Page (Page 2 - Empty) ---
        sut.fetchFollowingFeed()
        await yield()

        // Then: No new posts are added, and the API was called (returning empty)
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.followingPosts.count == 3)
        #expect(stubAPI.getPostsForFollowedUsersCallCount == 3)
        
        // --- 4. Try to Fetch Again (Should be blocked by `canLoadMore`) ---
        sut.fetchFollowingFeed()
        await yield()
        
        // Then: The API call count *did not increase*
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.followingPosts.count == 3)
        #expect(stubAPI.getPostsForFollowedUsersCallCount == 3)
    }
}


