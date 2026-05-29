//
//  FollowingFeedViewModel.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/26/25.
//

import Foundation

// ViewModel to manage the state of the "Following" feed
@MainActor
final class FollowingFeedViewModel: ObservableObject {
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol
    private let account: String
    private let keychainService = "positive-only-social.Positive-Only-Social"
    @Published var followingPosts: [Post] = []
    @Published var isLoadingNextPage = false
    private var canLoadMore = true
    private var currentPage = 0
    
    convenience init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.init(api: api, keychainHelper: keychainHelper, account: "userSessionToken")
    }
    
    init(api: Networking, keychainHelper: KeychainHelperProtocol, account: String) {
        self.api = api
        self.keychainHelper = keychainHelper
        self.account = account
    }
    
    func fetchFollowingFeed() {
        guard !isLoadingNextPage && canLoadMore else { return }
        isLoadingNextPage = true
        
        Task {
            do {
                guard let userSession = try keychainHelper.load(UserSession.self, from: keychainService, account: account) else {
                    NSLog("%@", "No active session — cannot fetch following feed")
                    isLoadingNextPage = false
                    return
                }

                // --- KEY CHANGE ---
                // Call the API endpoint for followed users
                let responseData = try await api.getPostsForFollowedUsers(sessionManagementToken: userSession.sessionToken, batch: currentPage)
                // --- END KEY CHANGE ---

                let newPosts = try JSONDecoder().decode([Post].self, from: responseData)
                
                if newPosts.isEmpty {
                    canLoadMore = false
                } else {
                    // Add new posts to the followingPosts array
                    followingPosts.append(contentsOf: newPosts)
                    currentPage += 1
                }
            } catch {
                NSLog("%@", "Failed to fetch following feed: \(error)")
            }
            isLoadingNextPage = false
        }
    }
    
    func refreshFeed() {
        // 1. Reset pagination state
        currentPage = 0
        canLoadMore = true
        
        // 2. Clear existing posts (optional: remove this if you want to keep data while loading)
        followingPosts.removeAll()
        
        // 3. Fetch fresh data
        fetchFollowingFeed()
    }
}
