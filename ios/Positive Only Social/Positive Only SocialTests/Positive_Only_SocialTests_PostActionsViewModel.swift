//
//  Positive_Only_SocialTests_PostActionsViewModel.swift
//  Positive Only Social
//
//  Covers acting on a post straight from a list — like, report, retract report
//  and delete (issue #267) — plus the listing fields those actions rely on.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_PostActionsViewModel {

    // --- SUT & Stub ---
    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Test Helpers ---

    /// Helper to pause the test and let async tasks complete.
    private func yield() async {
        try? await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    /// Unwraps a value the test can't continue without, failing the test rather
    /// than trapping when it's unexpectedly nil.
    private func unwrap<T>(_ value: T?, _ what: String) throws -> T {
        guard let value else { throw MissingTestValue(what: what) }
        return value
    }

    /// Registers a user with the stub API and returns their session token.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }

    /// Registers a user and stores their session under `account`.
    @discardableResult
    private func setupLoggedInUser(username: String, account: String) async throws -> String {
        let token = try await registerUserAndGetToken(username: username)
        let userSession = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)
        return token
    }

    /// Fetches the first post another user made, as the signed-in user's feed
    /// returns it — so the test operates on exactly what the UI would render.
    private func firstFeedPost(token: String) async throws -> Post {
        let data = try await stubAPI.getPostsInFeed(sessionManagementToken: token, batch: 0)
        let posts = try JSONDecoder().decode([Post].self, from: data)
        return try unwrap(posts.first, "a post in the feed")
    }

    // --- Listing Payload Tests ---

    @Test func testPostDecoding_CarriesInteractionStateAndDetails() throws {
        let json = """
        [{
            "post_identifier": "p1",
            "image_url": "https://example.com/1.jpg",
            "original_image_url": "https://example.com/original.jpg",
            "caption": "Hello",
            "author_username": "someone",
            "post_likes": 3,
            "is_liked": true,
            "is_reported": true,
            "report_reason": "spam",
            "comment_count": 7,
            "creation_time": "2024-01-15T10:30:45.123456+00:00"
        }]
        """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode([Post].self, from: json)
        let post = try unwrap(decoded.first, "a decoded post")
        #expect(post.postLikes == 3)
        #expect(post.isLiked == true)
        #expect(post.isReported == true)
        #expect(post.reportReason == "spam")
        #expect(post.commentCount == 7)
        #expect(post.createdDate != nil, "The Django-style timestamp should parse")
    }

    @Test func testPostDecoding_OlderResponseWithoutInteractionState_StillDecodes() throws {
        // A response from a backend that predates issues #267 / #249.
        let json = """
        [{
            "post_identifier": "p1",
            "image_url": null,
            "caption": "Text only",
            "author_username": "someone"
        }]
        """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode([Post].self, from: json)
        let post = try unwrap(decoded.first, "a decoded post")
        #expect(post.postLikes == 0)
        #expect(post.isLiked == false)
        #expect(post.isReported == false)
        #expect(post.reportReason == nil)
        #expect(post.commentCount == 0)
        #expect(post.createdDate == nil, "No timestamp means no relative-time label")
    }

    @Test func testFeedListing_IncludesLikeReportAndCommentState() async throws {
        let account = "listingState_account"
        let viewerToken = try await setupLoggedInUser(username: "listingViewer", account: account)
        let authorToken = try await registerUserAndGetToken(username: "listingAuthor")

        _ = try await stubAPI.makePost(sessionManagementToken: authorToken, imageURL: "img/1", caption: "Post 1")

        // The viewer likes, reports and comments on the post.
        let original = try await firstFeedPost(token: viewerToken)
        #expect(original.isLiked == false)
        #expect(original.postLikes == 0)
        #expect(original.commentCount == 0)

        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: original.id)
        _ = try await stubAPI.reportPost(sessionManagementToken: viewerToken, postIdentifier: original.id, reason: "not nice")
        _ = try await stubAPI.commentOnPost(sessionManagementToken: viewerToken, postIdentifier: original.id, commentText: "Hi")

        // The listing now reports all of that back, like get_post_details does.
        let refreshed = try await firstFeedPost(token: viewerToken)
        #expect(refreshed.postLikes == 1)
        #expect(refreshed.isLiked == true)
        #expect(refreshed.isReported == true)
        #expect(refreshed.reportReason == "not nice")
        #expect(refreshed.commentCount == 1)
        #expect(refreshed.createdDate != nil)
    }

    // --- Like Tests ---

    @Test func testToggleLike_LikesThenUnlikes() async throws {
        let account = "toggleLike_account"
        let viewerToken = try await setupLoggedInUser(username: "likeViewer", account: account)
        let authorToken = try await registerUserAndGetToken(username: "likeAuthor")
        _ = try await stubAPI.makePost(sessionManagementToken: authorToken, imageURL: "img/1", caption: "Post 1")

        let post = try await firstFeedPost(token: viewerToken)
        let sut = PostActionsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        // When: the heart is tapped, the row updates immediately...
        sut.toggleLike(post)
        #expect(sut.state(for: post).isLiked == true)
        #expect(sut.state(for: post).likeCount == 1)
        await yield()

        // ...and the backend agrees.
        let afterLike = try await firstFeedPost(token: viewerToken)
        #expect(afterLike.isLiked == true)
        #expect(afterLike.postLikes == 1)

        // When: it's tapped again, the like is removed.
        sut.toggleLike(post)
        #expect(sut.state(for: post).isLiked == false)
        #expect(sut.state(for: post).likeCount == 0)
        await yield()

        let afterUnlike = try await firstFeedPost(token: viewerToken)
        #expect(afterUnlike.isLiked == false)
        #expect(afterUnlike.postLikes == 0)
    }

    @Test func testToggleLike_OnOwnPost_DoesNothing() async throws {
        let account = "likeOwnPost_account"
        let token = try await setupLoggedInUser(username: "selfLiker", account: account)
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "img/1", caption: "Mine")

        let data = try await stubAPI.getPostsForUser(sessionManagementToken: token, username: "selfLiker", batch: 0)
        let ownPosts = try JSONDecoder().decode([Post].self, from: data)
        let post = try unwrap(ownPosts.first, "the user's own post")

        let sut = PostActionsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)
        #expect(sut.state(for: post).isOwn == true, "The signed-in user authored this post")

        // The backend rejects liking your own post, so the like is a no-op
        // rather than an optimistic update that would have to be reverted.
        sut.toggleLike(post)
        #expect(sut.state(for: post).isLiked == false)
        #expect(sut.state(for: post).likeCount == 0)
        await yield()
        #expect(sut.alertMessage == nil)
    }

    @Test func testToggleLike_WhenRequestFails_RevertsAndAlerts() async throws {
        let account = "likeFails_account"
        let viewerToken = try await setupLoggedInUser(username: "failLiker", account: account)
        let authorToken = try await registerUserAndGetToken(username: "failLikeAuthor")
        _ = try await stubAPI.makePost(sessionManagementToken: authorToken, imageURL: "img/1", caption: "Post 1")

        let post = try await firstFeedPost(token: viewerToken)
        let sut = PostActionsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        // Given: the post is already liked on the backend, so liking it again fails.
        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: post.id)

        sut.toggleLike(post)
        #expect(sut.state(for: post).isLiked == true, "Optimistic update applies first")
        await yield()

        // Then: the optimistic like is rolled back and the user is told.
        #expect(sut.state(for: post).isLiked == false)
        #expect(sut.state(for: post).likeCount == 0)
        #expect(sut.alertMessage != nil)
    }

    // --- Report / Retract Tests ---

    @Test func testReportThenRetract_UpdatesRowState() async throws {
        let account = "reportRetract_account"
        let viewerToken = try await setupLoggedInUser(username: "reporter", account: account)
        let authorToken = try await registerUserAndGetToken(username: "reportedAuthor")
        _ = try await stubAPI.makePost(sessionManagementToken: authorToken, imageURL: "img/1", caption: "Post 1")

        let post = try await firstFeedPost(token: viewerToken)
        let sut = PostActionsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)
        #expect(sut.state(for: post).isReported == false)

        sut.report(post, reason: "rude")
        await yield()
        #expect(sut.state(for: post).isReported == true)
        #expect(sut.state(for: post).reportReason == "rude")

        sut.retractReport(post)
        await yield()
        #expect(sut.state(for: post).isReported == false)
        #expect(sut.state(for: post).reportReason == nil)

        // And the backend agrees the report is gone.
        let refreshed = try await firstFeedPost(token: viewerToken)
        #expect(refreshed.isReported == false)
    }

    // --- Delete Tests ---

    @Test func testDelete_DropsThePostFromLoadedListsWithoutReloading() async throws {
        let account = "deleteFromList_account"
        let token = try await setupLoggedInUser(username: "deleter", account: account)
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "img/1", caption: "Mine 1")
        _ = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "img/2", caption: "Mine 2")

        // Inject a private NotificationCenter so this test's notification can't
        // leak into (or be disturbed by) view models on `.default`.
        let center = NotificationCenter()
        let profile = ProfileViewModel(
            user: User(username: "deleter", identityIsVerified: false),
            api: stubAPI,
            keychainHelper: keychainHelper,
            account: account,
            notificationCenter: center
        )
        profile.fetchUserPosts()
        await yield()
        #expect(profile.userPosts.count == 2)

        let sut = PostActionsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account, notificationCenter: center)
        let doomed = try unwrap(profile.userPosts.first, "the post to delete")
        let survivorId = try unwrap(profile.userPosts.last, "the post that survives").id

        sut.delete(doomed)
        await yield()

        // Then: only that post is gone — the rest of the list is untouched, so
        // the user's place in it doesn't shift under them.
        #expect(profile.userPosts.count == 1)
        #expect(!profile.userPosts.contains { $0.id == doomed.id })
        #expect(profile.userPosts.first?.id == survivorId)
        #expect(stubAPI.getPostsForUserCallCount == 1, "Deleting must not reload the list")
    }

    @Test func testDelete_OfSomeoneElsesPost_Fails_AndKeepsTheList() async throws {
        let account = "deleteOthers_account"
        let viewerToken = try await setupLoggedInUser(username: "notTheAuthor", account: account)
        let authorToken = try await registerUserAndGetToken(username: "theAuthor")
        _ = try await stubAPI.makePost(sessionManagementToken: authorToken, imageURL: "img/1", caption: "Not yours")

        let post = try await firstFeedPost(token: viewerToken)

        let center = NotificationCenter()
        let feed = FeedViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account, notificationCenter: center)
        feed.fetchFeed()
        await yield()
        #expect(feed.feedPosts.count == 1)

        let sut = PostActionsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account, notificationCenter: center)
        sut.delete(post)
        await yield()

        // The backend rejects deleting another user's post, so the row stays.
        #expect(feed.feedPosts.count == 1)
        #expect(sut.alertMessage != nil)
    }
}

/// Thrown when a test can't find a value it needs, so the failure names what
/// was missing instead of trapping on a force-unwrap.
private struct MissingTestValue: Error, CustomStringConvertible {
    let what: String
    var description: String { "Expected \(what) but found nil" }
}
