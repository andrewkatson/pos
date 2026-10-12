//
//  FollowRequestsViewModel.swift
//  Vibes
//
//  Loads the signed-in private account's incoming follow requests and approves
//  or denies them (issue #96). Reached from Settings and from the owner's
//  profile header.
//

import Foundation
import Combine

/// The navigation value the profile header pushes to open the follow requests
/// list. Hashable so it can ride the Profile tab's NavigationPath alongside
/// `FollowListMode`.
struct FollowRequestsDestination: Hashable {}

@MainActor
final class FollowRequestsViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    @Published var requests: [User] = []
    @Published var isLoading = false
    /// Set once a load succeeds, so a failed load shows only its error — never
    /// the "no one is waiting" empty state for a list that was never fetched.
    @Published var hasLoaded = false
    /// Whether another page may exist (issue #96: a popular account's backlog
    /// is unbounded, so the list is paginated).
    @Published private(set) var canLoadMore = false
    @Published private(set) var isLoadingMore = false
    /// Keyset cursor: the oldest request id loaded so far, kept even if that
    /// row is answered meanwhile, so answering rows can't shift a later request
    /// out of the next page.
    private var nextCursor: Int?
    /// Bumped by every approve/deny that succeeds. A full load that started
    /// before a decision drops its response, so a pull-to-refresh overlapping a
    /// decision can't put the answered row back.
    private var decisionGeneration = 0
    /// Bumped by every full load (pull-to-refresh). A next page requested with
    /// the previous cursor is dropped once a full load has started, since the
    /// refreshed list's cursor may differ and appending it could skip requests.
    private var fullLoadGeneration = 0
    @Published var errorMessage: String?
    /// Usernames with an approve/deny in flight, so each row's buttons disable
    /// independently (several decisions may overlap).
    @Published var decidingUsernames: Set<String> = []

    private let notificationCenter: NotificationCenter

    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String = "userSessionToken",
         notificationCenter: NotificationCenter = .default) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
        self.notificationCenter = notificationCenter
    }

    private func loadSession() throws -> UserSession? {
        try keychainHelper.load(UserSession.self, from: keychainService, account: account)
    }

    /// Loads (or reloads) the incoming requests, newest first.
    func load() async {
        let generation = decisionGeneration
        fullLoadGeneration += 1
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            guard let session = try loadSession() else {
                NSLog("%@", "No active session found — cannot load follow requests")
                return
            }
            let data = try await api.getFollowRequests(sessionManagementToken: session.sessionToken, after: nil)
            let page = try JSONDecoder().decode([User].self, from: data)
            guard generation == decisionGeneration else { return }
            requests = page
            nextCursor = requests.last?.requestId
            canLoadMore = !requests.isEmpty
            hasLoaded = true
        } catch {
            if error.isCancellation {
                NSLog("%@", "Follow requests load cancelled")
            } else {
                NSLog("%@", "Error loading follow requests: \(error)")
                errorMessage = error.userFacingMessage
            }
        }
    }

    /// Fetches the next page and appends it, skipping anyone already listed
    /// (answering rows shifts later pages up). An empty page ends the list.
    func loadMore() async {
        guard canLoadMore, !isLoadingMore, !isLoading else { return }
        let generation = fullLoadGeneration
        isLoadingMore = true
        defer { isLoadingMore = false }
        do {
            guard let session = try loadSession() else { return }
            let data = try await api.getFollowRequests(sessionManagementToken: session.sessionToken, after: nextCursor)
            let page = try JSONDecoder().decode([User].self, from: data)
            // Superseded by a pull-to-refresh: that full load owns the list and
            // its cursor now.
            guard generation == fullLoadGeneration else { return }
            // No decision check here, unlike load(): this page holds only
            // requests older than the cursor, so it can't contain a row answered
            // meanwhile — and dropping it could strand the rest of the backlog
            // when the answered row was the last one on screen.
            let shown = Set(requests.map(\.username))
            requests.append(contentsOf: page.filter { !shown.contains($0.username) })
            if let last = page.last?.requestId { nextCursor = last }
            canLoadMore = !page.isEmpty
        } catch {
            if !error.isCancellation {
                NSLog("%@", "Error loading more follow requests: \(error)")
                errorMessage = error.userFacingMessage
            }
        }
    }

    /// Approves `username`'s request — they become a follower — and drops the row.
    func approve(username: String) async {
        await decide(username: username) { token in
            _ = try await self.api.approveFollowRequest(sessionManagementToken: token, username: username)
        }
    }

    /// Denies `username`'s request and drops the row. The requester isn't told.
    func deny(username: String) async {
        await decide(username: username) { token in
            _ = try await self.api.denyFollowRequest(sessionManagementToken: token, username: username)
        }
    }

    private func decide(username: String, _ call: (String) async throws -> Void) async {
        decidingUsernames.insert(username)
        errorMessage = nil
        defer { decidingUsernames.remove(username) }
        do {
            guard let session = try loadSession() else {
                errorMessage = "You must be logged in to answer a follow request."
                return
            }
            try await call(session.sessionToken)
            decisionGeneration += 1
            requests.removeAll { $0.username == username }
            // The owner's profile refreshes its request badge and follower count.
            notificationCenter.post(name: .followRequestsChanged, object: nil)
        } catch {
            NSLog("%@", "Error answering follow request: \(error)")
            errorMessage = error.userFacingMessage
        }
    }
}
