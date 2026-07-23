//
//  PostActionsViewModel.swift
//  Positive Only Social
//

import Foundation
import Combine

/// Like / report / retract-report / delete for posts shown in a list, so the
/// user can act on them without opening each one (issue #267). Shared by the
/// profile grids and the feeds, which have different layouts but identical
/// actions — and identical to what `PostDetailView` offers for a single post.
///
/// The like/report state comes from the listing endpoints themselves
/// (`post_likes` / `is_liked` / `is_reported` / `report_reason` on `Post`);
/// local overrides layer on top so an action shows immediately without
/// refetching the page. Overrides are only cleared by a successful delete, so a
/// list reloaded from the server still shows the user's most recent action.
@MainActor
final class PostActionsViewModel: ObservableObject {

    /// Everything a row needs to render its controls for one post.
    struct InteractionState: Equatable {
        /// The backend rejects liking your own post, so the like control is
        /// hidden for it and the menu offers Delete instead of Report.
        var isOwn: Bool
        var isLiked: Bool
        var likeCount: Int
        var isReported: Bool
        var reportReason: String?
    }

    /// The post whose action menu (Delete / Retract Report / Report) is showing.
    @Published var postForMenu: Post?
    /// The post whose report sheet is showing.
    @Published var postToReport: Post?
    /// The post whose retract-report confirmation is showing.
    @Published var postToRetract: Post?
    /// Surfaced by the container view as an error alert.
    @Published var alertMessage: String?

    /// Per-post state the user has changed locally since the list was fetched.
    @Published private(set) var overrides: [String: InteractionState] = [:]

    /// The signed-in user's username, used to tell your own posts from others'.
    private(set) var currentUsername: String?

    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService
    private let notificationCenter: NotificationCenter

    convenience init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }

    init(api: Networking,
         keychainHelper: KeychainHelperProtocol,
         account: String,
         notificationCenter: NotificationCenter = .default) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
        self.notificationCenter = notificationCenter
        self.currentUsername = try? keychainHelper.load(
            UserSession.self, from: GVOAppConstants.keychainService, account: account
        )?.username
    }

    // MARK: - Derived State

    /// The interaction state for a post: the local override if the user has
    /// acted on it this session, otherwise the state the server sent with the list.
    func state(for post: Post) -> InteractionState {
        if let override = overrides[post.id] { return override }
        return InteractionState(
            isOwn: post.authorUsername == currentUsername,
            isLiked: post.isLiked,
            likeCount: post.postLikes,
            isReported: post.isReported,
            reportReason: post.reportReason
        )
    }

    // MARK: - Actions

    /// Likes or unlikes a post, updating the row immediately and reverting if
    /// the request fails — the same optimistic behavior as `PostDetailViewModel`.
    func toggleLike(_ post: Post) {
        let previous = state(for: post)
        // The control isn't rendered for your own post; guard anyway so a stray
        // call can't desync the count against a request the backend will reject.
        guard !previous.isOwn else { return }

        let liking = !previous.isLiked
        var updated = previous
        updated.isLiked = liking
        updated.likeCount = liking ? previous.likeCount + 1 : max(0, previous.likeCount - 1)
        overrides[post.id] = updated

        Task {
            guard let token = loadToken(for: liking ? "like post" : "unlike post") else {
                overrides[post.id] = previous
                return
            }
            do {
                if liking {
                    _ = try await api.likePost(sessionManagementToken: token, postIdentifier: post.id)
                } else {
                    _ = try await api.unlikePost(sessionManagementToken: token, postIdentifier: post.id)
                }
            } catch {
                NSLog("%@", "Failed to \(liking ? "like" : "unlike") post: \(error)")
                overrides[post.id] = previous
                alertMessage = "Failed to \(liking ? "like" : "unlike") post: \(error.userFacingMessage)"
            }
        }
    }

    /// Reports a post with the reason the user typed into the shared report sheet.
    func report(_ post: Post, reason: String) {
        Task {
            guard let token = loadToken(for: "report post") else { return }
            do {
                _ = try await api.reportPost(sessionManagementToken: token, postIdentifier: post.id, reason: reason)
                var updated = state(for: post)
                updated.isReported = true
                updated.reportReason = reason
                overrides[post.id] = updated
            } catch {
                NSLog("%@", "Failed to report post: \(error)")
                alertMessage = "Failed to report post: \(error.userFacingMessage)"
            }
        }
    }

    /// Retracts the user's own report against a post (issue #176).
    func retractReport(_ post: Post) {
        Task {
            guard let token = loadToken(for: "retract post report") else { return }
            do {
                _ = try await api.retractReportPost(sessionManagementToken: token, postIdentifier: post.id)
                var updated = state(for: post)
                updated.isReported = false
                updated.reportReason = nil
                overrides[post.id] = updated
            } catch {
                NSLog("%@", "Failed to retract post report: \(error)")
                alertMessage = "Failed to retract report: \(error.userFacingMessage)"
            }
        }
    }

    /// Deletes one of the user's own posts. On success it announces the deletion
    /// so every loaded list drops that one post — the lists are deliberately not
    /// reloaded, since refetching a weighted feed would reshuffle it under the user.
    func delete(_ post: Post) {
        Task {
            guard let token = loadToken(for: "delete post") else { return }
            do {
                _ = try await api.deletePost(sessionManagementToken: token, postIdentifier: post.id)
                overrides[post.id] = nil
                notificationCenter.post(name: .postDeleted, object: post.id)
            } catch {
                NSLog("%@", "Failed to delete post: \(error)")
                alertMessage = "Failed to delete post: \(error.userFacingMessage)"
            }
        }
    }

    // MARK: - Helpers

    /// Loads the session token, reporting a user-facing error when there isn't one.
    private func loadToken(for action: String) -> String? {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot \(action)")
                alertMessage = "Session not found."
                return nil
            }
            return userSession.sessionToken
        } catch {
            NSLog("%@", "Failed to load session — cannot \(action): \(error)")
            alertMessage = "Session not found."
            return nil
        }
    }
}
