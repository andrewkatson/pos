//
//  HomeView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import SwiftUI
import Kingfisher

struct HomeView: View {
    
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    // The ViewModel is the single source of truth for this view's state.
    @StateObject private var viewModel: HomeViewModel
    
    @State private var currentTab = 0
    
    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        // We use _viewModel because we are initializing a @StateObject property
        _viewModel = StateObject(wrappedValue: HomeViewModel(api: api, keychainHelper: keychainHelper))
        
        self.api = api
        self.keychainHelper = keychainHelper
    }
    
    //TabView Menu
    var body: some View {
        TabView(selection: $currentTab){
            // Tab 1: User's personal post grid
            MyPostsGridView(api: api, keychainHelper: keychainHelper)
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }.tag(0)
            
            // Tab 2: Global feed view
            FeedView(api: api, keychainHelper: keychainHelper)
                .tabItem {
                    Label("Feed", systemImage: "list.bullet")
                }.tag(1)
            
            // Tab 3: New post creation view
            NewPostView(api: api, keychainHelper: keychainHelper, tabSelection: $currentTab)
                .tabItem {
                    Label("Post", systemImage: "plus.square")
                }.tag(2)
            
            // Tab 4: Settings view with logout
            SettingsView(api: api, keychainHelper: keychainHelper)
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }.tag(3)
        }
        .environmentObject(viewModel)
    }
}

// This sub-view contains the user's post grid and search logic
struct MyPostsGridView: View {
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    @EnvironmentObject private var viewModel: HomeViewModel
    
    // Define the grid layout: 3 columns, flexible size, with a 1pt gap that
    // shows the black grid background as a thin border between posts.
    private let columns: [GridItem] = Array(repeating: GridItem(.flexible(), spacing: 1), count: 3)
    
    var body: some View {
        NavigationStack {
            ScrollView {
                // If the user is searching, show the user list. Otherwise, show the post grid.
                if !viewModel.searchText.isEmpty {
                    UserSearchResultsView()
                } else {
                    postGrid // Your updated postGrid is now correctly placed in the stack
                }
            }
            .navigationTitle("Your Posts")
            // The searchable modifier provides the search bar UI and manages its state.
            .searchable(text: $viewModel.searchText, prompt: "Search for Users")
            .refreshable {
                // Pull-to-refresh: reload the newest posts from the backend.
                // Run the reload in an unstructured Task so SwiftUI cancelling
                // the refreshable task on a re-render can't cancel the request.
                await Task { await viewModel.refreshMyPosts() }.value
            }
            .onAppear {
                // Fetch initial posts only if the list is empty
                if viewModel.userPosts.isEmpty {
                    viewModel.fetchMyPosts()
                }
            }
            .navigationDestination(for: Post.self) { post in
                PostDetailView(postIdentifier: post.id, api: api, keychainHelper: keychainHelper)
            }
            .navigationDestination(for: User.self) { user in
                ProfileView(user: user, api: api, keychainHelper: keychainHelper)
            }
        }
    }
    
    /// The view for the user's posts
    private var postGrid: some View {
        LazyVGrid(columns: columns, spacing: 1) {
            ForEach(viewModel.userPosts) { post in

                // Wrap the image in a NavigationLink and pass the post as the value.
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
                        .clipped()
                }

                // This is the trigger for infinite scrolling
                .onAppear {
                    // If this post is the last one in the list, fetch the next page
                    if post.id == viewModel.userPosts.last?.id {
                        viewModel.fetchMyPosts()
                    }
                }
                .accessibilityIdentifier("MyPostImage")
            }
        }
        // Black backing shows through the 1pt gaps as thin borders between posts.
        .background(Color.black)
    }
}

/// A square grid thumbnail for a post. Loads the compressed `imageUrl` and, if
/// that fails, falls back to the full-resolution `originalImageUrl` before giving
/// up to a grey placeholder. The compressed copy is produced by an async Lambda,
/// so a just-posted or recently hidden-pending-appeal image can 403 in the
/// compressed bucket for a while — the fallback keeps those tiles from rendering
/// as empty grey boxes until the user re-logs in.
///
/// Backed by Kingfisher rather than AsyncImage: AsyncImage is one-shot, so a
/// load that fails or gets cancelled (lazy-grid scrolling, pull-to-refresh,
/// navigation transitions) parks the tile on the grey placeholder until the
/// view's identity changes — QA's "fixes itself after toggling search" on #254.
/// KFImage restarts a failed load when the tile reappears, keeps downloads
/// alive off-screen, briefly retries HTTP errors, and disk-caches the result.
/// Shared by the Home, For You, Following, and Profile grids.
/// See issues #252, #253, and #254.
struct GridPostImage: View {
    /// Nil for a text-only post (#307), which renders as a caption tile.
    let imageUrl: String?
    let originalImageUrl: String?
    /// The post caption, rendered as the tile for a text-only post.
    var caption: String = ""
    /// Shown while loading and when both the compressed and original images fail.
    /// Defaults to the grid's grey backing; callers (e.g. the feed) override it to
    /// match their own placeholder shade.
    var placeholderColor: Color = Color(.systemGray4)

    // Once the compressed URL genuinely fails, switch to the original and let
    // Kingfisher load the new URL.
    @State private var useOriginal = false

    var body: some View {
        if let imageUrl {
            let urlString = useOriginal ? (originalImageUrl ?? imageUrl) : imageUrl
            KFImage(URL(string: urlString))
                // Rides out the just-posted window where the compressed copy isn't
                // in the bucket yet; only HTTP errors are retried, not cancellations.
                .retry(maxCount: 2, interval: .seconds(1))
                .placeholder { placeholderColor }
                .onFailure { error in
                    // A cancelled load isn't a missing image — the tile reloads the
                    // same URL when it next appears, so save the fallback for real
                    // failures.
                    guard !error.isTaskCancelled else { return }
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

/// The view for displaying user search results
struct UserSearchResultsView: View {
    @EnvironmentObject private var viewModel: HomeViewModel
    
    var body: some View {
        LazyVStack(alignment: .leading) {
            ForEach(viewModel.searchedUsers) { user in
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
                Divider()
            }
        }
    }
}


#Preview {
    HomeView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
