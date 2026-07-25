//
//  TagFeedViewModel.swift
//  Positive Only Social
//
//  Drives the tag feed (issue #379): the posts carrying a given #hashtag,
//  paginated. Mirrors FeedViewModel, swapping the feed fetch for the
//  browse-by-tag endpoint.
//

import Foundation
import Combine

@MainActor
final class TagFeedViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService
    let tag: String
    @Published var posts: [Post] = []
    @Published var isLoadingNextPage = false
    private var canLoadMore = true
    private var currentPage = 0

    // Drops a post from the list when it is deleted from its detail view, so
    // the tag feed reflects the removal without a full reload.
    private var postDeletedCancellable: AnyCancellable?

    convenience init(tag: String, api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(tag: tag, api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }

    init(tag: String, api: Networking, keychainHelper: KeychainHelperProtocol, account: String,
         notificationCenter: NotificationCenter = .default) {
        self.tag = tag
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account

        postDeletedCancellable = notificationCenter.publisher(for: .postDeleted)
            .receive(on: RunLoop.main)
            .sink { [weak self] notification in
                guard let postIdentifier = notification.object as? String else { return }
                self?.posts.removeAll { $0.id == postIdentifier }
            }
    }

    func fetchNextPage() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true
        Task { await loadPage(currentPage, replacingExisting: false) }
    }

    /// Reloads the tag feed from the first page. `async` so `.refreshable`
    /// keeps the spinner up until the fresh posts arrive; the cursor is only
    /// reset on a successful first page so a failed refresh can't duplicate it.
    func refresh() async {
        guard !isLoadingNextPage else { return }
        isLoadingNextPage = true
        await loadPage(0, replacingExisting: true)
    }

    private func loadPage(_ page: Int, replacingExisting: Bool) async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session found — cannot fetch tag feed")
                isLoadingNextPage = false
                return
            }

            let responseData = try await api.getPostsForTag(
                sessionManagementToken: userSession.sessionToken, tag: tag, batch: page)
            let newPosts = try JSONDecoder().decode([Post].self, from: responseData)

            if replacingExisting {
                posts = newPosts
                canLoadMore = !newPosts.isEmpty
                currentPage = newPosts.isEmpty ? 0 : 1
            } else if newPosts.isEmpty {
                canLoadMore = false
            } else {
                posts.append(contentsOf: newPosts)
                currentPage += 1
            }
        } catch {
            NSLog("%@", "Failed to fetch tag feed: \(error)")
        }
        isLoadingNextPage = false
    }
}
