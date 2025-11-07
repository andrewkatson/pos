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
    
    // State to track the selected top tab
    @State private var selectedFeed: FeedType = .forYou
    
    init(api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        _forYouViewModel = StateObject(wrappedValue: FeedViewModel(api: api, keychainHelper: keychainHelper))
        _followingViewModel = StateObject(wrappedValue: FollowingFeedViewModel(api: api, keychainHelper: keychainHelper))
    }
    
    var body: some View {
        NavigationStack {
            VStack {
                // This Picker creates the segmented top tabs
                Picker("Feed Type", selection: $selectedFeed) {
                    ForEach(FeedType.allCases, id: \.self) { type in
                        Text(type.rawValue).tag(type)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)

                // The content switches based on the selected tab
                switch selectedFeed {
                case .forYou:
                    // --- KEY CHANGE ---
                    // Pass the forYouViewModel
                    ForYouFeedView(viewModel: forYouViewModel)
                    // --- END KEY CHANGE ---
                case .following:
                    // --- KEY CHANGE ---
                    // Pass the followingViewModel
                    FollowingFeedView(viewModel: followingViewModel)
                    // --- END KEY CHANGE ---
                }
            }
            .navigationTitle("Feed")
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
                        // Correctly displays the author's username
                        Text(post.authorUsername)
                            .font(.headline)
                            .fontWeight(.bold)
                            .padding(.horizontal)
                        
                        // Asynchronously loads the post image
                        AsyncImage(url: URL(string: post.imageUrl)) { image in
                            image.resizable().scaledToFit()
                        } placeholder: {
                            // A placeholder while the image loads
                            Rectangle()
                                .foregroundColor(Color(.systemGray5))
                                .aspectRatio(1, contentMode: .fit)
                        }
                        .onAppear {
                            // Trigger for infinite scrolling
                            if post.id == viewModel.feedPosts.last?.id {
                                viewModel.fetchFeed()
                            }
                        }
                    }
                }
                // Loading indicator at the bottom of the list
                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }
            }
            .padding(.top)
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
    // --- KEY CHANGES ---
    // This view now observes the new FollowingFeedViewModel
    @ObservedObject var viewModel: FollowingFeedViewModel
    
    var body: some View {
        // We use the same UI structure as ForYouFeedView
        ScrollView {
            LazyVStack(spacing: 25) {
                // Iterate over the followingPosts array
                ForEach(viewModel.followingPosts) { post in
                    VStack(alignment: .leading, spacing: 10) {
                        Text(post.authorUsername)
                            .font(.headline)
                            .fontWeight(.bold)
                            .padding(.horizontal)
                        
                        AsyncImage(url: URL(string: post.imageUrl)) { image in
                            image.resizable().scaledToFit()
                        } placeholder: {
                            Rectangle()
                                .foregroundColor(Color(.systemGray5))
                                .aspectRatio(1, contentMode: .fit)
                        }
                        .onAppear {
                            // Trigger for infinite scrolling
                            // Use followingPosts and fetchFollowingFeed
                            if post.id == viewModel.followingPosts.last?.id {
                                viewModel.fetchFollowingFeed()
                            }
                        }
                    }
                }
                
                if viewModel.isLoadingNextPage {
                    ProgressView().padding()
                }
            }
            .padding(.top)
        }
        // Add .onAppear to trigger the *initial* fetch
        .onAppear {
            if viewModel.followingPosts.isEmpty {
                viewModel.fetchFollowingFeed()
            }
        }
    }
    // --- END KEY CHANGES ---
}

// MARK: - Preview
#Preview {
    FeedView(api: StatefulStubbedAPI(), keychainHelper: KeychainHelper())
}
