//
//  FollowingFeedViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/26/25.
//

import Foundation
import Combine

// ViewModel to manage the state of the "Following" feed
@MainActor
final class FollowingFeedViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService
    @Published var followingPosts: [Post] = []
    @Published var isLoadingNextPage = false
    /// Optional group filter (issue #392): nil is the whole following feed.
    @Published private(set) var selectedCategory: FollowCategory? = nil
    private var canLoadMore = true
    private var currentPage = 0

    // Listens for `.postDeleted` so a post deleted from the feed itself (#267)
    // or from its detail view drops out of the list, without reloading (and so
    // reordering) the rest of the feed.
    private var postDeletedCancellable: AnyCancellable?

    convenience init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }

    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String,
         notificationCenter: NotificationCenter = .default) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account

        postDeletedCancellable = notificationCenter.publisher(for: .postDeleted)
            .receive(on: RunLoop.main)
            .sink { [weak self] notification in
                guard let postIdentifier = notification.object as? String else { return }
                self?.followingPosts.removeAll { $0.id == postIdentifier }
            }
    }

    func fetchFollowingFeed() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true

        Task {
            await loadPage(currentPage, replacingExisting: false)
        }
    }

    /// Switches the group filter and reloads from the first page (issue #392).
    /// A no-op when the category is unchanged so re-selecting doesn't refetch.
    func selectCategory(_ category: FollowCategory?) {
        guard category != selectedCategory else { return }
        selectedCategory = category
        Task { await refreshFeed() }
    }

    /// Reloads the following feed from the first page.
    ///
    /// This is `async` so SwiftUI's `.refreshable` keeps the pull-to-refresh
    /// spinner visible until the fresh posts have actually been loaded. The
    /// pagination cursor is only reset once the first page successfully loads,
    /// so a failed refresh leaves the existing cursor (and posts) intact and
    /// can't cause the next infinite-scroll fetch to duplicate page 0.
    func refreshFeed() async {
        // Avoid stomping on an in-flight page load.
        guard !isLoadingNextPage else { return }

        isLoadingNextPage = true
        await loadPage(0, replacingExisting: true)
    }

    /// Fetches the given page of posts. When `replacingExisting` is true the
    /// freshly fetched posts replace the existing list and the pagination cursor
    /// is reset (used by pull-to-refresh); otherwise they are appended (used by
    /// infinite scrolling). Pagination state is only mutated on a successful
    /// response so failures don't corrupt the cursor.
    private func loadPage(_ page: Int, replacingExisting: Bool) async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot fetch following feed")
                isLoadingNextPage = false
                return
            }

            // Call the API endpoint for followed users, narrowed to the
            // selected group when one is chosen (issue #392).
            let responseData = try await api.getPostsForFollowedUsers(
                sessionManagementToken: userSession.sessionToken,
                batch: page,
                category: selectedCategory?.rawValue)

            let newPosts = try JSONDecoder().decode([Post].self, from: responseData)

            if replacingExisting {
                followingPosts = newPosts
                canLoadMore = !newPosts.isEmpty
                currentPage = newPosts.isEmpty ? 0 : 1
            } else if newPosts.isEmpty {
                canLoadMore = false
            } else {
                followingPosts.append(contentsOf: newPosts)
                currentPage += 1
            }
        } catch {
            NSLog("%@", "Failed to fetch following feed: \(error)")
        }
        isLoadingNextPage = false
    }
}
