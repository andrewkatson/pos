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
                let userSession = try keychainHelper.load(UserSession.self, from: "positive-only-social.Positive-Only-Social", account: account) ?? UserSession(sessionToken: "123", username: "test", isIdentityVerified: false)
                
                
                // --- KEY CHANGE ---
                // Call the API endpoint for followed users
                let responseData = try await api.getPostsForFollowedUsers(sessionManagementToken: userSession.sessionToken, batch: currentPage)
                // --- END KEY CHANGE ---
                
                let wrapper = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else { return }
                let newPosts = try JSONDecoder().decode([DjangoObject<Post>].self, from: innerData).map { $0.fields }
                
                if newPosts.isEmpty {
                    canLoadMore = false
                } else {
                    // Add new posts to the followingPosts array
                    followingPosts.append(contentsOf: newPosts)
                    currentPage += 1
                }
            } catch {
                print("Failed to fetch following feed: \(error)")
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
