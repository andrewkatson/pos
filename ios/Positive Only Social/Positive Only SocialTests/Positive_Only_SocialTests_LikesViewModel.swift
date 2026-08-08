//
//  Positive_Only_SocialTests_LikesViewModel.swift
//  Positive Only Social
//
//  Tests for "who liked this" (issue #478): the batched liker list behind your
//  own post's or comment's like count. Only your own content is ever listed.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_LikesViewModel {

    let stubAPI: StatefulStubbedAPI
    let keychainHelper: KeychainHelperProtocol

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    /// Registers a user and returns their token and User object.
    private func registerUser(username: String) async throws -> (token: String, user: User) {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        let token = try JSONDecoder().decode(RegFields.self, from: data).session_management_token
        return (token, User(username: username, identityIsVerified: false))
    }

    /// Logs a user in by saving their session to the keychain under `account`.
    private func setupLoggedInUser(user: User, token: String, account: String) async throws {
        let userSession = UserSession(sessionToken: token, username: user.username, userId: "1", isIdentityVerified: user.identityIsVerified)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)
    }

    /// Creates a post owned by `token` and returns its identifier.
    private func makePost(token: String) async throws -> String {
        let data = try await stubAPI.makePost(
            sessionManagementToken: token,
            imageURL: "https://example.com/a.jpg",
            caption: "a sunny day",
            audience: nil,
            captionFont: "default",
            backgroundColor: "default"
        )
        struct PostFields: Decodable { let post_identifier: String }
        return try JSONDecoder().decode(PostFields.self, from: data).post_identifier
    }

    // --- Post likes ---

    @Test func testPostLikers_EmptyWhenNobodyLiked() async throws {
        let (token, user) = try await registerUser(username: "author")
        let account = "author_account"
        try await setupLoggedInUser(user: user, token: token, account: account)
        let postIdentifier = try await makePost(token: token)

        let sut = LikesViewModel(target: .post(postIdentifier: postIdentifier), api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()

        #expect(sut.users.isEmpty)
        #expect(sut.canLoadMore == false)
        #expect(sut.errorMessage == nil)
    }

    @Test func testPostLikers_ReturnsLikersMostRecentFirst() async throws {
        let (token, user) = try await registerUser(username: "author")
        let account = "author_account"
        try await setupLoggedInUser(user: user, token: token, account: account)
        let postIdentifier = try await makePost(token: token)

        let (earlyToken, _) = try await registerUser(username: "early")
        _ = try await stubAPI.likePost(sessionManagementToken: earlyToken, postIdentifier: postIdentifier)
        let (laterToken, _) = try await registerUser(username: "later")
        _ = try await stubAPI.likePost(sessionManagementToken: laterToken, postIdentifier: postIdentifier)

        let sut = LikesViewModel(target: .post(postIdentifier: postIdentifier), api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()

        #expect(sut.users.map { $0.username } == ["later", "early"])
    }

    @Test func testPostLikers_RefusedForSomeoneElsesPost() async throws {
        let (authorToken, _) = try await registerUser(username: "author")
        let postIdentifier = try await makePost(token: authorToken)

        let (viewerToken, viewer) = try await registerUser(username: "viewer")
        let account = "viewer_account"
        try await setupLoggedInUser(user: viewer, token: viewerToken, account: account)
        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: postIdentifier)

        let sut = LikesViewModel(target: .post(postIdentifier: postIdentifier), api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()

        #expect(sut.users.isEmpty)
        #expect(sut.errorMessage != nil)
    }

    @Test func testPostLikers_LoadMoreAppendsTheNextBatchAndStopsAtTheEnd() async throws {
        let (token, user) = try await registerUser(username: "author")
        let account = "author_account"
        try await setupLoggedInUser(user: user, token: token, account: account)
        let postIdentifier = try await makePost(token: token)

        // The stub's page size is 2, so three likers span two batches.
        for name in ["first", "second", "third"] {
            let (likerToken, _) = try await registerUser(username: name)
            _ = try await stubAPI.likePost(sessionManagementToken: likerToken, postIdentifier: postIdentifier)
        }

        let sut = LikesViewModel(target: .post(postIdentifier: postIdentifier), api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()
        #expect(sut.users.map { $0.username } == ["third", "second"])
        #expect(sut.canLoadMore == true)

        await sut.loadMore()
        // The first batch stays listed rather than being replaced.
        #expect(sut.users.map { $0.username } == ["third", "second", "first"])

        // Paging past the end returns nothing and retires the control.
        await sut.loadMore()
        #expect(sut.users.map { $0.username } == ["third", "second", "first"])
        #expect(sut.canLoadMore == false)
    }

    // --- Comment likes ---

    @Test func testCommentLikers_OnlyTheCommentAuthorMaySeeThem() async throws {
        let (authorToken, author) = try await registerUser(username: "author")
        let postIdentifier = try await makePost(token: authorToken)

        let (commenterToken, commenter) = try await registerUser(username: "commenter")
        let commentData = try await stubAPI.commentOnPost(
            sessionManagementToken: commenterToken, postIdentifier: postIdentifier, commentText: "lovely")
        struct CommentFields: Decodable { let comment_thread_identifier: String; let comment_identifier: String }
        let comment = try JSONDecoder().decode(CommentFields.self, from: commentData)

        let (fanToken, _) = try await registerUser(username: "fan")
        _ = try await stubAPI.likeComment(
            sessionManagementToken: fanToken,
            postIdentifier: postIdentifier,
            commentThreadIdentifier: comment.comment_thread_identifier,
            commentIdentifier: comment.comment_identifier)

        let commenterAccount = "commenter_account"
        try await setupLoggedInUser(user: commenter, token: commenterToken, account: commenterAccount)
        let mine = LikesViewModel(
            target: .comment(
                postIdentifier: postIdentifier,
                commentThreadIdentifier: comment.comment_thread_identifier,
                commentIdentifier: comment.comment_identifier),
            api: stubAPI, keychainHelper: keychainHelper, account: commenterAccount)
        await mine.load()
        #expect(mine.users.map { $0.username } == ["fan"])

        // Owning the post is not owning the comment.
        let authorAccount = "author_account"
        try await setupLoggedInUser(user: author, token: authorToken, account: authorAccount)
        let theirs = LikesViewModel(
            target: .comment(
                postIdentifier: postIdentifier,
                commentThreadIdentifier: comment.comment_thread_identifier,
                commentIdentifier: comment.comment_identifier),
            api: stubAPI, keychainHelper: keychainHelper, account: authorAccount)
        await theirs.load()
        #expect(theirs.users.isEmpty)
        #expect(theirs.errorMessage != nil)
    }

    // --- Target metadata ---

    /// The sheet is titled for what it lists. Written through a view model so
    /// the enum is reached by contextual member lookup rather than by naming the
    /// type, which the test target's second copy of the app sources would make
    /// ambiguous.
    @Test func testTargetTitlesDistinguishPostsFromComments() {
        let postLikes = LikesViewModel(
            target: .post(postIdentifier: "p"), api: stubAPI, keychainHelper: keychainHelper)
        let commentLikes = LikesViewModel(
            target: .comment(postIdentifier: "p", commentThreadIdentifier: "t", commentIdentifier: "c"),
            api: stubAPI, keychainHelper: keychainHelper)

        #expect(postLikes.target.title == "Likes")
        #expect(commentLikes.target.title == "Comment likes")
    }
}
