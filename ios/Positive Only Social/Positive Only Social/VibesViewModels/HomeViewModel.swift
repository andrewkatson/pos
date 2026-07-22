//
//  HomeViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import Foundation
import Combine

/// Backs the first tab. Since issue #347 that tab shows the signed-in user's own
/// profile, whose post grid is loaded by `ProfileViewModel` (the same one every
/// other profile uses), so what this view model drives there is the user search.
@MainActor
final class HomeViewModel: ObservableObject {
    // MARK: - Properties
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService
    
    // Data for the view
    @Published var userPosts: [Post] = []
    @Published var searchedUsers: [User] = []
    @Published var searchText = ""
    
    // State tracking
    @Published var isLoadingNextPage = false
    @Published var errorMessage: String?
    private var canLoadMorePosts = true
    private var currentPage = 0

    // For debouncing search text
    private var searchCancellable: AnyCancellable?

    // Listens for `.postDeleted` so a post deleted from its detail view is also
    // dropped from this grid's cached list.
    private var postDeletedCancellable: AnyCancellable?

    /// The signed-in user's username, loaded once at init. Search results use it
    /// so tapping yourself doesn't navigate to a profile you're already on (#347).
    private(set) var currentUsername: String?

    // MARK: - Initializer
    convenience init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }

    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String,
         notificationCenter: NotificationCenter = .default) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
        self.currentUsername = try? keychainHelper.load(
            UserSession.self, from: GVOAppConstants.keychainService, account: account
        )?.username

        // This subscriber automatically triggers a search when the user stops typing.
        searchCancellable = $searchText
            .debounce(for: .milliseconds(500), scheduler: RunLoop.main) // Wait 500ms after user stops typing
            .removeDuplicates()
            .sink { [weak self] searchText in
                self?.performSearch(for: searchText)
            }

        // When a post is deleted (from its detail view), remove it from the grid
        // so its now-missing image doesn't linger as an empty grey tile (#256).
        postDeletedCancellable = notificationCenter.publisher(for: .postDeleted)
            .receive(on: RunLoop.main)
            .sink { [weak self] notification in
                guard let postIdentifier = notification.object as? String else { return }
                self?.userPosts.removeAll { $0.id == postIdentifier }
            }
    }

    // MARK: - Public Methods
    
    /// Fetches the next page of the current user's posts.
    func fetchMyPosts() {
        // Prevent multiple fetches at the same time or fetching beyond the end
        guard !isLoadingNextPage && canLoadMorePosts else { return }

        isLoadingNextPage = true

        Task {
            await loadPage(currentPage, replacingExisting: false)
        }
    }

    /// Reloads the user's posts from the first page.
    ///
    /// This is `async` so SwiftUI's `.refreshable` keeps the pull-to-refresh
    /// spinner visible until the fresh posts have actually been loaded. The
    /// pagination cursor is only reset once the first page successfully loads,
    /// so a failed refresh leaves the existing cursor (and posts) intact and
    /// can't cause the next infinite-scroll fetch to duplicate page 0.
    func refreshMyPosts() async {
        // Avoid stomping on an in-flight page load.
        guard !isLoadingNextPage else { return }

        isLoadingNextPage = true
        await loadPage(0, replacingExisting: true)
    }

    /// Fetches the given page of the user's posts. When `replacingExisting` is
    /// true the freshly fetched posts replace the existing list and the
    /// pagination cursor is reset (used by pull-to-refresh); otherwise they are
    /// appended (used by infinite scrolling). Pagination state is only mutated
    /// on a successful response so failures don't corrupt the cursor.
    private func loadPage(_ page: Int, replacingExisting: Bool) async {
        do {
            guard let user = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session found — cannot fetch posts")
                isLoadingNextPage = false
                return
            }

            // Call the API
            let newPosts = try await fetchPosts(for: user.username, token: user.sessionToken, page: page)

            if replacingExisting {
                self.userPosts = newPosts
                self.canLoadMorePosts = !newPosts.isEmpty
                self.currentPage = newPosts.isEmpty ? 0 : 1
                // A fresh first page grants a fresh reconcile-poll budget (#282).
            } else if newPosts.isEmpty {
                // No more posts to load
                self.canLoadMorePosts = false
            } else {
                self.userPosts.append(contentsOf: newPosts)
                self.currentPage += 1
            }
            self.startStatusPollIfNeeded()

        } catch {
            // A cancelled load (e.g. SwiftUI tearing down a pull-to-refresh
            // task) is not a real failure — keep the existing data and stay
            // quiet so routine cancellations don't pollute the error logs.
            if error.isCancellation {
                NSLog("%@", "My posts load cancelled")
            } else {
                NSLog("%@", "Error fetching my posts: \(error)")
                errorMessage = error.userFacingMessage
            }
        }

        self.isLoadingNextPage = false
    }

    // MARK: - Private Helpers

    /// Called automatically by the search text subscriber.
    private func performSearch(for query: String) {
        // Only search if query is 3+ characters
        guard query.count >= 3 else {
            searchedUsers = []
            return
        }

        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session found — cannot search users")
                    return
                }

                let results = try await searchForUsers(fragment: query, token: userSession.sessionToken)

                // The user may have kept typing while this request was in
                // flight; drop the results if they're for a stale query so a
                // slow response can't overwrite results for the current text.
                guard query == self.searchText else { return }
                self.searchedUsers = results
            } catch {
                // Cancelled searches (e.g. superseded by newer keystrokes) are
                // routine, not failures worth alerting or error-logging about.
                if error.isCancellation {
                    NSLog("%@", "Search for \"\(query)\" cancelled")
                } else {
                    NSLog("%@", "Error performing search: \(error)")
                    self.errorMessage = error.userFacingMessage
                }
            }
        }
    }
    
    // Decodes the API response for get_posts_for_user
    private func fetchPosts(for username: String, token: String, page: Int) async throws -> [Post] {
        let responseData = try await api.getPostsForUser(sessionManagementToken: token, username: username, batch: page)
        return try JSONDecoder().decode([Post].self, from: responseData)
    }

    // Decodes the API response for get_users_matching_fragment
    private func searchForUsers(fragment: String, token: String) async throws -> [User] {
        let responseData = try await api.getUsersMatchingFragment(sessionManagementToken: token, usernameFragment: fragment)
        return try JSONDecoder().decode([User].self, from: responseData)
    }
}
