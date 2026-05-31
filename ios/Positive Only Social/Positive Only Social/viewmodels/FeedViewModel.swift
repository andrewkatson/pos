//
//  FeedViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import Foundation

// ViewModel to manage the state of the global feed
@MainActor
final class FeedViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = AppConstants.keychainService
    @Published var feedPosts: [Post] = []
    @Published var isLoadingNextPage = false
    private var canLoadMore = true
    private var currentPage = 0
    
    convenience init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }
    
    func fetchFeed() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true

        Task {
            await loadNextPage()
        }
    }

    /// Resets pagination and reloads the feed from the first page.
    ///
    /// This is `async` so SwiftUI's `.refreshable` keeps the pull-to-refresh
    /// spinner visible until the fresh posts have actually been loaded.
    func refreshFeed() async {
        // Avoid stomping on an in-flight page load.
        guard !isLoadingNextPage else { return }

        currentPage = 0
        canLoadMore = true
        isLoadingNextPage = true
        await loadNextPage(replacingExisting: true)
    }

    /// Fetches the current page of posts. When `replacingExisting` is true the
    /// freshly fetched posts replace the existing list (used by pull-to-refresh);
    /// otherwise they are appended (used by infinite scrolling).
    private func loadNextPage(replacingExisting: Bool = false) async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session found — cannot fetch feed")
                isLoadingNextPage = false
                return
            }

            let responseData = try await api.getPostsInFeed(sessionManagementToken: userSession.sessionToken, batch: currentPage)
            let newPosts = try JSONDecoder().decode([Post].self, from: responseData)

            if newPosts.isEmpty {
                if replacingExisting { feedPosts = [] }
                canLoadMore = false
            } else {
                if replacingExisting {
                    feedPosts = newPosts
                } else {
                    feedPosts.append(contentsOf: newPosts)
                }
                currentPage += 1
            }
        } catch {
            NSLog("%@", "Failed to fetch feed: \(error)")
        }
        isLoadingNextPage = false
    }
}
