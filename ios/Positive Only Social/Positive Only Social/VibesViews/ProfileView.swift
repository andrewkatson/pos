//
//  ProfileView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/20/25.
//

import SwiftUI

// A helper view for displaying stats
struct StatItem: View {
    let count: Int
    let label: String
    
    var body: some View {
        VStack {
            Text("\(count)")
                .font(.headline)
                .fontWeight(.bold)
                .accessibilityIdentifier("\(label)Count")
            Text(label)
                .font(.caption)
                .foregroundColor(.gray)
                .accessibilityIdentifier(label)
        }
    }
}

/// Another user's profile, pushed from a search result, a feed row or a post.
///
/// The profile itself lives in `ProfileBodyView`, which the Profile tab renders
/// too — the signed-in user's own profile is the same view (issue #347).
struct ProfileView: View {

    // This view has its own ViewModel to manage its own state
    @StateObject private var viewModel: ProfileViewModel
    // Powers the like / report / delete controls on each post (issue #267).
    @StateObject private var postActions: PostActionsViewModel

    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol

    init(user: User, api: Networking, keychainHelper: KeychainHelperProtocol) {
        // Initialize the StateObject with the user and API
        _viewModel = StateObject(wrappedValue: ProfileViewModel(user: user, api: api, keychainHelper: keychainHelper))
        _postActions = StateObject(wrappedValue: PostActionsViewModel(api: api, keychainHelper: keychainHelper))

        self.api = api
        self.keychainHelper = keychainHelper
    }

    var body: some View {
        ProfileBodyView(viewModel: viewModel, postActions: postActions)
            .navigationTitle(viewModel.user.username) // Set title to the user's name
            .navigationDestination(for: Post.self) { post in
                PostDetailView(postIdentifier: post.id, api: api, keychainHelper: keychainHelper)
            }
            .postActionDialogs(postActions)
    }
}

/// The body of a profile: the stat header (and, for anyone but the signed-in
/// user, the Follow / Block buttons) above that user's post grid.
///
/// Shared by `ProfileView` and the Profile tab so the stats have a single
/// implementation. It deliberately declares neither a navigation title nor a
/// navigation destination — the container owns those, since the two containers
/// title the screen differently and register different destinations.
struct ProfileBodyView: View {

    @ObservedObject var viewModel: ProfileViewModel
    @ObservedObject var postActions: PostActionsViewModel

    /// The accessibility identifier for each grid tile. The Profile tab keeps
    /// "MyPostImage" so your own grid stays distinguishable from someone else's.
    var postAccessibilityIdentifier: String = "ProfilePostImage"

    // Grid layout: 3 columns with a 1pt gap that shows the black grid
    // background as a thin border between posts.
    private let columns: [GridItem] = Array(repeating: GridItem(.flexible(), spacing: 1), count: 3)

    var body: some View {
        ScrollView {
            profileHeader.padding(.horizontal)
            Divider()
            postGrid
        }
        // Surfaces the outcome when one of your posts' async review (#282)
        // resolves to a rejection while this grid is visible. Only your own
        // posts carry a status, so this never fires on someone else's profile.
        .alert(
            "Post Review",
            isPresented: Binding(
                get: { viewModel.reviewNotice != nil },
                set: { if !$0 { viewModel.reviewNotice = nil } }
            )
        ) {
            Button("OK") { viewModel.reviewNotice = nil }
                .accessibilityIdentifier("OkButtonReviewNotice")
        } message: {
            Text(viewModel.reviewNotice ?? "")
        }
        .refreshable {
            // Pull-to-refresh: reload the newest posts and the profile stats /
            // follow-block status so neither goes stale.
            // Run the reloads in an unstructured Task so SwiftUI cancelling
            // the refreshable task on a re-render can't cancel the requests.
            await Task {
                await viewModel.refreshUserPosts()
                await viewModel.refreshProfileDetails()
            }.value
        }
        .onAppear {
            // Fetch posts when the view appears for the first time
            if viewModel.userPosts.isEmpty {
                viewModel.fetchUserPosts()
            }

            if viewModel.profileDetails == nil {
                viewModel.fetchProfileDetails()
            }
        }
    }

