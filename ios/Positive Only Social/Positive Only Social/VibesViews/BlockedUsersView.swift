//
//  BlockedUsersView.swift
//  Positive Only Social
//
//  Lists everyone the signed-in user has blocked, each with an Unblock
//  button. Reached from Settings.
//

import SwiftUI

struct BlockedUsersView: View {
    @StateObject private var viewModel: BlockedUsersViewModel

    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: BlockedUsersViewModel(api: api, keychainHelper: keychainHelper))
    }

    var body: some View {
        List {
            if viewModel.blockedUsers.isEmpty && !viewModel.isLoading {
                Text("You haven't blocked anyone.").foregroundColor(.gray)
            }
            ForEach(viewModel.blockedUsers) { user in
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
                    Button("Unblock") {
                        Task { await viewModel.unblock(username: user.username) }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .disabled(viewModel.unblockingUsernames.contains(user.username))
                    .accessibilityIdentifier("UnblockButton")
                }
            }
        }
        .navigationTitle("Blocked Users")
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
        BlockedUsersView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
    }
}
