//
//  Positive_Only_SocialTests_HomeViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/31/25.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_HomeViewModel {

    // --- SUT & Stub ---
    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!
    
    // --- Keychain Test Fixtures ---
    
    // --- Test Setup ---
    init() {
        
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---
    
    /// Helper to pause the test and let async/debounce tasks complete.
    private func yield(for duration: Duration = .seconds(TestConstants.shortTimeout)) async {
        try? await Task.sleep(for: duration)
    }
    
    /// Helper to register a user and return their session token.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }
    
    /// Helper to log in the "testuser" and save their token to the keychain
    private func setupLoggedInUser(username: String) async throws {
        let token = try await registerUserAndGetToken(username: username)
        let userSession = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: AppConstants.keychainService, account: "\(username)_account")
    }

    // --- Post Fetching Tests ---
    @Test func testFetchMyPosts_Pagination_FetchesAndStops() async throws {
        stubAPI.pageSize = 2
        
        try await setupLoggedInUser(username: "fetchMyPostsUser")
        
        let sut = HomeViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchMyPostsUser_account")

        // 1. Tell the 'load' function what type you're expecting.
        //    Swift can now infer the generic type 'T' is 'UserSession'.
        let session = try keychainHelper.load(UserSession.self, from: AppConstants.keychainService, account: "fetchMyPostsUser_account")

        // 2. Now you can safely unwrap and access the property.
        let token = session!.sessionToken
        
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/1", caption: "Post 1")
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/3", caption: "Post 3")
        
        
        // --- 1. Fetch First Page ---
        sut.fetchMyPosts()
        await yield()
        #expect(sut.userPosts.count == 2, "Should load first page (2 posts)")
        #expect(stubAPI.getPostsForUserCallCount == 1)

        // --- 2. Fetch Second Page ---
        sut.fetchMyPosts()
        await yield()
        #expect(sut.userPosts.count == 3, "Should load second page (1 more post)")
        #expect(stubAPI.getPostsForUserCallCount == 2)

        // --- 3. Fetch Third (Empty) Page ---
        sut.fetchMyPosts()
        await yield()
        #expect(sut.userPosts.count == 3, "Should load empty page, no change")
        #expect(stubAPI.getPostsForUserCallCount == 3)
        
        // --- 4. Fetch Again (Blocked by `canLoadMorePosts`) ---
        sut.fetchMyPosts()
        await yield()
        #expect(sut.userPosts.count == 3, "Should be blocked by `canLoadMorePosts`")
        #expect(stubAPI.getPostsForUserCallCount == 3, "API call count should not increase")
    }
    
    @Test func testFetchMyPosts_WhileAlreadyLoading_DoesNotFetch() async throws {
        
        try await setupLoggedInUser(username: "fetchMyPostsWhileAlreadyLoading")
        
        let sut = HomeViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "fetchMyPostsWhileAlreadyLoading_account")
        
        // And: The viewmodel is already loading
        sut.isLoadingNextPage = true
        
        // When: We try to fetch
        sut.fetchMyPosts()
        await yield()
        
        // Then: The API was never called
        #expect(stubAPI.getPostsForUserCallCount == 0)
        #expect(sut.userPosts.isEmpty == true)
    }

    @Test func testRefreshMyPosts_PullsNewestPostsAndReplacesList() async throws {
        stubAPI.pageSize = 2

        try await setupLoggedInUser(username: "refreshMyPostsPullsNewest")
        let sut = HomeViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "refreshMyPostsPullsNewest_account")

        let session = try keychainHelper.load(UserSession.self, from: AppConstants.keychainService, account: "refreshMyPostsPullsNewest_account")
        let token = session!.sessionToken

        // Given: One post exists and the grid has loaded once
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/1", caption: "Post 1")
        sut.fetchMyPosts()
        await yield()
        #expect(sut.userPosts.count == 1)
        #expect(stubAPI.getPostsForUserCallCount == 1)

        // When: Two more posts are made and we pull-to-refresh
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/3", caption: "Post 3")
        await sut.refreshMyPosts()

        // Then: The list is replaced with the freshest first page (newest first)
        #expect(sut.isLoadingNextPage == false)
        #expect(sut.userPosts.count == 2)
        #expect(sut.userPosts.first?.imageUrl == "my.image/3")
        #expect(sut.userPosts.last?.imageUrl == "my.image/2")
        #expect(stubAPI.getPostsForUserCallCount == 2)
    }

    @Test func testRefreshMyPosts_ResetsPaginationAfterEndReached() async throws {
        stubAPI.pageSize = 2

        try await setupLoggedInUser(username: "refreshMyPostsResetsPagination")
        let sut = HomeViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "refreshMyPostsResetsPagination_account")

        let session = try keychainHelper.load(UserSession.self, from: AppConstants.keychainService, account: "refreshMyPostsResetsPagination_account")
        let token = session!.sessionToken

        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/1", caption: "Post 1")

        // Given: We have paged to the end (canLoadMorePosts becomes false)
        sut.fetchMyPosts()
        await yield()
        sut.fetchMyPosts() // empty page 1 -> canLoadMorePosts = false
        await yield()
        #expect(sut.userPosts.count == 1)
        #expect(stubAPI.getPostsForUserCallCount == 2)

        // And: Two more posts now exist on the backend (3 total = 2 pages)
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/3", caption: "Post 3")

        // When: We refresh
        await sut.refreshMyPosts()

        // Then: The freshest first page replaces the list...
        #expect(sut.userPosts.count == 2)

        // ...and pagination is reset, so a subsequent fetch loads page 1 again.
        sut.fetchMyPosts()
        await yield()
        #expect(sut.userPosts.count == 3)
    }

    // --- Search Tests ---

    @Test func testSearch_Debouncer_Success() async throws {
        try await setupLoggedInUser(username: "searchDebouncerSuccess")
        
        let sut = HomeViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "searchDebouncerSuccess_account")
        
        _ = try await registerUserAndGetToken(username: "alice")
        _ = try await registerUserAndGetToken(username: "alicia")
        _ = try await registerUserAndGetToken(username: "bob")
       
        
        // When: The search text is set
        sut.searchText = "ali"
        
        // Then: Immediately, the results are still empty
        #expect(sut.searchedUsers.isEmpty == true)
        
        // And: We wait for the 500ms debounce + 100ms buffer
        await yield()
        
        // Then: The API was called and results are published
        #expect(sut.searchedUsers.count == 2)
        #expect(sut.searchedUsers.first?.username == "alice")
        #expect(stubAPI.getUsersMatchingFragmentCallCount == 1)
    }
    
    @Test func testSearch_QueryTooShort_DoesNotSearch() async throws {
        try await setupLoggedInUser(username: "searchQueryTooShort")
        
        let sut = HomeViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "searchQueryTooShort_account")
        
        // When: The search text is set to 2 characters
        sut.searchText = "zz"
        
        // And: We wait for the debounce
        await yield()
        
        // Then: The API was *not* called (due to `query.count >= 3` guard)
        #expect(sut.searchedUsers.isEmpty == true)
        #expect(stubAPI.getUsersMatchingFragmentCallCount == 0)
    }
    
    @Test func testSearch_QueryBecomesTooShort_ClearsResults() async throws {
        try await setupLoggedInUser(username: "searchQueryBecomesTooShort")
        
        let sut = HomeViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "searchQueryBecomesTooShort_account")
        
        _ = try await registerUserAndGetToken(username: "tommy")
        
        sut.searchText = "tom"
        await yield()
        #expect(sut.searchedUsers.count == 1, "Pre-condition: results are loaded")

        // When: The search text is cleared (or becomes too short)
        sut.searchText = "t"
        await yield()
        
        // Then: The results are cleared
        #expect(sut.searchedUsers.isEmpty == true, "Results should be cleared")
        #expect(stubAPI.getUsersMatchingFragmentCallCount == 1, "API count should not increase")
    }
}
