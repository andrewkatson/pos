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
    let testService = "positive-only-social.Positive-Only-Social"

    // --- Test Setup ---
    init() {
        keychainHelper = KeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // --- Local Decoder Structs (for test setup) ---
    // These mirror the structs used by the stub API to decode responses
    
    /// A generic wrapper for the stub API's double-encoded JSON
    private struct APIWrapperResponse: Decodable {
        let response_list: String
    }
    
    /// A generic wrapper for the "fields" object inside the JSON
    private struct DjangoObject<F: Decodable>: Decodable {
        let fields: F
    }
    
    // MARK: - Test Helpers
    
    /// Helper to pause the test and let async/debounce tasks complete.
    private func yield(for duration: Duration = .seconds(0.5)) async {
        // Using a slightly shorter yield as VM tasks are not debounced
        try? await Task.sleep(for: duration)
    }
    
    /// Helper to register a user and return their session token.
    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        
        struct RegFields: Decodable { let session_management_token: String }
        
        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let innerData = wrapper.response_list.data(using: .utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoObject<RegFields>.self, from: innerData)
        
        return djangoObject.fields.session_management_token
    }
    
    /// Helper to log in the "testuser" and save their token to the keychain
    private func setupLoggedInUser(username: String, account: String) async throws -> String {
        let token = try await registerUserAndGetToken(username: username)
        let userSession = UserSession(sessionToken: token, username: username, isIdentityVerified: false)
        try keychainHelper.save(userSession, for: testService, account: account)
        return token
    }
    
    /// Helper to create a post and return its identifier
    private func makePostAndGetID(token: String, caption: String) async throws -> String {
        let data = try await stubAPI.makePost(sessionManagementToken: token, imageURL: "my.image/1", caption: caption)
        
        struct PostFields: Decodable { let post_identifier: String }
        
        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let innerData = wrapper.response_list.data(using: .utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoObject<PostFields>.self, from: innerData)
        
        return djangoObject.fields.post_identifier
    }
    
    /// Helper to create a comment and return its thread and comment identifiers
    private func commentOnPostAndGetIDs(token: String, postID: String, body: String) async throws -> (threadID: String, commentID: String) {
        let data = try await stubAPI.commentOnPost(sessionManagementToken: token, postIdentifier: postID, commentText: body)
        
        struct CommentFields: Decodable {
            let comment_thread_identifier: String
            let comment_identifier: String
        }
        
        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let innerData = wrapper.response_list.data(using: .utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoObject<CommentFields>.self, from: innerData)
        
        return (djangoObject.fields.comment_thread_identifier, djangoObject.fields.comment_identifier)
    }

    /// Helper to reply to a comment and return its new comment identifier
    private func replyToCommentAndGetID(token: String, postID: String, threadID: String, body: String) async throws -> String {
        let data = try await stubAPI.replyToCommentThread(sessionManagementToken: token, postIdentifier: postID, commentThreadIdentifier: threadID, commentText: body)
        
        struct ReplyFields: Decodable { let comment_identifier: String }
        
        let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: data)
        let innerData = wrapper.response_list.data(using: .utf8)!
        let djangoObject = try JSONDecoder().decode(DjangoObject<ReplyFields>.self, from: innerData)
        
        return djangoObject.fields.comment_identifier
    }
    
    /// A master helper to set up a full environment for testing
    private func setupTestEnvironment(account: String) async throws -> (sut: PostDetailViewModel, postID: String, threadID: String, commentID: String) {
        // 1. Create a user, log them in, and save to keychain
        let postOwnerToken = try await setupLoggedInUser(username: "postOwner", account: account)
        
        // 2. Create a second user for commenting
        let commenterToken = try await registerUserAndGetToken(username: "commenter")
        
        // 3. Create a post
        let postID = try await makePostAndGetID(token: postOwnerToken, caption: "Test Post 1")
        
        // 4. Create a comment thread
        let (threadID, commentID) = try await commentOnPostAndGetIDs(token: commenterToken, postID: postID, body: "First comment")
        
        // 5. Create a reply in that thread
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
        
        // And: The comment threads should be loaded
        #expect(sut.commentThreads.count == 1, "Should be 1 comment thread")
        #expect(sut.commentThreads.first?.comments.count == 2, "Thread should have 2 comments")
        
        // And: Comments should be sorted by creation date (oldest first)
        let firstComment = sut.commentThreads.first?.comments.first
        let secondComment = sut.commentThreads.first?.comments.last
        
        #expect(firstComment?.body == "First comment")
        #expect(firstComment?.authorUsername == "commenter")
        #expect(secondComment?.body == "Reply comment")
        #expect(secondComment?.authorUsername == "postOwner")
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
        
        // And: We should find the new comment, authored by the SUT's user ("postOwner")
        let newThread = sut.commentThreads.first {
            $0.comments.first?.body == newCommentText
        }
        #expect(newThread != nil, "New comment thread was not found")
        #expect(newThread?.comments.count == 1)
        #expect(newThread?.comments.first?.authorUsername == "postOwner")
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
        #expect(newReply?.authorUsername == "postOwner", "New reply author is incorrect")
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
