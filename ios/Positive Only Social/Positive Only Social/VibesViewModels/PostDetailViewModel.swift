//
//  PostDetailViewModel.swift
//  Vibes
//
//  Created by Andrew Katson on 11/9/25.
//

import Foundation
import Combine

// Use the Networking you've already defined
// (Assuming Networking is available in this scope)

@MainActor
final class PostDetailViewModel: ObservableObject {

    /// Comments per thread-comments page, matching the backend's
    /// COMMENT_BATCH_SIZE. A page shorter than this is the thread's last.
    nonisolated static let commentBatchSize = 30

    /// `loaded` followed by the comments of `page` it does not already hold.
    /// Thread pages come from a live like-weighted ranking, so a comment can
    /// reappear on the next page if the ranking shifts between requests.
    nonisolated static func appendingNewComments<Comment>(
        _ page: [Comment], to loaded: [Comment], id: (Comment) -> String
    ) -> [Comment] {
        var seen = Set(loaded.map(id))
        return loaded + page.filter { seen.insert(id($0)).inserted }
    }

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

    /// Drives the retract-report confirmation for the post / a comment. The
    /// dialog shows the user's original report reason pre-populated (issue #176).
    @Published var showRetractDialogForPost = false
    @Published var commentToRetract: CommentViewData?

    /// Drives the native share sheet for the post / a comment (issue #34). Set
    /// by the action menu's "Share" button and presented as a `.sheet(item:)`;
    /// `nil` when no share sheet is showing. Sharing is offered for any post or
    /// comment — your own and others'.
    @Published var postShareItem: ShareURLItem?
    @Published var commentShareItem: ShareURLItem?

    /// Set once the post has been deleted so the view can pop back — the post no
    /// longer exists to display.
    @Published var postWasDeleted = false
    
    /// The text for creating a brand new comment thread
    @Published var newCommentText: String = ""

    /// Drives the "Add a comment" composer sheet for a brand new comment on the
    /// post. Both this and the reply flow go through the same composer sheet so
    /// the character counter is always shown and comments aren't typed inline
    /// (issues #266, #289, #290).
    @Published var showAddCommentSheet = false

    /// When a user taps "Reply", this is set, which triggers the reply sheet
    @Published var threadToReplyTo: CommentThreadViewData?

    /// Drive the same composer sheet, prefilled, for editing the caption or one
    /// of the user's own comments (issue #462).
    @Published var showEditCaptionSheet = false
    @Published var commentToEdit: CommentViewData?

    /// Edit is offered on the user's own post once it's live — a pending,
    /// rejected or hidden post isn't theirs to rewrite (issue #462).
    var canEditPost: Bool {
        isOwnPost && postDetail?.isHidden == false
    }

    /// Edit is offered on the user's own comments while the post accepts
    /// comments: turning commenting off (issue #492) freezes existing ones too.
    func canEditComment(_ comment: CommentViewData) -> Bool {
        isOwnComment(comment) && postDetail?.commentsDisabled == false
    }

    /// The active comment-list filter — the followed-feed toggle applied to
    /// comments (issue #445). `nil` means no filter (all visible comments).
    @Published private(set) var selectedCommentCategory: FollowCategory?

    /// Switch the comment filter and reload. A no-op when unchanged so tapping
    /// the active chip doesn't refetch, mirroring the following feed.
    func selectCommentCategory(_ category: FollowCategory?) {
        guard category != selectedCommentCategory else { return }
        selectedCommentCategory = category
        loadAllData()
    }

    /// Ids of comments whose thread below them is collapsed. Tapping a comment's
    /// username/time header toggles its presence here (issue #243).
    @Published var collapsedCommentIds: Set<String> = []

    /// Toggles whether the thread below the given comment is collapsed.
    func toggleCommentCollapsed(_ commentId: String) {
        if collapsedCommentIds.contains(commentId) {
            collapsedCommentIds.remove(commentId)
        } else {
            collapsedCommentIds.insert(commentId)
        }
    }
    
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

