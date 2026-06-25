//
//  AppealsViewModel.swift
//  Positive Only Social
//
//  Loads the signed-in user's hidden posts/comments and their filed appeals,
//  and submits new content appeals. Ban appeals are not here — those go through
//  the suspension email (an outright-banned user has no session).
//

import Foundation
import Combine

@MainActor
final class AppealsViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = GVOAppConstants.keychainService

    @Published var hiddenPosts: [HiddenPost] = []
    @Published var hiddenComments: [HiddenComment] = []
    @Published var appeals: [MyAppeal] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String = "userSessionToken") {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }

    private func loadSession() throws -> UserSession? {
        try keychainHelper.load(UserSession.self, from: keychainService, account: account)
    }

    /// Loads (or reloads) the first page of hidden content and filed appeals.
    func load() async {
        isLoading = true
        errorMessage = nil  // clear any stale error from a previous load/submit
        defer { isLoading = false }
        do {
            guard let session = try loadSession() else {
                NSLog("%@", "No active session found — cannot load appeals")
                return
            }
            let token = session.sessionToken
            async let postsData = api.getHiddenPosts(sessionManagementToken: token, batch: 0)
            async let commentsData = api.getHiddenComments(sessionManagementToken: token, batch: 0)
            async let appealsData = api.getMyAppeals(sessionManagementToken: token, batch: 0)

            let decoder = JSONDecoder()
            hiddenPosts = try decoder.decode([HiddenPost].self, from: try await postsData)
            hiddenComments = try decoder.decode([HiddenComment].self, from: try await commentsData)
            appeals = try decoder.decode([MyAppeal].self, from: try await appealsData)
        } catch {
            if error.isCancellation {
                NSLog("%@", "Appeals load cancelled")
            } else {
                NSLog("%@", "Error loading appeals: \(error)")
                errorMessage = error.localizedDescription
            }
        }
    }

    /// Files an appeal for a hidden post or comment. `targetType` is "post" or
    /// "comment". Returns true on success (and reloads so the lists update).
    func submitAppeal(targetType: String, targetIdentifier: String, reason: String) async -> Bool {
        do {
            guard let session = try loadSession() else {
                errorMessage = "You must be logged in to file an appeal."
                return false
            }
            _ = try await api.submitAppeal(
                sessionManagementToken: session.sessionToken,
                targetType: targetType,
                targetIdentifier: targetIdentifier,
                reason: reason
            )
            await load()
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }
}
