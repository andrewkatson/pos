//
//  Positive_Only_SocialTests_PostDetailViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 11/9/25.
//

//
//  Positive_Only_SocialTests_PostDetailViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 11/10/25.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_PostDetailViewModel {

    // --- SUT & Stub ---
    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!
    
    // --- Keychain Test Fixtures ---

    // --- Test Setup ---
    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // MARK: - Test Helpers
    
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
    private func setupLoggedInUser(username: String, account: String) async throws -> String {
        let token = try await registerUserAndGetToken(username: username)
        let userSession = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)
        return token
    }
    
    /// Helper to create a post and return its identifier
    private func makePostAndGetID(token: String, caption: String) async throws -> String {
        let data = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/1", caption: caption)
        
        struct PostFields: Decodable { let post_identifier: String }
        return try JSONDecoder().decode(PostFields.self, from: data).post_identifier
    }
    
    /// Helper to create a comment and return its thread and comment identifiers
    private func commentOnPostAndGetIDs(token: String, postID: String, body: String) async throws -> (threadID: String, commentID: String) {
        let data = try await stubAPI.commentOnPost(sessionManagementToken: token, postIdentifier: postID, commentText: body)
        
        struct CommentFields: Decodable {
            let comment_thread_identifier: String
            let comment_identifier: String
        }
        
        let decoded = try JSONDecoder().decode(CommentFields.self, from: data)
        return (decoded.comment_thread_identifier, decoded.comment_identifier)
    }

    /// Helper to reply to a comment and return its new comment identifier
    private func replyToCommentAndGetID(token: String, postID: String, threadID: String, body: String) async throws -> String {
        let data = try await stubAPI.replyToCommentThread(sessionManagementToken: token, postIdentifier: postID, commentThreadIdentifier: threadID, commentText: body)
        
        struct ReplyFields: Decodable { let comment_identifier: String }
        return try JSONDecoder().decode(ReplyFields.self, from: data).comment_identifier
    }
    
    /// A master helper to set up a full environment for testing.
    ///
    /// The signed-in user is a "viewer" who authored neither the post nor the
    /// comment, so the like actions are allowed. Self-like prevention is covered
    /// by the dedicated own-content tests below.
    private func setupTestEnvironment(account: String) async throws -> (sut: PostDetailViewModel, postID: String, threadID: String, commentID: String) {
        // 1. The signed-in user — a viewer, not the post/comment author.
        _ = try await setupLoggedInUser(username: "viewer", account: account)

        // 2. Create the post author and a separate commenter.
        let postOwnerToken = try await registerUserAndGetToken(username: "postOwner")
        let commenterToken = try await registerUserAndGetToken(username: "commenter")

        // 3. Create a post (authored by postOwner)
        let postID = try await makePostAndGetID(token: postOwnerToken, caption: "Test Post 1")

        // 4. Create a comment thread (authored by commenter)
        let (threadID, commentID) = try await commentOnPostAndGetIDs(token: commenterToken, postID: postID, body: "First comment")

        // 5. Create a reply in that thread (authored by postOwner)
        _ = try await replyToCommentAndGetID(token: postOwnerToken, postID: postID, threadID: threadID, body: "Reply comment")

        // 6. Create the SUT. This triggers `loadAllData()`
        let sut = PostDetailViewModel(postIdentifier: postID, api: stubAPI, keychainHelper: keychainHelper, account: account)

        // 7. Wait for all loading to finish
        await yield()

        return (sut, postID, threadID, commentID)
    }

    // --- Loading Tests ---
    
    @Test func testLoadAllData_Success_PopulatesPostAndComments() async throws {
        // When: The environment is set up and SUT is initialized
        let (sut, postID, _, _) = try await setupTestEnvironment(account: "loadAllData_account")
        
        // Then: The SUT should be done loading
        #expect(sut.isLoading == false)
        
        // And: The post details should be loaded
        #expect(sut.postDetail != nil)
        #expect(sut.postDetail?.id == postID)
        #expect(sut.postDetail?.caption == "Test Post 1")
        #expect(sut.postDetail?.authorUsername == "postOwner")
        // And: The current user has not liked the post, so it seeds as not-liked
        #expect(sut.postDetail?.isLiked == false)

        // And: The comment threads should be loaded
        #expect(sut.commentThreads.count == 1, "Should be 1 comment thread")
        #expect(sut.commentThreads.first?.comments.count == 2, "Thread should have 2 comments")
        // And: Comments seed as not-liked for a user who hasn't liked them
        #expect(sut.commentThreads.first?.comments.first?.isLiked == false)
        
        // And: Comments should be sorted by creation date (oldest first)
        let firstComment = sut.commentThreads.first?.comments.first
        let secondComment = sut.commentThreads.first?.comments.last
        
        #expect(firstComment?.body == "First comment")
        #expect(firstComment?.authorUsername == "commenter")
        #expect(secondComment?.body == "Reply comment")
        #expect(secondComment?.authorUsername == "postOwner")
    }

    @Test func testRefresh_PullsLatestCommentsFromBackend() async throws {
        // Given: A fully loaded SUT with one comment thread
        let (sut, postID, _, _) = try await setupTestEnvironment(account: "refresh_account")
        #expect(sut.commentThreads.count == 1, "Pre-condition: Should have 1 thread")

        // And: Another user adds a brand new comment thread on the backend
        let otherCommenterToken = try await registerUserAndGetToken(username: "commenter2")
        _ = try await commentOnPostAndGetIDs(token: otherCommenterToken, postID: postID, body: "Fresh comment")

        // When: We pull-to-refresh
        await sut.refresh()

        // Then: The newest data is pulled in and loading is finished
        #expect(sut.isLoading == false)
        #expect(sut.commentThreads.count == 2, "Refreshed feed should include the new thread")
    }

    @Test func testRefresh_WhileAlreadyLoading_DoesNotReload() async throws {
        // Given: A fully loaded SUT with one comment thread
        let (sut, postID, _, _) = try await setupTestEnvironment(account: "refreshWhileLoading_account")
        #expect(sut.commentThreads.count == 1, "Pre-condition: Should have 1 thread")

        // And: A new comment thread appears on the backend
        let otherCommenterToken = try await registerUserAndGetToken(username: "commenter2")
        _ = try await commentOnPostAndGetIDs(token: otherCommenterToken, postID: postID, body: "Fresh comment")

        // And: A load is already in flight
        sut.isLoading = true

        // When: We pull-to-refresh
        await sut.refresh()

        // Then: The refresh is skipped (so a stale in-flight load can't be
        // raced), and the new thread is NOT pulled in.
        #expect(sut.commentThreads.count == 1, "Refresh should be a no-op while a load is already in flight")
    }

    // --- Post Action Tests ---

    @Test func testLikePost_OptimisticUpdate_IncrementsCount() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, _) = try await setupTestEnvironment(account: "likePostOptimisticUpdate_account")
        let initialLikeCount = sut.postDetail?.likeCount
        #expect(initialLikeCount == 0, "Pre-condition: Post likes should be 0")
        
        // When: The post is liked
        sut.likePost()
        
        // Then: The like count is optimistically updated immediately
        #expect(sut.postDetail?.likeCount == 1, "Like count should immediately increment")
        // And: The heart reflects the liked state
        #expect(sut.postDetail?.isLiked == true, "Post should be marked liked")

        // And: After the network call finishes, the count remains 1
        await yield()
        #expect(sut.postDetail?.likeCount == 1)
    }
    
    @Test func testUnlikePost_OptimisticUpdate_DecrementsCount() async throws {
        // Given: A fully loaded SUT with a liked post
        let (sut, _, _, _) = try await setupTestEnvironment(account: "unlikePostOptimisticUpdate_account")
        sut.likePost()
        await yield()
        #expect(sut.postDetail?.likeCount == 1, "Pre-condition: Post likes should be 1")
        
        // When: The post is unliked
        sut.unlikePost()
        
        // Then: The like count is optimistically updated immediately
        #expect(sut.postDetail?.likeCount == 0, "Like count should immediately decrement")
        // And: The heart reflects the not-liked state
        #expect(sut.postDetail?.isLiked == false, "Post should be marked not liked")

        // And: After the network call finishes, the count remains 0
        await yield()
        #expect(sut.postDetail?.likeCount == 0)
    }
    
    @Test func testUnlikePost_AtZero_StaysAtZero() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, _) = try await setupTestEnvironment(account: "unlikePostAtZero_account")
        #expect(sut.postDetail?.likeCount == 0, "Pre-condition: Post likes should be 0")
        
        // When: The post is unliked
        sut.unlikePost()
        
        // Then: The like count stays at 0
        #expect(sut.postDetail?.likeCount == 0, "Like count should not go below 0")
    }
    
    // --- Comment Action Tests ---
    
    @Test func testLikeComment_OptimisticUpdate_IncrementsCount() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, commentID) = try await setupTestEnvironment(account: "likeCommentOptimisticUpdate_account")
        guard let comment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID }) else {
            #expect(Bool(false), "Test setup error: Could not find comment")
            return
        }
        #expect(comment.likeCount == 0, "Pre-condition: Comment likes should be 0")
        
        // When: The comment is liked
        sut.likeComment(comment)
        
        // Then: The like count is optimistically updated immediately
        let updatedComment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID })
        #expect(updatedComment?.likeCount == 1, "Like count should immediately increment")
        // And: The heart reflects the liked state
        #expect(updatedComment?.isLiked == true, "Comment should be marked liked")

        // And: After the network call finishes, the count remains 1
        await yield()
        #expect(sut.commentThreads.first?.comments.first?.likeCount == 1)
    }
    
    @Test func testUnlikeComment_OptimisticUpdate_DecrementsCount() async throws {
        // Given: A fully loaded SUT with a liked comment
        let (sut, _, _, commentID) = try await setupTestEnvironment(account: "unlikeCommentOptimisticUpdate_account")
        guard let comment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID }) else {
            #expect(Bool(false), "Test setup error: Could not find comment")
            return
        }
        
        sut.likeComment(comment) // Like it first
        await yield()
        #expect(sut.commentThreads.first?.comments.first?.likeCount == 1, "Pre-condition: Comment likes should be 1")

        // When: The comment is unliked
        guard let likedComment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID }) else {
            #expect(Bool(false), "Test setup error: Could not find liked comment")
            return
        }
        sut.unlikeComment(likedComment)
        
        // Then: The like count is optimistically updated immediately
        let unlikedComment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID })
        #expect(unlikedComment?.likeCount == 0, "Like count should immediately decrement")
        // And: The heart reflects the not-liked state
        #expect(unlikedComment?.isLiked == false, "Comment should be marked not liked")

        // And: After the network call finishes, the count remains 0
        await yield()
        #expect(sut.commentThreads.first?.comments.first?.likeCount == 0)
    }
    
    @Test func testUnlikeComment_AtZero_StaysAtZero() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, commentID) = try await setupTestEnvironment(account: "unlikeCommentAtZero_account")
        guard let comment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID }) else {
            #expect(Bool(false), "Test setup error: Could not find comment")
            return
        }
        #expect(comment.likeCount == 0, "Pre-condition: Comment likes should be 0")
        
        // When: The comment is unliked
        sut.unlikeComment(comment)
        
        // Then: The like count stays at 0
        let updatedComment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID })
        #expect(updatedComment?.likeCount == 0, "Like count should not go below 0")
    }

    // --- Self-Like Prevention Tests ---

    /// Sets up an environment where the signed-in user authored both the post
    /// and the single comment, so both are "own" content.
    private func setupOwnContentEnvironment(account: String) async throws -> (sut: PostDetailViewModel, postID: String, commentID: String) {
        // The signed-in user authors everything here.
        let authorToken = try await setupLoggedInUser(username: "author", account: account)
        let postID = try await makePostAndGetID(token: authorToken, caption: "My own post")
        let (_, commentID) = try await commentOnPostAndGetIDs(token: authorToken, postID: postID, body: "My own comment")

        let sut = PostDetailViewModel(postIdentifier: postID, api: stubAPI, keychainHelper: keychainHelper, account: account)
        await yield()
        return (sut, postID, commentID)
    }

    @Test func testLikePost_OwnPost_DoesNothing() async throws {
        // Given: The signed-in user is viewing their own post
        let (sut, _, _) = try await setupOwnContentEnvironment(account: "likeOwnPost_account")
        #expect(sut.isOwnPost, "Pre-condition: the post should be the user's own")
        #expect(sut.postDetail?.likeCount == 0, "Pre-condition: Post likes should be 0")

        // When: They attempt to like their own post
        sut.likePost()

        // Then: Nothing happens — no optimistic like is applied
        #expect(sut.postDetail?.likeCount == 0, "Own post like count should not change")
        #expect(sut.postDetail?.isLiked == false, "Own post should not be marked liked")
    }

    @Test func testLikeComment_OwnComment_DoesNothing() async throws {
        // Given: The signed-in user is viewing their own comment
        let (sut, _, commentID) = try await setupOwnContentEnvironment(account: "likeOwnComment_account")
        guard let comment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID }) else {
            #expect(Bool(false), "Test setup error: Could not find comment")
            return
        }
        #expect(sut.isOwnComment(comment), "Pre-condition: the comment should be the user's own")
        #expect(comment.likeCount == 0, "Pre-condition: Comment likes should be 0")

        // When: They attempt to like their own comment
        sut.likeComment(comment)

        // Then: Nothing happens — no optimistic like is applied
        let updatedComment = sut.commentThreads.first?.comments.first(where: { $0.id == commentID })
        #expect(updatedComment?.likeCount == 0, "Own comment like count should not change")
        #expect(updatedComment?.isLiked == false, "Own comment should not be marked liked")
    }

    @Test func testCommentOnPost_Success_ReloadsData() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, _) = try await setupTestEnvironment(account: "commentOnPost_account")
        #expect(sut.commentThreads.count == 1, "Pre-condition: Should have 1 thread")
        
        let newCommentText = "This is a new comment thread"
        sut.newCommentText = newCommentText // Set the text in the VM
        
        // When: We comment on the post
        sut.commentOnPost(commentText: newCommentText)
        
        // And: We wait for the API call and the reload
        await yield()
        
        // Then: The text field should be cleared
        #expect(sut.newCommentText == "", "Text field should be cleared on success")
        
        // And: The number of threads should increase
        #expect(sut.commentThreads.count == 2, "Should have 2 threads after commenting")
        
        // And: We should find the new comment, authored by the SUT's user ("viewer")
        let newThread = sut.commentThreads.first {
            $0.comments.first?.body == newCommentText
        }
        #expect(newThread != nil, "New comment thread was not found")
        #expect(newThread?.comments.count == 1)
        #expect(newThread?.comments.first?.authorUsername == "viewer")
    }
    
    @Test func testReplyToCommentThread_Success_ReloadsData() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, _) = try await setupTestEnvironment(account: "replyToComment_account")
        guard let threadToReplyTo = sut.commentThreads.first else {
            #expect(Bool(false), "Test setup error: Could not find thread")
            return
        }
        #expect(sut.commentThreads.count == 1, "Pre-condition: Should have 1 thread")
        #expect(threadToReplyTo.comments.count == 2, "Pre-condition: Thread should have 2 comments")
        
        let newReplyText = "This is a new reply"
        
        // When: We reply to the thread
        sut.replyToCommentThread(thread: threadToReplyTo, commentText: newReplyText)
        
        // And: We wait for the API call and the reload
        await yield()
        
        // Then: The number of threads should stay the same
        #expect(sut.commentThreads.count == 1, "Should still have 1 thread")
        
        // And: The number of comments in that thread should increase
        #expect(sut.commentThreads.first?.comments.count == 3, "Thread should now have 3 comments")
        
        // And: The new comment should be the last one (most recent)
        let newReply = sut.commentThreads.first?.comments.last
        #expect(newReply?.body == newReplyText, "New reply text is incorrect")
        #expect(newReply?.authorUsername == "viewer", "New reply author is incorrect")
    }
    
    @Test func testCommentOnPost_EmptyText_DoesNotReload() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, _) = try await setupTestEnvironment(account: "commentOnPostEmpty_account")
        #expect(sut.commentThreads.count == 1, "Pre-condition: Should have 1 thread")
        
        // When: We try to comment with empty text
        sut.commentOnPost(commentText: "")
        
        // And: We wait
        await yield()
        
        // Then: The number of threads should NOT change (reload was not called)
        #expect(sut.commentThreads.count == 1, "Should still have 1 thread")
        #expect(sut.alertMessage == nil, "No alert should be shown for an empty guard")
    }
    
    @Test func testReplyToCommentThread_EmptyText_DoesNotReload() async throws {
        // Given: A fully loaded SUT
        let (sut, _, _, _) = try await setupTestEnvironment(account: "replyToCommentEmpty_account")
        guard let threadToReplyTo = sut.commentThreads.first else {
            #expect(Bool(false), "Test setup error: Could not find thread")
            return
        }
        #expect(threadToReplyTo.comments.count == 2, "Pre-condition: Thread should have 2 comments")
        
        // When: We try to reply with empty text
        sut.replyToCommentThread(thread: threadToReplyTo, commentText: "")
        
        // And: We wait
        await yield()
        
        // Then: The number of comments should NOT change (reload was not called)
        #expect(sut.commentThreads.first?.comments.count == 2, "Thread should still have 2 comments")
        #expect(sut.alertMessage == nil, "No alert should be shown for an empty guard")
    }
}
