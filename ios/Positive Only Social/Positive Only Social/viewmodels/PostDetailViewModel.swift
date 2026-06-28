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

    /// Drives the long-press action menu for the post. The menu offers either
    /// "Report" (others' posts) or "Delete" (the user's own post) — never both,
    /// so you can't report your own content.
    @Published var showActionSheetForPost = false

    /// The comment whose long-press action menu is showing, if any. Like the
    /// post action menu, it offers "Report" or "Delete" depending on ownership.
    @Published var commentForAction: CommentViewData?

    /// Set once the post has been deleted so the view can pop back — the post no
    /// longer exists to display.
    @Published var postWasDeleted = false
    
    /// The text for creating a brand new comment thread
    @Published var newCommentText: String = ""
    
    /// When a user taps "Reply", this is set, which triggers the reply sheet
    @Published var threadToReplyTo: CommentThreadViewData?
    
    @Published var isPostReported = false
    @Published var reportedCommentIds: Set<String> = []

    /// The signed-in user's username, loaded alongside the post. The backend
    /// rejects liking your own post/comment, so the UI hides the like control
    /// (and the like actions are guarded) for content this user authored.
    @Published private(set) var currentUsername: String?

    /// Whether the loaded post was authored by the signed-in user.
    var isOwnPost: Bool {
        guard let post = postDetail, let username = currentUsername else { return false }
        return post.authorUsername == username
    }

    /// Whether the given comment was authored by the signed-in user.
    func isOwnComment(_ comment: CommentViewData) -> Bool {
        comment.authorUsername == currentUsername
    }
    
    // MARK: - Private Properties
    private let postIdentifier: String
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService
    
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
            await performLoad()
        }
    }

    /// Pull-to-refresh entry point. Awaitable so SwiftUI's `.refreshable`
    /// keeps the spinner visible until the post and comments have reloaded.
    func refresh() async {
        // Don't start a refresh while another load is already in flight (the
        // initial `loadAllData()` or an action-triggered reload). Two concurrent
        // loads both write `postDetail`/`commentThreads`, so an older response
        // could otherwise overwrite the fresher refreshed data.
        guard !isLoading else { return }
        isLoading = true
        await performLoad()
    }

    private func performLoad() async {
            do {
                // These authenticated GETs need the session token so the backend can
                // report whether the current user has liked the post / each comment.
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot load post details")
                    self.alertMessage = "Session not found."
                    self.isLoading = false
                    return
                }
                let token = userSession.sessionToken
                self.currentUsername = userSession.username

                // 1. Fetch the main post details
                let postData = try await api.getPostDetails(sessionManagementToken: token, postIdentifier: postIdentifier)
                let postFields = try self.decodeSingle(from: postData, type: PostDetailsFields.self)

                self.postDetail = PostDisplayData(
                    id: postFields.post_identifier,
                    imageURL: postFields.image_url,
                    caption: postFields.caption,
                    likeCount: postFields.post_likes,
                    isLiked: postFields.is_liked,
                    authorUsername: postFields.author_username
                )

                // 2. Fetch the list of comment thread IDs for this post
                let threadListData = try await api.getCommentsForPost(sessionManagementToken: token, postIdentifier: postIdentifier, batch: 0)
                let threadIDFields = try self.decodeList(from: threadListData, type: ThreadIDFields.self)
                let threadIdentifiers = threadIDFields.map { $0.comment_thread_identifier }

                // 3. Fetch all comments for *each* thread in parallel
                var loadedThreads: [CommentThreadViewData] = []

                try await withThrowingTaskGroup(of: [CommentViewData].self) { group in
                    for threadId in threadIdentifiers {
                        group.addTask {
                            let commentsData = try await self.api.getCommentsForThread(sessionManagementToken: token, commentThreadIdentifier: threadId, batch: 0)

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
                                    isLiked: field.is_liked,
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
                // A cancelled load (e.g. SwiftUI tearing down a pull-to-refresh
                // task) is not a real failure — keep the existing data and stay
                // quiet so routine cancellations don't pollute the error logs.
                if error.isCancellation {
                    NSLog("%@", "Post details load cancelled")
                } else {
                    NSLog("%@", "Error loading post details: \(error)")
                    self.alertMessage = "Failed to load post: \(error.localizedDescription)"
                }
            }

            self.isLoading = false
    }

    // MARK: - User Actions
    
    func likePost() {
        // The backend rejects liking your own post; don't optimistically like it.
        guard !isOwnPost else { return }
        NSLog("%@", "ACTION: Like post \(postIdentifier)")
        // Stub: Increment like count locally for instant feedback
        if var post = postDetail {
            post = PostDisplayData(
                id: post.id,
                imageURL: post.imageURL,
                caption: post.caption,
                likeCount: post.likeCount + 1, // Optimistic update
                isLiked: true,
                authorUsername: post.authorUsername
            )
            self.postDetail = post
        }
        
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot like post")
                    self.alertMessage = "Session not found."
                    return
                }
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
                isLiked: false,
                authorUsername: post.authorUsername
            )
            self.postDetail = post
        }
        
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot unlike post")
                    self.alertMessage = "Session not found."
                    return
                }
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
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot report post")
                    self.alertMessage = "Session not found."
                    return
                }
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
    
    /// Deletes the user's own post, then signals the view to pop back since the
    /// post no longer exists. Only reachable from the action menu on an own post.
    func deletePost() {
        NSLog("%@", "ACTION: Delete post \(postIdentifier)")
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot delete post")
                    self.alertMessage = "Session not found."
                    return
                }
                let token = userSession.sessionToken
                _ = try await api.deletePost(sessionManagementToken: token, postIdentifier: postIdentifier)
                await MainActor.run {
                    self.postWasDeleted = true
                    // Tell the Home grid to drop this post so its now-deleted
                    // image doesn't linger as an empty grey tile (issue #256).
                    NotificationCenter.default.post(name: .postDeleted, object: self.postIdentifier)
                }
            } catch {
                NSLog("%@", "Failed to delete post: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to delete post: \(error.localizedDescription)"
                }
            }
        }
    }

    /// Deletes one of the user's own comments, then reloads so it disappears from
    /// the thread. Only reachable from the action menu on an own comment.
    func deleteComment(_ comment: CommentViewData) {
        NSLog("%@", "ACTION: Delete comment \(comment.id)")
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot delete comment")
                    self.alertMessage = "Session not found."
                    return
                }
                let token = userSession.sessionToken
                _ = try await api.deleteComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id)
                self.loadAllData()
            } catch {
                NSLog("%@", "Failed to delete comment: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to delete comment: \(error.localizedDescription)"
                }
            }
        }
    }

    func likeComment(_ comment: CommentViewData) {
        // The backend rejects liking your own comment; don't optimistically like it.
        guard !isOwnComment(comment) else { return }
        NSLog("%@", "ACTION: Like comment \(comment.id)")

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
            isLiked: true,
            createdDate: oldComment.createdDate
        )
        
        // Replace the old comment with the new one in the published array
        commentThreads[threadIndex].comments[commentIndex] = newComment

        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot like comment")
                    self.alertMessage = "Session not found."
                    return
                }
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
            isLiked: false,
            createdDate: oldComment.createdDate
        )
        
        commentThreads[threadIndex].comments[commentIndex] = newComment

        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot unlike comment")
                    self.alertMessage = "Session not found."
                    return
                }
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
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot report comment")
                    self.alertMessage = "Session not found."
                    return
                }
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
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot comment on post")
                    self.alertMessage = "Session not found."
                    return
                }
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
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot reply to comment thread")
                    self.alertMessage = "Session not found."
                    return
                }
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
        let is_liked: Bool
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
        let is_liked: Bool
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
