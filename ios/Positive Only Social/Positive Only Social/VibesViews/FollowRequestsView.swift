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
            // Empty only once paging has ended: answering every loaded row can
            // leave older pages still to fetch.
            if viewModel.hasLoaded && viewModel.requests.isEmpty && !viewModel.isLoading
                && !viewModel.canLoadMore {
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
                    .accessibilityLabel("Approve \(user.username)")
                    .accessibilityIdentifier("ApproveFollowRequestButton")
                    Button("Deny") {
                        Task { await viewModel.deny(username: user.username) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .accessibilityLabel("Deny \(user.username)")
                    .accessibilityIdentifier("DenyFollowRequestButton")
                }
                .disabled(viewModel.decidingUsernames.contains(user.username))
            }
            // The pager sits after the rows rather than on the last one, so it
            // survives every loaded row being answered. Scrolling it into view
            // fetches the next page; tapping retries a failed fetch.
            if viewModel.hasLoaded && viewModel.canLoadMore {
                Button("Load more") {
                    Task { await viewModel.loadMore() }
                }
                .disabled(viewModel.isLoadingMore)
                .frame(maxWidth: .infinity)
                .onAppear { Task { await viewModel.loadMore() } }
                .accessibilityIdentifier("LoadMoreFollowRequestsButton")
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
