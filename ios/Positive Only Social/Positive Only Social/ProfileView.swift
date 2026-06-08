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

struct ProfileView: View {
    
    // This view has its own ViewModel to manage its own state
    @StateObject private var viewModel: ProfileViewModel
    
    // Grid layout, same as in HomeView: 3 columns with a 1pt gap that shows the
    // black grid background as a thin border between posts.
    private let columns: [GridItem] = Array(repeating: GridItem(.flexible(), spacing: 1), count: 3)
    
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    
    init(user: User, api: Networking, keychainHelper: KeychainHelperProtocol) {
        // Initialize the StateObject with the user and API
        _viewModel = StateObject(wrappedValue: ProfileViewModel(user: user, api: api, keychainHelper: keychainHelper))
        
        self.api = api
        self.keychainHelper = keychainHelper
    }
    
    var body: some View {
        ScrollView {
            profileHeader.padding(.horizontal)
            Divider()
            postGrid
        }
        .navigationTitle(viewModel.user.username) // Set title to the user's name
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
                StatItem(count: viewModel.profileDetails?.followerCount ?? 0, label: "Followers")
                Spacer()
                StatItem(count: viewModel.profileDetails?.followingCount ?? 0, label: "Following")
                Spacer()
            }
            .padding(.top)
            
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
            .disabled(viewModel.isLoadingProfile) // Disable while loading
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
            .disabled(viewModel.isLoadingProfile)
            .padding(.bottom)
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
                    // Wrap each cell in a NavigationLink so tapping a post opens
                    // its detail view (matches Home/Feed and the destination below).
                    NavigationLink(value: post) {
                        // Force every post into an identical square, cropping to fill
                        // so images no longer keep their original dimensions.
                        Color(.systemGray4)
                            .aspectRatio(1, contentMode: .fit)
                            .overlay {
                                AsyncImage(url: URL(string: post.imageUrl)) { image in
                                    image.resizable().scaledToFill()
                                } placeholder: {
                                    Color(.systemGray4)
                                }
                            }
                            .clipped()
                    }
                    .onAppear {
                        // Trigger for infinite scrolling
                        if post.id == viewModel.userPosts.last?.id {
                            viewModel.fetchUserPosts()
                        }
                    }
                    .accessibilityIdentifier("ProfilePostImage")
                }.navigationDestination(for: Post.self) { post in
                    PostDetailView(postIdentifier: post.id, api: api, keychainHelper: keychainHelper)
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
