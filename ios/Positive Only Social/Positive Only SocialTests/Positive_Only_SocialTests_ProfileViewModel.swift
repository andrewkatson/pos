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
    
    // --- Test Setup ---
    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---
    
    /// Helper to pause the test and let async tasks complete.
    private func yield(for duration: Duration = .seconds(TestConstants.shortTimeout)) async {
        try? await Task.sleep(for: duration)
    }
    
    /// Helper to register a user and return both their token and User object.
    private func registerUser(username: String) async throws -> (token: String, user: User) {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        
        struct RegFields: Decodable { let session_management_token: String }
        let token = try JSONDecoder().decode(RegFields.self, from: data).session_management_token
        // Create the simple User object that the VM needs
        let user = User(username: username, identityIsVerified: false)
        return (token, user)
    }
    
    /// Helper to log in a user and save their token to the keychain
    private func setupLoggedInUser(user: User, token: String, account: String) async throws {
        let userSession = UserSession(sessionToken: token, username: user.username, userId: "1", isIdentityVerified: user.identityIsVerified)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)
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

    @Test func testFetchProfileDetails_LoadsMembershipNumber() async throws {
        // Given: the requesting user registers first (member #1) and the
        // profile user second (member #2). The stub numbers accounts in
        // registration order, mirroring the backend (issue #198).
        let (requestingUserToken, requestingUser) = try await registerUser(username: "firstMember")
        let (_, profileUser) = try await registerUser(username: "secondMember")

        let account = "firstMember_account"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)

        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account)

        // When: we fetch the profile details
        sut.fetchProfileDetails()
        await yield()

        // Then: the profile user's join number is surfaced
        #expect(sut.profileDetails?.membershipNumber == 2)
    }

    // --- Membership Number Decoding (issue #198) ---

    @Test func testProfileDetailsResponse_DecodesMembershipNumber() throws {
        let json = """
        {
          "username": "ada",
          "post_count": 3,
          "follower_count": 5,
          "following_count": 2,
          "is_following": false,
          "membership_number": 42
        }
        """.data(using: .utf8)!

        let details = try JSONDecoder().decode(ProfileDetailsResponse.self, from: json)
        #expect(details.membershipNumber == 42)
    }

    @Test func testProfileDetailsResponse_MissingMembershipNumber_DecodesToNil() throws {
        // A server that predates the field omits it; the profile must still
        // decode with membershipNumber == nil rather than failing.
        let json = """
        {
          "username": "grace",
          "post_count": 1,
          "follower_count": 0,
          "following_count": 0,
          "is_following": true
        }
        """.data(using: .utf8)!

        let details = try JSONDecoder().decode(ProfileDetailsResponse.self, from: json)
        #expect(details.membershipNumber == nil)
    }

    @Test func testRegisterResponse_DecodesMembershipNumber() throws {
        // The register response carries the session (ignored here) plus the new
        // member's number, which is all RegisterResponse keeps.
        let json = """
        {
          "session_management_token": "tok",
          "user_id": "abc",
          "membership_number": 7
        }
        """.data(using: .utf8)!

        let response = try JSONDecoder().decode(RegisterResponse.self, from: json)
        #expect(response.membershipNumber == 7)
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

    @Test func testFollowThenBlockThenFollow_DoesNotDoubleCountFollowers() async throws {
        // Given: A logged-in user and a profile user
        let (requestingUserToken, requestingUser) = try await registerUser(username: "mainRecounter")
        let (_, profileUser) = try await registerUser(username: "profileToRecount")

        let account = "mainRecounterAccount"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)

        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account)

        // --- 1. Load Initial State (Not Following, Not Blocked) ---
        sut.fetchProfileDetails()
        await yield()
        #expect(sut.isFollowing == false, "Pre-condition: Not following")
        #expect(sut.profileDetails?.followerCount == 0, "Pre-condition: 0 followers")

        // --- 2. Follow -> count goes to 1 ---
        sut.toggleFollow()
        await yield()
        #expect(sut.isFollowing == true)
        #expect(sut.profileDetails?.followerCount == 1, "Follower count should be 1 after follow")

        // --- 3. Block -> backend unfollows, so the count must drop back to 0 ---
        sut.toggleBlock()
        await yield()
        #expect(sut.isBlocked == true)
        #expect(sut.isFollowing == false, "Blocking should unfollow")
        #expect(sut.profileDetails?.followerCount == 0, "Follower count should drop to 0 after block")

        // --- 4. Unblock then follow again -> count is 1, not 2 ---
        sut.toggleBlock()
        await yield()
        sut.toggleFollow()
        await yield()
        #expect(sut.isFollowing == true)
        #expect(sut.profileDetails?.followerCount == 1, "Following again should not double-count to 2")
    }

    // --- Own Profile (issue #347) ---

    @Test func testForCurrentUser_BuildsTheSignedInUsersOwnProfile() async throws {
        let (token, user) = try await registerUser(username: "ownProfileUser")
        let account = "ownProfileUser_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        // The Profile tab builds its view model from the stored session rather
        // than being handed a User, since there's nothing to navigate from.
        let sut = ProfileViewModel.forCurrentUser(api: stubAPI, keychainHelper: keychainHelper, account: account)

        #expect(sut.user.username == "ownProfileUser")
        #expect(sut.isOwnProfile == true, "Follow/Block stay hidden on your own profile")
    }

    @Test func testPostCreatedNotification_RefreshesOwnProfileGrid() async throws {
        let (token, user) = try await registerUser(username: "postCreatedOwner")
        let account = "postCreatedOwner_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        // Inject a private NotificationCenter so this test's notification can't
        // leak into (or be disturbed by) view models on `.default`.
        let center = NotificationCenter()
        let sut = ProfileViewModel(user: user, api: stubAPI, keychainHelper: keychainHelper, account: account,
                                   notificationCenter: center)

        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "own.image/1", caption: "Post 1")
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.count == 1)

        // When: a new post is created elsewhere in the app
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "own.image/2", caption: "Post 2")
        center.post(name: .postCreated, object: nil)
        await yield()

        // Then: it shows up without a manual pull-to-refresh
        #expect(sut.userPosts.count == 2)
        #expect(sut.userPosts.first?.imageUrl == "own.image/2", "Newest first")
    }

    @Test func testPostCreatedNotification_IgnoredOnSomeoneElsesProfile() async throws {
        let (requestingUserToken, requestingUser) = try await registerUser(username: "otherProfileViewer")
        let (profileUserToken, profileUser) = try await registerUser(username: "otherProfileOwner")
        let account = "otherProfileViewer_account"
        try await setupLoggedInUser(user: requestingUser, token: requestingUserToken, account: account)

        let center = NotificationCenter()
        let sut = ProfileViewModel(user: profileUser, api: stubAPI, keychainHelper: keychainHelper, account: account,
                                   notificationCenter: center)

        _ = try await stubAPI.makePost(sessionManagementToken: profileUserToken, imageURL: "other.image/1", caption: "Post 1")
        sut.fetchUserPosts()
        await yield()
        #expect(stubAPI.getPostsForUserCallCount == 1)

        // A post the signed-in user created doesn't belong on someone else's
        // profile, so the grid isn't refetched.
        center.post(name: .postCreated, object: nil)
        await yield()
        #expect(stubAPI.getPostsForUserCallCount == 1)
    }

    @Test func testPostDeletedNotification_RemovesPostFromProfileGrid() async throws {
        stubAPI.pageSize = 10
        let (token, user) = try await registerUser(username: "profileDeleter")
        let account = "profileDeleter_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        let center = NotificationCenter()
        let sut = ProfileViewModel(user: user, api: stubAPI, keychainHelper: keychainHelper, account: account,
                                   notificationCenter: center)

        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "del.image/1", caption: "Post 1")
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "del.image/2", caption: "Post 2")
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.count == 2)

        // When: one of the loaded posts is deleted (announced by whichever list
        // or detail view deleted it)
        let deletedId = sut.userPosts.first!.id
        center.post(name: .postDeleted, object: deletedId)
        await yield()

        // Then: it's dropped from the grid rather than the grid being reloaded
        #expect(sut.userPosts.count == 1)
        #expect(!sut.userPosts.contains { $0.id == deletedId })
        #expect(stubAPI.getPostsForUserCallCount == 1)
    }

    // --- Async Classification Reconciliation Tests (#282) ---
    //
    // The bounded status poll lives in ProfileViewModel rather than
    // HomeViewModel because the Profile tab's grid is this view model's
    // (issue #347). Only your own posts ever carry a status, so these view
    // their own profile.

    @Test func testStatusPoll_PendingPostResolvesToApproved_ReloadsGrid() async throws {
        stubAPI.pageSize = 10
        stubAPI.deferClassification = true
        let (token, user) = try await registerUser(username: "statusPollApproved")
        let account = "statusPollApproved_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: nil, caption: "waiting on review")

        let sut = ProfileViewModel(user: user, api: stubAPI, keychainHelper: keychainHelper, account: account)
        // A comfortably long interval so the classification below is resolved
        // before the first poll round fires (the round then sees the outcome).
        sut.statusPollIntervalSeconds = 1
        sut.fetchUserPosts()
        await yield(for: .seconds(0.5))

        // The author sees their own pending post, marked as such.
        #expect(sut.userPosts.count == 1)
        #expect(sut.userPosts.first?.status == "pending")

        // When the (stubbed) worker approves it, the bounded poll notices and
        // reloads the grid.
        stubAPI.resolvePendingClassifications()
        await yield()

        #expect(sut.userPosts.first?.status == "approved")
        #expect(sut.reviewNotice == nil)
    }

    @Test func testStatusPoll_PendingPostResolvesToRejected_SurfacesNotice() async throws {
        stubAPI.pageSize = 10
        stubAPI.deferClassification = true
        let (token, user) = try await registerUser(username: "statusPollRejected")
        let account = "statusPollRejected_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: nil, caption: "a borderline take")

        let sut = ProfileViewModel(user: user, api: stubAPI, keychainHelper: keychainHelper, account: account)
        sut.statusPollIntervalSeconds = 1
        sut.fetchUserPosts()
        await yield(for: .seconds(0.5))
        #expect(sut.userPosts.first?.status == "pending")

        stubAPI.resolvePendingClassifications()
        await yield()

        // The rejection is surfaced once, and the reloaded grid still shows the
        // post (hidden but appealable) with its rejected state.
        #expect(sut.reviewNotice != nil)
        #expect(sut.userPosts.first?.status == "rejected")
        #expect(sut.userPosts.first?.appealable == true)
    }

    @Test func testStatusPoll_NoPendingPosts_DoesNotPoll() async throws {
        stubAPI.pageSize = 10
        let (token, user) = try await registerUser(username: "statusPollNotNeeded")
        let account = "statusPollNotNeeded_account"
        try await setupLoggedInUser(user: user, token: token, account: account)

        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/1", caption: "instantly approved")

        let sut = ProfileViewModel(user: user, api: stubAPI, keychainHelper: keychainHelper, account: account)
        sut.statusPollIntervalSeconds = 0.05
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.first?.status == "approved")

        // No pending posts, so the poll never re-fetches the grid.
        await yield()
        #expect(stubAPI.getPostsForUserCallCount == 1)
    }
}
