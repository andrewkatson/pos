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
    @Published var errorMessage: String?
    /// Usernames with an approve/deny in flight, so each row's buttons disable
    /// independently (several decisions may overlap).
    @Published var decidingUsernames: Set<String> = []

    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String = "userSessionToken") {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }

    private func loadSession() throws -> UserSession? {
        try keychainHelper.load(UserSession.self, from: keychainService, account: account)
    }

    /// Loads (or reloads) the incoming requests, newest first.
    func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            guard let session = try loadSession() else {
                NSLog("%@", "No active session found — cannot load follow requests")
                return
            }
            let data = try await api.getFollowRequests(sessionManagementToken: session.sessionToken)
            requests = try JSONDecoder().decode([User].self, from: data)
        } catch {
            if error.isCancellation {
                NSLog("%@", "Follow requests load cancelled")
            } else {
                NSLog("%@", "Error loading follow requests: \(error)")
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
            requests.removeAll { $0.username == username }
        } catch {
            NSLog("%@", "Error answering follow request: \(error)")
            errorMessage = error.userFacingMessage
        }
    }
}
