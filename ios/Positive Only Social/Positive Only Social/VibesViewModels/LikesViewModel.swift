//
//  LikesViewModel.swift
//  Positive Only Social
//
//  Loads "who liked this" for one of the signed-in user's own posts or comments
//  (issue #478), a batch at a time. Only your own content is ever asked about —
//  the backend answers for nobody else's — so the like count is only tappable on
//  your own post/comment.
//

import Foundation
import Combine

/// What a `LikesViewModel` is listing the likers of. Hashable so a view can put
/// it in `.sheet(item:)`, and it carries the identifiers rather than a closure
/// so the view model owns the fetching.
enum LikesTarget: Hashable, Identifiable {
    case post(postIdentifier: String)
    case comment(postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String)

    var id: String {
        switch self {
        case .post(let postIdentifier):
            return "post:\(postIdentifier)"
        case .comment(let postIdentifier, let threadIdentifier, let commentIdentifier):
            return "comment:\(postIdentifier):\(threadIdentifier):\(commentIdentifier)"
        }
    }

    /// The navigation-bar title for this list.
    var title: String {
        switch self {
        case .post: return "Likes"
        case .comment: return "Comment likes"
        }
    }
}

@MainActor
final class LikesViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    let target: LikesTarget

    @Published var users: [User] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    /// Whether another batch might exist. False once a batch comes back empty,
    /// or after a failure — the list then stands as "here is what we have"
    /// rather than paging into the same error again.
    @Published var canLoadMore = false

    /// The next batch index to request. 0 until the first batch lands.
    private var nextBatch = 0

    init(target: LikesTarget, api: Networking, keychainHelper: KeychainHelperProtocol, account: String = "userSessionToken") {
        self.target = target
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }

    private func loadSession() throws -> UserSession? {
        try keychainHelper.load(UserSession.self, from: keychainService, account: account)
    }

    private func fetch(token: String, batch: Int) async throws -> Data {
        switch target {
        case .post(let postIdentifier):
            return try await api.getPostLikers(
                sessionManagementToken: token, postIdentifier: postIdentifier, batch: batch)
        case .comment(let postIdentifier, let threadIdentifier, let commentIdentifier):
            return try await api.getCommentLikers(
                sessionManagementToken: token,
                postIdentifier: postIdentifier,
                commentThreadIdentifier: threadIdentifier,
                commentIdentifier: commentIdentifier,
                batch: batch)
        }
    }

    /// Loads (or reloads) the first batch, discarding anything already listed.
    func load() async {
        await load(batch: 0, replacing: true)
    }

    /// Appends the next batch, if there is one.
    func loadMore() async {
        guard canLoadMore, !isLoading else { return }
        await load(batch: nextBatch, replacing: false)
    }

    private func load(batch: Int, replacing: Bool) async {
        isLoading = true
        errorMessage = nil  // clear any stale error from a previous load
        defer { isLoading = false }
        do {
            guard let session = try loadSession() else {
                NSLog("%@", "No active session found — cannot load likes")
                return
            }
            let data = try await fetch(token: session.sessionToken, batch: batch)
            let page = try JSONDecoder().decode([User].self, from: data)
            if replacing {
                users = page
            } else {
                users.append(contentsOf: page)
            }
            // An empty batch is the end of the list, not an error.
            canLoadMore = !page.isEmpty
            nextBatch = page.isEmpty ? batch : batch + 1
        } catch {
            if error.isCancellation {
                NSLog("%@", "Likes load cancelled")
            } else {
                NSLog("%@", "Error loading likes: \(error)")
                errorMessage = error.userFacingMessage
                canLoadMore = false
            }
        }
    }
}
