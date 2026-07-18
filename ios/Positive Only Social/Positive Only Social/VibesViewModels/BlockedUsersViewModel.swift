//
//  BlockedUsersViewModel.swift
//  Positive Only Social
//
//  Loads the signed-in user's blocked users and unblocks them on demand
//  (toggle_block). Reached from Settings.
//

import Foundation
import Combine

@MainActor
final class BlockedUsersViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    @Published var blockedUsers: [User] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    /// The username currently being unblocked, so its button can be disabled.
    @Published var unblockingUsername: String?

    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String = "userSessionToken") {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }

    private func loadSession() throws -> UserSession? {
        try keychainHelper.load(UserSession.self, from: keychainService, account: account)
    }

    /// Loads (or reloads) the full list of blocked users.
    func load() async {
        isLoading = true
        errorMessage = nil  // clear any stale error from a previous load/unblock
        defer { isLoading = false }
        do {
            guard let session = try loadSession() else {
                NSLog("%@", "No active session found — cannot load blocked users")
                return
            }
            let data = try await api.getBlockedUsers(sessionManagementToken: session.sessionToken)
            blockedUsers = try JSONDecoder().decode([User].self, from: data)
        } catch {
            if error.isCancellation {
                NSLog("%@", "Blocked users load cancelled")
            } else {
                NSLog("%@", "Error loading blocked users: \(error)")
                errorMessage = error.userFacingMessage
            }
        }
    }

    /// Unblocks a user via toggle_block and removes them from the list.
    func unblock(username: String) async {
        unblockingUsername = username
        errorMessage = nil
        defer { unblockingUsername = nil }
        do {
            guard let session = try loadSession() else {
                errorMessage = "You must be logged in to unblock a user."
                return
            }
            _ = try await api.toggleBlock(sessionManagementToken: session.sessionToken, username: username)
            blockedUsers.removeAll { $0.username == username }
        } catch {
            NSLog("%@", "Error unblocking user: \(error)")
            errorMessage = error.userFacingMessage
        }
    }
}
