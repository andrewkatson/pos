//
//  PostDetailViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 11/9/25.
//

import Foundation
import Combine

// Use the APIProtocol you've already defined
// (Assuming APIProtocol is available in this scope)

@MainActor
final class PostDetailViewModel: ObservableObject {
    
    // MARK: - Published State
    @Published var postDetail: PostDisplayData?
    @Published var commentThreads: [CommentThreadViewData] = []
    @Published var isLoading = true
    @Published var alertMessage: String?
    
    // State for presentation
    @Published var showReportSheetForPost = false
    @Published var commentToReport: CommentViewData? // Use item-based sheet
    
    // MARK: - Private Properties
    private let postIdentifier: String
    private let api: APIProtocol
    private let keychainHelper: KeychainHelperProtocol
    private let account : String
    
    // Helper to keep track of requests
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization
    convenience init(postIdentifier: String, api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        self.init(postIdentifier: postIdentifier, api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(postIdentifier: String, api: APIProtocol, keychainHelper: KeychainHelperProtocol, account: String) {
        self.postIdentifier = postIdentifier
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
        
        loadAllData()
    }
    
    // MARK: - Data Fetching
    
    func loadAllData() {
        isLoading = true
        
        Task {
            do {
                // 1. Fetch the main post details
                let postData = try await api.getPostDetails(postIdentifier: postIdentifier)
                let postFields = try self.decodeSingle(from: postData, type: PostDetailsFields.self)
                
                self.postDetail = PostDisplayData(
                    id: postFields.post_identifier,
                    imageURL: postFields.image_url,
                    caption: postFields.caption,
                    likeCount: postFields.post_likes,
                    authorUsername: postFields.author_username
                )
                
                // 2. Fetch the list of comment thread IDs for this post
                let threadListData = try await api.getCommentsForPost(postIdentifier: postIdentifier, batch: 0)
                let threadIDFields = try self.decodeList(from: threadListData, type: ThreadIDFields.self)
                let threadIdentifiers = threadIDFields.map { $0.comment_thread_identifier }
                
                // 3. Fetch all comments for *each* thread in parallel
                var loadedThreads: [CommentThreadViewData] = []
                
                try await withThrowingTaskGroup(of: [CommentViewData].self) { group in
                    for threadId in threadIdentifiers {
                        group.addTask {
                            let commentsData = try await self.api.getCommentsForThread(commentThreadIdentifier: threadId, batch: 0)
                            
                            // *** FIXED: Removed 'await' here, as decodeList is not async ***
                            let commentFields = try await self.decodeList(from: commentsData, type: CommentFields.self)
                            
                            // 4. Convert network models to View Models
                            return commentFields.map { field in
                                CommentViewData(
                                    id: field.comment_identifier,
                                    threadId: threadId, // We know this from the context
                                    authorUsername: field.author_username,
                                    body: field.body,
                                    likeCount: field.comment_likes,
                                    // Handle date conversion
                                    createdDate: ISO8601DateFormatter().date(from: field.comment_creation_time) ?? Date()
                                )
                            }
                        }
                    }
                    
                    // 5. Collect results as they complete
                    for try await commentList in group {
                        if !commentList.isEmpty {
                            // Sort comments by date (oldest first)
                            let sortedComments = commentList.sorted { $0.createdDate < $1.createdDate }
                            loadedThreads.append(CommentThreadViewData(comments: sortedComments))
                        }
                    }
                }
                
                // Sort threads by their first comment's date
                self.commentThreads = loadedThreads.sorted {
                    ($0.comments.first?.createdDate ?? Date()) < ($1.comments.first?.createdDate ?? Date())
                }
                
            } catch {
                print("Error loading post details: \(error)")
                self.alertMessage = "Failed to load post: \(error.localizedDescription)"
            }
            
            self.isLoading = false
        }
    }
    
    // MARK: - User Actions
    
    func likePost() {
        print("ACTION: Like post \(postIdentifier)")
        // Stub: Increment like count locally for instant feedback
        if var post = postDetail {
            post = PostDisplayData(
                id: post.id,
                imageURL: post.imageURL,
                caption: post.caption,
                likeCount: post.likeCount + 1, // Optimistic update
                authorUsername: post.authorUsername
            )
            self.postDetail = post
        }
        
        Task {
            let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
            let token = userSession.sessionToken
            _ = try await api.likePost(sessionManagementToken: token, postIdentifier: postIdentifier)
        }
    }
    
    func unlikePost() {
        print("ACTION: Unliking post \(postIdentifier)")
        // Stub: Decrement like count locally for instant feedback
        if var post = postDetail {
            post = PostDisplayData(
                id: post.id,
                imageURL: post.imageURL,
                caption: post.caption,
                likeCount: max(0, post.likeCount - 1), // Optimistic update
                authorUsername: post.authorUsername
            )
            self.postDetail = post
        }
        
        Task {
            let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
            let token = userSession.sessionToken
            _ = try await api.unlikePost(sessionManagementToken: token, postIdentifier: postIdentifier)
        }
    }
    
    func reportPost(reason: String) {
        print("ACTION: Report post \(postIdentifier) for reason: \(reason)")
        Task {
            let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
            let token = userSession.sessionToken
            _ = try await api.reportPost(sessionManagementToken: token, postIdentifier: postIdentifier, reason: reason)
        }
    }
    
    func likeComment(_ comment: CommentViewData) {
        print("ACTION: Like comment \(comment.id)")
        
        // --- ⬇️ ADDED OPTIMISTIC UPDATE ⬇️ ---
        // Find the index of the thread
        guard let threadIndex = commentThreads.firstIndex(where: { $0.id == comment.threadId }) else {
            print("Error: Could not find thread for optimistic update.")
            return
        }
        
        // Find the index of the comment within that thread
        guard let commentIndex = commentThreads[threadIndex].comments.firstIndex(where: { $0.id == comment.id }) else {
            print("Error: Could not find comment for optimistic update.")
            return
        }
        
        // Get the old comment
        let oldComment = commentThreads[threadIndex].comments[commentIndex]
        
        // Create a new comment with the updated like count
        let newComment = CommentViewData(
            id: oldComment.id,
            threadId: oldComment.threadId,
            authorUsername: oldComment.authorUsername,
            body: oldComment.body,
            likeCount: oldComment.likeCount + 1, // The update
            createdDate: oldComment.createdDate
        )
        
        // Replace the old comment with the new one in the published array
        commentThreads[threadIndex].comments[commentIndex] = newComment
        // --- ⬆️ END OF OPTIMISTIC UPDATE ⬆️ ---

        Task {
            let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
            let token = userSession.sessionToken
            _ = try await api.likeComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id)
        }
    }
    
    func unlikeComment(_ comment: CommentViewData) {
        print("ACTION: unliking comment \(comment.id)")
        
        // --- ⬇️ ADDED OPTIMISTIC UPDATE ⬇️ ---
        guard let threadIndex = commentThreads.firstIndex(where: { $0.id == comment.threadId }) else {
            print("Error: Could not find thread for optimistic update.")
            return
        }
        guard let commentIndex = commentThreads[threadIndex].comments.firstIndex(where: { $0.id == comment.id }) else {
            print("Error: Could not find comment for optimistic update.")
            return
        }
        
        let oldComment = commentThreads[threadIndex].comments[commentIndex]
        
        // Ensure likes don't go below zero
        let newLikeCount = max(0, oldComment.likeCount - 1)
        
        let newComment = CommentViewData(
            id: oldComment.id,
            threadId: oldComment.threadId,
            authorUsername: oldComment.authorUsername,
            body: oldComment.body,
            likeCount: newLikeCount, // The update
            createdDate: oldComment.createdDate
        )
        
        commentThreads[threadIndex].comments[commentIndex] = newComment
        // --- ⬆️ END OF OPTIMISTIC UPDATE ⬆️ ---

        Task {
            let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
            let token = userSession.sessionToken
            _ = try await api.unlikeComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id)
        }
    }
    
