// xcode: set sdk=iOS

//
//  FollowRequestsView.swift
//  Vibes
//
//  Lists everyone waiting to follow the signed-in private account, each with
//  Approve and Deny (issue #96). Reached from Settings and the owner's profile.
//

import SwiftUI

struct FollowRequestsView: View {
    @StateObject private var viewModel: FollowRequestsViewModel

    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: FollowRequestsViewModel(api: api, keychainHelper: keychainHelper))
    }

    var body: some View {
        List {
            if viewModel.hasLoaded && viewModel.requests.isEmpty && !viewModel.isLoading {
                Text("No one is waiting to follow you.").foregroundColor(.gray)
            }
            ForEach(viewModel.requests) { user in
                HStack {
                    ProfileAvatarView(
                        imageUrl: user.authorProfileImageUrl,
                        originalImageUrl: user.authorProfileImageOriginalUrl,
                        blurHash: user.authorProfileImageBlurHash,
                        size: 32
                    )
                    Text(user.username)
                    if user.identityIsVerified {
                        Image(systemName: "checkmark.seal.fill")
                            .foregroundColor(.blue)
                            .accessibilityLabel("Verified")
                    }
                    Spacer()
                    Button("Approve") {
                        Task { await viewModel.approve(username: user.username) }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .accessibilityIdentifier("ApproveFollowRequestButton")
                    Button("Deny") {
                        Task { await viewModel.deny(username: user.username) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .accessibilityIdentifier("DenyFollowRequestButton")
                }
                .disabled(viewModel.decidingUsernames.contains(user.username))
            }
        }
        .navigationTitle("Follow Requests")
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
        FollowRequestsView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
    }
}
