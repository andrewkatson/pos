//
//  Positive_Only_SocialTests_ProfileViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/31/25.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_ProfileViewModel {

    // --- SUT & Stub ---
    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!
    
    // --- Keychain Test Fixtures ---
    let testService = "positive-only-social.Positive-Only-Social"
    
    // --- Test Setup ---
    init() {
        keychainHelper = KeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---
    
    /// Helper to pause the test and let async tasks complete.
    private func yield(for duration: Duration = .seconds(2)) async {
        // Using a slightly shorter yield as VM tasks don't have a debounce
        try? await Task.sleep(for: duration)
    }
    
    /// Helper to register a user and return both their token and User object.
    private func registerUser(username: String) async throws -> (token: String, user: User) {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1")
        
        struct RegFields: Codable { let session_management_token: String }
        struct DjangoRegObject: Codable { let fields: RegFields }
        
        let wrapper: APIWrapperResponse = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let innerData = wrapper.responseList.data(using: .utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoRegObject.self, from: innerData)
        
        let token = djangoObject.fields.session_management_token
        // Create the simple User object that the VM needs
        let user = User(username: username, identityIsVerified: false)
        return (token, user)
    }
    
    /// Helper to log in a user and save their token to the keychain
    private func setupLoggedInUser(user: User, token: String, account: String) async throws {
        let userSession = UserSession(sessionToken: token, username: user.username, isIdentityVerified: user.identityIsVerified)
        try keychainHelper.save(userSession, for: testService, account: account)
    }

    // --- Post Fetching Tests ---
    
    @Test func testFetchUserPosts_Pagination_FetchesAndStops() async throws {
        // Given: A logged-in user and a profile user with 3 posts
        stubAPI.pageSize = 2
        let (requestingUserToken, requestingUser) = try await registerUser(username: "requestingUser")
        let (profileUserToken, profileUser) = try await registerUser(username: "profileUser")
        
        let account = "requestingUser_account"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)
        
        // The profileUser makes 3 posts
        _ = try await stubAPI.makePost(sessionManagementToken: profileUserToken, imageURL: "my.image/1", caption: "Post 1")
        _ = try await stubAPI.makePost(sessionManagementToken: profileUserToken, imageURL: "my.image/2", caption: "Post 2")
        _ = try await stubAPI.makePost(sessionManagementToken: profileUserToken, imageURL: "my.image/3", caption: "Post 3")
        
        // When: The SUT is created for the profileUser
        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account)

        // --- 1. Fetch First Page ---
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.count == 2, "Should load first page (2 posts)")
        #expect(stubAPI.getPostsForUserCallCount == 1)
        #expect(sut.canLoadMore == true)

        // --- 2. Fetch Second Page ---
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.count == 3, "Should load second page (1 more post)")
        #expect(stubAPI.getPostsForUserCallCount == 2)
        #expect(sut.canLoadMore == true) // The API returns an empty list *next* time

        // --- 3. Fetch Third (Empty) Page ---
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.count == 3, "Should load empty page, no change")
        #expect(stubAPI.getPostsForUserCallCount == 3)
        #expect(sut.canLoadMore == false, "Should set canLoadMore to false after empty response")
        
        // --- 4. Fetch Again (Blocked by `canLoadMore`) ---
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.count == 3, "Should be blocked by `canLoadMore`")
        #expect(stubAPI.getPostsForUserCallCount == 3, "API call count should not increase")
    }
    
    @Test func testFetchUserPosts_WhileAlreadyLoading_DoesNotFetch() async throws {
        // Given: A logged-in user and a profile user
        let (requestingUserToken, requestingUser) = try await registerUser(username: "requestingUser_loading")
        let (_, profileUser) = try await registerUser(username: "profileUser_loading")
        
        let account = "requestingUser_loading_account"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)

        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account)
        
        // And: The viewmodel is already loading
        sut.isLoading = true
        
        // When: We try to fetch
        sut.fetchUserPosts()
        await yield()
        
        // Then: The API was never called
        #expect(stubAPI.getPostsForUserCallCount == 0)
        #expect(sut.userPosts.isEmpty == true)
    }

    // --- Profile Details & Follow Tests ---

    @Test func testFetchProfileDetails_Success_LoadsDetailsAndFollowStatus() async throws {
        // Given: A logged-in user, a profile user, and another follower
        let (requestingUserToken, requestingUser) = try await registerUser(username: "mainUser")
        let (profileUserToken, profileUser) = try await registerUser(username: "starUser")
        let (followerToken, _) = try await registerUser(username: "otherFollower")
        
        let account = "mainUser_account"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)
        
        // And: The profile user has 2 posts and 1 follower
        _ = try await stubAPI.makePost(sessionManagementToken: profileUserToken, imageURL: "star.image/1", caption: "Post 1")
        _ = try await stubAPI.makePost(sessionManagementToken: profileUserToken, imageURL: "star.image/2", caption: "Post 2")
        _ = try await stubAPI.followUser(sessionManagementToken: followerToken, username: "starUser")
        
        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account)

        // When: We fetch the profile details
        sut.fetchProfileDetails()
        await yield()

        // Then: The details are loaded correctly
        #expect(sut.profileDetails != nil)
        #expect(sut.profileDetails?.username == "starUser")
        #expect(sut.profileDetails?.postCount == 2)
        #expect(sut.profileDetails?.followerCount == 1)
        #expect(sut.profileDetails?.followingCount == 0)
        #expect(sut.isFollowing == false, "Requesting user is not following yet")
    }
    
    @Test func testToggleFollow_FollowAndUnfollow_Success() async throws {
        // Given: A logged-in user and a profile user
        let (requestingUserToken, requestingUser) = try await registerUser(username: "mainToggler")
        let (profileUserToken, profileUser) = try await registerUser(username: "profileToToggle")
        
        let account = "mainToggler_account"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)
        
        // And: The profile user has 1 post
        _ = try await stubAPI.makePost(sessionManagementToken: profileUserToken, imageURL: "toggle.image/1", caption: "Post 1")
        
        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account)
        
        // --- 1. Load Initial State (Not Following) ---
        sut.fetchProfileDetails()
        await yield()
        
        #expect(sut.isFollowing == false, "Pre-condition: Not following")
        #expect(sut.profileDetails?.followerCount == 0, "Pre-condition: 0 followers")

        // --- 2. Toggle to FOLLOW ---
        sut.toggleFollow()
        await yield()
        
        // Then: The state is updated and details are re-fetched
        #expect(sut.isFollowing == true, "Should now be following")
        #expect(sut.profileDetails?.followerCount == 1, "Follower count should refresh to 1")

        // --- 3. Toggle to UNFOLLOW ---
        sut.toggleFollow()
        await yield()

        // Then: The state is updated and details are re-fetched
        #expect(sut.isFollowing == false, "Should now be unfollowing")
        #expect(sut.profileDetails?.followerCount == 0, "Follower count should refresh to 0")
    }
    
    @Test func testToggleBlock_BlockAndUnblock_Success() async throws {
        // Given: A logged-in user and a profile user
        let (requestingUserToken, requestingUser) = try await registerUser(username: "mainBlocker")
        let (profileUserToken, profileUser) = try await registerUser(username: "profileToBlock")
        
        let account = "mainBlocker_account"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)
        
        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account)
        
        // --- 1. Load Initial State (Not Blocked) ---
        sut.fetchProfileDetails()
        await yield()
        
        #expect(sut.isBlocked == false, "Pre-condition: Not blocked")
        
        // --- 2. Toggle to BLOCK ---
        sut.toggleBlock()
        await yield()
        
        // Then: The state is updated
        #expect(sut.isBlocked == true, "Should now be blocked")
        
        // Verify in API stub that the block was recorded (optional, if we can access stub state cleanly)
        // With current Stub API, we might need a helper, but verifying VM state matches expectation is key.

        // --- 3. Toggle to UNBLOCK ---
        sut.toggleBlock()
        await yield()

        // Then: The state is updated
        #expect(sut.isBlocked == false, "Should now be unblocked")
    }
}

