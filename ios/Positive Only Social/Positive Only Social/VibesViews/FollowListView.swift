//
//  FollowListView.swift
//  Positive Only Social
//
//  Shows the signed-in user's own followers or following list, each row a
//  tap-through to that user's profile. Only your own lists are shown (issue #8);
//  reached from the Followers / Following counts on your own profile.
//

import SwiftUI

struct FollowListView: View {
    @StateObject private var viewModel: FollowListViewModel

    /// Whether tapping the current user's own row should push their profile
    /// again. It's the signed-in user's own list, so their own row (if present)
    /// selects the Profile tab rather than pushing a second copy (issue #347).
    private let currentUsername: String?

    init(mode: FollowListMode, api: Networking, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: FollowListViewModel(mode: mode, api: api, keychainHelper: keychainHelper))
        self.currentUsername = try? keychainHelper.load(
            UserSession.self, from: GVOAppConstants.keychainService, account: "userSessionToken"
        )?.username
    }

    var body: some View {
        List {
            if viewModel.users.isEmpty && !viewModel.isLoading {
                Text(viewModel.mode.emptyMessage).foregroundColor(.gray)
            }
            ForEach(viewModel.users) { user in
                AuthorNameLink(username: user.username, isCurrentUser: user.username == currentUsername) {
                    HStack {
                        Image(systemName: "person.circle.fill")
                            .foregroundColor(.gray)
                        Text(user.username)
                        if user.identityIsVerified {
                            Image(systemName: "checkmark.seal.fill")
                                .foregroundColor(.blue)
                                .accessibilityLabel("Verified")
                        }
                        Spacer()
                    }
                    .contentShape(Rectangle())
                }
                .accessibilityIdentifier(user.username)
            }
        }
        .navigationTitle(viewModel.mode.title)
        .navigationBarTitleDisplayMode(.inline)
        .task { await viewModel.load() }
        .refreshable { await viewModel.load() }
        .alert("Error", isPresented: Binding(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { viewModel.errorMessage = nil }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }
}

#Preview {
    NavigationStack {
        FollowListView(mode: .followers, api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
    }
}
