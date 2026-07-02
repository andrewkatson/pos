//
//  FeedView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import SwiftUI
import Kingfisher

// An enum to define our top tabs
enum FeedType: String, CaseIterable {
    case forYou = "For You"
    case following = "Following"
}

struct FeedView: View {
    @StateObject private var forYouViewModel: FeedViewModel
    @StateObject private var followingViewModel: FollowingFeedViewModel
    
    // Store api and keychainHelper to pass to navigation destinations
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    // State to track the selected top tab
    @State private var selectedFeed: FeedType = .forYou
    
    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        _forYouViewModel = StateObject(wrappedValue: FeedViewModel(api: api, keychainHelper: keychainHelper))
        _followingViewModel = StateObject(wrappedValue: FollowingFeedViewModel(api: api, keychainHelper: keychainHelper))
        
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
                    ForYouFeedView(viewModel: forYouViewModel)
                case .following:
                    FollowingFeedView(viewModel: followingViewModel)
                }
            }
            .navigationTitle("Feed")
            
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
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: 25) {
                ForEach(viewModel.feedPosts) { post in
                    VStack(alignment: .leading, spacing: 10) {
                        
                        // Wrap text in a NavigationLink to go to the profile
                        NavigationLink(value: User(username: post.authorUsername, identityIsVerified: false)) {
                            Text(post.authorUsername)
                                .font(.headline)
                                .fontWeight(.bold)
                                .padding(.horizontal)
                        }
                        .buttonStyle(.plain) // Keeps the text style
                        .accessibilityIdentifier("PostAuthor")
                        
                        // Wrap image in a NavigationLink to go to post details.
                        // Force every post into an identical square, cropping to
                        // fill so images no longer keep their original dimensions.
                        NavigationLink(value: post) {
                            Color(.systemGray5)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    KFGridPostImage(
                                        imageUrl: post.imageUrl,
                                        originalImageUrl: post.originalImageUrl,
                                        caption: post.caption
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
    
    var body: some View {
        // We use the same UI structure as ForYouFeedView
        ScrollView {
            LazyVStack(spacing: 25) {
                // Iterate over the followingPosts array
                ForEach(viewModel.followingPosts) { post in
                    VStack(alignment: .leading, spacing: 10) {
                        
                        // Wrap text in a NavigationLink to go to the profile
                        NavigationLink(value: User(username: post.authorUsername, identityIsVerified: false)) {
                            Text(post.authorUsername)
                                .font(.headline)
                                .fontWeight(.bold)
                                .padding(.horizontal)
                        }
                        .buttonStyle(.plain) // Keeps the text style
                        
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

/// A square feed thumbnail backed by Kingfisher (for its disk cache). Loads the
/// compressed `imageUrl` and, if that fails, retries with the full-resolution
/// `originalImageUrl`. The compressed copy is produced by an async Lambda, so a
/// just-posted image can 404 in the compressed bucket for a while — without the
/// fallback those tiles render as an empty grey box until the image is ready.
/// See issues #252 and #254.
struct KFGridPostImage: View {
    /// Nil for a text-only post (#307), which renders as a caption tile.
    let imageUrl: String?
    let originalImageUrl: String?
    /// The post caption, rendered as the tile for a text-only post.
    var caption: String = ""
    /// Shown while loading and when both images fail.
    var placeholderColor: Color = Color(.systemGray5)

    // Once the compressed URL fails, switch to the original and let Kingfisher
    // reload from the new URL.
    @State private var useOriginal = false

    var body: some View {
        if let imageUrl {
            let urlString = useOriginal ? (originalImageUrl ?? imageUrl) : imageUrl
            KFImage(URL(string: urlString))
                .placeholder { placeholderColor }
                .onFailure { _ in
                    if !useOriginal, originalImageUrl != nil {
                        useOriginal = true
                    }
                }
                .resizable()
                .scaledToFill()
        } else {
            CaptionTileView(caption: caption)
        }
    }
}

// MARK: - Preview
#Preview {
    // Assuming KeychainHelper() is a valid initializer
    // If not, you may need to use your mock
    FeedView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
