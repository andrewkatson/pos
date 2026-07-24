//
//  FeedView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import SwiftUI

// An enum to define our top tabs
enum FeedType: String, CaseIterable {
    case forYou = "For You"
    case following = "Following"
}

struct FeedView: View {
    @StateObject private var forYouViewModel: FeedViewModel
    @StateObject private var followingViewModel: FollowingFeedViewModel
    // Powers the like / report / delete controls on each feed row (issue #267).
    @StateObject private var postActions: PostActionsViewModel

    // Store api and keychainHelper to pass to navigation destinations
    let api: Networking
    let keychainHelper: KeychainHelperProtocol

    // State to track the selected top tab
    @State private var selectedFeed: FeedType = .forYou

    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        _forYouViewModel = StateObject(wrappedValue: FeedViewModel(api: api, keychainHelper: keychainHelper))
        _followingViewModel = StateObject(wrappedValue: FollowingFeedViewModel(api: api, keychainHelper: keychainHelper))
        _postActions = StateObject(wrappedValue: PostActionsViewModel(api: api, keychainHelper: keychainHelper))

        self.api = api
        self.keychainHelper = keychainHelper
    }

    var body: some View {
        NavigationStack {
            VStack {
                // This Picker creates the segmented top tabs
                Picker("Feed Type", selection: $selectedFeed) {
                    ForEach(FeedType.allCases, id: \.self) { type in
                        Text(type.rawValue).tag(type).accessibilityIdentifier(type.rawValue)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .accessibilityIdentifier("FeedTypePicker")

                // The content switches based on the selected tab
                switch selectedFeed {
                case .forYou:
                    ForYouFeedView(viewModel: forYouViewModel, postActions: postActions)
                case .following:
                    FollowingFeedView(viewModel: followingViewModel, postActions: postActions)
                }
            }
            .navigationTitle("Feed")
            .postActionDialogs(postActions)

            // Handles navigation when a User object is passed
            .navigationDestination(for: User.self) { user in
                ProfileView(user: user, api: api, keychainHelper: keychainHelper)
            }
            
            // Handles navigation when a FeedPost object is passed
            .navigationDestination(for: Post.self) { post in
                PostDetailView(postIdentifier: post.id, api: api, keychainHelper: keychainHelper)
            }
            .onChange(of: selectedFeed) { oldValue, newValue in
                 // Fetch fresh data whenever the tab changes
                 switch newValue {
                 case .forYou:
                     Task { await forYouViewModel.refreshFeed() }
                 case .following:
                     Task { await followingViewModel.refreshFeed() }
                 }
             }
        }
    }
}


// MARK: - Sub-views for Each Tab

/// The view for the "For You" feed, containing the scrolling list of posts.
struct ForYouFeedView: View {
    @ObservedObject var viewModel: FeedViewModel
    @ObservedObject var postActions: PostActionsViewModel

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 25) {
                ForEach(viewModel.feedPosts) { post in
                    VStack(alignment: .leading, spacing: 10) {

                        // Tapping the author opens their profile — or the
                        // Profile tab when it's you (issue #347). Their profile
                        // photo sits next to the name (issue #7).
                        HStack(spacing: 8) {
                            ProfileAvatarView(
                                imageUrl: post.authorProfileImageUrl,
                                originalImageUrl: post.authorProfileImageOriginalUrl,
                                size: 32
                            )
                            AuthorNameLink(
                                username: post.authorUsername,
                                isCurrentUser: postActions.state(for: post).isOwn
                            ) {
                                Text(post.authorUsername)
                                    .font(.headline)
                                    .fontWeight(.bold)
                            }
                            .accessibilityIdentifier("PostAuthor")
                            Spacer()
                        }
                        .padding(.horizontal)

                        // Wrap image in a NavigationLink to go to post details.
                        // Force every post into an identical square, cropping to
                        // fill so images no longer keep their original dimensions.
                        NavigationLink(value: post) {
                            Color(.systemGray5)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    GridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        caption: post.caption,
                                        captionFont: post.captionFont,
                                        backgroundColor: post.backgroundColor,
                                        placeholderColor: Color(.systemGray5)
                                    )
                                }
                                .clipped()
                                .border(Color.gray, width: 0.5)
                                .cornerRadius(15)
                                .shadow(color: Color.black.opacity(0.4), radius: 10, x: 0, y: 0)
                        }
                        .onAppear {
                            // Trigger for infinite scrolling
                            if post.id == viewModel.feedPosts.last?.id {
                                viewModel.fetchFeed()
                            }
                        }
                        .accessibilityIdentifier("ForYouPostImage")

                        // Like / report / delete, the comment count and the
                        // post's age (issues #267 and #249).
                        PostActionBar(post: post, postActions: postActions, showsPostDetails: true)
                            .padding(.horizontal)
                    }
                }
                // Loading indicator at the bottom of the list
                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }
            }
            .padding(.top)
        }
        .refreshable {
            // Pull-to-refresh: reload the newest posts from the backend.
            // Run the reload in an unstructured Task so SwiftUI cancelling
            // the refreshable task on a re-render can't cancel the request.
            await Task { await viewModel.refreshFeed() }.value
        }
        .onAppear {
            if viewModel.feedPosts.isEmpty {
                viewModel.fetchFeed()
            }
        }
    }
}