    func reportComment(_ comment: CommentViewData, reason: String) {
        print("ACTION: Report comment \(comment.id) for reason: \(reason)")
        Task {
            let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
            let token = userSession.sessionToken
            _ = try await api.reportComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id, reason: reason)
        }
    }
    
    // MARK: - Private Decoding Helpers
    
    // These match the 'Fields' structs in your stub API
    private struct PostDetailsFields: Decodable {
        let post_identifier: String
        let image_url: String
        let caption: String
        let post_likes: Int
        let author_username: String
    }
    
    private struct ThreadIDFields: Decodable {
        let comment_thread_identifier: String
    }
    
    private struct CommentFields: Decodable {
        let comment_identifier: String
        let body: String
        let author_username: String
        let comment_creation_time: String
        let comment_updated_time: String
        let comment_likes: Int
    }
    
    // These helpers handle the specific double-encoded JSON from your stub
    private struct APIResponseWrapper: Decodable {
        let response_list: String
    }
    
    private struct DjangoSerializedObject<F: Decodable>: Decodable {
        let fields: F
    }

    private func decodeSingle<T: Decodable>(from data: Data, type: T.Type) throws -> T {
        let decoder = JSONDecoder()
        let wrapper = try decoder.decode(APIResponseWrapper.self, from: data)
        guard let innerData = wrapper.response_list.data(using: .utf8) else {
            throw SerializationError()
        }
        let serializedObject = try decoder.decode(DjangoSerializedObject<T>.self, from: innerData)
        return serializedObject.fields
    }

    private func decodeList<T: Decodable>(from data: Data, type: T.Type) throws -> [T] {
        let decoder = JSONDecoder()
        let wrapper = try decoder.decode(APIResponseWrapper.self, from: data)
        guard let innerData = wrapper.response_list.data(using: .utf8) else {
            throw SerializationError()
        }
        let serializedObjects = try decoder.decode([DjangoSerializedObject<T>].self, from: innerData)
        return serializedObjects.map { $0.fields }
    }
}
