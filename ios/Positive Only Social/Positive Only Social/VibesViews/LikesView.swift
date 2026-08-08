//
//  LikesView.swift
//  Positive Only Social
//
//  "Who liked this" (issue #478): the scrollable, batched list of accounts
//  behind one of your own posts' or comments' like counts, presented as a sheet
//  from that count. Only your own content is listed — the backend answers for
//  nobody else's — so the count is only tappable on your own post/comment.
//
//  Mirrors the web LikesModal and the Android LikesDialog.
//

import SwiftUI

struct LikesView: View {
    @StateObject private var viewModel: LikesViewModel

    @Environment(\.dismiss) private var dismiss

    /// Set when a liker's row is tapped, to push their profile.
    @State private var selectedUser: User? = nil

    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol

    init(target: LikesTarget, api: Networking, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: LikesViewModel(target: target, api: api, keychainHelper: keychainHelper))
        self.api = api
        self.keychainHelper = keychainHelper
    }

    var body: some View {
        NavigationStack {
            List {
                if viewModel.users.isEmpty && !viewModel.isLoading {
                    Text("No one has liked this yet.").foregroundColor(.gray)
                }
                ForEach(viewModel.users) { user in
                    Button {
                        selectedUser = user
                    } label: {
                        HStack {
                            ProfileAvatarView(
                                imageUrl: user.authorProfileImageUrl,
                                originalImageUrl: user.authorProfileImageOriginalUrl,
                                size: 28
                            )
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
                    .buttonStyle(.plain)
                    .accessibilityIdentifier(user.username)
                }
                // Paging control rather than an infinite scroll, matching the
                // feed: the user asks for the next batch.
                if viewModel.canLoadMore {
                    Button("Load more") {
                        Task { await viewModel.loadMore() }
                    }
                    .accessibilityIdentifier("LoadMoreLikesButton")
                }
                if viewModel.isLoading {
                    ProgressView()
                }
            }
            .navigationTitle(viewModel.target.title)
            .navigationBarTitleDisplayMode(.inline)
            // State-driven push rather than an inline NavigationLink, matching
            // how the post detail screen opens a tapped author's profile.
            .navigationDestination(isPresented: Binding(
                get: { selectedUser != nil },
                set: { if !$0 { selectedUser = nil } }
            )) {
                if let user = selectedUser {
                    ProfileView(user: user, api: api, keychainHelper: keychainHelper)
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
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
}

#Preview {
    LikesView(
        target: .post(postIdentifier: "preview-post"),
        api: PreviewHelpers.api,
        keychainHelper: PreviewHelpers.keychainHelper
    )
}