/// The view for the "Following" feed.
struct FollowingFeedView: View {
    @ObservedObject var viewModel: FollowingFeedViewModel
    @ObservedObject var postActions: PostActionsViewModel

    var body: some View {
        // We use the same UI structure as ForYouFeedView
        ScrollView {
            LazyVStack(spacing: 25) {
                // Iterate over the followingPosts array
                ForEach(viewModel.followingPosts) { post in
                    VStack(alignment: .leading, spacing: 10) {

                        // Tapping the author opens their profile — or the
                        // Profile tab when it's you (issue #347). Their profile
                        // photo sits next to the name (issue #7).
                        HStack(spacing: 8) {
                            ProfileAvatarView(
                                imageUrl: post.authorProfileImageUrl,
                                originalImageUrl: post.authorProfileImageOriginalUrl,
                                size: 32
                            )
                            AuthorNameLink(
                                username: post.authorUsername,
                                isCurrentUser: postActions.state(for: post).isOwn
                            ) {
                                Text(post.authorUsername)
                                    .font(.headline)
                                    .fontWeight(.bold)
                            }
                            Spacer()
                        }
                        .padding(.horizontal)

                        // Wrap image in a NavigationLink to go to post details.
                        // Force every post into an identical square, cropping to
                        // fill so images no longer keep their original dimensions.
                        NavigationLink(value: post) {
                            Color(.systemGray5)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    GridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        caption: post.caption,
                                        captionFont: post.captionFont,
                                        backgroundColor: post.backgroundColor,
                                        placeholderColor: Color(.systemGray5)
                                    )
                                }
                                .clipped()
                                .border(Color.black, width: 1)
                        }
                        .onAppear {
                            // Trigger for infinite scrolling
                            // Use followingPosts and fetchFollowingFeed
                            if post.id == viewModel.followingPosts.last?.id {
                                viewModel.fetchFollowingFeed()
                            }
                        }
                        .accessibilityIdentifier("FollowingPostImage")

                        // Like / report / delete, the comment count and the
                        // post's age (issues #267 and #249).
                        PostActionBar(post: post, postActions: postActions, showsPostDetails: true)
                            .padding(.horizontal)
                    }
                }
                
                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }
            }
            .padding(.top)
        }
        .refreshable {
            // Pull-to-refresh: reload the newest posts from the backend.
            // Run the reload in an unstructured Task so SwiftUI cancelling
            // the refreshable task on a re-render can't cancel the request.
            await Task { await viewModel.refreshFeed() }.value
        }
        // Add .onAppear to trigger the *initial* fetch
        .onAppear {
            if viewModel.followingPosts.isEmpty {
                viewModel.fetchFollowingFeed()
            }
        }
    }
}


// MARK: - Preview
#Preview {
    // Assuming KeychainHelper() is a valid initializer
    // If not, you may need to use your mock
    FeedView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
