//
//  TopUsersViewModel.swift
//  Vibes
//

import Foundation
import Combine

/// ViewModel for the Top feed's "People" board: who has the most followers
/// right now (issue #562).
@MainActor
final class TopUsersViewModel: ObservableObject {
    // State the view observes.
    @Published var topUsers: [TopUser] = []
    @Published var isLoadingNextPage = false

    // Dependencies.
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    // Pagination state.
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

    func fetchTopUsers() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true
        Task { await loadPage(currentPage, replacingExisting: false) }
    }

    /// Reloads the board from the first page. `async` so `.refreshable` keeps
    /// its spinner until the fresh rows arrive.
    func refresh() async {
        guard !isLoadingNextPage else { return }
        isLoadingNextPage = true
        await loadPage(0, replacingExisting: true)
    }

    private func loadPage(_ page: Int, replacingExisting: Bool) async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot fetch top users")
                isLoadingNextPage = false
                return
            }

            var page = page
            while true {
                let responseData = try await api.getTopUsers(
                    sessionManagementToken: userSession.sessionToken, batch: page)
                let newUsers = try JSONDecoder().decode([TopUser].self, from: responseData)

                if replacingExisting {
                    topUsers = newUsers
                    canLoadMore = !newUsers.isEmpty
                    currentPage = newUsers.isEmpty ? 0 : 1
                    break
                }
                if newUsers.isEmpty {
                    canLoadMore = false
                    break
                }
                // Live OFFSET paging can repeat someone whose count moved between
                // requests; drop repeats so ForEach identities stay unique, and
                // keep going past a page of nothing but repeats so the last
                // row's onAppear isn't left with nothing new to trigger.
                let seen = Set(topUsers.map(\.id))
                let unseen = newUsers.filter { !seen.contains($0.id) }
                currentPage += 1
                if !unseen.isEmpty {
                    topUsers.append(contentsOf: unseen)
                    break
                }
                page = currentPage
            }
        } catch {
            NSLog("%@", "Failed to fetch top users: \(error)")
        }
        isLoadingNextPage = false
    }
}