    /// A new sub-view for the profile header and follow button
    @ViewBuilder
    private var profileHeader: some View {
        VStack {
            // Placeholder for profile stats (you can build this out)
            HStack {
                Spacer()
                StatItem(count: viewModel.userPosts.count, label: "Posts")
                Spacer()
                // Only your own follow lists are viewable, so the counts tap
                // through on your own profile and are plain stats on anyone
                // else's (issue #8). The container registers the destination.
                if viewModel.isOwnProfile {
                    NavigationLink(value: FollowListMode.followers) {
                        StatItem(count: viewModel.profileDetails?.followerCount ?? 0, label: "Followers")
                    }
                    .buttonStyle(.plain)
                    Spacer()
                    NavigationLink(value: FollowListMode.following) {
                        StatItem(count: viewModel.profileDetails?.followingCount ?? 0, label: "Following")
                    }
                    .buttonStyle(.plain)
                } else {
                    StatItem(count: viewModel.profileDetails?.followerCount ?? 0, label: "Followers")
                    Spacer()
                    StatItem(count: viewModel.profileDetails?.followingCount ?? 0, label: "Following")
                }
                Spacer()
            }
            .padding(.top)
            
            if !viewModel.isOwnProfile {
                Button(action: viewModel.toggleFollow) {
                    Text(viewModel.isFollowing ? "Following" : "Follow")
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(viewModel.isFollowing ? Color.clear : Color.blue)
                        .foregroundColor(viewModel.isFollowing ? .primary : .white)
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(viewModel.isFollowing ? Color.gray : Color.blue, lineWidth: 1)
                        )
                }
                .disabled(viewModel.isLoadingProfile || viewModel.isBusy)
                .padding(.vertical)
                .accessibilityIdentifier("FollowButton")

                Button(action: viewModel.toggleBlock) {
                    Text(viewModel.isBlocked ? "Unblock" : "Block")
                        .fontWeight(.medium)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .foregroundColor(viewModel.isBlocked ? .white : .red)
                        .background(viewModel.isBlocked ? Color.red : Color.clear)
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.red, lineWidth: 1)
                        )
                }
                .disabled(viewModel.isLoadingProfile || viewModel.isBusy)
                .padding(.bottom)
            }
        }
    }
    
    /// The view for displaying the user's posts
    @ViewBuilder
    private var postGrid: some View {
        // Show a loading indicator while fetching initial posts
        if viewModel.userPosts.isEmpty && viewModel.isLoading {
            ProgressView()
                .padding(.top, 50)
            // Show a message if the user has no posts
        } else if viewModel.userPosts.isEmpty && !viewModel.isLoading {
            Text("\(viewModel.user.username) hasn't posted anything yet.")
                .foregroundColor(.gray)
                .padding(.top, 50)
            // Display the post grid
        } else {
            LazyVGrid(columns: columns, spacing: 1) {
                ForEach(viewModel.userPosts) { post in
                    // The action bar sits below the tile, outside the link, so
                    // it can't swallow the tap that opens the post (#267). The
                    // square tiles have no room for the comment count or the
                    // post's age, so those stay on the feed rows only (#249).
                    VStack(spacing: 0) {
                        // Wrap each cell in a NavigationLink so tapping a post opens
                        // its detail view (destination registered by the container).
                        NavigationLink(value: post) {
                            // Force every post into an identical square, cropping to fill
                            // so images no longer keep their original dimensions.
                            Color(.systemGray4)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    GridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        caption: post.caption
                                    )
                                }
                                .overlay(alignment: .bottom) {
                                    // Author-only classification state (#282):
                                    // "In review" while the async classifier
                                    // runs, or the appeal hint on a rejection.
                                    // Only your own posts carry a status, so
                                    // this is absent on someone else's profile.
                                    if let badge = statusBadgeLabel(for: post) {
                                        Text(badge)
                                            .font(.caption2)
                                            .foregroundColor(.white)
                                            .frame(maxWidth: .infinity)
                                            .padding(.vertical, 3)
                                            .background(Color.black.opacity(0.72))
                                            .accessibilityIdentifier("PostStatusBadge")
                                    }
                                }
                                .clipped()
                        }
                        .accessibilityIdentifier(postAccessibilityIdentifier)

                        PostActionBar(post: post, postActions: postActions)
                    }
                    // Keeps the action bar off the grid's black backing, which
                    // is only meant to show through as the 1pt tile borders.
                    .background(Color(.systemBackground))
                    .onAppear {
                        // Trigger for infinite scrolling
                        if post.id == viewModel.userPosts.last?.id {
                            viewModel.fetchUserPosts()
                        }
                    }
                }
            }
            // Black backing shows through the 1pt gaps as thin borders between posts.
            .background(Color.black)
        }
    }
}

#Preview {
    ProfileView(user: User(username: "test", identityIsVerified: true), api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}

/// Overlay label for the author's own pending/rejected grid tiles (#282).
private func statusBadgeLabel(for post: Post) -> String? {
    switch post.status {
    case "pending": return "In review"
    case "rejected": return "Hidden — you can appeal"
    default: return nil
    }
}
