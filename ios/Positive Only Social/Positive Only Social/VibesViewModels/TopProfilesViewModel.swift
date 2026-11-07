//
//  TopProfilesViewModel.swift
//  Vibes
//

import Foundation
import Combine

/// ViewModel for the Profiles board in the Feed tab's Top segment: the public
/// accounts with the most followers, all-time (issue #588). Pages like
/// TopPostsViewModel, minus the period picker.
@MainActor
final class TopProfilesViewModel: ObservableObject {
    // State the view observes.
    @Published var topProfiles: [TopProfile] = []
    @Published var isLoadingNextPage = false

    // Dependencies.
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    // Pagination state.
    /// True once a page comes back empty: the whole board is loaded, so the
    /// view shows the "you finished!" banner. A failed load leaves it alone.
    @Published private(set) var reachedEnd = false
    private var canLoadMore = true {
        didSet { reachedEnd = !canLoadMore }
    }
    private var currentPage = 0

    convenience init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }

    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }

    func fetchTopProfiles() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true
        Task { await loadPage(currentPage, replacingExisting: false) }
    }

    /// Reloads the board from the first page. `async` so `.refreshable` keeps
    /// its spinner until the fresh rows arrive; the cursor is only reset once
    /// the first page loads, so a failed refresh leaves it intact.
    func refresh() async {
        guard !isLoadingNextPage else { return }
        isLoadingNextPage = true
        await loadPage(0, replacingExisting: true)
    }

    private func loadPage(_ page: Int, replacingExisting: Bool) async {
        do {
            guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                NSLog("%@", "No active session — cannot fetch top profiles")
                isLoadingNextPage = false
                return
            }

            var page = page
            while true {
                let responseData = try await api.getTopProfiles(
                    sessionManagementToken: userSession.sessionToken, batch: page)
                let newProfiles = try JSONDecoder().decode([TopProfile].self, from: responseData)

                if replacingExisting {
                    topProfiles = newProfiles
                    canLoadMore = !newProfiles.isEmpty
                    currentPage = newProfiles.isEmpty ? 0 : 1
                    break
                }
                if newProfiles.isEmpty {
                    canLoadMore = false
                    break
                }
                // Live OFFSET paging can repeat an account whose rank moved
                // between requests; drop repeats so ForEach identities stay unique.
                let seen = Set(topProfiles.map(\.id))
                let unseen = newProfiles.filter { !seen.contains($0.id) }
                currentPage += 1
                if !unseen.isEmpty {
                    topProfiles.append(contentsOf: unseen)
                    break
                }
                // A page of nothing but repeats appends no row, so the last
                // row's onAppear would never fire again: keep going.
                page = currentPage
            }
        } catch {
            NSLog("%@", "Failed to fetch top profiles: \(error)")
        }
        isLoadingNextPage = false
    }
}