    /// Whether the signed-in user has an active report against the comment —
    /// from the server-backed flag, or the local set for reports made this
    /// session before the next reload.
    func isCommentReported(_ comment: CommentViewData) -> Bool {
        comment.isReported || reportedCommentIds.contains(comment.id)
    }
    
    // Edits saved on this screen (issue #462). A load whose request went out
    // before a save can land after it with the old text, so every load
    // re-applies these over anything older (see SavedEdit.isNewer).
    private var savedCaptionEdit: EditPostResponse?
    private var savedCommentEdits: [String: EditCommentResponse] = [:]

    /// `post` as fetched, with this screen's saved caption edit laid over it
    /// when the fetch predates that edit.
    func applyingSavedEdit(to post: PostDisplayData, fetchedEditedTime: String?) -> PostDisplayData {
        guard let saved = savedCaptionEdit,
              SavedEdit.isNewer(saved: saved.editedTime, fetched: fetchedEditedTime) else { return post }
        var reconciled = post
        reconciled.caption = saved.caption
        reconciled.isEdited = true
        return reconciled
    }

    /// The comment-side counterpart of `applyingSavedEdit(to:fetchedEditedTime:)`.
    func applyingSavedEdit(to comment: CommentViewData) -> CommentViewData {
        guard let saved = savedCommentEdits[comment.id],
              SavedEdit.isNewer(saved: saved.editedTime, fetched: comment.editedTime) else { return comment }
        var reconciled = comment
        reconciled.body = saved.body
        reconciled.formatting = saved.bodyFormatting
        reconciled.isEdited = true
        reconciled.editedTime = saved.editedTime
        return reconciled
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

                self.postDetail = self.applyingSavedEdit(to: PostDisplayData(
                    id: postFields.post_identifier,
                    imageURL: postFields.image_url,
                    originalImageURL: postFields.original_image_url,
                    caption: postFields.caption,
                    captionFont: postFields.caption_font ?? "default",
                    backgroundColor: postFields.background_color ?? "default",
                    likeCount: postFields.post_likes,
                    isLiked: postFields.is_liked,
                    authorUsername: postFields.author_username,
                    authorProfileImageURL: postFields.author_profile_image_url,
                    authorProfileImageOriginalURL: postFields.author_profile_image_original_url,
                    authorProfileImageBlurHash: postFields.author_profile_image_blurhash,
                    createdDate: postFields.creation_time.flatMap { Self.parseOptionalDate($0) },
                    isReported: postFields.is_reported ?? false,
                    reportReason: postFields.report_reason,
                    audience: postFields.audience,
                    commentsDisabled: postFields.comments_disabled ?? false,
                    isEdited: postFields.edited_time != nil,
                    isHidden: postFields.hidden ?? false
                ), fetchedEditedTime: postFields.edited_time)
                // Server truth for the reported flag, so it survives reloads.
                self.isPostReported = postFields.is_reported ?? false

                // 2. Fetch the list of comment thread IDs for this post. The
                // optional category applies the followed-feed toggle to comments
                // (issue #445): nil returns all visible threads.
                let categoryFilter = self.selectedCommentCategory?.rawValue
                let threadListData = try await api.getCommentsForPost(sessionManagementToken: token, postIdentifier: postIdentifier, batch: 0, category: categoryFilter)
                let threadIDFields = try self.decodeList(from: threadListData, type: ThreadIDFields.self)
                let threadIdentifiers = threadIDFields.map { $0.comment_thread_identifier }

                // 3. Fetch all comments for *each* thread in parallel
                var loadedThreads: [CommentThreadViewData] = []

                try await withThrowingTaskGroup(of: [CommentViewData].self) { group in
                    for threadId in threadIdentifiers {
                        group.addTask {
                            // Keep fetching while a page is full, so the whole
                            // thread is loaded and a comment at a page boundary
                            // still knows it has replies (issue #537).
                            var commentFields: [CommentFields] = []
                            for commentBatch in 0... {
                                let page: [CommentFields]
                                do {
                                    let commentsData = try await self.api.getCommentsForThread(sessionManagementToken: token, commentThreadIdentifier: threadId, batch: commentBatch, category: categoryFilter)

                                    // `await` is required even though decodeList is
                                    // synchronous: this ViewModel is @MainActor-isolated
                                    // and decodeList inherits that isolation, but we are
                                    // inside a detached withThrowingTaskGroup task, so the
                                    // call hops back to the main actor (an actor hop is an
                                    // async operation — it does NOT warn "no async
                                    // operations occur"). Dropping the await fails the
                                    // build with "main actor-isolated ... cannot be called
                                    // from outside of the actor".
                                    page = try await self.decodeList(from: commentsData, type: CommentFields.self)
                                } catch let error where commentBatch > 0 && !error.isCancellation {
                                    // A later page failing (e.g. rate limited) keeps the
                                    // pages already loaded rather than failing the whole
                                    // post; pull-to-refresh retries the rest.
                                    NSLog("%@", "Comment page \(commentBatch) of thread \(threadId) failed to load: \(error)")
                                    break
                                }
                                // The thread is paged by a live ranking, so a comment can
                                // shift onto the next page between requests; keep the
                                // first copy. The full-page check uses the raw page.
                                commentFields = Self.appendingNewComments(page, to: commentFields, id: \.comment_identifier)
                                if page.count < Self.commentBatchSize { break }
                            }

                            // 4. Convert network models to View Models
                            return commentFields.map { field in
                                CommentViewData(
                                    id: field.comment_identifier,
                                    threadId: threadId,
                                    authorUsername: field.author_username,
                                    authorProfileImageURL: field.author_profile_image_url,
                                    authorProfileImageOriginalURL: field.author_profile_image_original_url,
                                    authorProfileImageBlurHash: field.author_profile_image_blurhash,
                                    body: field.body,
                                    formatting: field.body_formatting,
                                    audience: field.audience,
                                    likeCount: field.comment_likes,
                                    isLiked: field.is_liked,
                                    createdDate: Self.parseDate(field.creation_time),
                                    isReported: field.is_reported ?? false,
                                    reportReason: field.report_reason,
                                    isEdited: field.edited_time != nil,
                                    editedTime: field.edited_time
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
                
                // Saved edits are laid over the fetched comments only now, at
                // the moment of publishing: a thread that finished early was
                // buffered while the others loaded, and an edit saved meanwhile
                // (issue #462) must not be undone by that buffered copy.
                let reconciledThreads = loadedThreads.map { thread in
                    CommentThreadViewData(comments: thread.comments.map { self.applyingSavedEdit(to: $0) })
                }
                // Sort threads by their first comment's date
                self.commentThreads = reconciledThreads.sorted {
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
                    self.alertMessage = "Failed to load post: \(error.userFacingMessage)"
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
                originalImageURL: post.originalImageURL,
                caption: post.caption,
                captionFont: post.captionFont,
                backgroundColor: post.backgroundColor,
                likeCount: post.likeCount + 1, // Optimistic update
                isLiked: true,
                authorUsername: post.authorUsername,
                authorProfileImageURL: post.authorProfileImageURL,
                authorProfileImageOriginalURL: post.authorProfileImageOriginalURL,
                authorProfileImageBlurHash: post.authorProfileImageBlurHash,
                createdDate: post.createdDate,
                isReported: post.isReported,
                reportReason: post.reportReason,
                audience: post.audience,
                commentsDisabled: post.commentsDisabled,
                isEdited: post.isEdited,
                isHidden: post.isHidden
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
                    self.alertMessage = "Failed to like post: \(error.userFacingMessage)"
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
                originalImageURL: post.originalImageURL,
                caption: post.caption,
                captionFont: post.captionFont,
                backgroundColor: post.backgroundColor,
                likeCount: max(0, post.likeCount - 1), // Optimistic update
                isLiked: false,
                authorUsername: post.authorUsername,
                authorProfileImageURL: post.authorProfileImageURL,
                authorProfileImageOriginalURL: post.authorProfileImageOriginalURL,
                authorProfileImageBlurHash: post.authorProfileImageBlurHash,
                createdDate: post.createdDate,
                isReported: post.isReported,
                reportReason: post.reportReason,
                audience: post.audience,
                commentsDisabled: post.commentsDisabled,
                isEdited: post.isEdited,
                isHidden: post.isHidden
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
                    self.alertMessage = "Failed to unlike post: \(error.userFacingMessage)"
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
                // Reload so the server-backed isReported/reportReason state
                // (used by the action menu and retract dialog) refreshes.
                self.loadAllData()
            } catch {
                NSLog("%@", "Failed to report post: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to report post: \(error.userFacingMessage)"
                }
            }
        }
    }
    
    /// Retracts the current user's report against the post (issue #176), then
    /// reloads so the isReported/reportReason state refreshes.
    func retractReportPost() {
        NSLog("%@", "ACTION: Retract report on post \(postIdentifier)")
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot retract post report")
                    self.alertMessage = "Session not found."
                    return
                }
                let token = userSession.sessionToken
                _ = try await api.retractReportPost(sessionManagementToken: token, postIdentifier: postIdentifier)
                await MainActor.run {
                    isPostReported = false
                }
                self.loadAllData()
            } catch {
                NSLog("%@", "Failed to retract post report: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to retract report: \(error.userFacingMessage)"
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
                    self.alertMessage = "Failed to delete post: \(error.userFacingMessage)"
                }
            }
        }
    }

    /// Turns off commenting on the post (issue #492), optimistically hiding the
    /// composer/reply controls, and reverting on failure. Only reachable from
    /// the action menu on an own post.
    func lockComments() {
        NSLog("%@", "ACTION: Lock comments on post \(postIdentifier)")
        guard var post = postDetail else { return }
        post.commentsDisabled = true
        self.postDetail = post
        // Weak so a dismissed detail screen isn't kept alive by the request.
        Task { [weak self] in
            guard let self else { return }
            do {
                guard let userSession = try self.keychainHelper.load(UserSession.self, from: self.keychainService, account: self.account) else {
                    NSLog("%@", "No active session — cannot lock comments")
                    // Undo the optimistic update since no request was sent.
                    if var reverted = self.postDetail { reverted.commentsDisabled = false; self.postDetail = reverted }
                    self.alertMessage = "Session not found."
                    return
                }
                let token = userSession.sessionToken
                _ = try await api.lockComments(sessionManagementToken: token, postIdentifier: self.postIdentifier)
                await MainActor.run {
                    NotificationCenter.default.post(name: .postCommentsDisabledChanged, object: self.postIdentifier, userInfo: ["commentsDisabled": true])
                }
            } catch {
                NSLog("%@", "Failed to lock comments: \(error)")
                await MainActor.run {
                    if var reverted = self.postDetail { reverted.commentsDisabled = false; self.postDetail = reverted }
                    self.alertMessage = "Failed to turn off commenting: \(error.userFacingMessage)"
                }
            }
        }
    }

    /// Re-allows commenting on a post previously locked with `lockComments`
    /// (issue #492).
    func unlockComments() {
        NSLog("%@", "ACTION: Unlock comments on post \(postIdentifier)")
        guard var post = postDetail else { return }
        post.commentsDisabled = false
        self.postDetail = post
        // Weak so a dismissed detail screen isn't kept alive by the request.
        Task { [weak self] in
            guard let self else { return }
            do {
                guard let userSession = try self.keychainHelper.load(UserSession.self, from: self.keychainService, account: self.account) else {
                    NSLog("%@", "No active session — cannot unlock comments")
                    // Undo the optimistic update since no request was sent.
                    if var reverted = self.postDetail { reverted.commentsDisabled = true; self.postDetail = reverted }
                    self.alertMessage = "Session not found."
                    return
                }
                let token = userSession.sessionToken
                _ = try await api.unlockComments(sessionManagementToken: token, postIdentifier: self.postIdentifier)
                await MainActor.run {
                    NotificationCenter.default.post(name: .postCommentsDisabledChanged, object: self.postIdentifier, userInfo: ["commentsDisabled": false])
                }
            } catch {
                NSLog("%@", "Failed to unlock comments: \(error)")
                await MainActor.run {
                    if var reverted = self.postDetail { reverted.commentsDisabled = true; self.postDetail = reverted }
                    self.alertMessage = "Failed to turn on commenting: \(error.userFacingMessage)"
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
                    self.alertMessage = "Failed to delete comment: \(error.userFacingMessage)"
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
            authorProfileImageURL: oldComment.authorProfileImageURL,
            authorProfileImageOriginalURL: oldComment.authorProfileImageOriginalURL,
            authorProfileImageBlurHash: oldComment.authorProfileImageBlurHash,
            body: oldComment.body,
            formatting: oldComment.formatting,
            audience: oldComment.audience,
            likeCount: oldComment.likeCount + 1, // The update
            isLiked: true,
            createdDate: oldComment.createdDate,
            isReported: oldComment.isReported,
            reportReason: oldComment.reportReason,
            isEdited: oldComment.isEdited,
            editedTime: oldComment.editedTime
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
                    self.alertMessage = "Failed to like comment: \(error.userFacingMessage)"
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
            authorProfileImageURL: oldComment.authorProfileImageURL,
            authorProfileImageOriginalURL: oldComment.authorProfileImageOriginalURL,
            authorProfileImageBlurHash: oldComment.authorProfileImageBlurHash,
            body: oldComment.body,
            formatting: oldComment.formatting,
            audience: oldComment.audience,
            likeCount: newLikeCount, // The update
            isLiked: false,
            createdDate: oldComment.createdDate,
            isReported: oldComment.isReported,
            reportReason: oldComment.reportReason,
            isEdited: oldComment.isEdited,
            editedTime: oldComment.editedTime
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
                    self.alertMessage = "Failed to unlike comment: \(error.userFacingMessage)"
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
                // Reload so the server-backed isReported/reportReason state
                // (used by the action menu and retract dialog) refreshes.
                self.loadAllData()
            } catch {
                NSLog("%@", "Failed to report comment: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to report comment: \(error.userFacingMessage)"
                }
            }
        }
    }
    /// Retracts the current user's report against a comment (issue #176), then
    /// reloads so the isReported/reportReason state refreshes.
    func retractReportComment(_ comment: CommentViewData) {
        NSLog("%@", "ACTION: Retract report on comment \(comment.id)")
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot retract comment report")
                    self.alertMessage = "Session not found."
                    return
                }
                let token = userSession.sessionToken
                _ = try await api.retractReportComment(sessionManagementToken: token, postIdentifier: postIdentifier, commentThreadIdentifier: comment.threadId, commentIdentifier: comment.id)
                await MainActor.run {
                    reportedCommentIds.remove(comment.id)
                }
                self.loadAllData()
            } catch {
                NSLog("%@", "Failed to retract comment report: \(error)")
                await MainActor.run {
                    self.alertMessage = "Failed to retract report: \(error.userFacingMessage)"
                }
            }
        }
    }

    /// Creates a new comment (and thus a new thread) on the post.
    /// `formatting` carries optional inline styling spans (issue #318);
    /// `audience` scopes who may see the comment (issue #445).
    func commentOnPost(commentText: String, formatting: [CommentFormatSpan]? = nil, audience: PostAudience = .public) {
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
                    commentText: commentText,
                    formatting: formatting,
                    audience: audience.rawValue
                )
                
                // Success! Clear the text field and reload all data to show the new comment.
                self.newCommentText = ""
                self.loadAllData() // Reload to get the new thread
                
            } catch {
                self.alertMessage = "Failed to post comment: \(error.userFacingMessage)"
            }
        }
    }
    
    /// Replies to an existing comment thread.
    /// `formatting` carries optional inline styling spans (issue #318);
    /// `audience` scopes who may see the reply (issue #445).
    func replyToCommentThread(thread: CommentThreadViewData, commentText: String, formatting: [CommentFormatSpan]? = nil, audience: PostAudience = .public) {
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
                    commentText: commentText,
                    formatting: formatting,
                    audience: audience.rawValue
                )
                
                // Success! Reload all data to show the new reply.
                self.loadAllData() // Reload to get the new comment in the thread
                
            } catch {
                self.alertMessage = "Failed to post reply: \(error.userFacingMessage)"
            }
        }
    }
    
    // MARK: - Editing (issue #462)

    /// Saves an edited caption. The backend judges the new caption before it
    /// replaces anything, and a rejection keeps the original — so the post on
    /// screen only changes once the save succeeds.
    func editCaption(_ caption: String) {
        guard !caption.isEmpty, caption != postDetail?.caption else { return }
        NSLog("%@", "ACTION: Edit caption of post \(postIdentifier)")
        Task { [weak self] in
            guard let self else { return }
            do {
                guard let userSession = try self.keychainHelper.load(UserSession.self, from: self.keychainService, account: self.account) else {
                    self.alertMessage = "Session not found."
                    return
                }
                let data = try await self.api.editPost(sessionManagementToken: userSession.sessionToken, postIdentifier: self.postIdentifier, caption: caption)
                let saved = try self.decodeSingle(from: data, type: EditPostResponse.self)
                self.savedCaptionEdit = saved
                if var post = self.postDetail {
                    post.caption = saved.caption
                    post.isEdited = saved.editedTime != nil
                    self.postDetail = post
                }
                // Lists that already show this post pick up the new caption.
                var userInfo: [String: Any] = ["caption": saved.caption, "tags": saved.tags]
                userInfo["editedTime"] = saved.editedTime
                NotificationCenter.default.post(name: .postCaptionEdited, object: self.postIdentifier, userInfo: userInfo)
            } catch {
                NSLog("%@", "Failed to edit caption: \(error)")
                self.alertMessage = "Failed to edit caption: \(error.userFacingMessage)"
            }
        }
    }

    /// Saves an edit to one of the user's own comments, with the same
    /// change-only-on-success behaviour as `editCaption`.
    func editComment(_ comment: CommentViewData, commentText: String, formatting: [CommentFormatSpan]?) {
        guard !commentText.isEmpty else { return }
        NSLog("%@", "ACTION: Edit comment \(comment.id)")
        Task { [weak self] in
            guard let self else { return }
            do {
                guard let userSession = try self.keychainHelper.load(UserSession.self, from: self.keychainService, account: self.account) else {
                    self.alertMessage = "Session not found."
                    return
                }
                let data = try await self.api.editComment(
                    sessionManagementToken: userSession.sessionToken,
                    postIdentifier: self.postIdentifier,
                    commentThreadIdentifier: comment.threadId,
                    commentIdentifier: comment.id,
                    commentText: commentText,
                    formatting: formatting
                )
                let saved = try self.decodeSingle(from: data, type: EditCommentResponse.self)
                self.savedCommentEdits[comment.id] = saved
                guard let threadIndex = self.commentThreads.firstIndex(where: { $0.id == comment.threadId }),
                      let commentIndex = self.commentThreads[threadIndex].comments.firstIndex(where: { $0.id == comment.id }) else { return }
                self.commentThreads[threadIndex].comments[commentIndex].body = saved.body
                self.commentThreads[threadIndex].comments[commentIndex].formatting = saved.bodyFormatting
                self.commentThreads[threadIndex].comments[commentIndex].isEdited = saved.editedTime != nil
                self.commentThreads[threadIndex].comments[commentIndex].editedTime = saved.editedTime
            } catch {
                NSLog("%@", "Failed to edit comment: \(error)")
                self.alertMessage = "Failed to edit comment: \(error.userFacingMessage)"
            }
        }
    }

    // MARK: - Sharing (issue #34)

    /// Builds the website link for this post and shows the native share sheet.
    /// Available for any post — the backend/website links currently require
    /// login (Scope A), which is expected.
    func sharePost() {
        guard let url = ShareURL.post(postIdentifier) else { return }
        postShareItem = ShareURLItem(url: url)
    }

    /// Builds the website link for the given comment (a post URL with a
    /// `#comment-<id>` fragment) and shows the native share sheet. Available for
    /// any comment.
    func shareComment(_ comment: CommentViewData) {
        guard let url = ShareURL.comment(postIdentifier: postIdentifier, commentIdentifier: comment.id) else { return }
        commentShareItem = ShareURLItem(url: url)
    }

    // MARK: - Private Decoding Helpers
    
    // These match the 'Fields' structs in your stub API
    private struct PostDetailsFields: Decodable {
        let post_identifier: String
        // Nil for a text-only post (#307).
        let image_url: String?
        /// Full-res original for the compressed→original fallback (#252/#254).
        /// Optional so responses that predate the field still decode.
        let original_image_url: String?
        let caption: String
        /// Caption font + background color keys (issue #318); optional so
        /// responses that predate the fields still decode.
        let caption_font: String?
        let background_color: String?
        /// When the post was created. Optional so responses that predate the
        /// field still decode.
        //TODO: eBlender rename to camelCase creationTime (via CodingKeys).
        let creation_time: String?
        let post_likes: Int
        let is_liked: Bool
        /// Whether the current user has an active report against this post, and
        /// their own reason (#176). Optional so older responses still decode.
        let is_reported: Bool?
        let report_reason: String?
        let author_username: String
        /// The author's approved profile photo (issue #7); nil when they have
        /// none or on older responses.
        let author_profile_image_url: String?
        let author_profile_image_original_url: String?
        /// That photo's BlurHash (issue #460), shown blurred while it loads.
        let author_profile_image_blurhash: String?
        /// Who may see the post (issue #392); optional so older responses still
        /// decode (treated as public by the audience badge, issue #518).
        let audience: String?
        /// Whether the author has turned off commenting on this post (issue
        /// #492). Optional so responses that predate the field still decode
        /// as comments allowed.
        let comments_disabled: Bool?
        /// When the caption was last edited (issue #462); nil if never, and
        /// absent on older responses.
        let edited_time: String?
        /// Author-only: whether the viewer's own post is hidden (pending,
        /// rejected or moderated). Absent on everyone else's posts.
        let hidden: Bool?
    }

    private struct ThreadIDFields: Decodable {
        let comment_thread_identifier: String
    }

    private struct CommentFields: Decodable {
        let comment_identifier: String
        let body: String
        /// Inline formatting spans over `body` (issue #318); nil = plain text.
        let body_formatting: [CommentFormatSpan]?
        /// Who may see this comment (issue #445); optional so older responses
        /// still decode (treated as public).
        let audience: String?
        let author_username: String
        /// The comment author's approved profile photo (issue #7); nil when they
        /// have none or on older responses.
        let author_profile_image_url: String?
        let author_profile_image_original_url: String?
        /// That photo's BlurHash (issue #460), shown blurred while it loads.
        let author_profile_image_blurhash: String?
        let creation_time: String
        let updated_time: String
        let comment_likes: Int
        let is_liked: Bool
        /// Whether the current user has an active report against this comment,
        /// and their own reason (#176). Optional so older responses still decode.
        let is_reported: Bool?
        let report_reason: String?
        /// When the author last edited it (issue #462); nil if never.
        let edited_time: String?
    }

    private func decodeSingle<T: Decodable>(from data: Data, type: T.Type) throws -> T {
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func decodeList<T: Decodable>(from data: Data, type: T.Type) throws -> [T] {
        return try JSONDecoder().decode([T].self, from: data)
    }

    // MARK: - Date Parsing

    /// Parses one of the backend's ISO8601 timestamps, returning nil when it
    /// can't be read so callers omit the relative-time label rather than showing
    /// a bogus "now". Shared with the feed rows via `RelativeTime` (#249).
    private nonisolated static func parseOptionalDate(_ string: String) -> Date? {
        RelativeTime.date(from: string)
    }

    private nonisolated static func parseDate(_ string: String) -> Date {
        parseOptionalDate(string) ?? Date()
    }
}
