//
//  HomeView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import SwiftUI

struct HomeView: View {
    
    let api: APIProtocol
    let keychainHelper: KeychainHelperProtocol
    
    // The ViewModel is the single source of truth for this view's state.
    @StateObject private var viewModel: HomeViewModel
    
    init(api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        // We use _viewModel because we are initializing a @StateObject property
        _viewModel = StateObject(wrappedValue: HomeViewModel(api: api, keychainHelper: keychainHelper))
        
        self.api = api
        self.keychainHelper = keychainHelper
    }

    var body: some View {
            TabView {
                // Tab 1: User's personal post grid
                MyPostsGridView(api: api, keychainHelper: keychainHelper)
                    .tabItem {
                        Label("Home", systemImage: "house.fill")
                    }.accessibilityIdentifier("HomeTab")
                
                // Tab 2: Global feed view
                FeedView(api: api, keychainHelper: keychainHelper)
                    .tabItem {
                        Label("Feed", systemImage: "list.bullet")
                    }.accessibilityIdentifier("FeedTab")
                
                // Tab 3: New post creation view
                NewPostView(api: api, keychainHelper: keychainHelper)
                    .tabItem {
                        Label("Post", systemImage: "plus.square")
                    }.accessibilityIdentifier("PostTab")
                
                // Tab 4: Settings view with logout
                SettingsView(api: api, keychainHelper: keychainHelper)
                    .tabItem {
                        Label("Settings", systemImage: "gear")
                    }.accessibilityIdentifier("SettingsTab")
            }
            .environmentObject(viewModel)
        }
}

// This sub-view contains the user's post grid and search logic
struct MyPostsGridView: View {
    let api: APIProtocol
    let keychainHelper: KeychainHelperProtocol
    @EnvironmentObject private var viewModel: HomeViewModel
    @Environment(\.isSearching) private var isSearching

    // Define the grid layout: 3 columns, flexible size
    private let columns: [GridItem] = Array(repeating: .init(.flexible()), count: 3)

    var body: some View {
        NavigationStack {
            ScrollView {
                // If the user is searching, show the user list. Otherwise, show the post grid.
                if isSearching {
                    UserSearchResultsView()
                } else {
                    postGrid // Your updated postGrid is now correctly placed in the stack
                }
            }
            .navigationTitle("Your Posts")
            // The searchable modifier provides the search bar UI and manages its state.
            .searchable(text: $viewModel.searchText, prompt: "Search for Users")
            .onAppear {
                // Fetch initial posts only if the list is empty
                if viewModel.userPosts.isEmpty {
                    viewModel.fetchMyPosts()
                }
            }
            // --- RECOMMENDED ---
            // Move the navigationDestination *here*, to the ScrollView
            // or one of its children, but *outside* the ForEach.
            .navigationDestination(for: Post.self) { post in
                PostDetailView(postIdentifier: post.id, api: api, keychainHelper: keychainHelper)
            }
        }
    }
    
    /// The view for the user's posts
    private var postGrid: some View {
        LazyVGrid(columns: columns, spacing: 2) {
            ForEach(viewModel.userPosts) { post in
                
                // --- THIS IS THE FIX ---
                // Wrap your image in a NavigationLink and pass the post as the value.
                NavigationLink(value: post) {
                    // Display the post image
                    AsyncImage(url: URL(string: post.imageUrl)) { image in
                        image.resizable().scaledToFill()
                    } placeholder: {
                        Color(.systemGray4) // Placeholder color
                    }
                    .aspectRatio(1, contentMode: .fill)
                    .clipped()
                }
                // --- END FIX ---
                
                // This is the trigger for infinite scrolling
                .onAppear {
                    // If this post is the last one in the list, fetch the next page
                    if post.id == viewModel.userPosts.last?.id {
                        viewModel.fetchMyPosts()
                    }
                }
                // --- REMOVED ---
                // The .navigationDestination modifier was here, but it's
                // more efficient to place it on the parent container (see above).
            }
        }
    }
}

/// The view for displaying user search results
struct UserSearchResultsView: View {
    @EnvironmentObject private var viewModel: HomeViewModel

    var body: some View {
        List(viewModel.searchedUsers) { user in
            NavigationLink(value: user) {
                HStack(spacing: 15) {
                    Image(systemName: "person.circle.fill")
                        .font(.largeTitle)
                        .foregroundColor(.gray)

                    Text(user.username)
                        .fontWeight(.bold)

                    if user.identityIsVerified {
                        Image(systemName: "checkmark.seal.fill")
                            .foregroundColor(.blue)
                    }
                }
            }.accessibilityIdentifier(user.username)
        }
        .listStyle(.plain)
    }
}


#Preview {
    HomeView(api: StatefulStubbedAPI(), keychainHelper: KeychainHelper())
}
