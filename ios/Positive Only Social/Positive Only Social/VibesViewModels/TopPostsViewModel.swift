//
//  TopPostsViewModel.swift
//  Vibes
//

import Foundation
import Combine

/// ViewModel for the "Top" feed: the scoreboard of the most-liked public posts
/// across the app over a chosen period (issue #558).
@MainActor
final class TopPostsViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService
    @Published var topPosts: [Post] = []
    @Published var isLoadingNextPage = false
    @Published private(set) var selectedPeriod: TopPostPeriod = .week
    private var canLoadMore = true
    private var currentPage = 0

    // Listens for `.postDeleted` so a post deleted from the feed itself or from
    // its detail view drops out of the list without reloading it.
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
                self?.topPosts.removeAll { $0.id == postIdentifier }
            }
    }

    func fetchTopPosts() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true

        Task {
            await loadPage(currentPage, replacingExisting: false)
        }
    }

    /// Switches the time period and reloads from the first page. A no-op when
    /// the period is unchanged so re-selecting doesn't refetch.
    func selectPeriod(_ period: TopPostPeriod) {
        guard period != selectedPeriod else { return }
        selectedPeriod = period
        Task { await refreshFeed() }
    }

    /// Reloads the scoreboard from the first page. `async` so `.refreshable`
    /// keeps its spinner until the fresh posts arrive; the cursor is only reset
    /// once the first page loads, so a failed refresh leaves it intact.
    func refreshFeed() async {
        guard !isLoadingNextPage else { return }

        isLoadingNextPage = true
        await loadPage(0, replacingExisting: true)
    }

    private func loadPage(_ page: Int, replacingExisting: Bool) async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot fetch top posts")
                isLoadingNextPage = false
                return
            }

            let responseData = try await api.getTopPosts(
                sessionManagementToken: userSession.sessionToken,
                batch: page,
                period: selectedPeriod.rawValue)

            let newPosts = try JSONDecoder().decode([Post].self, from: responseData)

            if replacingExisting {
                topPosts = newPosts
                canLoadMore = !newPosts.isEmpty
                currentPage = newPosts.isEmpty ? 0 : 1
            } else if newPosts.isEmpty {
                canLoadMore = false
            } else {
                topPosts.append(contentsOf: newPosts)
                currentPage += 1
            }
        } catch {
            NSLog("%@", "Failed to fetch top posts: \(error)")
        }
        isLoadingNextPage = false
    }
}
