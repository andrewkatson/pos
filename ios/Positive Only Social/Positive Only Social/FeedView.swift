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
    @StateObject private var viewModel: FeedViewModel
    
    // State to track the selected top tab
    @State private var selectedFeed: FeedType = .forYou
    
    init(api: APIProtocol) {
        _viewModel = StateObject(wrappedValue: FeedViewModel(api: api))
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
                    ForYouFeedView(viewModel: viewModel)
                case .following:
                    FollowingFeedView()
                }
            }
            .navigationTitle("Feed")
            .onAppear {
                if viewModel.feedPosts.isEmpty {
                    viewModel.fetchFeed()
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
    }
}

/// A placeholder for the "Following" feed content.
struct FollowingFeedView: View {
    var body: some View {
        VStack {
            Spacer()
            Image(systemName: "person.2.fill")
                .font(.largeTitle)
                .foregroundColor(.gray)
            Text("Posts from people you follow will appear here.")
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding()
            Spacer()
        }
    }
}

// MARK: - Preview
#Preview {
    FeedView(api: StatefulStubbedAPI())
}
