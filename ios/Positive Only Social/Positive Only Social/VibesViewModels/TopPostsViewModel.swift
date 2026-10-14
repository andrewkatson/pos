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
    // State the view observes.
    @Published var topPosts: [Post] = []
    @Published var isLoadingNextPage = false
    @Published private(set) var selectedPeriod: TopPostPeriod = .week

    // Dependencies.
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    // Pagination state.
    private var canLoadMore = true
    private var currentPage = 0
    // Bumped when the period changes, so a load still in flight for the old
    // period recognises it was superseded and drops its response instead of
    // filling the list under the new selection.
    private var loadGeneration = 0

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

        // Captured now, not inside the Task: a period switch landing before the
        // Task starts must still mark this load as superseded.
        let generation = loadGeneration
        Task {
            await loadPage(currentPage, replacingExisting: false, generation: generation)
        }
    }

    /// Switches the time period and reloads from the first page. A no-op when
    /// the period is unchanged so re-selecting doesn't refetch.
    func selectPeriod(_ period: TopPostPeriod) {
        guard period != selectedPeriod else { return }
        selectedPeriod = period
        // Supersede any in-flight load rather than going through refreshFeed(),
        // whose loading guard would otherwise skip the reload entirely.
        loadGeneration += 1
        // Clear the old board rather than leaving it under the new selection:
        // SwiftUI would reuse a row whose id survives into the new page, so the
        // last row's onAppear wouldn't fire again and page 1 would never load.
        topPosts = []
        canLoadMore = true
        currentPage = 0
        isLoadingNextPage = true
        let generation = loadGeneration
        Task { await loadPage(0, replacingExisting: true, generation: generation) }
    }

    /// Reloads the scoreboard from the first page. `async` so `.refreshable`
    /// keeps its spinner until the fresh posts arrive; the cursor is only reset
    /// once the first page loads, so a failed refresh leaves it intact.
    func refreshFeed() async {
        guard !isLoadingNextPage else { return }

        isLoadingNextPage = true
        await loadPage(0, replacingExisting: true, generation: loadGeneration)
    }

    private func loadPage(_ page: Int, replacingExisting: Bool, generation: Int) async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot fetch top posts")
                isLoadingNextPage = false
                return
            }

            var page = page
            while true {
                let responseData = try await api.getTopPosts(
                    sessionManagementToken: userSession.sessionToken,
                    batch: page,
                    period: selectedPeriod.rawValue)

                // A newer load owns the list and the loading flag now.
                guard generation == loadGeneration else { return }

                let newPosts = try JSONDecoder().decode([Post].self, from: responseData)

                if replacingExisting {
                    topPosts = newPosts
                    canLoadMore = !newPosts.isEmpty
                    currentPage = newPosts.isEmpty ? 0 : 1
                    break
                }
                if newPosts.isEmpty {
                    canLoadMore = false
                    break
                }
                // Live OFFSET paging can repeat a post whose rank moved between
                // requests; drop repeats so ForEach identities stay unique.
                let seen = Set(topPosts.map(\.id))
                let unseen = newPosts.filter { !seen.contains($0.id) }
                currentPage += 1
                if !unseen.isEmpty {
                    topPosts.append(contentsOf: unseen)
                    break
                }
                // A page of nothing but repeats appends no row, so the last
                // row's onAppear would never fire again: keep going until a page
                // adds something or comes back empty (the server stops at 100).
                page = currentPage
            }
        } catch {
            NSLog("%@", "Failed to fetch top posts: \(error)")
            guard generation == loadGeneration else { return }
        }
        isLoadingNextPage = false
    }
}
