//
//  PostDetailViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 11/9/25.
//

import Foundation
import Combine

// Use the Networking you've already defined
// (Assuming Networking is available in this scope)

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
    
    /// The text for creating a brand new comment thread
    @Published var newCommentText: String = ""
    
    /// When a user taps "Reply", this is set, which triggers the reply sheet
    @Published var threadToReplyTo: CommentThreadViewData?
    
    @Published var isPostReported = false
    @Published var reportedCommentIds: Set<String> = []
    
    // MARK: - Private Properties
    private let postIdentifier: String
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account : String
    
    // Helper to keep track of requests
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization
    convenience init(postIdentifier: String, api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(postIdentifier: postIdentifier, api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(postIdentifier: String, api: Networking, keychainHelper: KeychainHelperProtocol, account: String) {
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
                                    threadId: threadId,
                                    authorUsername: field.author_username,
                                    body: field.body,
                                    likeCount: field.comment_likes,
                                    createdDate: Self.parseDate(field.creation_time)
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
                NSLog("%@", "Error loading post details: \(error)")
                self.alertMessage = "Failed to load post: \(error.localizedDescription)"
            }
            
            self.isLoading = false
        }
    }
    
    // MARK: - User Actions
    
    func likePost() {
        NSLog("%@", "ACTION: Like post \(postIdentifier)")
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
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                _ = try await api.likePost(sessionManagementToken: token, postIdentifier: postIdentifier)
            } catch {
                NSLog("%@", "Failed to like post: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to like post: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func unlikePost() {
        NSLog("%@", "ACTION: Unliking post \(postIdentifier)")
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
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                _ = try await api.unlikePost(sessionManagementToken: token, postIdentifier: postIdentifier)
            } catch {
                NSLog("%@", "Failed to unlike post: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to unlike post: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func reportPost(reason: String) {
        NSLog("%@", "ACTION: Report post \(postIdentifier) for reason: \(reason)")
        Task {
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                _ = try await api.reportPost(sessionManagementToken: token, postIdentifier: postIdentifier, reason: reason)
                await MainActor.run {
                    isPostReported = true
                }
            } catch {
                NSLog("%@", "Failed to report post: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to report post: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func likeComment(_ comment: CommentViewData) {
        NSLog("%@", "ACTION: Like comment \(comment.id)")
        
        // --- ⬇️ ADDED OPTIMISTIC UPDATE ⬇️ ---
        // Find the index of the thread
        guard let threadIndex = commentThreads.firstIndex(where: { $0.id == comment.threadId }) else {
            NSLog("%@", "Error: Could not find thread for optimistic update.")
            return
        }

        // Find the index of the comment within that thread
        guard let commentIndex = commentThreads[threadIndex].comments.firstIndex(where: { $0.id == comment.id }) else {
            NSLog("%@", "Error: Could not find comment for optimistic update.")
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
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                _ = try await api.likeComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id)
            } catch {
                NSLog("%@", "Failed to like comment: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to like comment: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func unlikeComment(_ comment: CommentViewData) {
        NSLog("%@", "ACTION: unliking comment \(comment.id)")
        
        // --- ⬇️ ADDED OPTIMISTIC UPDATE ⬇️ ---
        guard let threadIndex = commentThreads.firstIndex(where: { $0.id == comment.threadId }) else {
            NSLog("%@", "Error: Could not find thread for optimistic update.")
            return
        }
        guard let commentIndex = commentThreads[threadIndex].comments.firstIndex(where: { $0.id == comment.id }) else {
            NSLog("%@", "Error: Could not find comment for optimistic update.")
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
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                _ = try await api.unlikeComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id)
            } catch {
                NSLog("%@", "Failed to unlike comment: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to unlike comment: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func reportComment(_ comment: CommentViewData, reason: String) {
        NSLog("%@", "ACTION: Report comment \(comment.id) for reason: \(reason)")
        Task {
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                _ = try await api.reportComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id, reason: reason)
                
                await MainActor.run {
                    _ = reportedCommentIds.insert(comment.id)
                }
            } catch {
                NSLog("%@", "Failed to report comment: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to report comment: \(error.localizedDescription)"
                }
            }
        }
    }
    /// Creates a new comment (and thus a new thread) on the post.
    func commentOnPost(commentText: String) {
        guard !commentText.isEmpty else { return }
        
        NSLog("%@", "ACTION: Commenting on post \(postIdentifier)")
        Task {
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                
                _ = try await api.commentOnPost(
                    sessionManagementToken: token,
                    postIdentifier: postIdentifier,
                    commentText: commentText
                )
                
                // Success! Clear the text field and reload all data to show the new comment.
                self.newCommentText = ""
                self.loadAllData() // Reload to get the new thread
                
            } catch {
                self.alertMessage = "Failed to post comment: \(error.localizedDescription)"
            }
        }
    }
    
    /// Replies to an existing comment thread.
    func replyToCommentThread(thread: CommentThreadViewData, commentText: String) {
        guard !commentText.isEmpty else { return }
        
        NSLog("%@", "ACTION: Replying to thread \(thread.id)")
        Task {
            do {
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", userId: "", isIdentityVerified: false)
                let token = userSession.sessionToken
                
                _ = try await api.replyToCommentThread(
                    sessionManagementToken: token,
                    postIdentifier: postIdentifier,
                    commentThreadIdentifier: thread.id,
                    commentText: commentText
                )
                
                // Success! Reload all data to show the new reply.
                self.loadAllData() // Reload to get the new comment in the thread
                
            } catch {
                self.alertMessage = "Failed to post reply: \(error.localizedDescription)"
            }
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
        let creation_time: String
        let updated_time: String
        let comment_likes: Int
    }

    private func decodeSingle<T: Decodable>(from data: Data, type: T.Type) throws -> T {
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func decodeList<T: Decodable>(from data: Data, type: T.Type) throws -> [T] {
        return try JSONDecoder().decode([T].self, from: data)
    }

    // MARK: - Date Parsing

    /// Parses an ISO8601 date string produced by Django, which typically includes
    /// fractional seconds and a `+00:00` timezone offset (e.g. "2024-01-15T10:30:45.123456+00:00").
    /// Falls back to parsing without fractional seconds for older rows, then to `Date()`.
    /// Marked `nonisolated` so it can be called from async task groups without actor hopping.
    /// Formatters are created locally to avoid sharing non-Sendable NSObject state across isolation domains.
    /// Parses an ISO8601 date string produced by Django, which typically includes
    /// fractional seconds and a `+00:00` timezone offset (e.g. "2024-01-15T10:30:45.123456+00:00").
    /// Falls back to parsing without fractional seconds for older rows, then to `Date()`.
    /// Uses `Date.ISO8601FormatStyle` (a value type) to avoid allocating `NSObject`-backed
    /// formatters on each call — safe to call from any isolation domain without extra cost.
    private nonisolated static func parseDate(_ string: String) -> Date {
        if let date = try? Date(string, strategy: .iso8601.year().month().day()
            .time(includingFractionalSeconds: true)
            .timeZone(separator: .omitted)) {
            return date
        }
        if let date = try? Date(string, strategy: .iso8601.year().month().day()
            .time(includingFractionalSeconds: false)
            .timeZone(separator: .omitted)) {
            return date
        }
        return Date()
    }
}
