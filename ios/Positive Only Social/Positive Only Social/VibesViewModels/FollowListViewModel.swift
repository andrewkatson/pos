//
//  FollowListViewModel.swift
//  Positive Only Social
//
//  Loads the signed-in user's own followers or following list. Only your own
//  lists are ever fetched — the endpoints take no username — so nobody else's
//  followers/following can be viewed (issue #8). Reached by tapping the
//  Followers / Following counts on your own profile.
//

import Foundation
import Combine

/// Which of the two own-lists a `FollowListView` shows. Hashable so it can be a
/// navigation value pushed from the profile stat header.
enum FollowListMode: Hashable {
    case followers
    case following

    /// The navigation-bar title for this list.
    var title: String {
        switch self {
        case .followers: return "Followers"
        case .following: return "Following"
        }
    }

    /// The message shown when the list is empty.
    var emptyMessage: String {
        switch self {
        case .followers: return "You don't have any followers yet."
        case .following: return "You aren't following anyone yet."
        }
    }
}

@MainActor
final class FollowListViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    let mode: FollowListMode

    @Published var users: [User] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    init(mode: FollowListMode, api: Networking, keychainHelper: KeychainHelperProtocol, account: String = "userSessionToken") {
        self.mode = mode
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }

    private func loadSession() throws -> UserSession? {
        try keychainHelper.load(UserSession.self, from: keychainService, account: account)
    }

    /// Loads (or reloads) the list for this mode.
    func load() async {
        isLoading = true
        errorMessage = nil  // clear any stale error from a previous load
        defer { isLoading = false }
        do {
            guard let session = try loadSession() else {
                NSLog("%@", "No active session found — cannot load \(mode.title)")
                return
            }
            let data: Data
            switch mode {
            case .followers:
                data = try await api.getFollowers(sessionManagementToken: session.sessionToken)
            case .following:
                data = try await api.getFollowing(sessionManagementToken: session.sessionToken)
            }
            users = try JSONDecoder().decode([User].self, from: data)
        } catch {
            if error.isCancellation {
                NSLog("%@", "\(mode.title) load cancelled")
            } else {
                NSLog("%@", "Error loading \(mode.title): \(error)")
                errorMessage = error.userFacingMessage
            }
        }
    }
}
